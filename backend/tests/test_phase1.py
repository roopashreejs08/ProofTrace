"""Phase 1: extra retraction sources, honest coverage, doc DOI, splitter.

These are the generic fixes for documented limitations #3, #6, #7 and
#10. Nothing here is tied to a particular paper.
"""

from app.agents.claim_extractor import (
    extract_full,
    find_document_doi,
)
from app.agents.retraction_checker import RetractionChecker
from app.clients.europepmc import EuropePmcClient
from app.clients.pubmed import PubMedClient
from app.config import settings


# ---------------------------------------------------------------- config


def test_citation_cap_raised_to_200():
    # Limitation #7: the old default of 50 silently cut off long lists.
    assert settings.max_citations == 200


# ----------------------------------------------------------- europe pmc


EUROPEPMC_PAYLOAD = {
    "resultList": {
        "result": [
            {
                "pmid": "12345",
                "commentCorrectionList": {
                    "commentCorrection": [
                        {
                            "type": "Retraction of Publication",
                            "id": "999",
                        }
                    ]
                },
                "pubTypeList": {"pubType": ["Journal Article"]},
            }
        ]
    }
}


class _FakeApi:

    def __init__(self, payloads):
        self.payloads = payloads

    def get_json(self, source, url, params=None, **kwargs):
        return self.payloads.get(source)


def test_europepmc_detects_retraction():
    client = EuropePmcClient(_FakeApi({"europepmc": EUROPEPMC_PAYLOAD}))

    notices = client.notices_for("10.1/x")

    assert len(notices) == 1
    assert notices[0]["source"] == "europepmc"
    assert "retract" in notices[0]["type"].lower()


def test_europepmc_ignores_plain_article():
    payload = {
        "resultList": {
            "result": [
                {
                    "pmid": "1",
                    "pubTypeList": {"pubType": ["Journal Article"]},
                }
            ]
        }
    }

    client = EuropePmcClient(_FakeApi({"europepmc": payload}))

    assert client.notices_for("10.1/x") == []


def test_europepmc_missing_record_is_not_an_error():
    client = EuropePmcClient(_FakeApi({}))

    assert client.notices_for("10.1/x") == []


# --------------------------------------------------------------- pubmed


class _PubMedApi:

    def get_json(self, source, url, params=None, **kwargs):
        if "esearch" in url:
            return {"esearchresult": {"idlist": ["111"]}}

        return {
            "result": {
                "uids": ["111"],
                "111": {"pubtype": ["Retracted Publication"]},
            }
        }


def test_pubmed_detects_retraction():
    client = PubMedClient(_PubMedApi())

    notices = client.notices_for("10.1/x")

    assert len(notices) == 1
    assert notices[0]["source"] == "pubmed"
    assert "retract" in notices[0]["type"].lower()


def test_pubmed_no_doi_match_returns_nothing():
    class _Empty:

        def get_json(self, source, url, params=None, **kwargs):
            return {"esearchresult": {"idlist": []}}

    assert PubMedClient(_Empty()).notices_for("10.1/x") == []


# ----------------------------------------------- multi-source semantics


class _FakeCrossref:

    def __init__(self, updates=None, boom=False):
        self.updates = updates or []
        self.boom = boom

    def updates_for(self, doi):
        if self.boom:
            raise RuntimeError("crossref down")

        return self.updates


class _FakeSource:

    def __init__(self, notices=None, boom=False):
        self.notices = notices or []
        self.boom = boom

    def notices_for(self, doi):
        if self.boom:
            raise RuntimeError("source down")

        return self.notices


MATCH = {"status": "matched", "doi": "10.1/x"}


def test_all_sources_down_is_unknown():
    rc = RetractionChecker(
        None,
        _FakeCrossref(boom=True),
        _FakeSource(boom=True),
        _FakeSource(boom=True),
    )

    res, err = rc.check(MATCH)

    assert res.status == "unknown"
    assert err
    assert res.checked_sources == []


def test_partial_failure_keeps_status_but_reports_it():
    rc = RetractionChecker(
        None,
        _FakeCrossref(boom=True),
        _FakeSource(),
        _FakeSource(),
    )

    res, err = rc.check(MATCH)

    assert res.status == "clear"
    assert err
    assert set(res.checked_sources) == {"europepmc", "pubmed"}
    assert res.checked_at is not None
    assert res.source_urls


def test_any_source_can_flag_a_retraction():
    rc = RetractionChecker(
        None,
        _FakeCrossref(),
        _FakeSource(notices=[{
            "type": "Retraction of Publication",
            "doi": "10.1/x",
            "source": "europepmc",
        }]),
        _FakeSource(),
    )

    res, _ = rc.check(MATCH)

    assert res.status == "retracted"
    assert "europepmc" in res.sources


def test_openalex_flag_is_honoured():
    rc = RetractionChecker(
        None,
        _FakeCrossref(),
        _FakeSource(),
        _FakeSource(),
    )

    res, _ = rc.check({
        "status": "matched",
        "doi": "10.1/x",
        "openalex_retracted": True,
    })

    assert res.status == "retracted"
    assert "openalex" in res.sources


def test_clean_check_records_coverage_and_time():
    rc = RetractionChecker(
        None,
        _FakeCrossref(),
        _FakeSource(),
        _FakeSource(),
    )

    res, err = rc.check(MATCH)

    assert res.status == "clear"
    assert err == ""
    assert res.checked_at is not None
    assert "not proof" in res.note


def test_check_document_reuses_the_sources():
    rc = RetractionChecker(
        None,
        _FakeCrossref(updates=[{
            "type": "retraction",
            "doi": "10.1/doc",
            "source": "crossref",
        }]),
        _FakeSource(),
        _FakeSource(),
    )

    res = rc.check_document("10.1/doc")

    assert res.status == "retracted"
    assert rc.check_document(None) is None


# ------------------------------------------------------- document DOI


def test_document_doi_from_title_page():
    text = (
        "A Study of Chronic Kidney Disease\n"
        "Jane Doe\n"
        "DOI: 10.1038/nature14539\n"
        "Abstract ...\n"
    )

    assert find_document_doi(text) == "10.1038/nature14539"


def test_document_doi_requires_a_label():
    # A bare DOI in the reference list must not be taken as the
    # document's own DOI.
    text = "Some body text.\n\nReferences\n[1] Smith. https://doi.org/10.1/abc\n"

    assert find_document_doi(text) is None


def test_document_doi_only_scans_the_title_page():
    text = ("x" * 5000) + "\nDOI: 10.1/late\n"

    assert find_document_doi(text) is None


def test_document_doi_is_reported_in_meta():
    text = (
        "A Study\nDOI: 10.1038/nature14539\n\n"
        "Deep learning transformed vision (LeCun et al., 2015).\n\n"
        "References\n"
        "LeCun Y, Bengio Y. Deep learning. Nature, 2015.\n"
    )

    _, _, meta = extract_full(text)

    assert meta["document_doi"] == "10.1038/nature14539"


# --------------------------------------------- unnumbered splitter #10


def test_unnumbered_entry_without_surname_lead_is_split():
    # The second entry begins with a title, not a surname. It must not
    # be glued onto the first reference.
    text = (
        "Deep learning transformed vision (LeCun et al., 2015).\n\n"
        "References\n"
        "LeCun Y, Bengio Y. Deep learning. Nature, 2015.\n"
        "Deep learning: a survey of methods. Journal of AI, 2018.\n"
    )

    items, _, meta = extract_full(text)

    assert meta["references_parsed"] == 2

    first = next(
        it for it in items
        if (it.citation.first_author or "") == "LeCun"
    )

    assert "survey of methods" not in first.citation.raw_reference


def test_wrapped_continuation_line_is_still_joined():
    text = (
        "Deep learning transformed vision (LeCun et al., 2015).\n\n"
        "References\n"
        "LeCun Y, Bengio Y. Deep learning for image\n"
        "recognition tasks. Nature, 2015.\n"
    )

    items, _, meta = extract_full(text)

    assert meta["references_parsed"] == 1

    lecun = next(
        it for it in items
        if (it.citation.first_author or "") == "LeCun"
    )

    assert "recognition tasks" in lecun.citation.raw_reference


# ------------------------------------------- orchestrator: document DOI


DOC_TEXT = (
    "A Retracted Survey\n"
    "DOI: 10.1016/retracted-demo\n\n"
    "Deep learning transformed many fields [1].\n\n"
    "References\n"
    "[1] LeCun Y, Bengio Y, Hinton G. Deep learning. Nature 2015.\n"
    "https://doi.org/10.1038/nature14539\n"
)

LECUN_WORK = {
    "DOI": "10.1038/nature14539",
    "title": ["Deep learning"],
    "issued": {"date-parts": [[2015]]},
    "author": [{"given": "Yann", "family": "LeCun"}],
    "container-title": ["Nature"],
    "URL": "https://doi.org/10.1038/nature14539",
}


class _DocApi:
    """Crossref-only fake that retracts the uploaded document's DOI."""

    def get_json(self, source, url, params=None, **kwargs):
        params = params or {}

        if source in ("openalex", "europepmc", "pubmed"):
            return {"results": []} if source == "openalex" else None

        flt = str(params.get("filter", ""))

        if flt.startswith("updates:"):
            doi = flt.split(":", 1)[1]

            if doi == "10.1016/retracted-demo":
                return {"message": {"items": [{
                    "DOI": "10.1016/notice",
                    "update-to": [{
                        "type": "retraction",
                        "DOI": doi,
                        "source": "retraction-watch",
                    }],
                }]}}

            return {"message": {"items": []}}

        if url.endswith("/works/10.1038/nature14539"):
            return {"message": LECUN_WORK}

        if url.endswith("/works"):
            return {"message": {"items": []}}

        return None


class _NoLLM:
    enabled = False

    def json(self, *a, **k):
        return None


def test_pipeline_flags_a_retracted_uploaded_document(tmp_path):
    from app.memory import Memory
    from app.orchestrator import Pipeline

    mem = Memory(str(tmp_path / "t.db"))
    inv = mem.create_investigation(DOC_TEXT)

    Pipeline(mem, _NoLLM(), lambda i: _DocApi()).run(inv)

    d = mem.get_investigation(inv)

    assert d["status"] == "completed"

    document = d["report"]["document"]

    assert document["doi"] == "10.1016/retracted-demo"
    assert document["retraction"]["status"] == "retracted"

    assert any(
        "uploaded document itself" in n
        for n in d["report"]["notes"]
    )

