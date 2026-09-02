"""One canonical, step-by-step demo guide shared by the ZIP and completion UI."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.pdf_generator import Applicant
    from app.cases import AccidentCase


GUIDE_FILENAME = "00_시연_입력_가이드.json"
SIGNATURE_FILENAME = "04_시연용_서명.png"


def demo_workplace(case: AccidentCase) -> dict[str, str]:
    number = int(case.id.rsplit("-", 1)[1])
    return {
        "company_name": case.workplace,
        "management_number": f"900-00-{number:05d}-0",
        "business_registration_no": f"900-00-{number:05d}",
        "representative_name": ("김시연", "이데모", "박예시")[number % 3],
        "phone": f"02-0000-{number:04d}",
        "address": case.workplace_address,
        "occupation": case.occupation,
        "job_position": "현장 근로자",
    }


def demo_accident(case: AccidentCase, language: str) -> dict[str, object]:
    witness_present = case.witness != "목격자 없음"
    number = int(case.id.rsplit("-", 1)[1])
    return {
        "accident_type": case.case_type if case.case_type in {"commute", "occupational_disease"} else "work_accident",
        "accident_date": case.accident_date,
        "accident_date_precision": "exact",
        "accident_time": case.accident_time,
        "accident_time_precision": "exact",
        "accident_place": case.accident_place,
        "task_description": case.task,
        "raw_description": case.accident_description,
        "language": language,
        "injury_parts": [case.injury_part],
        "witness_status": "yes" if witness_present else "no",
        "witness_name": case.witness if witness_present else "",
        "witness_phone": f"010-0000-{number:04d}" if witness_present else "",
        "witness_relationship": "같은 작업조 동료" if witness_present else "",
        "witness_statement": case.accident_description if witness_present else "",
    }


def guide_steps(applicant: Applicant, case: AccidentCase, documents: list[str]) -> list[dict[str, object]]:
    survivor = case.case_type == "survivor"
    # Survivor claimant and deceased worker must never be the same identity.
    claimant_name = "김유족" if survivor else applicant.name
    claimant_birth = "1992-05-20" if survivor else applicant.birth_date
    profile = {
        "name": claimant_name, "birth_date": claimant_birth,
        "birth_date_verification": claimant_birth.replace("-", ""),
        "phone": "010-0000-0520" if survivor else applicant.phone,
        "address": applicant.address,
        "nationality": "대한민국" if survivor else applicant.nationality,
        "preferred_language": applicant.preferred_language,
        "signature_name": claimant_name,
        "signature_file": SIGNATURE_FILENAME if applicant.signature_image else None,
        "foreign_registration_no": None,
    }
    step_applicant = {
        "name": profile["name"], "birth_date": profile["birth_date"],
        "phone": profile["phone"], "address": profile["address"],
        "nationality": profile["nationality"], "preferred_language": applicant.preferred_language,
        "email": applicant.email, "worker_type": "근로자", "applicant_role": "self",
        "benefit_type": "survivor_benefit" if survivor else "medical_care",
        "deceased_worker_name": applicant.name if survivor else "",
        "relationship_to_deceased": "spouse" if survivor else "self",
    }
    return [
        {"id": "login", "title": "로그인", "instructions": ["demo_account의 이메일·비밀번호로 로그인합니다. 계정 생성 실패 시 상태를 확인하고 다시 생성합니다."]},
        {"id": "consent", "step": 0, "display_step": 1, "title": "약관·개인정보 동의", "instructions": ["각 동의 내용을 읽고 시연자가 직접 필수 항목에 동의합니다. 자동 동의하지 않습니다."]},
        {"id": "profile", "title": "최초 개인정보 등록·서명", "fields": profile,
         "instructions": ["서명 사진 업로드 버튼으로 signature_file을 선택합니다. 이름 기반 합성 서명이며 실제 서명을 모방하지 않습니다.", "applicant.registration_number는 전체 13자리 합성 번호이고, 화면·PDF만 마스킹합니다. 실제 신원 확인용이 아닙니다. 본 서비스는 주민번호를 받지 않으며 선택 항목인 외국인등록번호도 비워 둡니다."]},
        {"id": "basic", "step": 1, "display_step": 2, "title": "기본 정보", "fields": {"applicant": step_applicant, "workplace": demo_workplace(case)},
         "instructions": ["사업장 관리번호와 사업자등록번호는 서로 다른 항목입니다. 모두 시연용 합성 값입니다."] + (["김유족은 배우자 청구인, 재해 근로자는 사망 근로자입니다. 두 사람을 구분합니다."] if survivor else [])},
        {"id": "accident", "step": 2, "display_step": 3, "title": "사고 정보", "fields": demo_accident(case, applicant.preferred_language),
         "instructions": ["목격자가 없으면 관련 성명·연락처·내용은 입력하지 않습니다.", "제3자·유족·재요양 사례의 사고 분류는 업무상 사고로 선택하고 상세 경위와 급여 유형으로 구분합니다."]},
        {"id": "documents", "step": 3, "display_step": 4, "title": "증빙 업로드", "files": documents,
         "instructions": ["아래 입력용 증빙 3종을 업로드합니다. 가이드 JSON과 서명 PNG는 증빙 업로드 대상이 아닙니다.", "최종 신청서·재해경위서는 제너레이터가 만들지 않습니다."]},
        {"id": "requirements", "step": 4, "display_step": 5, "title": "필요 서류 확인", "instructions": ["유형별 분석 결과와 누락 항목을 확인합니다."]},
        {"id": "ocr", "step": 5, "display_step": 6, "title": "OCR 확인", "expected": {"worker_name": applicant.name, "diagnosis": case.diagnosis, "hospital": case.hospital}, "instructions": ["이름·날짜·사업장과 추출 결과를 대조합니다."]},
        {"id": "draft", "step": 6, "display_step": 7, "title": "AI 초안", "instructions": ["입력한 사실을 바탕으로 산재원샷이 재해경위서 초안을 생성했는지 확인합니다."]},
        {"id": "review", "step": 7, "display_step": 8, "title": "AI 검토·보완", "reference_facts": demo_accident(case, applicant.preferred_language), "instructions": ["필수 보완 질문에 답하고 답변 반영을 누릅니다. 확인되지 않은 사실은 만들지 않습니다."]},
        {"id": "final", "step": 8, "display_step": 9, "title": "최종 확인", "instructions": ["문안을 확인한 후 사실 확인·최종 제출 책임에 직접 체크합니다.", "산재원샷에서 신청정보와 재해경위서 PDF 2종을 최종 생성합니다. 합성 시연 자료는 실제 제출하지 않습니다."]},
    ]
