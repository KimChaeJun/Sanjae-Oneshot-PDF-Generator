from datetime import date
from io import BytesIO
from zipfile import ZipFile
import json

import pytest

from pypdf import PdfReader

from app.account_client import AccountCreationResult
from app.cases import CASE_TYPES, case_catalog, get_case
from app.main import build_demo_password
from app.pdf_generator import DOCUMENTS_BY_CASE, Applicant, build_package


def test_every_case_type_has_at_least_100_cases() -> None:
    catalog = case_catalog()
    assert set(catalog) == set(CASE_TYPES)
    assert all(len(items) >= 100 for items in catalog.values())
    assert sum(len(items) for items in catalog.values()) == 720


def test_demo_password_has_at_least_12_characters() -> None:
    password = build_demo_password(date(1991, 4, 18))
    assert password == "Demo0418!123"
    assert len(password) >= 12


def test_package_contains_guide_documents_and_manifest() -> None:
    applicant = Applicant(
        name="김민준",
        birth_date=date(1991, 4, 18).isoformat(),
        registration_number="910418-1******",
        address="서울특별시 구로구 디지털로 25",
        phone="010-2000-1001",
        email="demo001@demo.sanjae-oneshot.co.kr",
        preferred_language="ko",
    )
    account = AccountCreationResult(
        status="created",
        message="계정이 생성되었습니다.",
        email=applicant.email,
        password="Demo0418!123",
        user_id="00000000-0000-0000-0000-000000000001",
    )
    package = build_package(applicant, get_case("work_accident", seed=3), account)
    with ZipFile(BytesIO(package.content)) as archive:
        names = archive.namelist()
        assert [name for name in names if name.endswith(".json")] == ["00_시연_입력_가이드.json"]
        assert "00_시연_입력_가이드.pdf" not in names
        assert len([name for name in names if name.endswith(".pdf")]) == 3
        assert len(PdfReader(BytesIO(archive.read("01_진단소견서.pdf"))).pages) == 1
        assert len(PdfReader(BytesIO(archive.read("02_재직업무확인서.pdf"))).pages) == 1
        assert len(PdfReader(BytesIO(archive.read("03_현장작업기록.pdf"))).pages) == 1
        manifest = json.loads(archive.read("00_시연_입력_가이드.json"))
        assert manifest["package_role"] == "input_evidence_only"
        assert [step["step"] for step in manifest["steps"] if "step" in step] == list(range(9))
        assert "PDF 2종" in json.dumps(manifest["steps"], ensure_ascii=False)
        assert manifest["workplace"]["management_number"]


def test_every_case_type_builds_only_input_evidence() -> None:
    applicant = Applicant(
        name="김민준",
        birth_date=date(1991, 4, 18).isoformat(),
        registration_number="910418-1******",
        address="서울특별시 구로구 디지털로 25",
        phone="010-2000-1001",
        email="sanjae.oneshot.template.test@gmail.com",
        preferred_language="ko",
    )
    account = AccountCreationResult(
        status="created",
        message="계정이 생성되었습니다.",
        email=applicant.email,
        password="Demo0418!123",
        user_id="00000000-0000-0000-0000-000000000001",
    )

    for case_type in CASE_TYPES:
        package = build_package(applicant, get_case(case_type, seed=7), account)
        with ZipFile(BytesIO(package.content)) as archive:
            names = archive.namelist()
            assert len([name for name in names if name.endswith(".pdf")]) == 3
            assert not any(word in name for name in names for word in ("신청서", "재해경위서", "청구서", "신고서"))
            for filename, _title, _template_kind in DOCUMENTS_BY_CASE[case_type]:
                reader = PdfReader(BytesIO(archive.read(filename)))
                assert all(float(page.mediabox.width) > 590 for page in reader.pages)
                assert all(float(page.mediabox.height) > 840 for page in reader.pages)
                text = "".join(page.extract_text() for page in reader.pages)
                assert "입력용 합성 증빙" in text
                assert "김민준" in text


@pytest.mark.parametrize("case_type", CASE_TYPES)
def test_case_preview_uses_the_same_input_documents_as_zip(case_type):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/cases/random", params={"case_type": case_type})
    assert response.status_code == 200
    assert response.json()["input_documents"] == [name for name, _, _ in DOCUMENTS_BY_CASE[case_type]]
