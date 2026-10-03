from pathlib import Path

import pytest

from app.config import Settings
from app.retrieval.ingest import (
    MAX_CHARS,
    Chunk,
    build_chunks,
    chunk_pages,
    chunk_text,
    printed_page,
)
from app.retrieval.search import SearchIndex, tokenize

SENT = "The quick brown cow walked to the shed and ate some green fodder today."  # 72 chars


def test_chunk_text_targets_800_chars():
    text = " ".join([SENT] * 40)  # ~2900 chars
    chunks = chunk_text(text)
    assert len(chunks) >= 3
    assert all(len(c) <= MAX_CHARS for c in chunks)
    assert all(len(c) >= 600 for c in chunks[:-1])
    assert " ".join(chunks) == text  # nothing lost or reordered


def test_short_tail_merges_into_previous():
    chunks = chunk_text(" ".join([SENT] * 11) + " Tail.")
    assert chunks[-1].endswith("Tail.")
    assert len(chunks) == 1 or len(chunks[-1]) >= 200


def test_very_long_sentence_is_split():
    long = "word " * 600
    assert all(len(c) <= MAX_CHARS for c in chunk_text(long.strip()))


def test_chunks_keep_page_and_never_cross_pages():
    body = " ".join([SENT] * 15)
    pages = [
        (20, f"2\nSTANDARD VETERINARY TREATMENT GUIDELINES FOR LIVESTOCK AND POULTRY\n2.4 Foot and Mouth Disease (FMD)\n{body}"),
        (21, f"3\n{body}\n2.5 Lumpy Skin Disease (LSD)\n{body}"),
    ]
    chunks = chunk_pages(pages)
    assert {c.page for c in chunks} == {20, 21}
    assert all("STANDARD VETERINARY" not in c.text for c in chunks)
    p20 = [c for c in chunks if c.page == 20]
    p21 = [c for c in chunks if c.page == 21]
    assert all(c.section == "2.4 Foot and Mouth Disease (FMD)" for c in p20)
    # Section carries over the page break, then changes at the new heading.
    assert p21[0].section == "2.4 Foot and Mouth Disease (FMD)"
    assert p21[-1].section == "2.5 Lumpy Skin Disease (LSD)"
    assert [c.chunk_id for c in p21][0] == "p21-c1"


def test_bare_heading_does_not_become_its_own_chunk():
    body = " ".join([SENT] * 5)
    chunks = chunk_pages([(30, f"{body}\n3.2 Peste des Petits Ruminants (PPR)"), (31, body)])
    assert all(len(c.text) >= 60 for c in chunks)
    assert chunks[-1].section == "3.2 Peste des Petits Ruminants (PPR)"


def test_annexure_heading_sets_section():
    body = " ".join([SENT] * 5)
    chunks = chunk_pages(
        [(398, f"9.5.8 Parturient Paresis\n{body}"), (400, f"ANNEXURE-7 :\nDrugs usage in ruminants\n{body}")]
    )
    assert chunks[-1].section == "Annexure-7 Drugs usage in ruminants"


def test_printed_page_offset():
    assert printed_page(19) == 1
    assert printed_page(175) == 157
    assert printed_page(10) is None


def test_tokenize_normalises_spelling():
    assert tokenize("Haemorrhagic Septicaemia") == tokenize("hemorrhagic septicemia")
    assert "the" not in tokenize("the cow")


def _chunk(i: int, section: str, text: str) -> Chunk:
    return Chunk(chunk_id=f"p{i}-c1", page=i, printed_page=None, section=section, text=text)


def test_keyword_boost_prefers_section_about_the_term():
    filler = " ".join(f"filler{n}" for n in range(40))
    chunks = [
        _chunk(1, "1.1 Pneumonia", f"Theileriosis may be confused with pneumonia. {filler}"),
        _chunk(2, "4.4 Bovine Tropical Theileriosis", f"Fever and enlarged lymph nodes are seen. {filler}"),
        _chunk(3, "2.1 Mastitis", f"Udder swelling and clots. {filler}"),
    ]
    idx = SearchIndex(chunks)
    hits = idx.search("theileriosis", 3)
    assert hits[0].chunk.page == 2
    assert hits[0].boost > 0


def test_extra_keywords_boost_drug_names():
    filler = " ".join(f"filler{n}" for n in range(40))
    chunks = [
        _chunk(1, "", f"buparvaquone injection given {filler}"),
        _chunk(2, "", f"injection given injection given {filler}"),
    ]
    idx = SearchIndex(chunks, extra_keywords=["buparvaquone"])
    assert "buparvaquone" in idx.keywords
    assert idx.search("buparvaquone injection", 2)[0].chunk.page == 1


def test_empty_index_and_query():
    assert SearchIndex([]).search("anything") == []
    assert SearchIndex([_chunk(1, "", "text here")]).search("the of and") == []


# ---------- the real SVTG PDF ----------

PDF = Settings(_env_file=None).pdf_path
needs_pdf = pytest.mark.skipif(not PDF.is_file(), reason="SVTG PDF not present")


@pytest.fixture(scope="module")
def svtg(tmp_path_factory) -> SearchIndex:
    chunks = build_chunks(PDF, tmp_path_factory.mktemp("cache"))
    return SearchIndex(chunks, ["buparvaquone", "ketoprofen", "diclofenac", "albendazole"])


@needs_pdf
def test_svtg_chunk_stats(svtg):
    sizes = [len(c.text) for c in svtg.chunks]
    assert len(svtg) > 1000
    assert max(sizes) <= MAX_CHARS
    assert sorted(sizes)[len(sizes) // 2] > 500  # median near the 800 target
    assert all(19 <= c.page <= 406 for c in svtg.chunks)


@needs_pdf
@pytest.mark.parametrize(
    "query,expected_pages",
    [
        ("buparvaquone milk withdrawal theileriosis", {175}),
        ("milk fever calcium borogluconate recumbent cow", {36, 37}),
        ("anthrax do not open carcass", {116, 117, 155, 156, 316}),
        ("albendazole dose anthelmintic ruminants", {86, 400}),
    ],
)
def test_svtg_known_answers_rank_top3(svtg, query, expected_pages):
    pages = {h.chunk.page for h in svtg.search(query, 3)}
    assert pages & expected_pages, f"{query!r} → {sorted(pages)}"


@needs_pdf
def test_cache_roundtrip(tmp_path: Path):
    first = build_chunks(PDF, tmp_path)
    assert (tmp_path / "svtg_chunks.json").is_file()
    second = build_chunks(PDF, tmp_path)
    assert first == second
