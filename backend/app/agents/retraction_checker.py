import time
from urllib.parse import quote

from ..schemas import RetractionResult


RETRACT = ("retract", "withdrawal", "removed")
CONCERN = ("concern",)
CORRECT = ("correction", "erratum", "corrigendum", "addendum")


def _norm_entry(u):
    return {
        "type": str(u.get("type") or u.get("label") or "").lower(),
        "doi": u.get("DOI") or u.get("doi"),
        "source": u.get("source"),
    }


def split_notices(updates):
    """Classify update notices into (status, notices, corrections).

    Corrections are kept separate from retractions and expressions of
    concern so the UI can show them without implying misconduct.
    """

    status = "clear"
    notices = {}
    corrections = {}

    for u in updates or []:
        entry = _norm_entry(u)
        t = entry["type"]

        if not t:
            continue

        if any(k in t for k in RETRACT):
            status = "retracted"
            notices[(t, entry["doi"])] = entry

        elif any(k in t for k in CONCERN):
            if status != "retracted":
                status = "concern"
            notices[(t, entry["doi"])] = entry

        elif any(k in t for k in CORRECT):
            corrections[(t, entry["doi"])] = entry

    return status, list(notices.values()), list(corrections.values())


def classify(updates):
    # Backwards-compatible 2-tuple used by the unit tests.
    status, notices, _ = split_notices(updates)
    return status, notices


class RetractionChecker:
    """Check a matched DOI against several retraction sources.

    Sources are Crossref (which carries Retraction Watch data), OpenAlex
    and, when available, Europe PMC and PubMed. A "clear" result is only
    reported for the sources that actually responded; a failed source is
    recorded as partial coverage rather than silently ignored.
    """

    def __init__(self, memory, crossref, europepmc=None, pubmed=None):
        self.memory = memory
        self.crossref = crossref
        self.europepmc = europepmc
        self.pubmed = pubmed

    def run(self, inv, progress):
        items = self.memory.get_items(inv)

        found = self.memory.get_findings(
            inv,
            "paper_finder",
        )

        errors = 0
        partial = 0
        failed = []
        retracted = 0
        concerns = 0

        for n, it in enumerate(items, 1):
            res, err = self.check(found.get(it.id))

            if err:
                # A hard error is one where no source responded, so the
                # status is genuinely unknown. A partial failure (some
                # sources down, at least one answered) keeps its status
                # but is still reported honestly.
                if res.status == "unknown":
                    errors += 1
                    failed.append(it.id)
                else:
                    partial += 1

            if res.status == "retracted":
                retracted += 1
            elif res.status == "concern":
                concerns += 1

            self.memory.save_finding(
                inv,
                it.id,
                "retraction_checker",
                res.model_dump(),
            )

            progress(
                n,
                len(items),
                "Checked retraction status for %d of %d"
                % (n, len(items)),
            )

        notes = []

        if retracted:
            notes.append(
                "%d cited publication(s) have a retraction notice on "
                "record." % retracted
            )

        if errors:
            notes.append(
                "%d retraction lookup(s) failed; those citations are "
                "marked unknown, not clear." % errors
            )

        if partial:
            notes.append(
                "%d citation(s) had only partial retraction coverage "
                "(one or more sources were unavailable); the status "
                "shown comes from the sources that responded." % partial
            )

        return {
            "notes": notes,
            "errors": errors,
            "failed": failed,
            "data": {
                "retracted": retracted,
                "concern": concerns,
                "errors": errors,
                "partial": partial,
            },
        }

    def check_document(self, doi):
        """Retraction check for the uploaded document's own DOI."""

        if not doi:
            return None

        res, _ = self.check({
            "status": "matched",
            "doi": doi,
        })

        return res

    def check(self, m):
        """Return (RetractionResult, error_message).

        The error message is non-empty when a source could not be
        queried. It is only a *hard* error (status ``unknown``) when no
        source responded at all; otherwise the status stands and the
        failure is recorded as partial coverage.
        """

        if (
            not m
            or m.get("status") != "matched"
            or not m.get("doi")
        ):
            return RetractionResult(
                status="unknown",
                note=(
                    "No confirmed publication record with a DOI "
                    "to check."
                ),
            ), ""

        doi = m["doi"]

        updates = list(m.get("crossref_updates") or [])
        extra = []
        checked = []
        urls = []
        errors = []

        # Crossref, including Retraction Watch data.
        try:
            updates += self.crossref.updates_for(doi)
            checked.append("crossref")
        except Exception as e:
            errors.append("Crossref: " + str(e))

        urls.append(
            "https://api.crossref.org/works/" + quote(doi, safe="/")
        )

        # Europe PMC.
        if self.europepmc is not None:
            try:
                extra += self.europepmc.notices_for(doi)
                checked.append("europepmc")
            except Exception as e:
                errors.append("Europe PMC: " + str(e))

            urls.append(
                "https://europepmc.org/search?query=DOI:%22"
                + doi
                + "%22"
            )

        # PubMed.
        if self.pubmed is not None:
            try:
                extra += self.pubmed.notices_for(doi)
                checked.append("pubmed")
            except Exception as e:
                errors.append("PubMed: " + str(e))

            urls.append(
                "https://pubmed.ncbi.nlm.nih.gov/?term=" + doi
            )

        # The OpenAlex retraction flag travels with the match.
        if m.get("openalex_retracted"):
            extra.append({
                "type": "retracted",
                "doi": doi,
                "source": "openalex",
            })
            checked.append("openalex")

        status, notices, corrections = split_notices(updates + extra)

        if m.get("openalex_retracted"):
            status = "retracted"

        sources = sorted({
            (n.get("source") or "")
            for n in notices + corrections
            if n.get("source")
        })

        err = "; ".join(errors)

        # If every source failed, the status genuinely cannot be known.
        if status == "clear" and not checked:
            status = "unknown"

        note = self._note(status, err, checked, corrections)

        return RetractionResult(
            status=status,
            sources=sources,
            checked_sources=checked,
            source_urls=urls,
            notices=notices,
            corrections=corrections,
            checked_at=time.time(),
            note=note,
        ), err

    @staticmethod
    def _note(status, err, checked, corrections):
        covered = ", ".join(checked) if checked else "no source"

        if status == "retracted":
            note = (
                "A retraction or withdrawal notice is on record "
                "(confirmed by " + covered + ")."
            )

        elif status == "concern":
            note = (
                "An expression of concern is on record for this "
                "publication (confirmed by " + covered + ")."
            )

        elif status == "clear" and not err:
            note = (
                "No retraction notice found in " + covered
                + " at check time. This is not proof that none exists."
            )

        elif status == "clear" and err:
            note = (
                "No retraction notice was found in " + covered
                + ", but these sources could not be reached: " + err
                + " Coverage was incomplete."
            )

        elif status == "unknown":
            note = (
                "The retraction status could not be confirmed because "
                "the notice lookup failed: " + err
            )

        else:
            note = ""

        if corrections:
            note += (
                " %d correction notice(s) were also found; a "
                "correction is not misconduct." % len(corrections)
            )

        return note
