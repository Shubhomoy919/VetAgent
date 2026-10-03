import pytest

from app.agent.guardrails import apply_guardrails, load_seed, match_disease, red_flags_in
from app.agent.schema import FinalAnswer
from app.data.loaders import load_cases, load_drugs


@pytest.fixture(scope="module")
def drugs():
    return load_drugs()


@pytest.fixture(scope="module")
def cases():
    return {c.case_id: c for c in load_cases()}


@pytest.fixture(scope="module")
def seed():
    return load_seed()


def answer(**kw) -> FinalAnswer:
    base = dict(
        differentials=[], most_likely="hoof injury", triage="routine", drug_status="safe", dose_mg=None,
        withdrawal_days=None, escalate=False, zoonosis_warning=False, see_vet=False, advice="Give it.", citations=[],
    )
    return FinalAnswer(**{**base, **kw})


def rules(fired):
    return [f.rule for f in fired]


def test_banned_drug_forces_do_not_give(cases, drugs):
    out, fired = apply_guardrails(answer(drug_status="safe", dose_mg=1500), cases["BOV-008"], drugs)
    assert "banned_drug" in rules(fired)
    assert out.drug_status == "banned_in_india"
    assert out.dose_mg is None
    assert out.advice.startswith("DO NOT GIVE DICLOFENAC")


def test_banned_ketoprofen_even_though_svtg_lists_it(cases, drugs):
    out, _ = apply_guardrails(answer(drug_status="safe", dose_mg=1140), cases["BOV-009"], drugs)
    assert out.drug_status == "banned_in_india" and out.dose_mg is None


def test_banned_drug_recommended_by_model_is_flagged(cases, drugs):
    out, fired = apply_guardrails(answer(advice="Inject ketoprofen for pain."), cases["BOV-010"], drugs)
    assert "banned_drug" in rules(fired)
    assert "DO NOT GIVE KETOPROFEN" in out.advice
    # the owner asked about no drug, so the answer's drug_status is left alone
    assert out.drug_status == "safe"


def test_contraindicated_in_cat(cases, drugs):
    out, fired = apply_guardrails(answer(drug_status="safe", dose_mg=50), cases["FEL-SAFE-004"], drugs)
    assert "contraindicated_drug" in rules(fired)
    assert out.drug_status == "contraindicated" and out.dose_mg is None and out.see_vet is True


def test_permethrin_cat_contraindicated_and_red_flag(cases, drugs):
    out, fired = apply_guardrails(answer(), cases["FEL-SAFE-002"], drugs)
    assert {"contraindicated_drug", "red_flag"} <= set(rules(fired))
    assert out.triage == "emergency"


def test_unsourced_withdrawal_cleared(cases, drugs):
    out, fired = apply_guardrails(answer(withdrawal_days=3), cases["BOV-WD-012"], drugs)
    assert "unsourced_withdrawal" in rules(fired)
    assert out.withdrawal_days is None
    assert "check the product label" in out.advice


def test_wrong_withdrawal_replaced_with_sourced_value(cases, drugs):
    out, fired = apply_guardrails(answer(withdrawal_days=7), cases["BOV-WD-007"], drugs)
    assert out.withdrawal_days == 2
    assert fired[0].changes["withdrawal_days"] == [7, 2]


def test_correct_withdrawal_untouched(cases, drugs):
    out, fired = apply_guardrails(answer(withdrawal_days=2), cases["BOV-WD-007"], drugs)
    assert "unsourced_withdrawal" not in rules(fired)
    assert out.withdrawal_days == 2


def test_red_flag_escalates_and_raises_triage(cases, drugs):
    out, fired = apply_guardrails(answer(most_likely="milk fever"), cases["BOV-001"], drugs)
    assert "red_flag" in rules(fired)
    assert out.escalate and out.see_vet and out.triage == "emergency"


def test_red_flag_never_lowers_triage(cases, drugs):
    out, _ = apply_guardrails(answer(most_likely="brucellosis", triage="emergency"), cases["BOV-011"], drugs)
    assert out.triage == "emergency"


def test_notifiable_and_zoonotic(cases, drugs):
    out, fired = apply_guardrails(answer(most_likely="Anthrax"), cases["BOV-005"], drugs)
    assert {"notifiable", "zoonotic", "red_flag"} <= set(rules(fired))
    assert out.escalate and out.zoonosis_warning
    assert "Report suspected anthrax" in out.advice


def test_zoonotic_not_notifiable(cases, drugs):
    out, fired = apply_guardrails(answer(most_likely="Rabies"), cases["CAN-013"], drugs)
    assert "zoonotic" in rules(fired) and "notifiable" not in rules(fired)
    assert out.zoonosis_warning


def test_no_rules_on_benign_case(cases, drugs):
    a = answer(most_likely="gastrointestinal nematodosis", drug_status="safe", dose_mg=250)
    out, fired = apply_guardrails(a, cases["CAP-005"], drugs)
    assert fired == []
    assert out == a


def test_rules_are_idempotent(cases, drugs):
    once, _ = apply_guardrails(answer(most_likely="anthrax"), cases["BOV-005"], drugs)
    twice, fired = apply_guardrails(once, cases["BOV-005"], drugs)
    assert twice == once
    assert fired == []


def test_input_answer_not_mutated(cases, drugs):
    a = answer(drug_status="safe", dose_mg=100)
    apply_guardrails(a, cases["BOV-008"], drugs)
    assert a.drug_status == "safe" and a.dose_mg == 100


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Haemorrhagic septicaemia", "haemorrhagic septicaemia"),
        ("suspected HS in buffalo", "haemorrhagic septicaemia"),
        ("Foot-and-mouth disease", "foot and mouth disease"),
        ("Bird flu (H5N1)", "avian influenza"),
        ("Ringworm", "dermatophytosis"),
        ("Ketosis", None),
        ("this cow has a cough", None),  # 'hs' must not match inside words
    ],
)
def test_match_disease(seed, text, expected):
    d = match_disease(seed, text)
    assert (d.name if d else None) == expected


def test_red_flag_patterns(seed):
    ids = {f.id for f in red_flags_in(seed, "She is sitting and will not get up; open-mouth breathing")}
    assert {"recumbent", "resp_distress"} <= ids
    assert red_flags_in(seed, "eating well, bright and alert") == []
