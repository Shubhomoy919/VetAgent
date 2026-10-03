import pytest

from app.data.loaders import load_cases, load_drugs
from app.retrieval.ingest import Chunk
from app.retrieval.search import SearchIndex
from app.tools.drugs import canonical, detect_drugs, lookup_drug_safety, lookup_withdrawal
from app.tools.registry import Toolbox, case_view


@pytest.fixture(scope="module")
def drugs():
    return load_drugs()


@pytest.fixture(scope="module")
def cases():
    return {c.case_id: c for c in load_cases()}


# ---------- lookup_drug_safety ----------

def test_dose_math_done_in_python(drugs):
    r = lookup_drug_safety(drugs, "Buparvaquone", "cattle", 410)
    assert r["status"] == "safe"
    assert r["dose_mg_per_kg"] == {"min": 2.5, "max": 2.5}
    assert r["dose_mg_total"] == {"min": 1025.0, "max": 1025.0, "weight_kg": 410}


def test_dose_range_for_goat(drugs):
    r = lookup_drug_safety(drugs, "albendazole", "goat", 30)
    assert r["dose_mg_total"]["min"] == pytest.approx(225)
    assert r["dose_mg_total"]["max"] == pytest.approx(300)


def test_no_weight_no_total(drugs):
    assert lookup_drug_safety(drugs, "albendazole", "goat")["dose_mg_total"] is None


@pytest.mark.parametrize("species", ["cattle", "buffalo", "goat", "dog", "poultry"])
def test_banned_applies_to_every_species(drugs, species):
    r = lookup_drug_safety(drugs, "diclofenac", species, 400)
    assert r["status"] == "banned_in_india"
    assert r["legal_in_india"] is False
    assert "dose_mg_total" not in r


def test_ketoprofen_banned(drugs):
    assert lookup_drug_safety(drugs, "ketoprofen", "cattle", 380)["status"] == "banned_in_india"


@pytest.mark.parametrize(
    "drug,species", [("paracetamol", "cat"), ("Crocin", "cat"), ("permethrin", "cat"), ("xylitol", "dog"), ("raisins", "dog")]
)
def test_contraindicated_no_dose(drugs, drug, species):
    r = lookup_drug_safety(drugs, drug, species, 4)
    assert r["status"] == "contraindicated"
    assert r["dose_mg_total"] is None


def test_unknown_drug(drugs):
    r = lookup_drug_safety(drugs, "unobtainium", "cattle", 400)
    assert r["status"] == "unknown"
    assert "not in the drug table" in r["message"]


def test_unknown_for_species_without_row(drugs):
    # paracetamol is only listed for cats
    assert lookup_drug_safety(drugs, "paracetamol", "cattle", 400)["status"] == "unknown"


def test_related_species_fallback_is_flagged(drugs):
    r = lookup_drug_safety(drugs, "meloxicam", "buffalo", 500)
    assert r["status"] == "safe"
    assert r["matched_species"] == "cattle"
    assert r["dose_mg_total"]["min"] == pytest.approx(250)


def test_safe_drug_without_sourced_dose(drugs):
    r = lookup_drug_safety(drugs, "enrofloxacin", "poultry", 2)
    assert r["status"] == "safe"
    assert r["dose_mg_total"] is None
    assert "No sourced dose" in r["dose_message"]


# ---------- lookup_withdrawal ----------

def test_withdrawal_known(drugs):
    r = lookup_withdrawal(drugs, "buparvaquone", "cattle")
    assert r["known"] is True
    assert r["milk_withdrawal_days"] == 2
    assert r["meat_withdrawal_days"] is None


def test_withdrawal_not_stated(drugs):
    r = lookup_withdrawal(drugs, "oxytetracycline", "buffalo")
    assert r["known"] is False
    assert "do not guess" in r["message"]


def test_withdrawal_unknown_drug(drugs):
    r = lookup_withdrawal(drugs, "unobtainium", "goat")
    assert r["status"] == "unknown" and r["known"] is False


# ---------- detect_drugs / canonical ----------

def test_detect_drugs_in_order(drugs):
    text = "The shop gave diclofenac; later we tried meloxicam and Crocin."
    assert detect_drugs(drugs, text) == ["diclofenac", "meloxicam", "paracetamol"]


def test_detect_requires_word_boundary(drugs):
    assert detect_drugs(drugs, "melodious dolorous") == []


def test_canonical_aliases():
    assert canonical("  Kishmish ") == "grapes and raisins"
    assert canonical("Acetaminophen") == "paracetamol"


# ---------- Toolbox ----------

def _box(case, allowed, drugs):
    # BM25 needs more than one document for positive IDF.
    chunks = [
        Chunk("p175-c1", 175, 157, "4.4 Bovine Tropical Theileriosis", "Buparvaquone milk withdrawal 2 days."),
        Chunk("p36-c1", 36, 18, "1.2.1 Milk Fever", "Calcium borogluconate for recumbent cows."),
        Chunk("p116-c1", 116, 98, "2.21 Anthrax", "Do not open the carcass."),
    ]
    return Toolbox(case=case, index=SearchIndex(chunks), drugs=drugs, allowed=allowed)


def test_patient_record_hides_gold(cases, drugs):
    box = _box(cases["BOV-WD-007"], ("get_patient_record",), drugs)
    rec = box.call("get_patient_record", {})
    assert rec["signalment"]["weight_kg"] == 410
    for hidden in ("gold_answer", "red_flags", "source", "question_type"):
        assert hidden not in rec


def test_case_view_hides_gold(cases):
    view = case_view(cases["BOV-009"])
    assert "gold_answer" not in view and "red_flags" not in view and "question_type" not in view


def test_disallowed_tool(cases, drugs):
    box = _box(cases["BOV-WD-007"], ("search_guidelines",), drugs)
    assert "Unknown or unavailable" in box.call("lookup_drug_safety", {"drug": "x"})["error"]


def test_tool_argument_errors(cases, drugs):
    box = _box(cases["BOV-WD-007"], ("search_guidelines", "lookup_drug_safety", "ask_owner"), drugs)
    assert "error" in box.call("search_guidelines", {"query": " "})
    assert "error" in box.call("lookup_drug_safety", {})
    assert "error" in box.call("lookup_drug_safety", {"drug": "albendazole", "weight_kg": "heavy"})
    assert "not available" in box.call("ask_owner", {"question": "hi"})["error"]


def test_search_records_passages(cases, drugs):
    box = _box(cases["BOV-WD-007"], ("search_guidelines",), drugs)
    out = box.call("search_guidelines", {"query": "buparvaquone withdrawal"})
    assert out["passages"][0]["page"] == 175
    assert "p175-c1" in box.passages_seen


def test_lookup_defaults_species_from_case(cases, drugs):
    box = _box(cases["FEL-SAFE-004"], ("lookup_drug_safety",), drugs)
    assert box.call("lookup_drug_safety", {"drug": "paracetamol"})["status"] == "contraindicated"
