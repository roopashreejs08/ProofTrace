from app.agents.paper_finder import assess, norm, strip_doi
from app.schemas import Citation, PaperMatch


def test_hyphen_and_compact_tokens_match():
    cit = Citation(
        marker="[1]",
        raw_reference=(
            "Jiang S. Personalized Travel Sequence recommendation on "
            "Multisource Big Social Media. 2016."
        ),
        year=2016,
        first_author="Jiang",
    )

    cand = PaperMatch(
        source="crossref",
        title=(
            "Personalized Travel Sequence Recommendation on "
            "Multi-Source Big Social Media"
        ),
        authors=["Shuhui Jiang"],
        year=2016,
    )

    assess(cand, cit, via_doi=False)

    assert cand.checks["title_coverage"] == 1.0
    assert cand.status == "matched"


def test_low_overlap_is_not_matched():
    cit = Citation(
        marker="[1]",
        raw_reference="Smith J. An unrelated topic. 2019.",
        year=2019,
        first_author="Smith",
    )

    cand = PaperMatch(
        source="crossref",
        title="A completely different study of marine biology",
        authors=["Someone Else"],
        year=2019,
    )

    assess(cand, cit, via_doi=False)

    assert cand.status == "not_found"


def test_year_mismatch_is_flagged():
    cit = Citation(
        marker="[1]",
        raw_reference="Roe R. Gamma delta in practice. 2016.",
        year=2016,
        first_author="Roe",
    )

    cand = PaperMatch(
        source="crossref",
        title="Gamma delta in practice",
        authors=["R Roe"],
        year=2006,
    )

    assess(cand, cit, via_doi=False)

    assert cand.checks["year_match"] is False
    assert any("year" in d.lower() for d in cand.discrepancies)


def test_doi_stripping_and_norm():
    assert " ".join(strip_doi("see 10.1000/abc for details").split()) == (
        "see for details"
    )

    toks, compact = norm("Multi-Source Big Data")

    assert "multi" in toks and "source" in toks
    assert "multisourcebigdata" in compact
