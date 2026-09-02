from __future__ import annotations

import io
import base64
import random
from datetime import date
from pathlib import Path
from urllib.parse import quote
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.account_client import create_demo_account
from app.cases import case_catalog, get_case, public_case_types
from app.pdf_generator import DOCUMENTS_BY_CASE, Applicant, build_package
from app.registration import normalize_registration_number, validate_registration_persona
from app.signature import decode_signature
from app.demo_guide import demo_workplace, demo_accident
from app.service_target import service_target


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"

app = FastAPI(title="산재원샷 문서·데모계정 생성기", version="1.0.0")


def build_demo_password(birth_date: date) -> str:
    """Return a memorable demo password that satisfies the 12-character minimum."""
    return f"Demo{birth_date.strftime('%m%d')}!123"


class GenerateRequest(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    name: str = Field(min_length=2, max_length=100)
    birth_date: date
    registration_number: str
    address: str = Field(min_length=5, max_length=300)
    phone: str = Field(min_length=8, max_length=30)
    email: EmailStr
    preferred_language: str = Field(default="ko", pattern=r"^(ko|en|vi|fil)$")
    nationality: str = Field(default="대한민국", min_length=1, max_length=100)
    sex: Literal["male", "female"] | None = None
    signature_image: str = Field(default="", max_length=400_000)
    case_type: str
    case_id: str | None = None

    @field_validator("signature_image")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        if value:
            decode_signature(value)
        return value

    @field_validator("registration_number", mode="before")
    @classmethod
    def normalize_registration(cls, value: str) -> str:
        return normalize_registration_number(value)

    @model_validator(mode="after")
    def validate_registration(self) -> "GenerateRequest":
        validate_registration_persona(self.registration_number, self.birth_date, self.nationality, self.sex)
        return self

    @field_validator("case_type")
    @classmethod
    def validate_case_type(cls, value: str) -> str:
        if value not in case_catalog():
            raise ValueError("지원하지 않는 사고 유형입니다.")
        return value


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI normally echoes submitted values. Never reflect a raw ID, even on errors.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]})


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "case_types": len(case_catalog()),
        "total_cases": sum(len(items) for items in case_catalog().values()),
    }


@app.get("/api/case-types")
async def case_types() -> list[dict[str, object]]:
    return public_case_types()


@app.get("/api/config")
async def config() -> JSONResponse:
    return JSONResponse(service_target(), headers={"Cache-Control": "no-store"})


@app.get("/api/cases/random")
async def random_case(case_type: str) -> dict[str, object]:
    try:
        item = get_case(case_type, seed=random.SystemRandom().randrange(120))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="지원하지 않는 사고 유형입니다.") from exc
    return {**item.to_dict(), "input_documents": [name for name, _, _ in DOCUMENTS_BY_CASE[case_type]], "demo_workplace": demo_workplace(item), "demo_accident": demo_accident(item, "ko")}


@app.post("/api/generate")
async def generate(request: GenerateRequest, response_format: Literal["zip", "json"] = "zip"):
    try:
        selected_case = get_case(
            request.case_type,
            case_id=request.case_id,
            seed=random.SystemRandom().randrange(120),
        )
    except (KeyError, LookupError) as exc:
        raise HTTPException(status_code=404, detail="선택한 사고 케이스를 찾지 못했습니다.") from exc

    password = build_demo_password(request.birth_date)
    account = await create_demo_account(
        email=str(request.email),
        password=password,
        name=request.name,
        preferred_language=request.preferred_language,
    )
    package = build_package(
        Applicant(
            name=request.name,
            birth_date=request.birth_date.isoformat(),
            registration_number=request.registration_number,
            address=request.address,
            phone=request.phone,
            email=str(request.email),
            preferred_language=request.preferred_language,
            nationality=request.nationality,
            sex=request.sex,
            signature_image=request.signature_image,
        ),
        selected_case,
        account,
    )
    encoded_filename = quote(package.filename)
    if response_format == "json":
        return JSONResponse({"manifest": package.manifest, "filename": package.filename, "package_base64": base64.b64encode(package.content).decode("ascii")}, headers={"Cache-Control": "no-store"})
    return StreamingResponse(
        io.BytesIO(package.content),
        media_type="application/zip",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "X-Account-Status": account.status,
            "X-Account-Message": account.message.encode("utf-8").hex(),
        },
    )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="pages")
