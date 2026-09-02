from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from functools import lru_cache


@dataclass(frozen=True)
class AccidentCase:
    id: str
    case_type: str
    type_label: str
    workplace: str
    workplace_address: str
    occupation: str
    accident_date: str
    accident_time: str
    accident_place: str
    task: str
    accident_description: str
    diagnosis: str
    injury_part: str
    hospital: str
    witness: str
    transport: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


CASE_TYPES: dict[str, dict[str, object]] = {
    "work_accident": {
        "label": "업무상 사고",
        "summary": "작업 중 넘어짐, 끼임, 추락, 충돌 등",
        "diagnoses": ["우측 손목 염좌", "좌측 발목 골절", "요추 염좌", "우측 어깨 타박상"],
        "places": ["2층 조립라인", "물류창고 적재구역", "건설현장 3층", "식품가공 포장실"],
        "tasks": ["완성품 상자를 운반", "설비 주변을 정리", "사다리에서 배선을 점검", "원재료를 투입"],
        "events": ["바닥의 포장 비닐에 미끄러져 넘어졌습니다", "움직이던 대차와 작업대 사이에 손이 끼었습니다", "발판이 흔들려 아래로 떨어졌습니다", "쌓아 둔 자재가 기울어 몸에 부딪혔습니다"],
    },
    "commute": {
        "label": "출퇴근 재해",
        "summary": "통상적인 출퇴근 경로에서 발생한 교통·보행 사고",
        "diagnoses": ["경추 염좌", "좌측 무릎 타박상", "우측 손목 골절", "요추부 염좌"],
        "places": ["회사 앞 횡단보도", "지하철역 2번 출구", "통근버스 승강장", "자택 인근 교차로"],
        "tasks": ["평소 경로로 출근", "퇴근 후 지하철역으로 이동", "통근버스를 타기 위해 이동", "자전거로 퇴근"],
        "events": ["신호에 따라 건너던 중 우회전 차량과 충돌했습니다", "계단에서 미끄러져 넘어졌습니다", "승강장 턱에 발이 걸려 넘어졌습니다", "뒤따르던 차량과 접촉해 도로에 넘어졌습니다"],
    },
    "third_party": {
        "label": "제3자 행위 재해",
        "summary": "업무 중 타인 또는 외부 차량·장비의 행위로 발생한 사고",
        "diagnoses": ["안면부 열상", "우측 무릎 골절", "흉부 타박상", "좌측 팔꿈치 염좌"],
        "places": ["납품처 하역장", "공장 출입구", "도로 보수 현장", "물류센터 도크"],
        "tasks": ["납품 물품을 검수", "사업장 출입 차량을 안내", "교통 통제 업무", "지게차 하역을 보조"],
        "events": ["협력업체 직원이 밀던 카트와 충돌했습니다", "외부 차량이 후진하면서 작업 구역을 침범했습니다", "통제 지시를 따르지 않은 차량에 부딪혔습니다", "다른 업체 지게차가 적재물을 떨어뜨렸습니다"],
    },
    "occupational_disease": {
        "label": "업무상 질병",
        "summary": "반복 작업, 소음, 분진, 유해 요인으로 발생한 질병",
        "diagnoses": ["회전근개 건병증", "소음성 난청 의심", "수근관증후군", "요추 추간판탈출증"],
        "places": ["자동차 부품 조립라인", "금속 절단 작업장", "전자부품 검사실", "물류 상하차 구역"],
        "tasks": ["하루 7시간 이상 어깨 높이 조립", "금속 절단기 주변에서 근무", "소형 부품을 반복 조립", "중량 상자를 반복 운반"],
        "events": ["수개월 동안 같은 동작을 반복한 뒤 통증이 심해졌습니다", "장기간 큰 소음에 노출된 뒤 청력이 저하되었습니다", "손목을 반복해서 사용한 뒤 저림과 통증이 지속되었습니다", "무거운 물건을 반복 운반한 뒤 허리 통증이 악화되었습니다"],
    },
    "survivor": {
        "label": "유족급여·장례비",
        "summary": "업무상 사고로 근로자가 사망하여 유족이 신청하는 경우",
        "diagnoses": ["다발성 외상", "중증 두부 손상", "흉부 압박 손상", "급성 유해가스 중독"],
        "places": ["건설현장 옥상", "물류창고 자동화 구역", "제조공장 프레스실", "밀폐 저장탱크 내부"],
        "tasks": ["안전 난간을 점검", "자동설비 장애를 확인", "프레스 금형을 교체", "저장탱크 내부를 점검"],
        "events": ["점검 중 추락 사고가 발생해 병원으로 이송되었습니다", "설비가 갑자기 작동해 중대한 사고가 발생했습니다", "금형 사이에 끼이는 사고가 발생했습니다", "내부에서 의식을 잃어 구조 후 병원으로 이송되었습니다"],
    },
    "retreatment": {
        "label": "재요양",
        "summary": "치료가 끝난 기존 산재 상병이 재발하거나 악화된 경우",
        "diagnoses": ["우측 회전근개 재파열", "요추 통증 재발", "좌측 발목 불안정증", "수술 부위 신경병성 통증"],
        "places": ["자택", "통원 재활센터", "근무 복귀 후 작업장", "산재 지정 의료기관"],
        "tasks": ["치료 종결 후 일상생활", "재활 운동", "업무 복귀 후 경량 작업", "정기 추적 진료"],
        "events": ["치료 종결 뒤 같은 부위의 통증과 운동 제한이 다시 심해졌습니다", "재활 중 기존 상병 부위의 통증이 급격히 악화되었습니다", "업무에 복귀한 뒤 기존 상병 증상이 재발했습니다", "추적 검사에서 추가 치료가 필요하다는 소견을 받았습니다"],
    },
}


WORKPLACES = [
    ("한빛산업", "서울특별시 구로구 디지털로 210"),
    ("새봄물류", "경기도 이천시 부발읍 물류로 18"),
    ("대한건설", "인천광역시 서구 산업로 77"),
    ("푸른테크", "충청남도 천안시 서북구 공단로 42"),
    ("미래식품", "경상남도 김해시 주촌면 골든루트로 91"),
]
OCCUPATIONS = ["생산직 근로자", "물류 담당자", "현장 보조원", "설비 점검원", "품질 검사원"]
HOSPITALS = ["산재원샷병원", "서울안심정형외과", "우리산재의료원", "한마음종합병원"]
WITNESSES = ["김동료", "이안전", "박반장", "최현장", "목격자 없음"]
TIMES = ["07:45", "09:20", "11:35", "14:10", "17:40", "21:15"]


@lru_cache(maxsize=1)
def case_catalog() -> dict[str, tuple[AccidentCase, ...]]:
    catalog: dict[str, tuple[AccidentCase, ...]] = {}
    base_date = date(2026, 1, 3)
    for type_index, (case_type, config) in enumerate(CASE_TYPES.items(), start=1):
        items: list[AccidentCase] = []
        for index in range(1, 121):
            workplace, address = WORKPLACES[(index + type_index) % len(WORKPLACES)]
            diagnosis = config["diagnoses"][(index * 3 + type_index) % len(config["diagnoses"])]
            place = config["places"][(index + type_index * 2) % len(config["places"])]
            task = config["tasks"][(index * 2 + type_index) % len(config["tasks"])]
            event = config["events"][(index * 5 + type_index) % len(config["events"])]
            accident_date = base_date + timedelta(days=(index * 2 + type_index * 11) % 220)
            items.append(
                AccidentCase(
                    id=f"{case_type}-{index:03d}",
                    case_type=case_type,
                    type_label=str(config["label"]),
                    workplace=workplace,
                    workplace_address=address,
                    occupation=OCCUPATIONS[(index + type_index) % len(OCCUPATIONS)],
                    accident_date=accident_date.isoformat(),
                    accident_time=TIMES[(index + type_index) % len(TIMES)],
                    accident_place=str(place),
                    task=str(task),
                    accident_description=f"{task}하던 중 {event}",
                    diagnosis=str(diagnosis),
                    injury_part=str(diagnosis).split()[0],
                    hospital=HOSPITALS[(index * 2 + type_index) % len(HOSPITALS)],
                    witness=WITNESSES[(index + type_index * 3) % len(WITNESSES)],
                    transport="119 구급대 이송" if index % 3 == 0 else "동료 차량으로 병원 이동",
                )
            )
        catalog[case_type] = tuple(items)
    return catalog


def get_case(case_type: str, case_id: str | None = None, seed: int | None = None) -> AccidentCase:
    cases = case_catalog().get(case_type)
    if not cases:
        raise KeyError(case_type)
    if case_id:
        for item in cases:
            if item.id == case_id:
                return item
        raise LookupError(case_id)
    return cases[(seed or 0) % len(cases)]


def public_case_types() -> list[dict[str, object]]:
    catalog = case_catalog()
    return [
        {
            "code": code,
            "label": config["label"],
            "summary": config["summary"],
            "case_count": len(catalog[code]),
        }
        for code, config in CASE_TYPES.items()
    ]

