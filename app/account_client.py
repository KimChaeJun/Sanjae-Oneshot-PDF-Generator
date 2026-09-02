from __future__ import annotations

import os
from dataclasses import asdict, dataclass

import httpx

from app.service_target import service_target


@dataclass(frozen=True)
class AccountCreationResult:
    status: str
    message: str
    email: str
    password: str
    user_id: str | None = None
    email_confirmation_required: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


async def create_demo_account(
    *, email: str, password: str, name: str, preferred_language: str
) -> AccountCreationResult:
    target = service_target()
    api_url = target["api_url"]
    signup_path = os.getenv("SANJAE_ACCOUNT_SIGNUP_PATH", "/auth/signup")
    if not signup_path.startswith("/"):
        signup_path = f"/{signup_path}"
    try:
        # Signup includes both upstream account creation and sign-in (20s each).
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=5)) as client:
            response = await client.post(
                f"{api_url}{signup_path}",
                json={
                    "email": email,
                    "password": password,
                    "name": name,
                    "preferred_language": preferred_language,
                },
            )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", "회원가입 요청을 처리하지 못했습니다.")
            except (ValueError, AttributeError):
                detail = "회원가입 API의 응답이 올바르지 않습니다. 서버 상태를 확인해주세요."
            if isinstance(detail, list):
                detail = " ".join(str(item.get("msg", "입력값을 확인해주세요.")) for item in detail if isinstance(item, dict))
            return AccountCreationResult(
                status="failed",
                message=f"계정 생성 실패: {detail}",
                email=email,
                password=password,
            )
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("user_id"):
            raise ValueError("Missing signup result")
        confirmation_required = bool(payload.get("email_confirmation_required"))
        return AccountCreationResult(
            status="created",
            message=(
                "계정이 생성되었습니다. 이메일 확인 설정이 켜져 있어 로그인 전에 인증이 필요합니다."
                if confirmation_required
                else "계정이 생성되어 바로 로그인할 수 있습니다."
            ),
            email=email,
            password=password,
            user_id=payload.get("user_id"),
            email_confirmation_required=confirmation_required,
        )
    except httpx.ConnectError:
        recovery = ("산재원샷 폴더에서 docker compose up -d backend frontend nginx 실행 후 다시 생성해주세요."
                    if target["environment"] == "local" else "운영 서비스 상태와 네트워크 연결을 확인해주세요.")
        return AccountCreationResult(status="unavailable", message=f"산재원샷 API에 연결할 수 없습니다. {recovery}", email=email, password=password)
    except httpx.TimeoutException:
        return AccountCreationResult(status="unavailable", message="회원가입 응답 시간이 초과되었습니다. 계정이 이미 만들어졌을 수 있으니 표시된 정보로 로그인을 확인해주세요. 새 시연 생성은 새 이메일을 사용합니다.", email=email, password=password)
    except (ValueError, TypeError):
        return AccountCreationResult(status="failed", message="회원가입 API 응답 형식이 올바르지 않습니다. API 주소와 서버 상태를 확인해주세요.", email=email, password=password)
    except (httpx.HTTPError, OSError) as exc:
        return AccountCreationResult(
            status="unavailable",
            message=f"산재원샷 API에 연결하지 못했습니다: {type(exc).__name__}",
            email=email,
            password=password,
        )
