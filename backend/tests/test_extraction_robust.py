from app.agents.claim_extractor import extract, extract_full


# Synthetic, generic IEEE-style paper with repeated running headers,
# a licence stamp and multiline numbered references.
HEADER = (
    "INTERNATIONAL CONFERENCE ON THINGS (ICTHINGS 2019)\n"
    "978-1-5090-6135-8/17/$31.00 (c)2019 IEEE\n"
    "Authorized licensed use limited to: A University. Downloaded on "
    "January 01,2020 at 00:00:00 UTC from IEEE Xplore. Restrictions apply.\n"
)

PAGE = (
    "Some body text about alpha effects [1] and gamma effects [2].\n"
)


def make_paper(pages=4, filler=""):
    body = (HEADER + PAGE + filler) * pages

    refs = (
        "\nREFERENCES\n"
        "[1] Smith J, Doe A. A study of alpha\n"
        "and beta effects. Journal of Testing 2018.\n"
        "https://doi.org/10.1000/abc123\n"
        "[2] Roe R. Gamma delta in practice. Proceedings of Stuff 2019, "
        "pp. 1-10.\n"
    )

    return body + refs


def test_multiline_numbered_references_are_joined():
    items, _ = extract(make_paper())

    assert len(items) == 2

    assert "alpha and beta effects" in items[0].citation.raw_reference
    assert items[0].citation.doi == "10.1000/abc123"
    assert "Gamma delta in practice" in items[1].citation.raw_reference


def test_running_headers_are_not_citations():
    items, _ = extract(make_paper())

    markers = [it.citation.marker for it in items]

    assert not any("ICTHINGS" in m.upper() for m in markers)
    assert all(it.citation.raw_reference for it in items)


def test_repeated_furniture_is_removed():
    _, _, meta = extract_full(make_paper())

    assert meta["furniture_lines_removed"] > 0


def test_author_year_citation_links_to_reference():
    text = (
        "Prior work showed a strong effect (Smith, 2018).\n\n"
        "References\n"
        "Smith J. A study of things. Journal of Testing 2018.\n"
    )

    items, _ = extract(text)

    assert len(items) == 1
    assert items[0].citation.first_author == "Smith"
    assert "A study of things" in items[0].citation.raw_reference


def test_long_bibliography_at_end_is_not_truncated():
    # A body far longer than the old 40,000-character cap.
    filler = ("word " * 20 + "\n") * 700
    text = make_paper(pages=1, filler=filler)

    assert len(text) > 40000

    items, _, meta = extract_full(text)

    assert meta["references_parsed"] == 2
    assert len(items) == 2
    assert meta["truncated"] is False


def test_unnumbered_harvard_references_are_split_per_entry():
    text = (
        "Deep learning transformed vision (LeCun et al., 2015). "
        "Residual networks helped (He et al., 2016).\n\n"
        "References\n"
        "LeCun Y, Bengio Y, Hinton G. Deep learning. Nature, 2015.\n"
        "He K, Zhang X, Ren S, Sun J. Deep residual learning for image "
        "recognition. CVPR, 2016.\n"
    )

    items, _, meta = extract_full(text)

    assert meta["references_parsed"] == 2

    lecun = next(
        it for it in items
        if (it.citation.first_author or "") == "LeCun"
    )

    assert "Deep learning" in lecun.citation.raw_reference
    assert "He K" not in lecun.citation.raw_reference


def test_blank_line_separated_references():
    text = (
        "A claim about vision (LeCun et al., 2015).\n\n"
        "References\n\n"
        "LeCun Y, Bengio Y, Hinton G. Deep learning. Nature, 2015.\n\n"
        "He K, Zhang X. Residual learning. CVPR, 2016.\n"
    )

    _, _, meta = extract_full(text)

    assert meta["references_parsed"] == 2


def test_narrative_et_al_year_citations_are_linked():
    # Day 6: "Devlin et al. (2019)" is a real citation form. The sentence
    # splitter used to break it after "et al." and the reference splitter
    # used to treat the trailing "2019."/"2020." as inline list markers,
    # so neither the claims nor the references were usable.
    text = (
        "Devlin et al. (2019) showed that pretraining helps. "
        "Brown et al. (2020) scaled the same idea up.\n\n"
        "References\n\n"
        "Devlin J, Chang MW, Lee K, Toutanova K. BERT: Pre-training of "
        "deep bidirectional transformers. NAACL 2019.\n\n"
        "Brown TB, et al. Language models are few-shot learners. "
        "NeurIPS 2020.\n"
    )

    items, _, meta = extract_full(text)

    authors = {it.citation.first_author for it in items}

    assert meta["references_parsed"] == 2
    assert meta["in_text_citations"] == 2
    assert authors == {"Devlin", "Brown"}


def test_bracket_number_with_dot_references_are_split_per_entry():
    # Some publishers number references "[1]. Author ..." (bracket, number,
    # bracket, full stop). That separator after the bracket used to stop the
    # entry regex matching, so the whole list was treated as unnumbered and
    # split mid-entry — leaving references cut off mid-sentence and merged
    # with the next one.
    text = (
        "Label encoding helps [1] and naive Bayes is effective [2].\n\n"
        "REFERENCES\n"
        "[1]. Wickramasinghe, M. P. N. M., D. M. Perera, and K. A. D. C. P.\n"
        "Kahandawaarachchi. \"Dietary prediction for patients with Chronic\n"
        "Kidney Disease (CKD).\" In 2017 IEEE Life Sciences Conference\n"
        "(LSC), pp.300-303. IEEE, 2017.\n"
        "[2]. Co-learning Lounge, \"Chronic Kidney Disease.\" Aug. 26, 2020.\n"
        "Accessed: Feb. 19, 2023.\n"
    )

    items, _, meta = extract_full(text)

    assert meta["references_parsed"] == 2
    assert meta["segmentation"] == "numbered"

    one = next(it for it in items if it.citation.marker == "[1]")
    two = next(it for it in items if it.citation.marker == "[2]")

    # The first entry keeps its wrapped continuation lines...
    assert "Dietary prediction" in one.citation.raw_reference
    assert "Sciences Conference" in one.citation.raw_reference
    # ...and does not swallow the next entry.
    assert "Co-learning Lounge" not in one.citation.raw_reference

    assert "Co-learning Lounge" in two.citation.raw_reference
    assert "Wickramasinghe" not in two.citation.raw_reference


def test_trailing_year_is_not_an_inline_list_marker():
    # A four-digit year at the end of a reference ("... NAACL 2019.") must
    # not be mistaken for a "1." style list marker.
    text = (
        "A claim (Devlin et al., 2019).\n\n"
        "References\n"
        "Devlin J. BERT. NAACL 2019. https://doi.org/10.1/bert\n"
        "Brown T. GPT-3. NeurIPS 2020. https://doi.org/10.1/gpt3\n"
    )

    _, _, meta = extract_full(text)

    assert meta["references_parsed"] == 2
    assert meta["segmentation"] != "inline-numbered"
