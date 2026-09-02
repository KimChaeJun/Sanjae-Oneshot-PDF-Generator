import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.account_client import create_demo_account
from app.main import app
from app.service_target import service_target


@pytest.fixture(autouse=True)
def clean_target(monkeypatch):
    monkeypatch.delenv("SANJAE_API_URL", raising=False)
    monkeypatch.delenv("SANJAE_APP_URL", raising=False)


def test_default_target_is_production():
    with TestClient(app) as client:
        response = client.get("/api/config")
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "environment": "production",
        "app_url": "https://sanjae-oneshot.co.kr",
        "api_url": "https://sanjae-oneshot.co.kr/api/v1",
        "application_url": "https://sanjae-oneshot.co.kr/?start=application",
    }


def test_local_override_requires_both_addresses(monkeypatch):
    monkeypatch.setenv("SANJAE_API_URL", "http://host.docker.internal:8000/api/v1")
    with pytest.raises(ValueError, match="같은 환경"):
        service_target()
    monkeypatch.setenv("SANJAE_APP_URL", "http://localhost:3000/")
    assert service_target()["environment"] == "local"
    assert service_target()["application_url"] == "http://localhost:3000/?start=application"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://user:password@example.com", "https://example.com/?token=hidden", "https://example.com/#fragment", "https://example.com/nested"])
def test_unsafe_public_addresses_rejected(url, monkeypatch):
    monkeypatch.setenv("SANJAE_APP_URL", url)
    with pytest.raises(ValueError):
        service_target()


def test_signup_uses_same_production_target(monkeypatch):
    real_client = httpx.AsyncClient
    def handle(request):
        assert str(request.url) == "https://sanjae-oneshot.co.kr/api/v1/auth/signup"
        return httpx.Response(201, json={"user_id": "synthetic-user"})
    monkeypatch.setattr("app.account_client.httpx.AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs))
    result = asyncio.run(create_demo_account(email="test@example.com", password="synthetic-only", name="시연", preferred_language="ko"))
    assert result.status == "created"
