from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.account_client import AccountCreationResult
from app.cases import AccidentCase
from app.demo_guide import GUIDE_FILENAME, SIGNATURE_FILENAME, demo_workplace, demo_accident, demo_followup, guide_steps
from app.signature import decode_signature
from app.registration import mask_registration_number, normalize_registration_number, validate_registration_persona


pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
FONT = "HYSMyeongJo-Medium"
BLUE = colors.HexColor("#315FD1")
BLUE_LIGHT = colors.HexColor("#EDF3FF")
INK = colors.HexColor("#182033")
MUTED = colors.HexColor("#657084")
LINE = colors.HexColor("#DFE4EC")


@dataclass(frozen=True)
class Applicant:
    name: str
    birth_date: str
    registration_number: str
    address: str
    phone: str
    email: str
    preferred_language: str
    nationality: str = "대한민국"
    signature_image: str = ""
    sex: str | None = None

    def __post_init__(self) -> None:
        number = normalize_registration_number(self.registration_number)
        validate_registration_persona(number, date.fromisoformat(self.birth_date), self.nationality, self.sex)
        object.__setattr__(self, "registration_number", number)
        if self.signature_image:
            decode_signature(self.signature_image)

    @property
    def masked_registration_number(self) -> str:
        return mask_registration_number(self.registration_number)


@dataclass(frozen=True)
class GeneratedPackage:
    content: bytes
    filename: str
    manifest: dict[str, object]


DOCUMENTS_BY_CASE = {
    "work_accident": [
        ("01_진단소견서.pdf", "진단 소견서", "medical"),
        ("02_재직업무확인서.pdf", "재직·업무 확인서", "employment"),
        ("03_현장작업기록.pdf", "현장 작업 기록", "work_record"),
    ],
    "commute": [
        ("01_진단소견서.pdf", "진단 소견서", "medical"),
        ("02_재직업무확인서.pdf", "재직·업무 확인서", "employment"),
        ("03_출퇴근경로기록.pdf", "출퇴근 경로 기록", "route"),
    ],
    "third_party": [
        ("01_진단소견서.pdf", "진단 소견서", "medical"),
        ("02_재직업무확인서.pdf", "재직·업무 확인서", "employment"),
        ("03_제3자사고사실기록.pdf", "제3자 사고 사실 기록", "third_party"),
    ],
    "occupational_disease": [
        ("01_진단소견서.pdf", "진단 소견서", "medical"),
        ("02_재직업무확인서.pdf", "재직·업무 확인서", "employment"),
        ("03_업무환경노출기록.pdf", "업무환경·노출 기록", "exposure"),
    ],
    "survivor": [
        ("01_사망사실기록.pdf", "사망 사실 기록", "death"),
        ("02_재직업무확인서.pdf", "재직·업무 확인서", "employment"),
        ("03_가족관계확인자료.pdf", "가족관계 확인 자료", "family"),
    ],
    "retreatment": [
        ("01_진단소견서.pdf", "진단 소견서", "medical"),
        ("02_기존요양승인내역.pdf", "기존 요양 승인 내역", "approval"),
        ("03_치료경과기록.pdf", "치료 경과 기록", "retreatment"),
    ],
}


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "KTitle", parent=base["Title"], fontName=FONT, fontSize=22, leading=30,
            textColor=BLUE, alignment=TA_CENTER, spaceAfter=8 * mm,
        ),
        "subtitle": ParagraphStyle(
            "KSubtitle", parent=base["Normal"], fontName=FONT, fontSize=10, leading=16,
            textColor=MUTED, alignment=TA_CENTER, spaceAfter=8 * mm,
        ),
        "heading": ParagraphStyle(
            "KHeading", parent=base["Heading2"], fontName=FONT, fontSize=13, leading=19,
            textColor=BLUE, spaceBefore=5 * mm, spaceAfter=3 * mm,
        ),
        "body": ParagraphStyle(
            "KBody", parent=base["BodyText"], fontName=FONT, fontSize=9.5, leading=16,
            textColor=INK, alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "KSmall", parent=base["BodyText"], fontName=FONT, fontSize=8, leading=12,
            textColor=MUTED,
        ),
        "guide": ParagraphStyle(
            "KGuide", parent=base["BodyText"], fontName=FONT, fontSize=10.5, leading=18,
            textColor=INK,
        ),
    }


def _footer(canvas, doc) -> None:  # type: ignore[no-untyped-def]
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont(FONT, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 9 * mm, "산재원샷 대회장 시연용 합성 문서 - 실제 제출 금지")
    canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, str(doc.page))
    canvas.restoreState()


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)


def _field_table(rows: list[tuple[str, object]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[_paragraph(label, styles["small"]), _paragraph(value, styles["body"])] for label, value in rows]
    table = Table(data, colWidths=[42 * mm, 118 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), BLUE_LIGHT),
        ("TEXTCOLOR", (0, 0), (0, -1), BLUE),
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _document_rows(kind: str, applicant: Applicant, case: AccidentCase) -> list[tuple[str, object]]:
    followup = demo_followup(case)
    common = [
        ("재해 근로자", applicant.name),
        ("생년월일", applicant.birth_date),
        ("주민·외국인등록번호", applicant.masked_registration_number),
        ("연락처", applicant.phone),
        ("주소", applicant.address),
    ]
    if kind == "medical":
        return common + [
            ("의료기관", case.hospital),
            ("진단명", case.diagnosis),
            ("상병 부위", case.injury_part),
            ("진료일", case.accident_date),
            ("시연 후속 조치", followup["post_accident_action"]),
            ("시연 진료 경과", followup["medical_treatment"]),
            ("시연 업무 상태", followup["work_disruption"]),
            ("의사 소견", "사고 또는 업무력과 상병의 관련성을 확인하기 위한 추가 진료와 안정이 필요함."),
        ]
    if kind == "employment":
        workplace = demo_workplace(case)
        return common + [
            ("사업장", case.workplace),
            ("사업장 관리번호", workplace["management_number"]),
            ("사업주명", workplace["representative_name"]),
            ("사업장 연락처", workplace["phone"]),
            ("사업장 주소", case.workplace_address),
            ("담당 업무", case.occupation),
            ("사고 당시 작업", case.task),
            ("근무 확인", "사고일 현재 위 사업장에서 근무한 사실을 확인함."),
            ("시연 후속 조치", followup["post_accident_action"]),
            ("시연 업무 상태", followup["work_disruption"]),
        ]
    if kind == "work_record":
        return common + [
            ("사업장", case.workplace),
            ("작업 일시", f"{case.accident_date} {case.accident_time}"),
            ("작업 장소", case.accident_place),
            ("배정 작업", case.task),
            ("시연 후속 조치", followup["post_accident_action"]),
            ("자료 성격", "작업 배정 사실을 확인하는 합성 기록. 재해경위서 완성본이 아닙니다."),
        ]
    if kind == "death":
        return common + [
            ("의료기관", case.hospital),
            ("확인일", case.accident_date),
            ("상병", case.diagnosis),
            ("확인 사실", "업무상 사고 후 사망한 가상 근로자의 시연용 기록"),
            ("시연 후속 조치", followup["post_accident_action"]),
            ("시연 진료 경과", followup["medical_treatment"]),
            ("시연 업무 상태", followup["work_disruption"]),
            ("자료 성격", "실제 사망진단서가 아닌 합성 증빙 자료"),
        ]
    if kind == "witness":
        return common + [
            ("목격자", case.witness),
            ("사고 일시", f"{case.accident_date} {case.accident_time}"),
            ("사고 장소", case.accident_place),
            ("확인 내용", case.accident_description),
            ("이송", case.transport),
        ]
    if kind == "commute":
        return common + [
            ("사고 일시", f"{case.accident_date} {case.accident_time}"),
            ("사고 장소", case.accident_place),
            ("통상 경로", "자택과 사업장 사이의 평소 이용 경로"),
            ("사고 경위", case.accident_description),
            ("일탈·중단", "개인적인 목적의 일탈 또는 중단 없음"),
        ]
    if kind == "route":
        return common + [("이동 일시", f"{case.accident_date} {case.accident_time}"), ("이동 목적", case.task), ("통상 경로", "자택과 사업장 사이의 평소 이용 경로"), ("발생 장소", case.accident_place), ("이송 방법", case.transport), ("자료 성격", "이동 경로를 확인하기 위한 합성 기록")]
    if kind == "third_party":
        return common + [("사고 일시", f"{case.accident_date} {case.accident_time}"), ("제3자", "외부 협력업체 관계자"), ("발생 장소", case.accident_place), ("사고 경위", case.accident_description), ("배상 여부", "시연용 - 확인 필요")]
    if kind == "exposure":
        return common + [("사업장", case.workplace), ("업무", case.task), ("노출 기간", "3년 8개월 (합성 사례)"), ("유해 요인", "반복 동작·소음·중량물 등 사례별 추정 요인"), ("증상 경과", case.accident_description)]
    if kind == "family":
        return common + [("관계 구분", "유족 청구인은 위 재해 근로자의 배우자 (합성 사례)"), ("유족 청구인 정보", "본 서비스에서 별도 입력 필요. 위 재해 근로자와 동일 인물로 입력하지 마세요."), ("확인 목적", "유족급여·장례비 신청 시 관계 확인"), ("비고", "가족관계등록부를 대신하지 않는 시연용 합성 문서")]
    if kind == "retreatment":
        return common + [("기존 상병", case.diagnosis), ("치료 종결일", "2025-11-28"), ("재발 확인일", case.accident_date), ("재발 경위", case.accident_description), ("추가 치료", "정밀검사 후 재활·약물 또는 수술 치료 검토")]
    if kind == "approval":
        return common + [("기존 승인 번호", f"DEMO-{case.id.upper()}"), ("승인 상병", case.diagnosis), ("최초 요양 기간", "2025-04-03 ~ 2025-11-28"), ("현재 상태", "동일 부위 증상 재발 - 재요양 검토")]
    raise ValueError(f"지원하지 않는 입력 증빙 종류: {kind}")


def build_document_pdf(title: str, kind: str, applicant: Applicant, case: AccidentCase) -> bytes:
    buffer = io.BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title=title, author="산재원샷 시연 생성기",
    )
    story = [
        _paragraph(title, styles["title"]),
        _paragraph("입력용 합성 증빙 · 실제 기관 발급 문서가 아닙니다", styles["subtitle"]),
        _field_table(_document_rows(kind, applicant, case), styles),
        Spacer(1, 4 * mm),
        _paragraph("확인 사항", styles["heading"]),
        _paragraph("이 문서는 산재원샷의 문서 업로드·OCR·사실 대조 흐름을 시연하기 위해 만든 합성 자료입니다. 실제 신청이나 신원 확인에 사용할 수 없습니다.", styles["body"]),
        Spacer(1, 6 * mm),
        _field_table([("작성일", datetime.now().date().isoformat()), ("작성자", "산재원샷 데모 문서 생성기"), ("확인", "시연 담당자 확인")], styles),
    ]
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()




def _safe_name(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", value).strip("-")
    return value[:30] or "demo"


def build_package(applicant: Applicant, case: AccidentCase, account: AccountCreationResult) -> GeneratedPackage:
    from app.service_target import service_target

    document_specs = DOCUMENTS_BY_CASE[case.case_type]
    manifest: dict[str, object] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": "KDT 본선 대회장 시연용 합성 데이터",
        "package_role": "input_evidence_only",
        "service_target": service_target(),
        "case": case.to_dict(),
        "applicant": {
            "name": applicant.name,
            "birth_date": applicant.birth_date,
            "registration_number": applicant.registration_number,
            "registration_number_masked": applicant.masked_registration_number,
            "registration_number_synthetic": True,
            "sex": applicant.sex,
            "address": applicant.address,
            "phone": applicant.phone,
            "email": applicant.email,
            "preferred_language": applicant.preferred_language,
        },
        "demo_account": account.to_dict(),
        "documents": [name for name, _, _ in document_specs],
        "schema_version": "2.1",
        "workplace": demo_workplace(case),
        "accident": demo_accident(case, applicant.preferred_language),
        "signature": {"name": "김유족" if case.case_type == "survivor" else applicant.name, "file": SIGNATURE_FILENAME if applicant.signature_image else None, "image": applicant.signature_image, "synthetic": True},
        "steps": guide_steps(applicant, case, [name for name, _, _ in document_specs]),
        "warnings": ["모든 정보·번호·서명은 시연용 합성 데이터입니다. 실제 제출 금지.", "등록번호는 생년월일·첫 숫자 규칙과 숫자 형식을 맞춘 무작위 합성 값입니다. 실제 발급·본인 인증 유효성을 보장하지 않습니다.", "주민번호를 본 서비스에 입력하지 마세요. 선택 항목인 외국인등록번호는 비워 둡니다."],
    }
    manifest["applicant"]["nationality"] = applicant.nationality
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for filename, title, kind in document_specs:
            bundle.writestr(filename, build_document_pdf(title, kind, applicant, case))
        if applicant.signature_image:
            bundle.writestr(SIGNATURE_FILENAME, decode_signature(applicant.signature_image))
        bundle.writestr(GUIDE_FILENAME, json.dumps(manifest, ensure_ascii=False, indent=2))
    filename = f"산재원샷_시연패키지_{_safe_name(applicant.name)}_{case.id}.zip"
    return GeneratedPackage(content=archive.getvalue(), filename=filename, manifest=manifest)
