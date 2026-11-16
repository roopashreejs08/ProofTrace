from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    VERIFIED = "VERIFIED"
    UNRESOLVABLE = "UNRESOLVABLE"
    RETRACTED = "RETRACTED"
    WEAK_SUPPORT = "WEAK SUPPORT"
    CONTRADICTED = "CONTRADICTED"


class Citation(BaseModel):
    # marker is the in-text form, e.g. "[1]" or "Smith, 2020".
    marker: str

    raw_reference: Optional[str] = None
    doi: Optional[str] = None
    year: Optional[int] = None
    first_author: Optional[str] = None

    # Identity of the matched reference-list entry. Used to associate
    # every in-text form of a citation with the same bibliography entry
    # so the same reference is not checked twice and none is missed.
    ref_key: Optional[str] = None

    # Extra details parsed from the bibliography entry. Optional so old
    # stored rows (which lack them) still deserialise.
    authors: list[str] = Field(default_factory=list)
    title: Optional[str] = None
    journal: Optional[str] = None
    kind: Optional[str] = None  # journal-article | conference | report | ...


class Item(BaseModel):
    id: str
    claim: str
    citation: Citation


class PaperMatch(BaseModel):
    source: str = "none"  # crossref | openalex | europepmc | pubmed | none
    status: str = "not_found"  # matched | possible | not_found | error

    doi: Optional[str] = None
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    journal: Optional[str] = None
    url: Optional[str] = None
    openalex_id: Optional[str] = None
    abstract: Optional[str] = None

    # Open-access full text, when one could be fetched. Kept out of the
    # final report (the Evidence Analyst reads it from the stored finding)
    # so the report does not carry a copy of every paper.
    full_text: Optional[str] = None
    full_text_source: Optional[str] = None  # europepmc | openalex-pdf
    oa_pdf_url: Optional[str] = None

    openalex_retracted: Optional[bool] = None
    crossref_updates: list[dict] = Field(default_factory=list)

    score: float = 0.0
    checks: dict = Field(default_factory=dict)
    discrepancies: list[str] = Field(default_factory=list)


class RetractionResult(BaseModel):
    # retracted | concern | clear | unknown
    status: str = "unknown"

    # Sources that actually produced a notice (retraction/concern/correction).
    sources: list[str] = Field(default_factory=list)

    # Every source that was successfully queried. Lets the UI show the
    # coverage behind a "clear" result instead of implying it is proof.
    checked_sources: list[str] = Field(default_factory=list)

    # Direct links to the records that were consulted, so a human can
    # verify the finding themselves.
    source_urls: list[str] = Field(default_factory=list)

    notices: list[dict] = Field(default_factory=list)

    # Corrections are kept distinct from retractions and concerns.
    corrections: list[dict] = Field(default_factory=list)

    # When the check actually ran (unix seconds).
    checked_at: Optional[float] = None

    note: str = ""


class EvidenceResult(BaseModel):
    # supports | partially_supports | contradicts | neutral | insufficient
    stance: str = "insufficient"

    confidence: float = 0.0
    rationale: str = ""
    quote: Optional[str] = None

    # llm | lexical | none
    method: str = "none"

    # Which text the stance was judged from: full_text | abstract | none.
    text_source: Optional[str] = None

    # Which model produced an llm result, and any error from an attempted
    # but failed LLM call. Lets the UI separate genuine AI analysis from
    # the keyword fallback.
    model: Optional[str] = None
    gemini_error: Optional[str] = None

    limitation: str = ""


class CitationReport(BaseModel):
    item_id: str
    claim: str
    citation: Citation

    verdict: Verdict
    explanation: str

    caveats: list[str] = Field(default_factory=list)

    publication_exists: bool = False

    match: Optional[PaperMatch] = None
    retraction: Optional[RetractionResult] = None
    evidence: Optional[EvidenceResult] = None
