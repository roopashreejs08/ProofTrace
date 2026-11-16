from app.agents.retraction_checker import (
    RetractionChecker,
    classify,
    split_notices,
)
from app.agents.verification_agent import decide
from app.schemas import (
    Citation,
    EvidenceResult,
    PaperMatch,
    RetractionResult,
    Verdict,
)


def test_corrections_are_kept_separate_from_retractions():
    status, notices, corrections = split_notices([
        {"type": "correction", "DOI": "10.1/corr"},
        {"type": "expression_of_concern", "DOI": "10.1/eoc"},
    ])

    assert status == "concern"
    assert [n["type"] for n in notices] == ["expression_of_concern"]
    assert [c["type"] for c in corrections] == ["correction"]


def test_classify_still_returns_two_tuple():
    status, notices = classify([{"type": "retraction", "DOI": "10.1/n"}])

    assert status == "retracted"
    assert notices[0]["doi"] == "10.1/n"


class BoomCrossref:

    def updates_for(self, doi):
        raise RuntimeError("network down")


def test_lookup_failure_is_unknown_not_clear():
    checker = RetractionChecker(None, BoomCrossref())

    res, err = checker.check({
        "status": "matched",
        "doi": "10.1/x",
        "crossref_updates": [],
        "openalex_retracted": False,
    })

    assert res.status == "unknown"
    assert err


class OkCrossref:

    def updates_for(self, doi):
        return []


def test_no_notices_is_clear():
    checker = RetractionChecker(None, OkCrossref())

    res, _ = checker.check({
        "status": "matched",
        "doi": "10.1/x",
        "crossref_updates": [],
        "openalex_retracted": False,
    })

    assert res.status == "clear"


CIT = Citation(marker="[1]", raw_reference="Smith J. A study. 2020.")


def match(**checks):
    base = {
        "title_match": True,
        "year_match": True,
        "author_match": True,
    }
    base.update(checks)

    return PaperMatch(
        source="crossref",
        status="matched",
        doi="10.1/x",
        title="A study",
        authors=["J Smith"],
        year=2020,
        abstract="text",
        checks=base,
    )


LLM_SUPPORT = EvidenceResult(
    stance="supports",
    confidence=0.9,
    rationale="ok",
    method="llm",
)


def test_year_mismatch_downgrades_verified():
    v, why, cav = decide(
        "claim",
        CIT,
        match(year_match=False),
        RetractionResult(status="clear"),
        LLM_SUPPORT,
    )

    assert v == Verdict.WEAK_SUPPORT
    assert any("year" in c.lower() for c in cav)


def test_keyword_support_never_verifies_even_at_high_confidence():
    e = EvidenceResult(
        stance="supports",
        confidence=0.95,
        rationale="keywords",
        method="lexical",
    )

    assert decide("claim", CIT, match(), None, e)[0] == Verdict.WEAK_SUPPORT


def test_llm_support_with_clean_checks_verifies():
    assert decide(
        "claim",
        CIT,
        match(),
        RetractionResult(status="clear"),
        LLM_SUPPORT,
    )[0] == Verdict.VERIFIED


def test_correction_adds_caveat_not_retraction():
    r = RetractionResult(
        status="clear",
        corrections=[{"type": "correction", "doi": "10.1/corr"}],
    )

    v, _, cav = decide("claim", CIT, match(), r, LLM_SUPPORT)

    assert v == Verdict.VERIFIED
    assert any("correction" in c.lower() for c in cav)


def test_no_abstract_says_support_could_not_be_assessed():
    # EvidenceResult() defaults to method="none": nothing was evaluated
    # because no abstract was available. The wording must not imply the
    # paper fails to support the claim, and must not repeat itself.
    e = EvidenceResult(
        limitation=(
            "No abstract or open-access full text was available to "
            "judge the claim."
        )
    )

    v, why, _ = decide(
        "claim",
        CIT,
        match(),
        RetractionResult(status="clear"),
        e,
    )

    assert v == Verdict.WEAK_SUPPORT
    assert why.lower().count("could not be assessed") == 1
    assert "does not clearly support" not in why
    assert "no abstract" in why.lower()


def test_partial_support_says_so_plainly():
    # A model that supports only part of the claim should not be reported
    # with the vague "does not clearly support" wording.
    e = EvidenceResult(
        stance="partially_supports",
        confidence=0.8,
        rationale="The text confirms one half of the claim only.",
        method="llm",
    )

    v, why, _ = decide(
        "claim",
        CIT,
        match(),
        RetractionResult(status="clear"),
        e,
    )

    assert v == Verdict.WEAK_SUPPORT
    assert "only part of the claim" in why
    assert "does not clearly support" not in why


def test_neutral_evidence_is_not_dressed_up_as_a_finding():
    e = EvidenceResult(
        stance="neutral",
        confidence=0.4,
        rationale="The text neither confirms nor denies it.",
        method="llm",
    )

    v, why, _ = decide(
        "claim",
        CIT,
        match(),
        RetractionResult(status="clear"),
        e,
    )

    assert v == Verdict.WEAK_SUPPORT
    assert "does not " in why
    assert "confirm or contradict" in why
