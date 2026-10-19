"""SVTG PDF → ~800-character chunks that keep their page number and section.

Chunks never cross a page boundary, so every chunk cites exactly one page.
The front matter (messages, acknowledgements, contents) is skipped.
Run by the seed script on a local copy of the PDF; pymupdf is a seed-time dependency only, never deployed.
"""

import re
from dataclasses import dataclass
from pathlib import Path

INDEX_VERSION = 4
TARGET_CHARS = 800
MAX_CHARS = 1000
MIN_TAIL_CHARS = 200

# PDF page 19 is printed page 1 in the SVTG (2024) edition.
FIRST_CONTENT_PAGE = 19
PRINTED_PAGE_OFFSET = FIRST_CONTENT_PAGE - 1

RUNNING_HEADER = "STANDARD VETERINARY TREATMENT GUIDELINES FOR LIVESTOCK AND POULTRY"
HEADING_RE = re.compile(r"^(\d{1,2}(?:[.\-]\d{1,2}){1,3})\.?\s*([A-Z][^\n]{2,90})$")
ANNEXURE_RE = re.compile(r"^ANNEXURE[-\s]*(\d+)\s*:?\s*(.*)$", re.IGNORECASE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    page: int  # PDF page, 1-based
    printed_page: int | None
    section: str
    text: str


def printed_page(pdf_page: int) -> int | None:
    n = pdf_page - PRINTED_PAGE_OFFSET
    return n if n >= 1 else None


def _clean_lines(raw: str) -> list[str]:
    lines = [ln.strip() for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln and ln != RUNNING_HEADER]
    # Drop the printed page number that opens each page.
    if lines and lines[0].isdigit():
        lines = lines[1:]
    return lines


def _join(lines: list[str]) -> str:
    text = " ".join(lines)
    text = re.sub(r"(\w)- (\w)", r"\1-\2", text)  # keep compound words split across lines
    text = text.replace(" ", " ").replace(" y ", " • ")  # PDF bullet glyph extracts as 'y'
    return re.sub(r"\s+", " ", text).strip()


def _split_long(sentence: str) -> list[str]:
    if len(sentence) <= MAX_CHARS:
        return [sentence]
    out, cur = [], ""
    for word in sentence.split(" "):
        if cur and len(cur) + 1 + len(word) > TARGET_CHARS:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        out.append(cur)
    return out


def chunk_text(text: str) -> list[str]:
    """Greedy sentence packing to ~TARGET_CHARS; a short tail merges into the previous chunk."""
    sentences = [p for s in SENTENCE_SPLIT_RE.split(text) if s for p in _split_long(s)]
    chunks: list[str] = []
    cur = ""
    for s in sentences:
        if cur and len(cur) + 1 + len(s) > TARGET_CHARS:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        if chunks and len(cur) < MIN_TAIL_CHARS and len(chunks[-1]) + 1 + len(cur) <= MAX_CHARS:
            chunks[-1] = f"{chunks[-1]} {cur}"
        else:
            chunks.append(cur)
    return chunks


_CONNECTORS = ("or", "and", "of", "in", "with", "&", "-", "–", "the")


def _heading_continues(title: str) -> bool:
    """A heading wrapped onto the next line: ends with a connector or has an unclosed '('."""
    last = title.rsplit(" ", 1)[-1].lower()
    return last in _CONNECTORS or title.count("(") > title.count(")")


def _merge_short(segments: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Fold segments shorter than MIN_TAIL_CHARS into their neighbour on the same page.

    A short segment (usually a bare heading) joins the *next* segment and takes
    its section; a short final segment joins the previous one. A page whose only
    text is a heading is dropped — the heading still carries to the next page.
    """
    segs = [(sec, txt) for sec, txt in segments if txt]
    out: list[tuple[str, str]] = []
    pending = ""
    for sec, txt in segs:
        txt = f"{pending} {txt}".strip() if pending else txt
        pending = ""
        if len(txt) < MIN_TAIL_CHARS:
            pending = txt
        else:
            out.append((sec, txt))
    if pending:
        if out:
            sec, txt = out[-1]
            out[-1] = (sec, f"{txt} {pending}")
        elif not HEADING_RE.match(pending):
            out.append((segs[-1][0], pending))
    return out


def chunk_pages(pages: list[tuple[int, str]]) -> list[Chunk]:
    """pages: (pdf_page_number, raw_text). Section headings carry across pages."""
    chunks: list[Chunk] = []
    section = ""
    for page_no, raw in pages:
        lines = _clean_lines(raw)
        # Split the page into segments at section headings.
        segments: list[tuple[str, list[str]]] = [(section, [])]
        skip = False
        for i, ln in enumerate(lines):
            if skip:
                skip = False
                continue
            m = HEADING_RE.match(ln)
            a = ANNEXURE_RE.match(ln)
            if m:
                title = m.group(2).strip()
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                if nxt and _heading_continues(title):
                    title = f"{title} {nxt}"
                    ln = f"{ln} {nxt}"
                    skip = True
                section = f"{m.group(1)} {title}"
                segments.append((section, [ln]))
            elif a:
                # "ANNEXURE-7 :" is usually followed by its title on the next line.
                title = a.group(2).strip() or (lines[i + 1] if i + 1 < len(lines) else "")
                section = f"Annexure-{a.group(1)} {title}".strip()
                segments.append((section, [ln]))
            else:
                segments[-1][1].append(ln)
        texts = _merge_short([(sec, _join(seg)) for sec, seg in segments])
        n = 0
        for seg_section, text in texts:
            for piece in chunk_text(text):
                n += 1
                chunks.append(
                    Chunk(
                        chunk_id=f"p{page_no}-c{n}",
                        page=page_no,
                        printed_page=printed_page(page_no),
                        section=seg_section,
                        text=piece,
                    )
                )
    return chunks


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    import pymupdf  # seed-time only (requirements-seed.txt)

    with pymupdf.open(pdf_path) as doc:
        return [
            (i + 1, doc[i].get_text())
            for i in range(FIRST_CONTENT_PAGE - 1, doc.page_count)
            if len(doc[i].get_text().strip()) >= 40
        ]


def page_count(pdf_path: Path) -> int:
    import pymupdf

    with pymupdf.open(pdf_path) as doc:
        return doc.page_count


def build_chunks(pdf_path: Path) -> list[Chunk]:
    return chunk_pages(extract_pages(pdf_path))
