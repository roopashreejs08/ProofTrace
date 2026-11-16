import re

from ..config import settings
from ..schemas import PaperMatch


BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


_RETRACT = ("retract", "withdraw", "removed")
_CONCERN = ("concern",)
_CORRECT = ("correct", "erratum", "corrigendum", "addendum")

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s]+", re.I)


def _interesting(t):
    t = (t or "").lower()
    return any(
        k in t
        for k in (_RETRACT + _CONCERN + _CORRECT)
    )


class PubMedClient:
    """PubMed via the free E-utilities API.

    Used for two things: retraction status (``esearch`` resolves a DOI to
    a PMID, ``esummary`` returns the publication types) and, since PubMed
    indexes biomedical work that Crossref and OpenAlex sometimes miss,
    bibliographic lookup for the Paper Finder.
    """

    def __init__(self, api):
        self.api = api

    def _get(self, path, params, ttl_hours=None):
        params = dict(params)
        params["tool"] = "ProofTrace"
        params["email"] = settings.contact_email

        return self.api.get_json(
            "pubmed",
            BASE + path,
            params,
            ttl_hours=(
                settings.retraction_cache_ttl_hours
                if ttl_hours is None
                else ttl_hours
            ),
        )

    def _summaries(self, ids, ttl_hours=None):
        if not ids:
            return []

        d = self._get(
            "/esummary.fcgi",
            {
                "db": "pubmed",
                "id": ",".join(ids),
                "retmode": "json",
            },
            ttl_hours=ttl_hours,
        )

        result = (d or {}).get("result") or {}

        return [
            result[pid]
            for pid in result.get("uids") or []
            if pid in result
        ]

    # ---- Paper lookup (used by the Paper Finder) ----

    @staticmethod
    def _parse(doc):
        doi = None

        for aid in doc.get("articleids") or []:
            if (aid.get("idtype") or "").lower() == "doi":
                doi = (aid.get("value") or "").lower() or None
                break

        if not doi:
            m = _DOI_RE.search(doc.get("elocationid") or "")

            if m:
                doi = m.group(0).rstrip(".").lower()

        authors = [
            a.get("name")
            for a in doc.get("authors") or []
            if a.get("name")
        ]

        year = None
        m = re.search(r"(?:19|20)\d{2}", doc.get("pubdate") or "")

        if m:
            year = int(m.group(0))

        return PaperMatch(
            source="pubmed",
            doi=doi,
            title=(doc.get("title") or "").rstrip("."),
            authors=authors,
            year=year,
            journal=doc.get("fulljournalname") or doc.get("source"),
            url=(
                "https://pubmed.ncbi.nlm.nih.gov/"
                + str(doc.get("uid"))
                + "/"
                if doc.get("uid")
                else None
            ),
        )

    def search(self, query, n=3):
        s = self._get(
            "/esearch.fcgi",
            {
                "db": "pubmed",
                "term": query[:300],
                "retmode": "json",
                "retmax": n,
            },
            ttl_hours=settings.cache_ttl_hours,
        )

        ids = (
            ((s or {}).get("esearchresult") or {}).get("idlist")
            or []
        )

        return [
            self._parse(doc)
            for doc in self._summaries(
                ids,
                ttl_hours=settings.cache_ttl_hours,
            )
        ]

    def by_doi(self, doi):
        s = self._get(
            "/esearch.fcgi",
            {
                "db": "pubmed",
                "term": doi + "[doi]",
                "retmode": "json",
                "retmax": 1,
            },
            ttl_hours=settings.cache_ttl_hours,
        )

        ids = (
            ((s or {}).get("esearchresult") or {}).get("idlist")
            or []
        )

        docs = self._summaries(
            ids,
            ttl_hours=settings.cache_ttl_hours,
        )

        return self._parse(docs[0]) if docs else None

    # ---- Retraction notices ----

    def notices_for(self, doi):
        s = self._get("/esearch.fcgi", {
            "db": "pubmed",
            "term": doi + "[doi]",
            "retmode": "json",
            "retmax": 3,
        })

        ids = ((s or {}).get("esearchresult") or {}).get("idlist") or []

        if not ids:
            return []

        out = []

        for doc in self._summaries(ids):
            for pt in doc.get("pubtype") or []:
                if _interesting(pt):
                    out.append({
                        "type": pt,
                        "doi": doi,
                        "source": "pubmed",
                        "url": (
                            "https://pubmed.ncbi.nlm.nih.gov/"
                            + str(doc.get("uid"))
                            + "/"
                        ),
                    })

        return out

    @staticmethod
    def record_url(doi):
        return "https://pubmed.ncbi.nlm.nih.gov/?term=" + doi
