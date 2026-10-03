import json

import pytest

from app.agent.parser import ParseError, extract_json, parse_action, parse_final_answer

GOOD = {
    "differentials": ["milk fever", "downer cow syndrome"],
    "most_likely": "milk fever",
    "triage": "emergency",
    "drug_status": "n/a",
    "dose_mg": None,
    "withdrawal_days": None,
    "escalate": True,
    "zoonosis_warning": False,
    "see_vet": True,
    "advice": "Call the vet.",
    "citations": [{"source": "SVTG", "page": 36}],
}


def test_plain_json():
    assert extract_json(json.dumps(GOOD))["most_likely"] == "milk fever"


@pytest.mark.parametrize(
    "wrapped",
    [
        "```json\n{body}\n```",
        "```\n{body}\n```",
        "Here is my answer:\n```JSON\n{body}\n```\nHope this helps.",
        "Sure! {body} Let me know.",
    ],
)
def test_fences_and_prose_are_stripped(wrapped):
    text = wrapped.replace("{body}", json.dumps(GOOD))
    assert parse_final_answer(text).most_likely == "milk fever"


def test_braces_inside_strings():
    obj = {**GOOD, "advice": "Use {care} and \"quotes\" } here"}
    text = "prefix " + json.dumps(obj) + " suffix {not json}"
    assert parse_final_answer(text).advice == obj["advice"]


def test_wrapped_final_answer_key():
    assert parse_final_answer({"final_answer": GOOD}).triage == "emergency"


def test_case_and_null_normalisation():
    obj = {**GOOD, "triage": "Emergency", "drug_status": None, "dose_mg": "null", "withdrawal_days": ""}
    a = parse_final_answer(obj)
    assert a.triage == "emergency"
    assert a.drug_status == "n/a"
    assert a.dose_mg is None and a.withdrawal_days is None


def test_numeric_strings_accepted():
    a = parse_final_answer({**GOOD, "dose_mg": "1025", "withdrawal_days": "2"})
    assert a.dose_mg == 1025 and a.withdrawal_days == 2


@pytest.mark.parametrize("text", ["", "   ", "no json at all", "[1, 2, 3]", "{broken: json"])
def test_unparseable_raises_with_message(text):
    with pytest.raises(ParseError) as e:
        parse_final_answer(text)
    assert str(e.value)  # a real message, never empty


def test_schema_error_names_the_field():
    bad = {**GOOD, "triage": "whenever"}
    with pytest.raises(ParseError, match="triage"):
        parse_final_answer(bad)


def test_missing_required_field():
    bad = {k: v for k, v in GOOD.items() if k != "escalate"}
    with pytest.raises(ParseError, match="escalate"):
        parse_final_answer(bad)


def test_negative_dose_rejected():
    with pytest.raises(ParseError, match="dose_mg"):
        parse_final_answer({**GOOD, "dose_mg": -5})


def test_parse_action_tool_call():
    step = parse_action('```json\n{"thought": "t", "action": " search_guidelines ", "action_input": {"query": "x"}}\n```')
    assert step["action"] == "search_guidelines"
    assert step["action_input"] == {"query": "x"}


def test_parse_action_null_input_becomes_empty():
    assert parse_action('{"action": "get_patient_record", "action_input": null}')["action_input"] == {}


def test_parse_action_final():
    assert "final_answer" in parse_action(json.dumps({"thought": "done", "final_answer": GOOD}))


@pytest.mark.parametrize(
    "text",
    ['{"thought": "hmm"}', '{"action": ""}', '{"action": "x", "action_input": "query"}', '{"final_answer": "text"}'],
)
def test_parse_action_errors(text):
    with pytest.raises(ParseError):
        parse_action(text)
