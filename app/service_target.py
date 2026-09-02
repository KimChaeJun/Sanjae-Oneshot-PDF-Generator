"""Keep demo account creation and application navigation in one environment."""

import os
from urllib.parse import urlsplit


PRODUCTION_APP_URL = "https://sanjae-oneshot.co.kr"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def service_target() -> dict[str, str]:
    app_url = os.getenv("SANJAE_APP_URL", PRODUCTION_APP_URL).rstrip("/")
    api_url = os.getenv("SANJAE_API_URL", f"{app_url}/api/v1").rstrip("/")
    app = urlsplit(app_url)
    api = urlsplit(api_url)
    for parsed in (app, api):
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("산재원샷 연결 주소는 인증정보·쿼리 없는 HTTP(S) 주소여야 합니다.")
    if app.path:
        raise ValueError("SANJAE_APP_URL에는 경로 없이 서비스 기본 주소를 설정해주세요.")
    both_local = app.hostname in LOCAL_HOSTS and api.hostname in LOCAL_HOSTS
    if not both_local and (app.scheme, app.hostname, app.port) != (api.scheme, api.hostname, api.port):
        raise ValueError("SANJAE_API_URL과 SANJAE_APP_URL을 같은 환경으로 설정해주세요.")
    return {
        "environment": "local" if both_local else "production" if app_url == PRODUCTION_APP_URL else "custom",
        "app_url": app_url,
        "api_url": api_url,
        "application_url": f"{app_url}/?start=application",
    }
