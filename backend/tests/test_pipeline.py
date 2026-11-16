import json

from app.memory import Memory
from app.orchestrator import Pipeline


TEXT = """
Deep learning transformed many fields [1].
A famous paper was later withdrawn [2].
Quantum gradient folding improves accuracy by 40% [3].

References
[1] LeCun Y, Bengio Y, Hinton G. Deep learning. Nature 2015.
https://doi.org/10.1038/nature14539
[2] Doe J. A retracted demonstration paper. Journal of Tests 2019.
https://doi.org/10.1016/retracted-demo
[3] Smithson J. Quantum gradient folding in neural cognition.
Journal of Imaginary Results 2021.
"""


WORKS = {
    "10.1038/nature14539": {
        "DOI": "10.1038/nature14539",
        "title": ["Deep learning"],
        "issued": {"date-parts": [[2015]]},
        "author": [
            {"given": "Yann", "family": "LeCun"}
        ],
        "container-title": ["Nature"],
        "URL": "https://doi.org/10.1038/nature14539",
        "abstract": (
            "<jats:p>Deep learning allows computational models "
            "to learn representations of data.</jats:p>"
        ),
    },
    "10.1016/retracted-demo": {
        "DOI": "10.1016/retracted-demo",
        "title": ["A retracted demonstration paper"],
        "issued": {"date-parts": [[2019]]},
        "author": [
            {"given": "Jane", "family": "Doe"}
        ],
        "container-title": ["Journal of Tests"],
        "updated-by": [
            {
                "type": "retraction",
                "DOI": "10.1016/notice",
                "source": "retraction-watch",
            }
        ],
    },
}


class NoLLM:
    enabled = False

    def json(self, *a, **k):
        return None


class FakeApi:

    def get_json(self, source, url, params=None, **kwargs):
        params = params or {}

        if source == "openalex":
            return {"results": []}

        if str(params.get("filter", "")).startswith("updates:"):
            return {"message": {"items": []}}

        for doi, work in WORKS.items():
            if url.endswith("/works/" + doi):
                return {"message": work}

        if url.endswith("/works"):
            return {"message": {"items": []}}

        return None


def test_full_pipeline(tmp_path):
    mem = Memory(str(tmp_path / "t.db"))

    inv = mem.create_investigation(TEXT)

    Pipeline(
        mem,
        NoLLM(),
        lambda i: FakeApi(),
    ).run(inv)

    d = mem.get_investigation(inv)

    assert d["status"] == "completed"

    assert [
        c["verdict"]
        for c in d["report"]["citations"]
    ] == [
        "WEAK SUPPORT",
        "RETRACTED",
        "UNRESOLVABLE",
    ]

    assert all(
        a["status"] == "completed"
        for a in d["agents"]
    )


class FullTextApi(FakeApi):
    """FakeApi plus an open-access Europe PMC full text for the LeCun DOI."""

    def get_json(self, source, url, params=None, **kwargs):
        if source == "europepmc":
            query = (params or {}).get("query", "")

            if "10.1038/nature14539" in query:
                return {"resultList": {"result": [{
                    "doi": "10.1038/nature14539",
                    "title": "Deep learning",
                    "pmcid": "PMC1",
                    "isOpenAccess": "Y",
                }]}}

            return {"resultList": {"result": []}}

        return super().get_json(source, url, params, **kwargs)

    def get_text(self, source, url, params=None, **kwargs):
        return (
            "<article><body><p>DISTINCTIVE FULL TEXT BODY about "
            "deep learning.</p></body></article>"
        )


def test_report_reports_full_text_use_without_storing_the_body(tmp_path):
    mem = Memory(str(tmp_path / "t.db"))

    inv = mem.create_investigation(TEXT)

    Pipeline(
        mem,
        NoLLM(),
        lambda i: FullTextApi(),
    ).run(inv)

    report = mem.get_investigation(inv)["report"]

    # The Evidence Analyst read the open-access full text for the one
    # paper that has one, and the report records that honestly.
    assert report["ai"]["full_text"] == 1

    lecun = report["citations"][0]

    assert lecun["evidence"]["text_source"] == "full_text"

    # The full text body is not copied into the report, which would
    # otherwise carry a copy of every open-access paper.
    assert lecun["match"]["full_text"] is None
    assert "DISTINCTIVE FULL TEXT BODY" not in json.dumps(report)


def test_no_citations_fails_cleanly(tmp_path):
    mem = Memory(str(tmp_path / "t.db"))

    inv = mem.create_investigation(
        "This paragraph has no citations at all in it."
    )

    Pipeline(
        mem,
        NoLLM(),
        lambda i: FakeApi(),
    ).run(inv)

    d = mem.get_investigation(inv)

    assert d["status"] == "failed"
    assert "No citations" in d["error"]


class CountingLLM:
    """Enabled LLM whose counter keeps rising across investigations."""

    enabled = True
    model = "fake-model"
    last_error = ""

    def __init__(self):
        self.used = 0
        self.failed = 0

    def json(self, prompt):
        self.used += 1

        return {
            "stance": "supports",
            "confidence": 0.9,
            "rationale": "ok",
            "quote": None,
        }


def test_ai_used_is_per_run_not_cumulative(tmp_path):
    # The LLM object outlives a single investigation, so its counter
    # keeps growing. The report must show how many claims *this* run
    # read, not the running total, or it would overstate AI usage.
    mem = Memory(str(tmp_path / "t.db"))
    llm = CountingLLM()

    counts = []

    for _ in range(2):
        inv = mem.create_investigation(TEXT)
        Pipeline(mem, llm, lambda i: FakeApi()).run(inv)
        d = mem.get_investigation(inv)
        counts.append(d["report"]["ai"]["used"])

    # Only one citation has an abstract, so each run read one claim.
    assert counts == [1, 1]
    # The underlying counter did accumulate, proving the point.
    assert llm.used == 2