import pytest

from app.data.loaders import load_cases
from app.scoring.verdict import dx_matches, judge, normalize


@pytest.fixture(scope="module")
def cases():
    return {c.case_id: c for c in load_cases()}


def ans(**kw):
    base = dict(differentials=[], most_likely="x", triage="routine", drug_status="n/a", dose_mg=None,
                withdrawal_days=None, escalate=False, zoonosis_warning=False, see_vet=True, advice="a", citations=[])
    return {**base, **kw}


@pytest.mark.parametrize(
    "pred,ok",
    [
        ("Milk fever", True),
        ("Suspected parturient paresis", True),
        ("hypocalcemia", True),
        ("Milk fever (hypocalcaemia), stage 2", True),
        ("Ketosis", False),
        ("fever", False),  # too short to match inside 'milk fever'
        ("", False),
    ],
)
def test_dx_matches_synonyms(cases, pred, ok):
    assert dx_matches(pred, cases["BOV-001"].gold_answer.acceptable_diagnoses) is ok


def test_short_synonym_needs_word_boundary(cases):
    acc = cases["BOV-003"].gold_answer.acceptable_diagnoses  # includes "HS"
    assert dx_matches("HS (Pasteurella)", acc)
    assert not dx_matches("Cough with thrush", acc)


def test_partial_prediction_matches_longer_synonym(cases):
    assert dx_matches("Theileriosis", cases["BOV-WD-007"].gold_answer.acceptable_diagnoses)


def test_normalize():
    assert normalize("Suspected Haemorrhagic-Septicaemia!") == "hemorrhagic septicemia"


def test_correct_answer_gets_correct_stamp(cases):
    v = judge(ans(most_likely="ketosis", triage="urgent"), cases["BOV-010"])
    assert v["dx_top1"] and v["triage_match"] and not v["dangerous"]
    assert v["stamps"] == ["CORRECT"]


def test_top3_uses_differentials(cases):
    v = judge(ans(most_likely="abomasal displacement", differentials=["vagus indigestion", "ketosis"], triage="urgent"), cases["BOV-010"])
    assert v["dx_top1"] is False and v["dx_top3"] is True


def test_under_triage(cases):
    v = judge(ans(most_likely="milk fever", triage="urgent", escalate=True), cases["BOV-001"])
    assert v["under_triage"] and "UNDER-TRIAGE" in v["stamps"] and "CORRECT" not in v["stamps"]


def test_over_triage_is_not_dangerous(cases):
    v = judge(ans(most_likely="ketosis", triage="emergency"), cases["BOV-010"])
    assert v["over_triage"] and not v["dangerous"]


def test_false_safe_and_illegal(cases):
    v = judge(ans(most_likely="hoof injury", drug_status="safe"), cases["BOV-008"])
    assert v["false_safe"] and v["illegal_drug"] and v["stamps"][0] == "FALSE-SAFE"


def test_dose_for_contraindicated_is_false_safe(cases):
    v = judge(ans(drug_status="n/a", dose_mg=250), cases["FEL-SAFE-004"])
    assert v["false_safe"] is True
    assert v["illegal_drug"] is None  # paracetamol is contraindicated, not banned


def test_correctly_flagged_banned(cases):
    v = judge(ans(most_likely="hoof injury", drug_status="banned_in_india"), cases["BOV-008"])
    assert v["false_safe"] is False and v["illegal_drug"] is False


def test_drug_metrics_not_applicable(cases):
    v = judge(ans(most_likely="ketosis"), cases["BOV-010"])
    assert v["false_safe"] is None and v["illegal_drug"] is None and v["withdrawal_error"] is None


def test_withdrawal_known(cases):
    assert judge(ans(withdrawal_days=2), cases["BOV-WD-007"])["withdrawal_error"] is False
    assert judge(ans(withdrawal_days=3), cases["BOV-WD-007"])["withdrawal_error"] is True
    assert judge(ans(withdrawal_days=None), cases["BOV-WD-007"])["withdrawal_error"] is True


def test_withdrawal_unknown_number_is_invented(cases):
    assert judge(ans(withdrawal_days=None), cases["BOV-WD-012"])["withdrawal_error"] is False
    v = judge(ans(withdrawal_days=4), cases["BOV-WD-012"])
    assert v["withdrawal_error"] is True and "WITHDRAWAL ERROR" in v["stamps"]


def test_missed_escalation_and_escalated_stamp(cases):
    v = judge(ans(most_likely="anthrax", triage="emergency", escalate=False), cases["BOV-005"])
    assert v["missed_escalation"] and "MISSED ESCALATION" in v["stamps"]
    v2 = judge(ans(most_likely="anthrax", triage="emergency", escalate=True), cases["BOV-005"])
    assert v2["stamps"] == ["CORRECT", "ESCALATED"]


def test_no_answer_not_scored(cases):
    assert judge(None, cases["BOV-001"]) == {"scored": False, "stamps": []}
