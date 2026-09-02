from pathlib import Path

from app.account_client import AccountCreationResult
from app.cases import get_case
from app.pdf_generator import Applicant, build_package


def main() -> None:
    output_dir = Path("output/pdf")
    output_dir.mkdir(parents=True, exist_ok=True)
    applicant = Applicant(
        name="김민준",
        birth_date="1991-04-18",
        registration_number="910418-1******",
        address="서울특별시 구로구 디지털로 25",
        phone="010-2000-1001",
        email="synthetic.fixture@example.com",
        preferred_language="ko",
    )
    account = AccountCreationResult(
        status="created",
        message="계정이 생성되어 바로 로그인할 수 있습니다.",
        email=applicant.email,
        password="SYNTHETIC-NOT-A-LOGIN",
        user_id="00000000-0000-0000-0000-000000000001",
    )
    package = build_package(applicant, get_case("work_accident", seed=3), account)
    output_path = output_dir / "산재원샷_시연패키지_샘플.zip"
    output_path.write_bytes(package.content)
    print(output_path.resolve())


if __name__ == "__main__":
    main()
