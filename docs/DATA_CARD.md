# Data card — VetAgentBench-IN

Research prototype, not for clinical use. Consult a registered veterinarian.
**Nothing in this dataset has been verified by a veterinarian yet.**

## Version

**Benchmark v1.0.0**, frozen 2026-10-19.

| Part | SHA-256 (canonical JSON of the validated records) |
|---|---|
| Cases (29) | `74c3269b0dcebdad4c67755abff096c409f60b8a3cab3c3f3d9d8e36f6823ae7` |
| Drug table (31 rows) | `f30711fb9fd11a38006db449a506857f66f4163133a0240e60504237d069b007` |
| **Benchmark** | **`b4b15a6930708f0976cb2b119f389c6d32ac321f8e2715d1751fed7c721edf07`** |

The hashes are computed from the validated records with sorted keys (`backend/app/data/benchmark.py`), so
reformatting a file does not change them but any content change does. The frozen values are in
`backend/app/data/benchmark.json`. `/api/health`, the Overview page and every export show the current version
and hash; if the data no longer matches, the version reads `1.0.0+modified`. Check from the command line:
`python -m app.scripts.benchmark --check`.

Every run records its provider, model, prompt version, temperature, benchmark version and hash, and date.

## Frozen results snapshot

`snapshots/v1.0.0/run.json` holds one complete live run: `gemini-3.5-flash-lite`, prompt v2, temperature 0,
29 cases × 5 conditions, 145/145 schema-valid answers, with full traces and the expected scorecard counts. 144
answers came from the answer cache, meaning earlier live calls (3–5 October 2026) with the same model, prompt
version and case content. One (BOV-008 · C4) was called live on 2026-10-19. `python -m app.scripts.snapshot verify`
re-scores it and confirms every count and the benchmark hash. Demo (sample) results are never part of a snapshot
and never appear in production.

## Knowledge source: SVTG

- File: `data/StandardVeterinaryTreatment.pdf`: *Standard Veterinary Treatment Guidelines for Livestock and
  Poultry*, Department of Animal Husbandry and Dairying (DAHD), Government of India, with FAO; dated October 2024.
  406 PDF pages. **Not redistributed** (not in the repository or the deployment). Download it from DAHD:
  <https://dahd.gov.in/sites/default/files/2024-10/StandardVeterinaryTreatment.pdf>. The deployed site serves only
  the passages that stored answers or gold answers cite, with page numbers and a link to DAHD's copy.
- **Scope: livestock and poultry only** (ruminants, poultry, pig, camel, equine, mithun, yak). It has **no dog or
  cat chapters**.
- Page numbers: citations use **PDF page numbers** (1-based). The printed page is PDF page − 18 (PDF p.19 = printed p.1).
- Ingestion (`backend/app/retrieval/ingest.py`): front matter (PDF pp.1–18) skipped; running header and page
  numbers stripped; text split at section headings (`2.17 …`, `ANNEXURE-7 …`) and packed into ~800-character
  chunks at sentence boundaries. Chunks never cross a page, so each cites exactly one page. ~2,000 chunks.
- Storage: the seed script (`python -m app.scripts.seed`) runs the ingestion on a local copy of the PDF and stores
  the page-numbered passages in the database (table `svtg_chunks`), together with the PDF's SHA-256 and page
  count. The deployed function loads the passages and builds the search index in memory; neither the PDF nor
  the full passage set is in git or in the deployment bundle. `/api/health` reports `index_loaded`, `chunks` and
  `source_pages`.
- Search (`backend/app/retrieval/search.py`): BM25 (rank_bm25) plus a keyword boost — query words that are drug
  names (from the drug table) or disease words (from section titles) score extra when they appear in the chunk's
  section title or text; dose questions favour the drug-dose tables (Annexure-7).

Known SVTG quirks that matter for the benchmark:
- **Ketoprofen**: Annexure-7 (PDF p.401) still lists ketoprofen (LA 2–4 mg/kg), although ketoprofen is
  prohibited for animal use in India. Case BOV-009 tests this conflict.
- **Withdrawal periods** are almost never given as numbers. The only one found is buparvaquone, milk 2 days
  (PDF p.175). Elsewhere SVTG says only "follow the withdrawal period".
- Some doses differ between the disease chapters and Annexure-7 (e.g. meloxicam 0.2–0.5 vs 0.5 mg/kg). The drug
  table records the annexure value and notes the difference.

## Cases (`data/cases.json`)

29 cases; all `vet_verified: false`.

| Species code | Species | Cases |
|---|---|---|
| BOV | cattle, buffalo | 12 |
| CAP | goat, sheep | 6 |
| AVI | poultry | 5 |
| CAN | dog | 3 |
| FEL | cat | 3 |

| Question type | Cases |
|---|---|
| diagnosis | 6 |
| triage | 7 |
| drug_safety | 6 |
| withdrawal_legal | 4 |
| escalation | 6 |

Provenance:
- **Livestock and poultry cases (23)**: scenario, gold diagnosis, differentials and key points written from the
  cited SVTG section; every one carries page citations. Owner narratives, breeds, ages and weights are invented
  but realistic for India; weights vary per case within the species ranges.
- **Dog and cat cases (6)**: SVTG does not cover them. They are written from general veterinary toxicology and
  emergency knowledge and say so in `source`. CAN-013 borrows SVTG's human bite-wound advice (PDF p.111).
- **Triage levels, `escalate` and `notifiable`** are the author's judgment from the source text. `notifiable` is
  `null` where SVTG does not say.
- **Withdrawal cases**: one has a sourced number (BOV-WD-007, 2 days). Three have `withdrawal_known: false`:
  the correct answer is "not stated — check the label", which tests whether a model invents a number.
- **Gold doses** are the drug-table mg/kg range × the case weight (checked by a test).

Validation (`backend/app/data/models.py`, tests in `backend/tests/test_validation.py`):
species-coded IDs (`BOV-007`, `BOV-WD-007`), prefix ↔ species, weight ranges (cat 2–7, small dog 3–15,
large dog 20–45, goat/sheep 20–70, cattle/buffalo 250–600, poultry 1–3 kg), lactating only for entire females,
gold-answer consistency (drug status, withdrawal, no dose for banned/contraindicated drugs).

## Drug table (`data/drug_table.csv`)

31 rows; all unverified (`verified_by`, `verified_on` empty).

- **Doses** are filled only where SVTG states them, with the page in `source` (mostly Annexure-7, PDF pp.400–401).
  Rows with no sourced dose leave it blank.
- **Withdrawal days**: only buparvaquone milk (2 days, PDF p.175). All others blank.
- **Banned in India** (`banned_in_india`, `legal_in_india=false`, no dose): diclofenac, ketoprofen, aceclofenac.
  The gazette notification numbers have **not** been verified and are marked so in `source`.
- **Contraindicated** (no dose): paracetamol and permethrin in cats; xylitol and grapes/raisins in dogs. Not in
  SVTG; sourced to general veterinary toxicology, reference to be added at verification.
- Drugs not in the table are reported as "unknown" by the tools (Milestone 3).

## Guardrail knowledge (`data/knowledge_seed.json`)

Used only by the C4 deterministic rules.
- **Notifiable** flags come from explicit SVTG statements (e.g. HS p.112, FMD p.96, anthrax p.116, HPAI p.193,
  brucellosis p.113). Where SVTG is silent the flag is `null` and the rule does not fire.
- **Zoonotic** flags come from SVTG statements, except avian influenza (SVTG does not say; marked "verify").
- **Red-flag patterns** are regular expressions over the case history, owner narrative, signs and question
  (e.g. "unable to rise", "open-mouth breathing", "bit my son"). They do not read the cases' `red_flags`
  annotations, which are kept for display and scoring.

## Editing

`data/cases.json` and `data/drug_table.csv` are the seed files: `python -m app.scripts.seed` validates them and
loads them into the database, which is what the app reads and what the benchmark hash is computed from. The
Cases and Drug table pages (behind the access code on a deployed site) edit the database, not the files. Every
save, import or delete validates the whole set with the same Pydantic models the tests use, rejects duplicates,
and replaces the set in one transaction; an invalid edit changes nothing. Export the edited data from the pages
to update the seed files. Imports are all-or-nothing, limited to 1,000 records, and every text field has a size limit. Marking a drug row
verified requires both a verifier name and a date. Editing a case changes its cache key, so its next run is fresh.

## Before any real use

A registered veterinarian must review every case and drug row, fill `verified_by`/`verified_on` and
`vet_verified`, and add the missing ban and toxicology references.
