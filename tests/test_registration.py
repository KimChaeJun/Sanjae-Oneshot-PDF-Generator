import json
import re
from html.parser import HTMLParser
from dataclasses import asdict
from io import BytesIO
from unittest.mock import AsyncMock
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfReader

from app.account_client import AccountCreationResult
from app.main import GenerateRequest, app
from app.pdf_generator import Applicant
from app.registration import mask_registration_number, normalize_registration_number


def request_data(**changes):
    return {
        "name": "NGUYEN VAN LONG",
        "birth_date": "1994-03-12",
        "registration_number": "940312-5******",
        "address": "경기도 안산시 시연로 100 (합성)",
        "phone": "010-0000-0902",
        "email": "registration-test@example.com",
        "preferred_language": "vi",
        "nationality": "베트남",
        "sex": "male",
        "case_type": "work_accident",
        "case_id": "work_accident-004",
        **changes,
    }


@pytest.mark.parametrize("value", [
    "940312-5******", "9403125******", "940312-5", "9403125",
    "940312-5000000", "9403125000000", " 940312 - 5****** ",
])
def test_full_registration_is_preserved_but_display_is_masked(value):
    assert mask_registration_number(value) == "940312-5******"
    model = GenerateRequest(**request_data(registration_number=value))
    assert re.fullmatch(r"940312-5[0-9]{6}", model.registration_number)
    if "5000000" in value:
        assert model.registration_number == "940312-5000000"
    assert mask_registration_number(model.registration_number) == "940312-5******"


def test_legacy_masked_number_is_completed_once(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("app.registration.random.SystemRandom", lambda: SimpleNamespace(randrange=lambda limit: 42))
    number = normalize_registration_number("940312-5******")
    assert number == "940312-5000042"
    assert normalize_registration_number(number) == number


@pytest.mark.parametrize("value", [None, 9403125, "", "940312", "940312-", "940312-******", "940312-X******", "940312-5123", "940312-5*****", "940312-5*******", "940312-5abc000", "９４０３１２５００００００"])
def test_invalid_registration_is_rejected(value):
    with pytest.raises((ValueError, ValidationError)):
        GenerateRequest(**request_data(registration_number=value))


@pytest.mark.parametrize(("birth", "number"), [
    ("1994-03-12", "940312-1******"),
    ("1994-03-12", "940312-2******"),
    ("1994-03-12", "940312-5******"),
    ("1994-03-12", "940312-6******"),
    ("2004-03-12", "040312-3******"),
    ("2004-03-12", "040312-4******"),
    ("2004-03-12", "040312-7******"),
    ("2004-03-12", "040312-8******"),
])
def test_domestic_and_foreign_registration_prefixes(birth, number):
    nationality = "베트남" if number[7] in "5678" else "대한민국"
    sex = "male" if int(number[7]) % 2 else "female"
    model = GenerateRequest(**request_data(birth_date=birth, registration_number=number, nationality=nationality, sex=sex))
    assert mask_registration_number(model.registration_number) == number
    assert re.fullmatch(r"[0-9]{6}-[0-9]{7}", model.registration_number)


@pytest.mark.parametrize("number", ["950312-5******", "940312-7******"])
def test_birth_date_mismatch_is_rejected(number):
    with pytest.raises(ValidationError):
        GenerateRequest(**request_data(registration_number=number))


def test_direct_pdf_applicant_preserves_json_digits_with_separate_masked_display():
    data = request_data(registration_number="940312-5000000")
    data.pop("case_type")
    data.pop("case_id")
    applicant = Applicant(**data)
    assert applicant.registration_number == "940312-5000000"
    assert applicant.masked_registration_number == "940312-5******"
    assert "5000000" in json.dumps(asdict(applicant))


@pytest.mark.parametrize("changes", [
    {"registration_number": "940312-5000042", "sex": "female"},
    {"registration_number": "940312-6000042", "sex": "male"},
    {"registration_number": "940312-1000042", "nationality": "베트남"},
    {"registration_number": "940312-5000042", "nationality": "대한민국"},
    {"registration_number": "940312-5000042", "sex": "unknown"},
    {"registration_number": "270101-7000042", "birth_date": "2127-01-01"},
])
def test_persona_rule_mismatch_is_rejected_before_signup(changes, monkeypatch):
    account_call = AsyncMock()
    monkeypatch.setattr("app.main.create_demo_account", account_call)
    with TestClient(app) as client:
        assert client.post("/api/generate", json=request_data(**changes)).status_code == 422
    account_call.assert_not_awaited()


@pytest.mark.parametrize("changes", [
    {"registration_number": "940312-5000000", "name": "X"},
    {"registration_number": "940312-5000000", "birth_date": "1995-03-12"},
    {"registration_number": "940312-5000000-invalid"},
])
def test_validation_response_never_echoes_submitted_identifier(changes, monkeypatch):
    account_call = AsyncMock()
    monkeypatch.setattr("app.main.create_demo_account", account_call)
    with TestClient(app) as client:
        response = client.post("/api/generate", json=request_data(**changes))
    assert response.status_code == 422
    assert "5000000" not in response.text
    assert all("input" not in error and "ctx" not in error for error in response.json()["detail"])
    account_call.assert_not_awaited()


def test_registration_is_required_before_account_creation(monkeypatch):
    data = request_data()
    del data["registration_number"]
    account_call = AsyncMock()
    monkeypatch.setattr("app.main.create_demo_account", account_call)
    with TestClient(app) as client:
        assert client.post("/api/generate", json=data).status_code == 422
    account_call.assert_not_awaited()


def test_wizard_page_revalidates_and_loads_versioned_assets():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    assert 'styles.css?v=' in response.text
    assert 'demo.mjs?v=' in response.text
    assert response.text.count('data-indicator=') == 3


def test_manual_synthetic_input_and_personas_are_both_available():
    class InputParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.inputs = []

        def handle_starttag(self, tag, attrs):
            if tag == "input":
                self.inputs.append(dict(attrs))

    with TestClient(app) as client:
        response = client.get("/")
        helper = client.get("/static/form-helpers.mjs")
    parser = InputParser()
    parser.feed(response.text)
    names = {item.get('name') for item in parser.inputs}
    assert {'name','year','month','day','nationality','address','phone'} <= names
    assert 'registration_number' not in names
    assert all('value' not in item for item in parser.inputs)
    assert 'id="synthetic-only" type="checkbox"' in response.text
    assert 'id="next" disabled' in response.text
    assert 'type="module"' in response.text
    assert helper.status_code == 200
    assert "javascript" in helper.headers["content-type"]


def test_public_entry_uses_fixed_production_api_without_zip_download():
    with TestClient(app) as client:
        page = client.get('/')
        script = client.get('/demo.mjs')
        assert client.get('/styles.css').status_code == 200
        assert client.get('/sanjae-logo.png').status_code == 200
    assert script.status_code == 200
    assert 'https://sanjae-oneshot.co.kr/api/v1/demo' in script.text
    assert "request('/prepare'" in script.text
    assert 'package_base64' not in script.text
    assert 'createObjectURL' not in script.text
    assert 'id="experience"' in page.text
    assert 'id="download-again"' not in page.text


@pytest.mark.parametrize("account_status", ["created", "failed", "unavailable"])
def test_generated_zip_contains_full_json_number_and_masked_pdf(account_status, monkeypatch):
    data = request_data(registration_number="940312-5000000")
    account = AccountCreationResult(
        status=account_status,
        message="합성 테스트 계정 상태",
        email=data["email"],
        password="synthetic-test-only",
    )
    account_call = AsyncMock(return_value=account)
    monkeypatch.setattr("app.main.create_demo_account", account_call)
    with TestClient(app) as client:
        response = client.post("/api/generate", json=data)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["X-Account-Status"] == account_status
    assert "registration_number" not in account_call.call_args.kwargs
    with ZipFile(BytesIO(response.content)) as archive:
        manifest = json.loads(archive.read("00_시연_입력_가이드.json"))
        assert manifest["schema_version"] == "2.1"
        assert manifest["applicant"]["registration_number"] == "940312-5000000"
        assert manifest["applicant"]["registration_number_masked"] == "940312-5******"
        assert manifest["applicant"]["registration_number_synthetic"] is True
        assert manifest["applicant"]["sex"] == "male"
        for name in archive.namelist():
            content = archive.read(name)
            if name.endswith(".pdf"):
                text = "".join(page.extract_text() for page in PdfReader(BytesIO(content)).pages)
                compact = "".join(text.split()).replace("-", "")
                assert "9403125******" in compact
                assert "9403125000000" not in compact
            else:
                assert b"940312-5000000" in content


def test_brand_icon_and_persona_controls_are_available():
    import hashlib

    with TestClient(app) as client:
        page = client.get("/")
        logo = client.get("/static/sanjae-logo.png")
        styles = client.get("/static/styles.css")
    assert 'data-persona="domestic"' in page.text
    assert 'data-persona="foreign"' in page.text
    assert 'rel="icon" type="image/png"' in page.text
    assert "최종 신청서·재해경위서" in page.text
    assert "--blue: #315fd1" in styles.text
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/png"
    assert hashlib.sha256(logo.content).hexdigest() == "6656f27014e6179e12dd5fa64344850c4e3e671b42f8fca58432c0baada22a33"
