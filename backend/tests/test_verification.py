from app.agents.verification_agent import decide
from app.schemas import (
    Citation,
    EvidenceResult,
    PaperMatch,
    RetractionResult,
    Verdict,
)


CIT = Citation(
    marker="[1]",
    raw_reference="Smith J. A study. 2020.",
)

MATCH = PaperMatch(
    source="crossref",
    status="matched",
    doi="10.1/x",
    title="A study",
    authors=["J Smith"],
    year=2020,
    abstract="text",
    checks={"author_match": True},
)

SUPPORTS = EvidenceResult(
    stance="supports",
    confidence=0.9,
    rationale="ok",
    method="llm",
)


def test_not_found_is_unresolvable_and_never_called_fabricated():
    v, why, _ = decide(
        "claim",
        CIT,
        PaperMatch(status="not_found"),
        None,
        None,
    )

    assert v == Verdict.UNRESOLVABLE
    assert "does not mean the paper is fabricated" in why


def test_possible_match_is_unresolvable():
    v, _, _ = decide(
        "claim",
        CIT,
        PaperMatch(status="possible", title="Other"),
        None,
        None,
    )

    assert v == Verdict.UNRESOLVABLE


def test_retraction_overrides_support():
    r = RetractionResult(
        status="retracted",
        sources=["crossref"],
    )

    assert decide("claim", CIT, MATCH, r, SUPPORTS)[0] == Verdict.RETRACTED


def test_contradiction():
    e = EvidenceResult(
        stance="contradicts",
        confidence=0.8,
        rationale="no",
        method="llm",
    )

    assert decide("claim", CIT, MATCH, None, e)[0] == Verdict.CONTRADICTED


def test_strong_support_is_verified():
    assert decide(
        "claim",
        CIT,
        MATCH,
        RetractionResult(status="clear"),
        SUPPORTS,
    )[0] == Verdict.VERIFIED


def test_full_text_support_is_verified_and_named():
    # A claim judged from open-access full text can be VERIFIED, and the
    # explanation must say it read the full text rather than the abstract.
    e = SUPPORTS.model_copy(
        update={"text_source": "full_text"}
    )

    v, why, _ = decide("claim", CIT, MATCH, None, e)

    assert v == Verdict.VERIFIED
    assert "full text supports the claim" in why


def test_keyword_only_evidence_never_verifies():
    e = EvidenceResult(
        stance="partially_supports",
        confidence=0.5,
        method="lexical",
    )

    assert decide("claim", CIT, MATCH, None, e)[0] == Verdict.WEAK_SUPPORT


def test_author_mismatch_downgrades():
    m = MATCH.model_copy(
        update={"checks": {"author_match": False}}
    )

    assert decide(
        "claim",
        CIT,
        m,
        None,
        SUPPORTS,
    )[0] == Verdict.WEAK_SUPPORT