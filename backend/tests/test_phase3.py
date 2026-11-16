"""Phase 3: broader lookup coverage (#2) and open-access full text (#1)."""

from app.agents.evidence_analyst import EvidenceAnalyst
from app.agents.paper_finder import PaperFinder
from app.clients.europepmc import EuropePmcClient
from app.clients.fulltext import clip, jats_to_text, pdf_to_text
from app.clients.pubmed import PubMedClient
from app.config import settings
from app.schemas import Citation, PaperMatch


# ------------------------------------------------- #2 coverage


class FakeEpmcApi:
    """Europe PMC: a search hit, a DOI hit, and an OA full-text XML."""

    def get_json(self, source, url, params=None, **kwargs):
        q = (params or {}).get("query", "")

        if 'DOI:"10.1/oa"' in q:
            return {"resultList": {"result": [{
                "doi": "10.1/oa",
                "title": "An open access paper",
                "authorString": "Doe J, Roe R",
                "pubYear": "2020",
                "journalTitle": "Journal of Open Work",
                "abstractText": "An abstract.",
                "pmcid": "PMC123",
                "isOpenAccess": "Y",
            }]}}

        if "deep learning" in q.lower():
            return {"resultList": {"result": [{
                "doi": "10.1/dl",
                "title": "Deep learning",
                "authorString": "LeCun Y",
                "pubYear": "2015",
                "journalTitle": "Nature",
            }]}}

        return {"resultList": {"result": []}}

    def get_text(self, source, url, params=None, **kwargs):
        return (
            "<article><front><abstract><p>Abstract text here.</p>"
            "</abstract></front><body><sec><p>Body sentence about "
            "deep learning.</p></sec></body><back><ref-list><ref>"
            "<p>Reference to ignore.</p></ref></ref-list></back>"
            "</article>"
        )


def test_europepmc_search_parses_metadata():
    c = EuropePmcClient(FakeEpmcApi())
    r = c.search("deep learning")

    assert r and r[0].source == "europepmc"
    assert r[0].title == "Deep learning"
    assert r[0].year == 2015
    assert "LeCun Y" in r[0].authors


def test_europepmc_by_doi_parses_abstract():
    m = EuropePmcClient(FakeEpmcApi()).by_doi("10.1/oa")

    assert m.doi == "10.1/oa"
    assert m.abstract == "An abstract."


class FakePubmedApi:
    def get_json(self, source, url, params=None, **kwargs):
        params = params or {}

        if "esearch.fcgi" in url:
            if "deep learning" in params.get("term", "").lower():
                return {"esearchresult": {"idlist": ["111"]}}

            return {"esearchresult": {"idlist": []}}

        if "esummary.fcgi" in url:
            return {"result": {
                "uids": ["111"],
                "111": {
                    "uid": "111",
                    "title": "Deep learning.",
                    "authors": [{"name": "LeCun Y"}],
                    "pubdate": "2015 May",
                    "source": "Nature",
                    "fulljournalname": "Nature",
                    "articleids": [
                        {"idtype": "doi", "value": "10.1038/nature14539"},
                    ],
                    "pubtype": [],
                },
            }}

        return None


def test_pubmed_search_parses_metadata():
    r = PubMedClient(FakePubmedApi()).search("deep learning")

    assert r and r[0].source == "pubmed"
    assert r[0].title == "Deep learning"
    assert r[0].year == 2015
    assert r[0].doi == "10.1038/nature14539"


class EmptyCrossref:
    def by_doi(self, doi):
        return None

    def search(self, query, rows=3):
        return []


class EmptyOpenAlex:
    def by_doi(self, doi):
        return None

    def search(self, query, n=3):
        return []


class EpmcOnly:
    def by_doi(self, doi):
        return None

    def search(self, query, n=3):
        return [PaperMatch(
            source="europepmc",
            doi="10.1/dl",
            title="Deep learning",
            authors=["Yann LeCun"],
            year=2015,
        )]

    def full_text(self, doi):
        return None


def test_paper_finder_uses_europepmc_when_others_are_empty():
    # A work indexed only in Europe PMC must still be found once Crossref
    # and OpenAlex return nothing.
    pf = PaperFinder(
        None, EmptyCrossref(), EmptyOpenAlex(), EpmcOnly()
    )

    cit = Citation(
        marker="[1]",
        raw_reference="LeCun Y. Deep learning. Nature 2015.",
        year=2015,
        first_author="LeCun",
    )

    m = pf.find(cit)

    assert m.status == "matched"
    assert m.source == "europepmc"


class CrossrefNoAbstract:
    def by_doi(self, doi):
        return PaperMatch(
            source="crossref",
            doi=doi,
            title="Deep learning",
            authors=["Yann LeCun"],
            year=2015,
            abstract=None,
        )

    def search(self, query, rows=3):
        return []


class OpenAlexNoAbstract:
    def by_doi(self, doi):
        return PaperMatch(
            source="openalex",
            doi=doi,
            title="Deep learning",
            authors=["Yann LeCun"],
            year=2015,
            abstract=None,
        )

    def search(self, query, n=3):
        return []


class EpmcAbstractOnly:
    def by_doi(self, doi):
        return PaperMatch(
            source="europepmc",
            doi=doi,
            title="Deep learning",
            authors=["Yann LeCun"],
            year=2015,
            abstract="Deep learning allows computational models to learn.",
        )

    def search(self, query, n=3):
        return []

    def full_text(self, doi):
        return None


def test_paper_finder_fills_missing_abstract_from_europepmc():
    # Crossref and OpenAlex often omit the abstract (e.g. Nature titles).
    # Europe PMC carries it, so the claim can be judged instead of being
    # reported as unassessable.
    pf = PaperFinder(
        None, CrossrefNoAbstract(), OpenAlexNoAbstract(), EpmcAbstractOnly()
    )

    cit = Citation(
        marker="[1]",
        raw_reference="LeCun Y. Deep learning. Nature 2015.",
        doi="10.1038/nature14539",
        year=2015,
        first_author="LeCun",
    )

    m = pf.find(cit)

    assert m.status == "matched"
    assert m.abstract and "Deep learning" in m.abstract


# ------------------------------------------------- #1 full-text mode


def test_jats_to_text_drops_references():
    xml = (
        "<article><body><p>Hello world.</p></body>"
        "<back><ref-list><ref><p>Ignore me.</p></ref></ref-list>"
        "</back></article>"
    )

    text = jats_to_text(xml)

    assert "Hello world" in text
    assert "Ignore me" not in text


def test_pdf_to_text_handles_bad_input():
    assert pdf_to_text(None) is None
    assert pdf_to_text(b"not a real pdf") is None


def test_clip_truncates_to_the_configured_cap():
    long = "x" * (settings.max_full_text_chars + 100)

    assert len(clip(long)) == settings.max_full_text_chars


class EpmcWithFullText:
    def by_doi(self, doi):
        return None

    def search(self, query, n=3):
        return [PaperMatch(
            source="europepmc",
            doi="10.1/dl",
            title="Deep learning",
            authors=["Yann LeCun"],
            year=2015,
        )]

    def full_text(self, doi):
        return "Full text about deep learning."


def test_paper_finder_attaches_open_access_full_text():
    pf = PaperFinder(
        None, EmptyCrossref(), EmptyOpenAlex(), EpmcWithFullText()
    )

    cit = Citation(
        marker="[1]",
        raw_reference="LeCun Y. Deep learning. Nature 2015.",
        year=2015,
        first_author="LeCun",
    )

    m = pf.find(cit)

    assert m.status == "matched"
    assert m.full_text_source == "europepmc"
    assert "deep learning" in m.full_text


class RecordingLLM:
    enabled = True
    model = "fake-model"
    last_error = ""

    def __init__(self):
        self.prompts = []

    def json(self, prompt):
        self.prompts.append(prompt)

        return {
            "stance": "supports",
            "confidence": 0.9,
            "rationale": "ok",
            "quote": None,
        }


def test_evidence_analyst_prefers_full_text_over_abstract():
    llm = RecordingLLM()
    ea = EvidenceAnalyst(None, llm)

    r = ea.analyse("Deep learning works", {
        "status": "matched",
        "abstract": "short abstract",
        "full_text": "a long full text about deep learning",
    })

    assert r.method == "llm"
    assert r.text_source == "full_text"
    assert "FULL TEXT" in llm.prompts[0]
    assert "a long full text" in llm.prompts[0]


def test_evidence_analyst_falls_back_to_abstract():
    llm = RecordingLLM()
    ea = EvidenceAnalyst(None, llm)

    r = ea.analyse("claim", {
        "status": "matched",
        "abstract": "the abstract",
    })

    assert r.text_source == "abstract"
    assert "ABSTRACT" in llm.prompts[0]


def test_evidence_analyst_without_text_is_skipped():
    ea = EvidenceAnalyst(None, RecordingLLM())

    r = ea.analyse("claim", {"status": "matched"})

    assert r.method == "none"
    assert r.text_source is None
    assert "full text" in r.limitation.lower()
