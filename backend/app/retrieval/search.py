"""BM25 search over SVTG chunks with a domain keyword boost.

score = BM25(query, chunk)
      + SECTION_BOOST × (domain keywords from the query found in the chunk's section title)
      + KEYWORD_BOOST × (domain keywords from the query found in the chunk text)
      + DOSE_TABLE_BOOST if the query asks about a dose and the chunk is in a drug-dose table
        that also contains one of the query's domain keywords

Domain keywords are drug names (from the drug table) plus words from SVTG
section titles (disease names), minus generic words. The boost lifts the
passage that is *about* a disease or drug above passages that only mention it.
"""

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.retrieval.ingest import Chunk

SECTION_BOOST = 2.0
KEYWORD_BOOST = 1.0
# Dose questions: lift the SVTG drug-dose tables ("Drugs usage in ruminants"),
# whose dense rows otherwise score poorly on term frequency.
DOSE_TERMS = frozenset({"dose", "dosage", "dosing", "mg"})
DOSE_TABLE_BOOST = 3.0
DOSE_TABLE_RE = re.compile(r"drugs? usage", re.IGNORECASE)

STOPWORDS = frozenset(
    """a an and are as at be been but by can could do does for from had has have how i if in into is it its
    may me my of on or our should so such than that the their them then there these they this to up was we
    were what when where which while who why will with would you your after before also any other per not
    no""".split()
)
# Generic words that appear in many section titles but say nothing about the disease.
GENERIC_SECTION_WORDS = frozenset(
    """disease diseases infection infections guidelines system animals animal poultry small large ruminants
    caused type syndrome preamble general control biosecurity treatment diagnosis definition""".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    out = []
    for tok in _TOKEN_RE.findall(text.lower()):
        if tok in STOPWORDS:
            continue
        # British/American spelling: haemorrhagic → hemorrhagic, oedema → edema.
        tok = tok.replace("ae", "e").replace("oe", "e")
        if len(tok) > 4 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        out.append(tok)
    return out


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    bm25: float
    boost: float


class SearchIndex:
    def __init__(self, chunks: list[Chunk], extra_keywords: list[str] | None = None):
        self.chunks = chunks
        self._tokens = [tokenize(f"{c.section} {c.text}") for c in chunks]
        self._token_sets = [set(t) for t in self._tokens]
        self._section_sets = [set(tokenize(c.section)) for c in chunks]
        self._dose_table = [bool(DOSE_TABLE_RE.search(c.section)) for c in chunks]
        self._bm25 = BM25Okapi(self._tokens) if chunks else None

        vocab: set[str] = set()
        for s in self._section_sets:
            vocab |= s
        for kw in extra_keywords or []:
            vocab |= set(tokenize(kw))
        self.keywords = frozenset(t for t in vocab if len(t) > 2 and not t.isdigit()) - frozenset(
            tokenize(" ".join(GENERIC_SECTION_WORDS))
        )

    def __len__(self) -> int:
        return len(self.chunks)

    def search(self, query: str, k: int = 5) -> list[Hit]:
        q = tokenize(query)
        if not q or self._bm25 is None:
            return []
        scores = self._bm25.get_scores(q)
        q_kw = [t for t in dict.fromkeys(q) if t in self.keywords]
        wants_dose = bool(DOSE_TERMS & set(q))
        hits = []
        for i, base in enumerate(scores):
            boost = 0.0
            kw_in_text = False
            for t in q_kw:
                if t in self._section_sets[i]:
                    boost += SECTION_BOOST
                if t in self._token_sets[i]:
                    boost += KEYWORD_BOOST
                    kw_in_text = True
            if wants_dose and kw_in_text and self._dose_table[i]:
                boost += DOSE_TABLE_BOOST
            total = float(base) + boost
            if total > 0:
                hits.append(Hit(self.chunks[i], total, float(base), boost))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]
