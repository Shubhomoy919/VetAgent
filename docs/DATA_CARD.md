# Data card — VetAgentBench-IN

Research prototype — not for clinical use. **Nothing in this dataset has been verified by a veterinarian yet.**

## Knowledge source: SVTG

- File: `data/StandardVeterinaryTreatment.pdf` — *Standard Veterinary Treatment Guidelines for Livestock and
  Poultry*, Department of Animal Husbandry and Dairying (DAHD), Government of India, with FAO; dated October 2024.
  406 PDF pages.
- **Scope: livestock and poultry only** (ruminants, poultry, pig, camel, equine, mithun, yak). It has **no dog or
  cat chapters**.
- Page numbers: citations use **PDF page numbers** (1-based). The printed page is PDF page − 18 (PDF p.19 = printed p.1).
- Ingestion (`backend/app/retrieval/ingest.py`): front matter (PDF pp.1–18) skipped; running header and page
  numbers stripped; text split at section headings (`2.17 …`, `ANNEXURE-7 …`) and packed into ~800-character
  chunks at sentence boundaries. Chunks never cross a page, so each cites exactly one page. ~2,000 chunks.
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

The Cases and Drug Table pages edit `data/cases.json` and `data/drug_table.csv` directly. Every save, import
or delete validates the whole file with the same Pydantic models the tests use, rejects duplicates, and writes
atomically (temp file + replace); an invalid edit changes nothing. Imports are all-or-nothing. Marking a drug row
verified requires both a verifier name and a date. Editing a case changes its cache key, so its next run is fresh.

## Before any real use

A registered veterinarian must review every case and drug row, fill `verified_by`/`verified_on` and
`vet_verified`, and add the missing ban and toxicology references.
