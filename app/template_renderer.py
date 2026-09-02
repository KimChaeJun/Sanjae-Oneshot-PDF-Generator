from __future__ import annotations

import io
import os
from datetime import date
from pathlib import Path
from typing import Any, Callable

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_DIR = ROOT.parent / "참고 서류"
FONT = "HYSMyeongJo-Medium"
pdfmetrics.registerFont(UnicodeCIDFont(FONT))

TEMPLATE_FILES = {
    "application": "1_산업재해보상보험_요양급여신청서(별지제2호서식).pdf",
    "opinion": "2_산업재해보상보험_요양급여신청_소견서(별지제3호서식).pdf",
    "commute": "3_출퇴근재해_발생신고서.pdf",
    "third_party": "4_제3자의_행위에_따른_재해발생신고서(별지제1호서식).pdf",
    "confirmation": "5_확인서(별지제1호의2서식).pdf",
    "accident_statement": "재해경위서 119구급대 이송.pdf",
    "work_order": "현장_작업지시서_양식.pdf",
}

FOREIGN_REGISTRATION_CELLS = (
    (326.3, 672.5, 340.5, 689.5), (343.3, 672.5, 357.5, 689.5),
    (360.3, 672.5, 374.4, 689.5), (377.2, 672.5, 391.4, 689.5),
    (394.2, 672.5, 408.4, 689.5), (411.1, 672.5, 425.3, 689.5),
    (431.5, 672.5, 445.7, 689.5), (448.6, 672.5, 462.7, 689.5),
    (465.5, 672.5, 479.6, 689.5), (482.4, 672.5, 496.7, 689.5),
    (499.4, 672.5, 513.6, 689.5), (516.3, 672.5, 530.5, 689.5),
    (533.4, 672.5, 547.5, 689.5),
)
ACCIDENT_DATETIME_CELLS = (
    (115.1, 610.5, 129.3, 627.4), (132.2, 610.5, 146.3, 627.4),
    (149.1, 610.5, 163.2, 627.4), (166.0, 610.5, 180.3, 627.4),
    (189.6, 610.5, 203.8, 627.4), (206.6, 610.5, 220.8, 627.4),
    (230.2, 610.5, 244.3, 627.4), (247.2, 610.5, 261.3, 627.4),
    (270.8, 610.5, 285.0, 627.4), (287.7, 610.5, 301.9, 627.4),
    (311.4, 610.5, 325.5, 627.4), (328.3, 610.5, 342.4, 627.4),
)
OPINION_REGISTRATION_CELLS = (
    (174, 700, 190, 731), (191, 700, 207, 731), (208, 700, 224, 731),
    (225, 700, 241, 731), (242, 700, 258, 731), (259, 700, 274, 731),
    (284, 700, 300, 731), (301, 700, 317, 731), (318, 700, 334, 731),
    (335, 700, 351, 731), (352, 700, 368, 731), (369, 700, 385, 731),
    (386, 700, 398, 731),
)
OPINION_ACCIDENT_DATE_CELLS = (
    (402, 704, 418, 728), (419, 704, 435, 728), (436, 704, 452, 728),
    (453, 704, 469, 728), (477, 704, 493, 728), (494, 704, 510, 728),
    (523, 704, 539, 728), (540, 704, 556, 728),
)


def _template_dir() -> Path:
    configured = os.getenv("SANJAE_TEMPLATE_DIR")
    return Path(configured) if configured else DEFAULT_TEMPLATE_DIR


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _fit_text(
    target: canvas.Canvas,
    value: Any,
    box: tuple[float, float, float, float],
    *,
    size: float = 9.2,
    minimum: float = 6.5,
    align: str = "left",
) -> None:
    text = _text(value)
    if not text:
        return
    x1, y1, x2, y2 = box
    current = size
    available = max(1, x2 - x1 - 5)
    while current > minimum and pdfmetrics.stringWidth(text, FONT, current) > available:
        current -= 0.25
    while text and pdfmetrics.stringWidth(text, FONT, current) > available:
        text = text[:-1]
    target.setFont(FONT, current)
    target.setFillColor(colors.black)
    baseline = y1 + max(1.5, ((y2 - y1) - current) / 2 + 1.7)
    if align == "center":
        target.drawCentredString((x1 + x2) / 2, baseline, text)
    elif align == "right":
        target.drawRightString(x2 - 2.5, baseline, text)
    else:
        target.drawString(x1 + 2.5, baseline, text)


def _wrap_lines(value: Any, width: float, size: float) -> list[str]:
    raw = " ".join(_text(value).split())
    lines: list[str] = []
    current = ""
    for character in raw:
        candidate = current + character
        if current and pdfmetrics.stringWidth(candidate, FONT, size) > width:
            lines.append(current.rstrip())
            current = character.lstrip()
        else:
            current = candidate
    if current:
        lines.append(current.rstrip())
    return lines


def _fit_multiline(
    target: canvas.Canvas,
    value: Any,
    box: tuple[float, float, float, float],
    *,
    size: float = 9.2,
    minimum: float = 7.0,
    max_lines: int = 5,
    align: str = "left",
    valign: str = "center",
) -> None:
    if not _text(value):
        return
    x1, y1, x2, y2 = box
    current = size
    available_width = max(1, x2 - x1 - 8)
    available_height = max(1, y2 - y1 - 6)
    lines = _wrap_lines(value, available_width, current)
    while current > minimum and (
        len(lines) > max_lines or len(lines) * current * 1.25 > available_height
    ):
        current -= 0.25
        lines = _wrap_lines(value, available_width, current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and pdfmetrics.stringWidth(lines[-1] + "…", FONT, current) > available_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    leading = current * 1.25
    block_height = len(lines) * leading
    if valign == "top":
        baseline = y2 - current - 4
    else:
        baseline = y1 + (available_height + block_height) / 2 - current
    target.setFont(FONT, current)
    target.setFillColor(colors.black)
    for index, line in enumerate(lines):
        y = baseline - index * leading
        if align == "center":
            target.drawCentredString((x1 + x2) / 2, y, line)
        else:
            target.drawString(x1 + 4, y, line)


def _draw_characters(
    target: canvas.Canvas,
    value: Any,
    cells: tuple[tuple[float, float, float, float], ...],
    *,
    size: float = 9.2,
) -> None:
    characters = [character for character in _text(value) if character.isalnum() or character == "*"]
    target.setFont(FONT, size)
    target.setFillColor(colors.black)
    for character, (x1, y1, x2, y2) in zip(characters, cells, strict=False):
        target.drawCentredString((x1 + x2) / 2, y1 + (y2 - y1 - size) / 2 + 1.5, character)


def _clear_box(
    target: canvas.Canvas,
    box: tuple[float, float, float, float],
    *,
    inset: float = 0,
) -> None:
    x1, y1, x2, y2 = box
    target.setFillColor(colors.white)
    target.rect(
        x1 + inset,
        y1 + inset,
        max(0, x2 - x1 - inset * 2),
        max(0, y2 - y1 - inset * 2),
        stroke=0,
        fill=1,
    )


def _date_parts(value: str) -> tuple[str, str, str]:
    parts = value.split("-")
    return tuple(parts[:3]) if len(parts) >= 3 else ("", "", "")


def _stamp(target: canvas.Canvas, width: float, height: float) -> None:
    target.setFillColor(colors.HexColor("#B42318"))
    target.setFont(FONT, 7.2)
    target.drawRightString(width - 30, height - 22, "시연용 합성정보 · 실제 제출 불가")


def _merge_template(
    template_name: str,
    draws: dict[int, Callable[[canvas.Canvas, float, float], None]],
    *,
    title: str,
) -> bytes:
    template_path = _template_dir() / template_name
    if not template_path.is_file():
        raise FileNotFoundError(f"참고 양식을 찾지 못했습니다: {template_path}")
    reader = PdfReader(str(template_path))
    writer = PdfWriter()
    for page_index, page in enumerate(reader.pages):
        writer.add_page(page)
        output_page = writer.pages[-1]
        draw = draws.get(page_index)
        if draw:
            width = float(output_page.mediabox.width)
            height = float(output_page.mediabox.height)
            overlay_stream = io.BytesIO()
            overlay = canvas.Canvas(overlay_stream, pagesize=(width, height))
            draw(overlay, width, height)
            _stamp(overlay, width, height)
            overlay.save()
            overlay_stream.seek(0)
            output_page.merge_page(PdfReader(overlay_stream).pages[0])
    writer.add_metadata({
        "/Title": title,
        "/Author": "산재원샷 시연 생성기",
        "/Subject": "참고 서식 기반 합성 시연 문서 - 실제 제출 불가",
    })
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


def _application_draws(applicant: Any, case: Any) -> dict[int, Callable[..., None]]:
    def page_one(target: canvas.Canvas, width: float, height: float) -> None:
        del width, height
        _fit_text(target, applicant.name, (62, 670, 323, 689), size=10.2)
        _draw_characters(target, applicant.masked_registration_number, FOREIGN_REGISTRATION_CELLS)
        _fit_multiline(target, applicant.address, (62, 633, 351, 660), size=9.4, max_lines=2, align="center")
        _fit_text(target, applicant.phone, (402, 645, 549, 662), size=9.4)
        accident_digits = case.accident_date.replace("-", "") + case.accident_time.replace(":", "")
        _draw_characters(target, accident_digits, ACCIDENT_DATETIME_CELLS, size=8.8)
        _fit_text(target, case.occupation, (432, 586, 549, 605), size=8.9)
        _fit_text(target, "V", (154, 516, 174, 534), size=10, align="center")
        accident_box = {
            "occupational_disease": (247, 486, 267, 504),
            "commute": (426, 486, 446, 504),
        }.get(case.case_type, (154, 486, 174, 504))
        _fit_text(target, "V", accident_box, size=10, align="center")
        _fit_text(target, case.workplace, (107, 468, 242, 487), size=9.1)
        _fit_multiline(target, case.workplace_address, (107, 412, 549, 444), size=9.1, max_lines=2, align="center")
        _fit_multiline(
            target,
            case.accident_description,
            (68, 332, 541, 399),
            size=10.0,
            minimum=8.4,
            max_lines=5,
        )
        has_119 = "119" in case.transport
        _fit_text(target, "V", (497, 309, 510, 324), size=10, align="center")
        _fit_text(target, "V", (446, 289, 460, 304) if has_119 else (497, 289, 510, 304), size=10, align="center")
        _fit_text(target, "V", (497, 269, 510, 284), size=10, align="center")
        if case.witness != "목격자 없음":
            _fit_text(target, case.witness, (180, 243, 245, 262), size=8.8, align="center")
            _fit_text(target, "동료", (466, 243, 541, 262), size=8.2, align="center")
        _fit_text(target, case.hospital, (123, 210, 330, 228), size=8.7)
        today = date.today()
        _fit_text(target, today.year, (225, 72, 255, 89), size=9.8, align="right")
        _fit_text(target, today.month, (275, 72, 292, 89), size=9.8, align="right")
        _fit_text(target, today.day, (314, 72, 331, 89), size=9.8, align="right")
        _fit_text(target, applicant.name, (318, 52, 426, 70), size=9.3, align="center")

    def page_two(target: canvas.Canvas, width: float, height: float) -> None:
        del width, height
        for box in ((404, 514, 416, 526), (404, 461, 416, 473), (404, 371, 416, 383), (404, 231, 416, 243), (404, 148, 416, 160)):
            _fit_text(target, "V", box, size=10, align="center")
        _fit_text(target, applicant.name, (454, 64, 538, 86), size=9.3, align="center")

    return {0: page_one, 1: page_two}


def _opinion_draws(applicant: Any, case: Any) -> dict[int, Callable[..., None]]:
    def page_one(target: canvas.Canvas, width: float, height: float) -> None:
        del width, height
        _fit_text(target, applicant.name, (52, 700, 169, 731), size=9.5, align="center")
        _draw_characters(target, applicant.masked_registration_number, OPINION_REGISTRATION_CELLS, size=8.4)
        _draw_characters(target, case.accident_date.replace("-", ""), OPINION_ACCIDENT_DATE_CELLS, size=7.8)
        year, month, day = _date_parts(case.accident_date)
        _fit_text(target, year, (170, 681, 207, 700), size=8.2, align="right")
        _fit_text(target, month, (217, 681, 233, 700), size=8.2, align="right")
        _fit_text(target, day, (244, 681, 260, 700), size=8.2, align="right")
        _fit_text(target, "V", (220, 648, 238, 666) if "119" in case.transport else (174, 648, 192, 666), size=9.5, align="center")
        _fit_multiline(target, case.accident_description, (170, 583, 557, 635), size=9.0, max_lines=4)
        _fit_text(target, year, (170, 578, 207, 600), size=8.2, align="right")
        _fit_text(target, month, (217, 578, 233, 600), size=8.2, align="right")
        _fit_text(target, day, (244, 578, 260, 600), size=8.2, align="right")
        _fit_text(target, case.accident_time, (268, 578, 306, 600), size=8.2, align="center")
        _fit_multiline(target, case.diagnosis, (220, 555, 557, 578), size=9.2, max_lines=2)
        _fit_multiline(target, f"현재 {case.injury_part} 부위 통증과 운동 제한을 호소함.", (170, 518, 557, 554), size=9.0, max_lines=3)
        _fit_multiline(target, "안정과 치료가 필요하며 업무 또는 사고 경위와 상병의 관련성을 확인함.", (170, 474, 557, 517), size=9.0, max_lines=3)
        _fit_text(target, case.diagnosis, (340, 237, 557, 257), size=8.4)

    def page_two(target: canvas.Canvas, width: float, height: float) -> None:
        del width, height
        today = date.today()
        _fit_text(target, today.year, (365, 218, 404, 235), size=8.4, align="right")
        _fit_text(target, today.month, (416, 218, 433, 235), size=8.4, align="right")
        _fit_text(target, today.day, (445, 218, 462, 235), size=8.4, align="right")
        _fit_text(target, case.hospital, (94, 163, 310, 179), size=8.6)
        _fit_text(target, "산재원샷 시연 담당의", (382, 156, 465, 174), size=7.6, align="center")

    return {0: page_one, 1: page_two}


def _commute_draws(applicant: Any, case: Any) -> dict[int, Callable[..., None]]:
    def page_one(target: canvas.Canvas, width: float, height: float) -> None:
        del width, height
        _fit_text(target, applicant.name, (174, 730, 343, 753), size=10, align="center")
        _fit_text(target, applicant.birth_date, (407, 730, 552, 753), size=9.3, align="center")
        _fit_text(target, "V", (176, 707, 190, 722), size=10, align="center")
        _fit_text(target, "V", (176, 682, 190, 699), size=10, align="center")
        _fit_text(target, "V", (176, 650, 190, 667), size=10, align="center")
        _fit_text(target, case.accident_date + " " + case.accident_time, (174, 619, 552, 642), size=9.5, align="center")
        _fit_text(target, "약 45분", (174, 592, 552, 614), size=9.3, align="center")
        _fit_text(target, applicant.address, (174, 547, 456, 577), size=8.8)
        _fit_text(target, case.accident_time, (456, 547, 552, 577), size=9.0, align="center")
        _fit_text(target, case.accident_place, (174, 516, 456, 546), size=8.8)
        _fit_text(target, case.accident_time, (456, 516, 552, 546), size=9.0, align="center")
        _fit_text(target, case.workplace_address, (174, 485, 456, 515), size=8.4)
        _fit_text(target, "V", (514, 458, 529, 474), size=10, align="center")
        _fit_multiline(target, case.accident_description, (174, 258, 552, 450), size=10.0, minimum=8.2, max_lines=12)
        today = date.today()
        _fit_text(target, today.year, (380, 84, 422, 103), size=9.0, align="right")
        _fit_text(target, today.month, (435, 84, 461, 103), size=9.0, align="right")
        _fit_text(target, today.day, (473, 84, 499, 103), size=9.0, align="right")
        _fit_text(target, applicant.name, (290, 62, 393, 80), size=9.2, align="center")

    return {0: page_one}


def _third_party_draws(applicant: Any, case: Any) -> dict[int, Callable[..., None]]:
    def page_one(target: canvas.Canvas, width: float, height: float) -> None:
        del width, height
        _fit_text(target, case.workplace, (151, 681, 310, 704), size=8.8)
        _fit_text(target, applicant.name, (151, 635, 310, 657), size=9.2)
        _fit_text(target, applicant.masked_registration_number, (310, 635, 443, 657), size=8.5, align="center")
        _fit_text(target, case.occupation, (480, 635, 548, 657), size=8.2, align="center")
        _fit_text(target, applicant.address, (203, 612, 420, 634), size=7.8)
        _fit_text(target, applicant.phone, (430, 612, 548, 634), size=8.6, align="center")
        year, month, day = _date_parts(case.accident_date)
        _fit_text(target, year, (177, 445, 225, 466), size=8.5, align="right")
        _fit_text(target, month, (245, 445, 276, 466), size=8.5, align="right")
        _fit_text(target, day, (297, 445, 330, 466), size=8.5, align="right")
        _fit_text(target, case.accident_place, (405, 445, 548, 466), size=8.0)
        _fit_multiline(target, case.accident_description, (153, 364, 548, 429), size=8.8, max_lines=5)
        _fit_text(target, f"{case.injury_part} / {case.diagnosis}", (153, 342, 548, 363), size=8.5)
        today = date.today()
        _fit_text(target, today.year, (180, 235, 222, 251), size=8.6, align="right")
        _fit_text(target, today.month, (234, 235, 254, 251), size=8.6, align="right")
        _fit_text(target, today.day, (266, 235, 285, 251), size=8.6, align="right")
        _fit_text(target, case.workplace, (330, 218, 429, 234), size=8.2, align="center")
        _fit_text(target, applicant.phone, (107, 202, 213, 218), size=8.0, align="center")
        _fit_text(target, applicant.name, (332, 202, 429, 218), size=8.4, align="center")

    return {0: page_one}


def _accident_statement_draws(applicant: Any, case: Any) -> dict[int, Callable[..., None]]:
    def page_one(target: canvas.Canvas, width: float, height: float) -> None:
        del width, height
        _fit_text(target, case.workplace, (145, 632, 302, 668), size=11, align="center")
        _fit_text(target, case.workplace_address, (145, 599, 302, 632), size=9.2, align="center")
        _fit_text(target, case.occupation, (145, 563, 302, 599), size=10.5, align="center")
        _fit_text(target, applicant.name, (146, 495, 297, 519), size=11.2, align="center")
        _fit_text(target, applicant.masked_registration_number, (145, 477, 297, 496), size=9.4, align="center")
        _fit_multiline(target, applicant.address, (385, 477, 547, 519), size=9.2, max_lines=2, align="center")
        _fit_text(target, applicant.phone, (146, 434, 297, 476), size=10.5, align="center")
        _fit_text(target, case.occupation, (370, 434, 547, 454), size=9.6, align="center")
        _fit_text(target, case.accident_date + " " + case.accident_time, (146, 376, 297, 434), size=9.8, align="center")
        _fit_text(target, case.injury_part, (146, 339, 297, 376), size=10.0, align="center")
        _fit_text(target, case.type_label, (368, 339, 547, 376), size=10.0, align="center")
        _fit_text(target, f"{case.workplace} / {case.occupation}", (220, 253, 545, 276), size=9.3)
        year, month, day = _date_parts(case.accident_date)
        _fit_text(target, year[-2:], (194, 212, 214, 237), size=9.8, align="center")
        _fit_text(target, month, (230, 212, 263, 237), size=9.8, align="center")
        _fit_text(target, day, (278, 212, 312, 237), size=9.8, align="center")
        _fit_text(target, case.accident_time, (327, 212, 382, 237), size=9.8, align="center")
        _clear_box(target, (160, 171, 320, 197), inset=1)
        _fit_text(target, case.accident_place, (160, 171, 545, 197), size=9.5)
        _fit_text(target, case.accident_date + " " + case.accident_time, (160, 96, 540, 124), size=9.8)
        _fit_text(target, case.accident_place, (160, 65, 540, 94), size=9.5)
        _fit_text(target, applicant.name, (160, 35, 540, 63), size=10.0)

    def page_two(target: canvas.Canvas, width: float, height: float) -> None:
        del width, height
        _fit_text(target, case.task, (210, 735, 540, 760), size=10.2)
        _fit_multiline(target, case.accident_description, (165, 691, 540, 730), size=9.5, max_lines=3)
        _fit_text(target, case.diagnosis, (145, 658, 540, 691), size=9.8)
        _clear_box(target, (250, 236, 390, 264))
        _fit_text(target, date.today().isoformat(), (250, 236, 390, 264), size=10.0, align="center")
        _fit_text(target, case.workplace, (325, 214, 540, 242), size=9.8)
        _fit_text(target, case.occupation, (325, 184, 540, 214), size=9.8)
        _fit_text(target, applicant.name, (325, 154, 450, 184), size=10.2)
        _fit_text(target, applicant.phone, (385, 124, 500, 154), size=9.5)

    return {0: page_one, 1: page_two}


def _work_order_draws(applicant: Any, case: Any) -> dict[int, Callable[..., None]]:
    def page_one(target: canvas.Canvas, width: float, height: float) -> None:
        del width, height
        _fit_text(target, case.accident_place, (116, 658, 298, 679), size=9.4, align="center")
        _fit_text(target, case.workplace, (431, 658, 556, 679), size=8.8, align="center")
        _fit_text(target, case.occupation, (116, 636, 298, 657), size=9.4, align="center")
        _fit_text(target, "즉시", (431, 636, 556, 657), size=9.4, align="center")
        _fit_text(target, f"{case.type_label} 관련 안전 작업지시", (116, 614, 556, 635), size=9.8)
        _fit_multiline(target, f"{case.task}. 사고 경위: {case.accident_description}\n재발 방지를 위해 작업 전 위험요인을 확인하고 보호구와 안전 절차를 준수합니다.", (48, 333, 551, 580), size=11.0, minimum=9.0, max_lines=14, valign="top")
        today = date.today()
        _fit_text(target, today.year, (197, 287, 235, 307), size=8.8, align="right")
        _fit_text(target, today.month, (239, 287, 258, 307), size=8.8, align="right")
        _fit_text(target, today.day, (262, 287, 282, 307), size=8.8, align="right")
        _fit_text(target, applicant.name, (425, 288, 540, 308), size=9.2, align="center")
        _fit_multiline(target, "시연용 확인: 작업구역 정리, 보호구 착용, 관리자 안전 확인을 완료합니다.", (48, 93, 551, 260), size=10.0, max_lines=8)

    return {0: page_one}


def _confirmation_draws(applicant: Any, case: Any) -> dict[int, Callable[..., None]]:
    def page_one(target: canvas.Canvas, width: float, height: float) -> None:
        del width, height
        year, month, day = _date_parts(case.accident_date)
        _fit_text(target, year, (110, 707, 153, 725), size=8.8, align="right")
        _fit_text(target, month, (165, 707, 210, 725), size=8.8, align="right")
        _fit_text(target, day, (221, 707, 267, 725), size=8.8, align="right")
        _fit_text(target, case.accident_time, (278, 707, 324, 725), size=8.8, align="center")
        _fit_text(target, case.accident_place, (334, 707, 453, 725), size=8.1)
        today = date.today()
        _fit_text(target, today.year, (211, 158, 255, 176), size=8.8, align="right")
        _fit_text(target, today.month, (268, 158, 299, 176), size=8.8, align="right")
        _fit_text(target, today.day, (311, 158, 343, 176), size=8.8, align="right")
        _fit_text(target, applicant.address, (295, 116, 453, 134), size=8.0)
        _fit_text(target, applicant.phone, (468, 116, 527, 134), size=6.8, minimum=5.6, align="center")
        _fit_text(target, applicant.name, (295, 99, 437, 116), size=8.8, align="center")

    return {0: page_one}


def build_template_document(template_kind: str, title: str, applicant: Any, case: Any) -> bytes:
    builders: dict[str, Callable[[Any, Any], dict[int, Callable[..., None]]]] = {
        "application": _application_draws,
        "opinion": _opinion_draws,
        "commute": _commute_draws,
        "third_party": _third_party_draws,
        "confirmation": _confirmation_draws,
        "accident_statement": _accident_statement_draws,
        "work_order": _work_order_draws,
    }
    if template_kind not in builders:
        raise KeyError(f"지원하지 않는 참고 양식입니다: {template_kind}")
    return _merge_template(
        TEMPLATE_FILES[template_kind],
        builders[template_kind](applicant, case),
        title=title,
    )
