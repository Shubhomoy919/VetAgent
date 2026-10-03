import json
from collections import defaultdict
from pathlib import Path

import pytest

from app.data.loaders import DRUG_COLUMNS, DataError, load_cases, load_drugs
from app.data.models import QUESTION_TYPES

# ---------- the real data files ----------


@pytest.fixture(scope="module")
def cases():
    return load_cases()


@pytest.fixture(scope="module")
def drugs():
    return load_drugs()


def test_at_least_25_cases(cases):
    assert len(cases) >= 25


def test_required_case_ids_present(cases):
    ids = {c.case_id for c in cases}
    assert {"CAN-013", "FEL-SAFE-004", "BOV-WD-007"} <= ids


def test_bov_wd_007_is_cattle(cases):
    case = next(c for c in cases if c.case_id == "BOV-WD-007")
    assert case.species == "cattle"
    assert case.question_type == "withdrawal_legal"


def test_every_species_code_and_question_type_present(cases):
    assert {c.case_id.split("-")[0] for c in cases} == {"CAN", "FEL", "BOV", "CAP", "AVI"}
    assert {c.question_type for c in cases} == set(QUESTION_TYPES)


def test_livestock_heavy_mix(cases):
    livestock = [c for c in cases if c.species in ("cattle", "buffalo", "goat", "sheep", "poultry")]
    assert len(livestock) / len(cases) >= 0.7


def test_all_cases_start_unverified(cases):
    assert all(c.vet_verified is False for c in cases)


def test_weights_vary_within_species(cases):
    by_species: dict[str, set[float]] = defaultdict(set)
    for c in cases:
        by_species[c.species].add(c.signalment.weight_kg)
    for species, weights in by_species.items():
        n = sum(1 for c in cases if c.species == species)
        if n > 1:
            assert len(weights) == n, f"{species} cases share identical weights: {sorted(weights)}"


def test_svtg_cases_cite_pages(cases):
    for c in cases:
        if c.source.startswith("SVTG"):
            assert c.gold_answer.citations, f"{c.case_id} cites SVTG but has no page citations"
            assert all(cit.page for cit in c.gold_answer.citations)


def test_withdrawal_cases_never_invent_numbers(cases, drugs):
    """A gold withdrawal number must match a sourced drug-table value."""
    table = {(d.species, d.drug.lower()): d for d in drugs}
    for c in cases:
        g = c.gold_answer
        if g.withdrawal_known:
            row = table.get((c.species, (g.drug or "").lower()))
            assert row is not None, f"{c.case_id}: withdrawal drug not in table"
            assert g.withdrawal_days in (row.milk_withdrawal_days, row.meat_withdrawal_days)


def test_gold_doses_match_table_times_weight(cases, drugs):
    table = {(d.species, d.drug.lower()): d for d in drugs}
    for c in cases:
        g = c.gold_answer
        if g.dose_mg is None:
            continue
        row = table[(c.species, (g.drug or "").lower())]
        assert row.dose_min_mg_per_kg is not None and row.dose_max_mg_per_kg is not None
        w = c.signalment.weight_kg
        assert g.dose_mg.min == pytest.approx(row.dose_min_mg_per_kg * w)
        assert g.dose_mg.max == pytest.approx(row.dose_max_mg_per_kg * w)


def test_drug_table_size(drugs):
    assert 25 <= len(drugs) <= 40


@pytest.mark.parametrize(
    "species,drug,status",
    [
        ("cat", "paracetamol", "contraindicated"),
        ("cat", "permethrin", "contraindicated"),
        ("dog", "xylitol", "contraindicated"),
        ("dog", "grapes and raisins", "contraindicated"),
    ],
)
def test_required_contraindications(drugs, species, drug, status):
    row = next((d for d in drugs if d.species == species and d.drug == drug), None)
    assert row is not None, f"missing {species}/{drug}"
    assert row.status == status


@pytest.mark.parametrize("drug", ["diclofenac", "ketoprofen", "aceclofenac"])
def test_required_bans(drugs, drug):
    rows = [d for d in drugs if d.drug == drug]
    assert rows, f"{drug} missing"
    for row in rows:
        assert row.status == "banned_in_india"
        assert row.legal_in_india is False


def test_all_drug_rows_start_unverified(drugs):
    assert all(not d.verified for d in drugs)


def test_sourced_numbers_only(drugs):
    """Any row with a dose or withdrawal number must cite SVTG with a page."""
    for d in drugs:
        has_number = any(
            v is not None
            for v in (d.dose_min_mg_per_kg, d.milk_withdrawal_days, d.meat_withdrawal_days)
        )
        if has_number:
            assert "SVTG" in d.source and "p." in d.source, f"{d.species}/{d.drug} has numbers without a page"


# ---------- error reporting ----------


def test_missing_cases_file(tmp_path: Path):
    with pytest.raises(DataError, match="not found"):
        load_cases(tmp_path / "cases.json")


def test_invalid_json(tmp_path: Path):
    p = tmp_path / "cases.json"
    p.write_text("[{", encoding="utf-8")
    with pytest.raises(DataError, match="not valid JSON"):
        load_cases(p)


def test_error_names_case_and_field(tmp_path: Path, cases):
    bad = json.loads(cases[0].model_dump_json())
    bad["signalment"]["weight_kg"] = 9999
    p = tmp_path / "cases.json"
    p.write_text(json.dumps([bad]), encoding="utf-8")
    with pytest.raises(DataError, match=rf"case {cases[0].case_id}: .*outside the"):
        load_cases(p)


def test_duplicate_case_ids(tmp_path: Path, cases):
    one = json.loads(cases[0].model_dump_json())
    p = tmp_path / "cases.json"
    p.write_text(json.dumps([one, one]), encoding="utf-8")
    with pytest.raises(DataError, match="duplicate case_id"):
        load_cases(p)


def test_drug_csv_missing_column(tmp_path: Path):
    p = tmp_path / "drug_table.csv"
    p.write_text("species,drug\ncat,paracetamol\n", encoding="utf-8")
    with pytest.raises(DataError, match="missing columns"):
        load_drugs(p)


def test_drug_csv_error_names_line(tmp_path: Path):
    p = tmp_path / "drug_table.csv"
    row = ["cattle", "x", "safe", "5", "1", "", "", "true", "s", "", "", ""]
    p.write_text(",".join(DRUG_COLUMNS) + "\n" + ",".join(row) + "\n", encoding="utf-8")
    with pytest.raises(DataError, match="line 2"):
        load_drugs(p)
