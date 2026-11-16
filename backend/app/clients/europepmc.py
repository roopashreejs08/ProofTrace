from ..config import settings
from ..schemas import PaperMatch
from .fulltext import clip, jats_to_text


BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"


# Words in a Europe PMC notice type that mean the record was acted on.
_RETRACT = ("retract", "withdraw", "removed")
_CONCERN = ("concern",)
_CORRECT = ("correct", "erratum", "corrigendum", "addendum")


def _interesting(t):
    t = (t or "").lower()
    return any(
        k in t
        for k in (_RETRACT + _CONCERN + _CORRECT)
    )


class EuropePmcClient:
    """Retraction notices from Europe PMC.

    Europe PMC aggregates PubMed, PMC and Agricola and is free and
    key-less, which is why it is used alongside Crossref and OpenAlex.
    A record that has been retracted carries the notice in its
    ``commentCorrectionList`` and/or ``pubTypeList``.
    """

    def __init__(self, api):
        self.api = api

    def notices_for(self, doi):
        d = self.api.get_json(
            "europepmc",
            BASE + "/search",
            {
                "query": 'DOI:"%s"' % doi,
                "format": "json",
                "resultType": "core",
                "pageSize": 1,
            },
            ttl_hours=settings.retraction_cache_ttl_hours,
        )

        out = []

        for r in (
            ((d or {}).get("resultList") or {}).get("result") or []
        ):
            pmid = r.get("pmid")

            url = (
                "https://europepmc.org/article/MED/" + str(pmid)
                if pmid
                else "https://europepmc.org/search?query=DOI:%22"
                + doi
                + "%22"
            )

            corrections = (
                (r.get("commentCorrectionList") or {})
                .get("commentCorrection")
                or []
            )

            for c in corrections:
                t = c.get("type")

                if _interesting(t):
                    out.append({
                        "type": t,
                        "doi": doi,
                        "source": "europepmc",
                        "url": url,
                    })

            for pt in (
                (r.get("pubTypeList") or {}).get("pubType") or []
            ):
                if _interesting(pt):
                    out.append({
                        "type": pt,
                        "doi": doi,
                        "source": "europepmc",
                        "url": url,
                    })

        return out

    # ---- Paper lookup (used by the Paper Finder) ----

    @staticmethod
    def _parse(r):
        authors = []

        for a in (
            (r.get("authorList") or {}).get("author") or []
        ):
            name = a.get("fullName") or (
                (a.get("firstName") or "")
                + " "
                + (a.get("lastName") or "")
            ).strip()

            if name:
                authors.append(name)

        if not authors and r.get("authorString"):
            authors = [
                s.strip()
                for s in r["authorString"].split(",")
                if s.strip()
            ]

        year = r.get("pubYear")

        try:
            year = int(year) if year else None
        except (TypeError, ValueError):
            year = None

        doi = (r.get("doi") or "").lower() or None

        return PaperMatch(
            source="europepmc",
            doi=doi,
            title=r.get("title") or "",
            authors=authors,
            year=year,
            journal=r.get("journalTitle"),
            url=EuropePmcClient.record_url(doi) if doi else None,
            abstract=r.get("abstractText"),
        )

    def _core(self, query, n):
        d = self.api.get_json(
            "europepmc",
            BASE + "/search",
            {
                "query": query[:300],
                "format": "json",
                "resultType": "core",
                "pageSize": n,
            },
        )

        return [
            self._parse(r)
            for r in (
                ((d or {}).get("resultList") or {}).get("result")
                or []
            )
        ]

    def search(self, query, n=3):
        return self._core(query, n)

    def by_doi(self, doi):
        r = self._core('DOI:"%s"' % doi, 1)

        return r[0] if r else None

    def full_text(self, doi):
        """Open-access full text from Europe PMC, or None.

        Europe PMC serves JATS full text only for articles that are open
        access and deposited in PMC, so a miss is normal, not an error.
        """

        if not settings.full_text_mode or not doi:
            return None

        d = self.api.get_json(
            "europepmc",
            BASE + "/search",
            {
                "query": 'DOI:"%s"' % doi,
                "format": "json",
                "resultType": "core",
                "pageSize": 1,
            },
        )

        res = (
            ((d or {}).get("resultList") or {}).get("result")
            or []
        )

        if not res:
            return None

        r = res[0]

        pmcid = r.get("pmcid")
        open_access = str(r.get("isOpenAccess") or "").upper() == "Y"

        if not pmcid or not open_access:
            return None

        xml = self.api.get_text(
            "europepmc",
            BASE + "/" + str(pmcid) + "/fullTextXML",
        )

        return clip(jats_to_text(xml))

    @staticmethod
    def record_url(doi):
        return (
            "https://europepmc.org/search?query=DOI:%22" + doi + "%22"
        )
