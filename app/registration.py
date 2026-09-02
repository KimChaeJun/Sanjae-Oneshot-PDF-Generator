"""Normalize synthetic demo IDs; mask them only when presenting documents/UI."""

import re
import random
from datetime import date


def normalize_registration_number(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("주민·외국인등록번호를 입력해주세요.")
    compact = re.sub(r"[\s-]", "", value)
    if not re.fullmatch(r"[0-9]{7}(?:[0-9]{6}|\*{6})?", compact):
        raise ValueError("합성 등록번호는 000000-0000000 형식이어야 합니다.")
    # Older clients sent only the prefix or six stars. Complete it once, then
    # preserve the generated digits throughout the request and ZIP/JSON export.
    suffix = compact[7:] if re.fullmatch(r"[0-9]{13}", compact) else f"{random.SystemRandom().randrange(1_000_000):06d}"
    return f"{compact[:6]}-{compact[6]}{suffix}"


def mask_registration_number(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("합성 등록번호를 확인해주세요.")
    compact = re.sub(r"[\s-]", "", value)
    if not re.fullmatch(r"[0-9]{7}(?:[0-9]{6}|\*{6})?", compact):
        raise ValueError("합성 등록번호 형식을 확인해주세요.")
    return f"{compact[:6]}-{compact[6]}******"


def validate_registration_birth_date(number: str, birth_date: date) -> None:
    if birth_date.year < 1800 or birth_date > date.today():
        raise ValueError("생년월일은 1800년부터 오늘 사이여야 합니다.")
    if number[:6] != birth_date.strftime("%y%m%d"):
        raise ValueError("등록번호 앞 6자리가 생년월일과 일치하지 않습니다.")
    century = {"0": 1800, "9": 1800, "1": 1900, "2": 1900, "5": 1900, "6": 1900,
               "3": 2000, "4": 2000, "7": 2000, "8": 2000}[number[7]]
    if birth_date.year // 100 * 100 != century:
        raise ValueError("등록번호 뒷자리의 첫 숫자와 출생 연도를 확인해주세요.")


def validate_registration_persona(number: str, birth_date: date, nationality: str, sex: str | None = None) -> None:
    validate_registration_birth_date(number, birth_date)
    digit = number[7]
    domestic = nationality.strip().casefold() in {"대한민국", "한국", "kr", "kor", "south korea", "republic of korea"}
    if (digit in "901234") != domestic:
        raise ValueError("등록번호 뒷자리의 첫 숫자와 내국인·외국인 구분이 일치하지 않습니다.")
    if sex is not None and (sex not in {"male", "female"} or (int(digit) % 2 == 1) != (sex == "male")):
        raise ValueError("등록번호 뒷자리의 첫 숫자와 페르소나 성별이 일치하지 않습니다.")
