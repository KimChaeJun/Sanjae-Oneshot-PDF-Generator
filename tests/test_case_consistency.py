import pytest
from io import BytesIO
from pypdf import PdfReader
from app.demo_guide import demo_accident, demo_followup
from app.pdf_generator import Applicant, build_document_pdf

from app.cases import CASE_TYPES, case_catalog, get_case


@pytest.mark.parametrize("case_type", CASE_TYPES)
def test_every_fixture_preserves_one_coherent_scenario(case_type):
    config = CASE_TYPES[case_type]
    columns = ("diagnoses", "places", "tasks", "events", "injury_parts")
    assert {len(config[key]) for key in columns} == {4}
    expected = {
        (diagnosis, place, task, f"{task}하던 중 {event}", injury)
        for diagnosis, place, task, event, injury in zip(
            *(config[key] for key in columns), strict=True
        )
    }
    cases = case_catalog()[case_type]
    assert len(cases) == 120
    assert len({case.id for case in cases}) == 120
    for case in cases:
        assert (
            case.diagnosis, case.accident_place, case.task,
            case.accident_description, case.injury_part,
        ) in expected
        assert case.injury_part not in {"좌측", "우측", "중증", "급성", "수술"}


def test_reported_hand_trapping_case_has_hand_diagnosis():
    case = get_case("work_accident", "work_accident-060")
    assert "손이 끼었습니다" in case.accident_description
    assert case.diagnosis == "우측 손 압궤상"
    assert case.injury_part == "우측 손"
    assert "발목" not in case.diagnosis


@pytest.mark.parametrize("case_type", CASE_TYPES)
def test_followup_facts_are_shared_by_scenario_and_input_evidence(case_type):
    case = get_case(case_type, seed=3)
    applicant = Applicant(name="SYNTHETIC DEMO", birth_date="1994-03-12",
        registration_number="940312-5123456", address="가상의 시연 주소",
        phone="010-0000-0000", email="demo@example.invalid", nationality="베트남",
        preferred_language="en")
    kind = "death" if case_type == "survivor" else "medical"
    pdf = PdfReader(BytesIO(build_document_pdf("합성 시연 증빙", kind, applicant, case)))
    content = "".join("".join(page.extract_text().split()) for page in pdf.pages)
    for answer in demo_followup(case).values():
        assert answer in demo_accident(case, "en")["raw_description"]
        assert "".join(answer.split()) in content
    assert len(pdf.pages) == 1
    if case_type == "survivor":
        assert "사망" in demo_followup(case)["medical_treatment"]
        assert "치료는 종결되지" not in demo_followup(case)["medical_treatment"]


def test_noise_exposure_is_not_combined_with_musculoskeletal_diagnosis():
    for case in case_catalog()["occupational_disease"]:
        if "소음" in case.accident_description:
            assert case.diagnosis == "소음성 난청 의심"
            assert case.injury_part == "양측 귀"
