import asyncio
import base64
import io
import json
import re
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock
from zipfile import ZipFile

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.account_client import AccountCreationResult, create_demo_account
from app.cases import get_case
from app.demo_guide import demo_accident
from app.main import app
from test_registration import request_data


def sample_signature():
    image = Image.new("RGBA", (960, 280))
    ImageDraw.Draw(image).line((50, 50, 650, 200), fill=(20, 30, 40, 255), width=8)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")


@pytest.mark.parametrize("case_type", ["work_accident", "commute", "third_party", "occupational_disease", "survivor", "retreatment"])
def test_json_response_matches_zip_and_steps(case_type, monkeypatch):
    account = AccountCreationResult("created", "합성 테스트 계정", "demo@example.com", "synthetic-only", user_id="00000000-0000-0000-0000-000000000001")
    call = AsyncMock(return_value=account)
    monkeypatch.setattr("app.main.create_demo_account", call)
    data = request_data(case_type=case_type, case_id=f"{case_type}-004", signature_image=sample_signature(), nationality="베트남")
    with TestClient(app) as client:
        response = client.post("/api/generate?response_format=json", json=data)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    manifest = result["manifest"]
    assert re.fullmatch(r"[0-9]{6}-[0-9]{7}", manifest["applicant"]["registration_number"])
    assert manifest["service_target"]["application_url"] == "https://sanjae-oneshot.co.kr/?start=application"
    with ZipFile(io.BytesIO(base64.b64decode(result["package_base64"]))) as archive:
        assert archive.testzip() is None
        assert json.loads(archive.read("00_시연_입력_가이드.json")) == manifest
        assert archive.read("04_시연용_서명.png") == base64.b64decode(data["signature_image"].split(",")[1])
        assert len(archive.namelist()) == 5
        assert manifest["documents"] == [name for name in archive.namelist() if name.endswith(".pdf")]
    assert manifest["workplace"]["management_number"] != manifest["workplace"]["business_registration_no"]
    steps = {step["id"]: step for step in manifest["steps"]}
    answers = steps["review"]["fields"]["answers"]
    assert steps["ocr"]["expected"]["diagnosis"] in answers["medical_treatment"]
    assert steps["ocr"]["expected"]["hospital"] in answers["medical_treatment"]
    for answer in answers.values():
        assert answer in steps["accident"]["fields"]["raw_description"]
        assert "확인되지 않았" not in answer
    assert "facts_confirmed" not in steps["final"].get("fields", {})
    assert steps["basic"]["fields"]["workplace"] == manifest["workplace"]
    assert steps["accident"]["fields"] == manifest["accident"]
    assert steps["profile"]["fields"]["foreign_registration_no"] is None
    assert steps["profile"]["fields"]["signature_name"] == manifest["signature"]["name"]
    if case_type == "survivor":
        assert steps["profile"]["fields"]["name"] != manifest["applicant"]["name"]
    call.assert_awaited_once()


def test_browser_personas_keep_full_number_through_api_and_zip(monkeypatch):
    script = """
      import {createDemoPersona} from './static/form-helpers.mjs';
      console.log(JSON.stringify(['domestic', 'foreign'].flatMap(kind =>
        [0, 0.49, 0.999].map(sample => createDemoPersona(kind, () => sample, `roundtrip-${kind}-${sample}`)))));
    """
    result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding="utf-8", check=True)
    personas = json.loads(result.stdout)
    async def fake_account(**fields):
        return AccountCreationResult("created", "합성 테스트", fields["email"], fields["password"], user_id="synthetic-user")
    account_call = AsyncMock(side_effect=fake_account)
    monkeypatch.setattr("app.main.create_demo_account", account_call)
    with TestClient(app) as client:
        for persona in personas:
            response = client.post("/api/generate?response_format=json", json={**persona, "case_type": "work_accident", "case_id": "work_accident-004"})
            assert response.status_code == 200
            result = response.json()
            assert result["manifest"]["applicant"]["registration_number"] == persona["registration_number"]
            assert result["manifest"]["applicant"]["sex"] == persona["sex"]
            with ZipFile(io.BytesIO(base64.b64decode(result["package_base64"]))) as archive:
                exported = json.loads(archive.read("00_시연_입력_가이드.json"))
                assert exported == result["manifest"]
                assert exported["applicant"]["registration_number"] == persona["registration_number"]
    assert account_call.await_count == 6


@pytest.mark.parametrize("image", ["data:image/svg+xml,<svg/>", "data:image/png;base64,bad", "https://example.com/signature.png"])
def test_invalid_signature_rejected_before_account_creation(image, monkeypatch):
    call = AsyncMock()
    monkeypatch.setattr("app.main.create_demo_account", call)
    with TestClient(app) as client:
        assert client.post("/api/generate", json=request_data(signature_image=image)).status_code == 422
    call.assert_not_awaited()


def test_absent_witness_has_no_contact():
    for seed in range(120):
        case = get_case("work_accident", seed=seed)
        if case.witness == "목격자 없음":
            assert demo_accident(case, "ko")["witness_phone"] == ""


@pytest.mark.parametrize("mode, expected", [("connect", "unavailable"), ("timeout", "unavailable"), ("html", "failed"), ("bad_json", "failed"), ("validation", "failed"), ("created", "created")])
def test_account_failures_are_actionable_and_do_not_echo_password(mode, expected, monkeypatch):
    real_client = httpx.AsyncClient
    def handle(request):
        if mode == "connect": raise httpx.ConnectError("offline", request=request)
        if mode == "timeout": raise httpx.ReadTimeout("slow", request=request)
        if mode == "html": return httpx.Response(502, text="<html>gateway</html>")
        if mode == "bad_json": return httpx.Response(200, text="not json")
        if mode == "validation": return httpx.Response(422, json={"detail": [{"msg": "Invalid field", "input": "do-not-echo"}]})
        return httpx.Response(201, json={"user_id": "demo-user", "email_confirmation_required": False})
    monkeypatch.setattr("app.account_client.httpx.AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs))
    result = asyncio.run(create_demo_account(email="test@example.com", password="do-not-echo", name="시연", preferred_language="ko"))
    assert result.status == expected
    assert "do-not-echo" not in result.message
    if mode == "connect": assert "운영 서비스 상태" in result.message
