import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from ..config import settings
from ..schemas import PaperMatch
from .claim_extractor import DOI_RE


STOP = {
    "the", "and", "for", "with", "from", "that", "this", "are", "was",
    "were", "into", "using", "based", "their", "its", "his", "her",
}

# A title must overlap the reference this much to be treated as a match.
MATCH_COV = 0.75
POSSIBLE_COV = 0.40


def _strip_accents(s):
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", s or "")
        if not unicodedata.combining(c)
    )


def _stem(t):
    """Very small stemmer: plural/ies only.

    Lets "networks" match "network" and "studies" match "study", which
    are common reasons a genuine match scored just under the threshold.
    """

    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"

    if (
        len(t) > 3
        and t.endswith("s")
        and not t.endswith(("ss", "us", "is"))
    ):
        return t[:-1]

    return t


def norm(s):
    """Lowercase tokens plus a compact (no punctuation) form.

    Accents are stripped and simple plurals folded so a reference and a
    record can match even when they are spelled differently. The compact
    form lets "multi-source" in a reference match the single token
    "multisource" in a title (and vice versa).
    """

    low = _strip_accents((s or "").lower())

    toks = set()

    for t in re.findall(r"[a-z0-9]+", low):
        if len(t) > 2 and t not in STOP:
            toks.add(_stem(t))

    compact = re.sub(r"[^a-z0-9]", "", low)

    return toks, compact


def _name_tokens(s):
    return {
        t
        for t in re.findall(r"[a-z]+", _strip_accents((s or "").lower()))
        if t
    }


def author_matches(first_author, authors):
    """True/False/None for whether the cited surname appears in a record.

    Matching is done on whole normalised tokens, so a short surname such
    as "Li" no longer matches inside "Collins", and accents are ignored.
    """

    if not first_author or not authors:
        return None

    target = _name_tokens(first_author)

    if not target:
        return None

    for a in authors:
        if target <= _name_tokens(a):
            return True

    return False


def tokens(s):
    return norm(s)[0]


def strip_doi(s):
    return DOI_RE.sub(" ", s or "")


def assess(cand, cit, via_doi):
    ref = strip_doi(cit.raw_reference)
    ref_toks, ref_compact = norm(ref)
    title_toks, _ = norm(cand.title)

    cov = None

    if len(ref_toks) >= 3 and title_toks:
        hits = sum(
            1
            for t in title_toks
            if t in ref_toks or t in ref_compact
        )
        cov = hits / len(title_toks)

    year_ok = (
        None
        if not (cit.year and cand.year)
        else abs(cit.year - cand.year) <= 1
    )

    author_ok = author_matches(cit.first_author, cand.authors)

    cand.checks = {
        "title_coverage": None if cov is None else round(cov, 2),
        "year_match": year_ok,
        "author_match": author_ok,
        "via_doi": via_doi,
    }

    d = []

    if year_ok is False:
        d.append(
            "Cited year %s differs from the published year %s."
            % (cit.year, cand.year)
        )

    if author_ok is False:
        d.append(
            "Cited first author %s was not found among the record authors."
            % cit.first_author
        )

    if cov is not None and cov < MATCH_COV:
        d.append(
            "Only %d%% of the record title words appear in the reference text."
            % round(cov * 100)
        )

    cand.score = round(
        0.7 * (1.0 if cov is None else cov)
        + 0.15 * (0.5 if year_ok is None else float(year_ok))
        + 0.15 * (0.5 if author_ok is None else float(author_ok)),
        3,
    )

    if cov is None:
        cand.status = "matched" if via_doi else "possible"

    elif cov >= MATCH_COV:
        cand.status = "matched"

    elif cov >= POSSIBLE_COV:
        cand.status = "possible"

    else:
        cand.status = "not_found"

    # A resolving DOI identifies the work even if the reference's title
    # words are incomplete, as long as nothing actively contradicts it.
    if via_doi and cand.status in ("possible", "not_found"):
        if author_ok is not False and year_ok is not False:
            cand.status = "matched"

            if cov is not None and cov < MATCH_COV:
                d.append(
                    "The DOI matched the record, but only %d%% of its "
                    "title words appear in the reference text."
                    % round(cov * 100)
                )
        else:
            # A DOI was supplied but the record it resolves to does not
            # fit the reference. Say so explicitly, so a wrong DOI is
            # reported as a DOI problem and not just a missing paper.
            d.append(
                "The DOI (%s) resolves to a record that does not match "
                "the reference text." % (cit.doi or "given")
            )

    cand.discrepancies = d


class PaperFinder:

    def __init__(
        self,
        memory,
        crossref,
        openalex,
        europepmc=None,
        pubmed=None,
    ):
        self.memory = memory
        self.crossref = crossref
        self.openalex = openalex
        self.europepmc = europepmc
        self.pubmed = pubmed

        # Lookup order for a DOI and for a bibliographic search. Crossref
        # and OpenAlex are richest; Europe PMC and PubMed are added so a
        # work indexed only in the biomedical databases is still found.
        self.clients = [
            c
            for c in (crossref, openalex, europepmc, pubmed)
            if c is not None
        ]

    def run(self, inv, progress):
        items = self.memory.get_items(inv)

        failed = []
        errors = 0

        def work(it):
            try:
                return self.find(it.citation), None

            except Exception as e:
                return (
                    PaperMatch(
                        source="none",
                        status="error",
                        discrepancies=["Lookup failed: " + str(e)],
                    ),
                    str(e),
                )

        with ThreadPoolExecutor(max_workers=4) as pool:

            for n, (it, (m, err)) in enumerate(
                zip(items, pool.map(work, items)),
                1,
            ):
                if err:
                    errors += 1
                    failed.append(it.id)

                self.memory.save_finding(
                    inv,
                    it.id,
                    "paper_finder",
                    m.model_dump(),
                )

                progress(
                    n,
                    len(items),
                    "Checked %d of %d citations" % (n, len(items)),
                )

        notes = []

        if errors:
            notes.append(
                "%d of %d citation lookups failed (network or API "
                "error); those citations are marked unresolved rather "
                "than assumed absent." % (errors, len(items))
            )

        return {
            "notes": notes,
            "errors": errors,
            "failed": failed,
            "data": {"checked": len(items), "errors": errors},
        }

    def find(self, cit):
        cands, notes, via_doi = [], [], False

        ref = strip_doi(cit.raw_reference)

        if cit.doi:
            m = self._by_doi(cit.doi, notes)

            if m:
                cands.append(m)
                via_doi = True

            else:
                notes.append(
                    "DOI " + cit.doi
                    + " was not found in Crossref, OpenAlex, Europe PMC "
                    "or PubMed. It may be mistyped or registered with "
                    "another agency such as DataCite."
                )

        ref_toks, _ = norm(ref)

        if not cands and len(ref_toks) >= 3:
            cands = self._search(ref, notes)

        if not cands:
            return PaperMatch(
                status="not_found",
                discrepancies=notes,
            )

        for c in cands:
            assess(c, cit, via_doi)

        best = max(cands, key=lambda c: c.score)

        best.discrepancies = notes + best.discrepancies

        if best.status != "not_found":
            self.enrich(best)

        return best

    def _by_doi(self, doi, notes):
        for client in self.clients:
            try:
                m = client.by_doi(doi)
            except Exception as e:
                notes.append("DOI lookup failed: " + str(e))
                m = None

            if m:
                return m

        return None

    def _search(self, ref, notes):
        found = []

        for client in self.clients:
            try:
                found += client.search(ref)
            except Exception as e:
                # One source being down must not lose the others.
                notes.append(
                    getattr(client, "__class__", type(client)).__name__
                    + " search failed: " + str(e)
                )

        return found

    def enrich(self, best):
        # Merge sources: abstract, open-access full text, retraction flag
        # and update notices.

        if not best.doi:
            return

        cr = None
        oa = None

        try:
            cr = (
                best
                if best.source == "crossref"
                else self.crossref.by_doi(best.doi)
            )

            oa = (
                best
                if best.source == "openalex"
                else self.openalex.by_doi(best.doi)
            )

        except Exception:
            # Enrichment is best-effort; the match already stands.
            pass

        if cr:
            best.crossref_updates = cr.crossref_updates
            best.abstract = best.abstract or cr.abstract

        if oa:
            best.openalex_id = oa.openalex_id
            best.openalex_retracted = oa.openalex_retracted
            best.abstract = best.abstract or oa.abstract
            best.oa_pdf_url = best.oa_pdf_url or oa.oa_pdf_url

        # Europe PMC often carries an abstract for works whose Crossref
        # or OpenAlex record has none (for example Nature titles). Use it
        # so the claim is judged on real text instead of being reported
        # as unassessable.
        if not best.abstract and self.europepmc is not None:
            try:
                ep = self.europepmc.by_doi(best.doi)
            except Exception:
                ep = None

            if ep and ep.abstract:
                best.abstract = ep.abstract

        best.url = best.url or (
            "https://doi.org/" + best.doi
        )

        self._add_full_text(best)

    def _add_full_text(self, best):
        """Attach open-access full text when it can be fetched.

        Europe PMC's structured XML is tried first; an OpenAlex
        open-access PDF is the fallback. A miss is normal and leaves the
        match abstract-only.
        """

        if not settings.full_text_mode:
            return

        if self.europepmc is not None:
            try:
                text = self.europepmc.full_text(best.doi)
            except Exception:
                text = None

            if text:
                best.full_text = text
                best.full_text_source = "europepmc"
                return

        if self.openalex is not None and best.oa_pdf_url:
            try:
                text = self.openalex.full_text(best.oa_pdf_url)
            except Exception:
                text = None

            if text:
                best.full_text = text
                best.full_text_source = "openalex-pdf"
