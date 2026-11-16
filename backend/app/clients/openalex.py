from ..config import settings
from ..schemas import PaperMatch
from .fulltext import clip, pdf_to_text


BASE = "https://api.openalex.org"


def rebuild_abstract(inv):
    if not inv:
        return None

    pos = {}

    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word

    return " ".join(
        pos[i] for i in sorted(pos)
    ) or None


class OpenAlexClient:

    def __init__(self, api):
        self.api = api

    def _params(self, p):
        p = dict(p)
        p["mailto"] = settings.contact_email

        if settings.openalex_api_key:
            p["api_key"] = settings.openalex_api_key

        return p

    def _get(self, params):
        d = self.api.get_json(
            "openalex",
            BASE + "/works",
            self._params(params)
        )

        return [
            self._parse(w)
            for w in (d or {}).get("results", [])
        ]

    def by_doi(self, doi):
        r = self._get({
            "filter": "doi:https://doi.org/" + doi,
            "per-page": 1,
        })

        return r[0] if r else None

    def search(self, query, n=3):
        return self._get({
            "search": query[:300],
            "per-page": n,
        })

    @staticmethod
    def _parse(w):
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}

        best = w.get("best_oa_location") or {}

        oa_pdf = (
            best.get("pdf_url")
            or loc.get("pdf_url")
            or None
        )

        doi = (
            (w.get("doi") or "")
            .replace("https://doi.org/", "")
            .lower()
            or None
        )

        return PaperMatch(
            source="openalex",
            doi=doi,
            title=w.get("display_name") or w.get("title") or "",
            authors=[
                (a.get("author") or {}).get("display_name", "")
                for a in w.get("authorships", [])
                if a.get("author")
            ],
            year=w.get("publication_year"),
            journal=src.get("display_name"),
            url=loc.get("landing_page_url") or w.get("doi"),
            openalex_id=w.get("id"),
            abstract=rebuild_abstract(
                w.get("abstract_inverted_index")
            ),
            oa_pdf_url=oa_pdf,
            openalex_retracted=w.get("is_retracted"),
        )

    def full_text(self, url):
        """Extract text from an open-access PDF, or None.

        Used as a fallback when Europe PMC has no XML full text. The PDF
        is capped by size and page count, and a parse failure is normal
        (some OA links are landing pages, not PDFs).
        """

        if not settings.full_text_mode or not url:
            return None

        data = self.api.get_bytes(
            "openalex",
            url,
            max_bytes=settings.max_fulltext_bytes,
        )

        return clip(pdf_to_text(data))