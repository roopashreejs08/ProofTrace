import re
from urllib.parse import quote

from ..config import settings
from ..schemas import PaperMatch


BASE = "https://api.crossref.org"


def strip_tags(s):
    if not s:
        return None

    return re.sub(
        r"\s+",
        " ",
        re.sub(r"<[^>]+>", " ", s)
    ).strip() or None


def parse_work(m):
    authors = []

    for a in m.get("author", []):
        name = (
            (a.get("given") or "")
            + " "
            + (a.get("family") or "")
        ).strip() or a.get("name", "")

        if name:
            authors.append(name)

    parts = (
        (m.get("issued") or {}).get("date-parts")
        or [[None]]
    )

    year = parts[0][0] if parts and parts[0] else None

    return PaperMatch(
        source="crossref",
        doi=(m.get("DOI") or "").lower() or None,
        title=(m.get("title") or [""])[0],
        authors=authors,
        year=year,
        journal=(m.get("container-title") or [None])[0],
        url=m.get("URL"),
        abstract=strip_tags(m.get("abstract")),
        crossref_updates=m.get("updated-by") or [],
    )


class CrossrefClient:

    def __init__(self, api):
        self.api = api

    def by_doi(self, doi):
        d = self.api.get_json(
            "crossref",
            BASE + "/works/" + quote(doi, safe="/")
        )

        return parse_work(d["message"]) if d else None

    def search(self, query, rows=3):
        d = self.api.get_json(
            "crossref",
            BASE + "/works",
            {
                "query.bibliographic": query[:300],
                "rows": rows,
            }
        )

        return [
            parse_work(m)
            for m in (d or {}).get("message", {}).get("items", [])
        ]

    def updates_for(self, doi):
        # Notices (retractions, corrections, concerns)
        # that point at this DOI.

        d = self.api.get_json(
            "crossref",
            BASE + "/works",
            {
                "filter": "updates:" + doi,
                "rows": 10,
            },
            ttl_hours=settings.retraction_cache_ttl_hours,
        )

        out = []

        for m in (d or {}).get("message", {}).get("items", []):
            for u in m.get("update-to", []):
                if (u.get("DOI") or "").lower() == doi.lower():
                    out.append({
                        "type": u.get("type") or u.get("label"),
                        "doi": m.get("DOI"),
                        "source": u.get("source"),
                    })

        return out