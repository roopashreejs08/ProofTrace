"""Phase 2: matching quality (#4), association (#8), segmentation (#9)."""

from app.agents.claim_extractor import (
    _by_number,
    _looks_like_blob,
    extract_full,
)
from app.agents.paper_finder import assess, author_matches, norm
from app.schemas import Citation, PaperMatch


# ------------------------------------------------- #4 matching quality


def test_author_match_ignores_accents():
    assert author_matches("Schonberg", ["Viktor Mayer-Schönberg"]) is True
    assert author_matches("Muller", ["Klaus Müller"]) is True


def test_author_match_uses_whole_tokens():
    # A short surname must not match inside a longer unrelated name.
    assert author_matches("Li", ["Robert Collins"]) is False
    assert author_matches("Li", ["Wei Li"]) is True


def test_norm_folds_simple_plurals():
    toks, _ = norm("Neural networks and studies")

    assert "network" in toks
    assert "study" in toks


def test_title_coverage_handles_plural_and_accent():
    cit = Citation(
        marker="[1]",
        raw_reference="Muller K. Neural network models. 2020.",
        year=2020,
        first_author="Muller",
    )

    cand = PaperMatch(
        source="crossref",
        title="Neural Networks Models",
        authors=["Klaus Müller"],
        year=2020,
    )

    assess(cand, cit, via_doi=False)

    # "networks" folds to "network" and the accent is ignored.
    assert cand.checks["author_match"] is True
    assert cand.checks["title_coverage"] == 1.0


def test_resolving_doi_promotes_a_partial_title_match():
    # The DOI identifies the work; an incomplete reference title must
    # not leave it stuck at "possible" when author and year agree.
    cit = Citation(
        marker="[1]",
        raw_reference="Smith J. Some short note. 2020.",
        doi="10.1/xyz",
        year=2020,
        first_author="Smith",
    )

    cand = PaperMatch(
        source="crossref",
        doi="10.1/xyz",
        title="A much longer and differently worded study about things",
        authors=["Jane Smith"],
        year=2020,
    )

    assess(cand, cit, via_doi=True)

    assert cand.status == "matched"
    assert any(
        "doi" in d.lower() for d in cand.discrepancies
    )


def test_doi_match_is_not_promoted_when_author_contradicts():
    cit = Citation(
        marker="[1]",
        raw_reference="Smith J. Some short note. 2020.",
        doi="10.1/xyz",
        year=2020,
        first_author="Smith",
    )

    cand = PaperMatch(
        source="crossref",
        doi="10.1/xyz",
        title="A much longer and differently worded study about things",
        authors=["Jane Roe"],
        year=2020,
    )

    assess(cand, cit, via_doi=True)

    assert cand.status != "matched"


def test_wrong_doi_reports_a_doi_discrepancy():
    # A DOI that resolves to an unrelated record must be reported as a
    # DOI problem, not merely as a missing paper, so the reader knows
    # the DOI itself is wrong rather than the paper being absent.
    cit = Citation(
        marker="[1]",
        raw_reference="Smith J. A study of feline sleep. 2020.",
        doi="10.1/xyz",
        year=2020,
        first_author="Smith",
    )

    cand = PaperMatch(
        source="crossref",
        doi="10.1/xyz",
        title="Deep residual learning for image recognition",
        authors=["Kaiming He"],
        year=2016,
    )

    assess(cand, cit, via_doi=True)

    assert cand.status != "matched"
    assert any(
        "resolves to a record that does not match" in d
        for d in cand.discrepancies
    )


# --------------------------------------------- #8 association


def test_author_year_links_despite_diacritic_difference():
    text = (
        "Prior work showed an effect (Muller, 2020).\n\n"
        "References\n"
        "Müller J. A study of effects. Journal of Tests 2020.\n"
    )

    items, _, _ = extract_full(text)

    assert len(items) == 1
    assert items[0].citation.raw_reference is not None
    assert "A study of effects" in items[0].citation.raw_reference


def test_author_year_links_with_small_year_drift():
    text = (
        "Prior work showed an effect (Muller, 2021).\n\n"
        "References\n"
        "Muller J. A study of effects. Journal of Tests 2020.\n"
    )

    items, _, _ = extract_full(text)

    assert items[0].citation.raw_reference is not None


def test_ambiguous_surname_is_left_unresolved():
    text = (
        "Prior work showed an effect (Smith, 2020).\n\n"
        "References\n"
        "Smith J. First study. Journal of Tests 2020.\n"
        "Smith A. Second study. Journal of Tests 2020.\n"
    )

    items, _, _ = extract_full(text)

    assert items[0].citation.raw_reference is None


def test_by_number_falls_back_to_ordinal_position():
    a = Citation(marker="[0]", ref_key="ref:0")
    b = Citation(marker="[1]", ref_key="ref:1")

    refs = {0: a, 1: b}

    assert _by_number(refs, 1) is b
    assert _by_number(refs, 9) is None


def test_missing_marker_still_missing():
    text = (
        "A claim with no entry [9].\n\n"
        "References\n"
        "[1] Smith J. A study. 2019.\n"
        "[2] Roe R. Another study. 2019.\n"
    )

    items, _, _ = extract_full(text)

    missing = next(
        it for it in items if it.citation.marker == "[9]"
    )

    assert missing.citation.raw_reference is None


# --------------------------------------------- #9 segmentation


def test_inline_numbered_blob_is_split():
    text = (
        "Alpha effect [1] and beta effect [2].\n\n"
        "References\n"
        "[1] Smith J. Alpha study. 2018. "
        "[2] Roe R. Beta study. 2019.\n"
    )

    items, _, meta = extract_full(text)

    assert meta["references_parsed"] == 2
    assert meta["segmentation"] == "inline-numbered"


def test_numbered_segmentation_is_recorded():
    text = (
        "A claim [1].\n\n"
        "References\n"
        "[1] Smith J. A study. 2019.\n"
        "[2] Roe R. Another study. 2019.\n"
    )

    _, _, meta = extract_full(text)

    assert meta["segmentation"] == "numbered"


def test_plain_unnumbered_segmentation_is_recorded():
    text = (
        "A claim (Smith, 2019).\n\n"
        "References\n"
        "Smith J. A study. 2019.\n"
        "Roe R. Another study. 2019.\n"
    )

    _, _, meta = extract_full(text)

    assert meta["segmentation"] == "unnumbered"


class _FakeLLM:
    enabled = True

    def __init__(self, references):
        self.references = references

    def json(self, prompt):
        return {"references": self.references}


def test_ai_fallback_splits_an_unseparated_blob():
    blob = (
        "Alpha effects in beta systems were studied extensively by many "
        "researchers over the years and the results were published in a "
        "variety of venues including journals and conferences around the "
        "world. Smith and colleagues reported one thing while Jones and "
        "others reported something completely different in a later work "
        "that contradicted the first set of findings, and so on for quite "
        "a long time indeed with many words to exceed the six hundred "
        "character threshold that triggers the model based fallback. "
        "Further studies by Brown and Green examined related phenomena "
        "in a range of settings and produced yet more findings that were "
        "reported across several different journals and conference "
        "proceedings over a period of many years, adding still more text "
        "so that the total length comfortably passes the required limit "
        "for this particular fallback path to be exercised at all."
    )

    llm = _FakeLLM([
        "Smith J. Alpha effects in beta systems. Journal A 2018.",
        "Jones R. Beta systems revisited. Journal B 2019.",
    ])

    items, notes, meta = extract_full(
        "Alpha effect [1] and beta effect [2].\n\nReferences\n" + blob,
        llm,
    )

    assert meta["segmentation"] == "llm"
    assert meta["references_parsed"] == 2
    assert any("AI model was used to split" in n for n in notes)


def test_blob_detection_thresholds():
    assert _looks_like_blob([], "x") is False
    assert _looks_like_blob([[1, "short"]], "short") is False
    assert _looks_like_blob([[1, "x" * 700]], "x" * 700) is True
    assert _looks_like_blob([[1, "x" * 2100]], "x") is True
