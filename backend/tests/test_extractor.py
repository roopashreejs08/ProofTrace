from app.agents.claim_extractor import extract, expand_numbers


TEXT = """Transformers became dominant in language tasks [1].
Deep residual networks improved vision (He et al., 2016).
A claim with no reference entry [9].

References
[1] Vaswani A, et al. Attention is all you need. NeurIPS 2017.
https://doi.org/10.48550/arXiv.1706.03762
[2] He K, Zhang X, Ren S, Sun J. Deep residual learning for image
recognition. CVPR 2016.
"""


def test_numeric_and_author_year_citations_are_linked():
    items, _ = extract(TEXT)

    assert len(items) == 3
    assert items[0].citation.doi == "10.48550/arxiv.1706.03762"
    assert items[1].citation.first_author == "He"
    assert "Deep residual" in items[1].citation.raw_reference


def test_missing_reference_entry_is_kept_not_dropped():
    items, _ = extract(TEXT)

    assert items[2].citation.raw_reference is None
    assert items[2].citation.marker == "[9]"


def test_ranges_expand():
    assert expand_numbers("1, 3-5") == [1, 3, 4, 5]


def test_inline_doi():
    items, _ = extract(
        "Prior work reported this result 10.1038/nature14539."
    )

    assert items[0].citation.doi == "10.1038/nature14539"


def test_reference_only_input():
    items, notes = extract(
        "References\n"
        "1. Smith J. A study of things. Journal of Stuff 2019."
    )

    assert len(items) == 1 and notes
