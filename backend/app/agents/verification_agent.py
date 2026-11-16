import time

from ..schemas import (
    CitationReport,
    EvidenceResult,
    PaperMatch,
    RetractionResult,
    Verdict,
)

from .claim_extractor import NO_CLAIM


def decide(claim, cit, m, r, e):
    cav = []

    if m is None or m.status in ("not_found", "error"):

        if m is not None and m.status == "error":
            why = (
                "The scholarly APIs could not be reached for this citation "
                "(" + " ".join(m.discrepancies) + "). Try again later."
            )

        elif not cit.raw_reference and not cit.doi:
            why = (
                "The text gives only a marker (" + cit.marker
                + ") with no reference details, so no lookup was possible."
            )

        else:
            why = (
                "No matching publication was found in Crossref, OpenAlex, "
                "Europe PMC or PubMed. "
                "This does not mean the paper is fabricated: "
                "the reference may be incomplete, mistyped, or indexed "
                "elsewhere. Check it manually."
            )

        if m is not None and m.status != "error":
            cav.extend(m.discrepancies)

        return Verdict.UNRESOLVABLE, why, cav

    if m.status == "possible":
        why = (
            "A similar record was found ("
            + (m.title or "untitled")
            + ") but it does not match the reference closely "
            "enough to confirm it is the cited work."
        )

        return Verdict.UNRESOLVABLE, why, list(m.discrepancies)

    cav.extend(m.discrepancies)

    # A confirmed record whose year disagrees with the reference is a
    # real discrepancy and must not be presented as a clean verification.
    year_bad = m.checks.get("year_match") is False

    if year_bad:
        cav.append(
            "The cited year (%s) does not match the published year (%s)."
            % (cit.year, m.year)
        )

    if r is not None and r.status == "retracted":
        return (
            Verdict.RETRACTED,
            "This publication has a retraction notice on record ("
            + ", ".join(r.sources)
            + "). Any claim that relies on it should be re-examined.",
            cav,
        )

    if r is not None and r.status == "concern":
        cav.append(
            "An expression of concern is on record for this publication."
        )

    if r is not None and r.status == "unknown":
        cav.append(
            "Retraction status could not be fully checked."
        )

    if r is not None and getattr(r, "corrections", None):
        cav.append(
            "A correction notice is on record; the record was amended "
            "but not retracted."
        )

    if claim == NO_CLAIM:
        if year_bad:
            return (
                Verdict.WEAK_SUPPORT,
                "The publication exists and matches the reference, and "
                "no retraction was found, but the cited year disagrees "
                "with the published year. No claim was supplied, so "
                "claim support was not evaluated.",
                cav,
            )

        return (
            Verdict.VERIFIED,
            "The publication exists and matches the reference, and "
            "no retraction was found. No claim was supplied, so "
            "claim support was not evaluated.",
            cav,
        )

    e = e or EvidenceResult()

    if e.limitation:
        cav.append(e.limitation)

    pct = round(e.confidence * 100)

    what = "full text" if e.text_source == "full_text" else "abstract"

    if e.stance == "contradicts" and e.confidence >= 0.6:
        return (
            Verdict.CONTRADICTED,
            "The %s appears to contradict the claim "
            "(confidence %d%%). %s" % (what, pct, e.rationale),
            cav,
        )

    if e.stance == "supports" and e.confidence >= 0.65:

        if e.method != "llm":
            return (
                Verdict.WEAK_SUPPORT,
                "The publication exists and the available text appears "
                "to support the claim, but this was judged by keyword "
                "overlap rather than AI reading, so it cannot be "
                "verified.",
                cav,
            )

        if m.checks.get("author_match") is False:
            return (
                Verdict.WEAK_SUPPORT,
                "The %s supports the claim, but the cited author "
                "does not match the record, so the attribution may be wrong."
                % what,
                cav,
            )

        if year_bad:
            return (
                Verdict.WEAK_SUPPORT,
                "The %s supports the claim, but the cited year "
                "does not match the published record, so the citation "
                "may point to the wrong work." % what,
                cav,
            )

        return (
            Verdict.VERIFIED,
            "The publication exists, matches the reference, and its "
            "%s supports the claim (confidence %d%%). %s"
            % (what, pct, e.rationale),
            cav,
        )

    # No evidence was actually evaluated (e.g. no abstract available).
    # Say so plainly instead of implying the paper fails to support it.
    if e.method == "none":
        why = (
            "The publication exists and matches the reference, but claim "
            "support could not be assessed."
        )

        detail = (e.limitation or e.rationale or "").strip()

        if detail and "could not be assessed" not in detail.lower():
            why += " " + detail

        return Verdict.WEAK_SUPPORT, why, cav

    # The publication is real, but the text was not enough to confirm the
    # claim. Name the actual situation rather than a vague "does not
    # clearly support", which reads as a finding when it often is not.
    if e.stance == "partially_supports":
        why = (
            "The publication exists, but the available evidence supports "
            "only part of the claim."
        )

    elif e.stance == "neutral":
        why = (
            "The publication exists, but the available evidence does not "
            "confirm or contradict the claim."
        )

    else:
        why = (
            "The publication exists, but the available text did not "
            "address the claim directly."
        )

    return (
        Verdict.WEAK_SUPPORT,
        why + (" " + e.rationale if e.rationale else ""),
        cav,
    )


class VerificationAgent:

    def __init__(self, memory):
        self.memory = memory

    def run(self, inv, progress, notes, context=None):
        items = self.memory.get_items(inv)

        pf = self.memory.get_findings(
            inv,
            "paper_finder",
        )

        rc = self.memory.get_findings(
            inv,
            "retraction_checker",
        )

        ea = self.memory.get_findings(
            inv,
            "evidence_analyst",
        )

        reports = []
        errors = 0

        for n, it in enumerate(items, 1):

            try:
                m = (
                    PaperMatch(**pf[it.id])
                    if it.id in pf
                    else None
                )

                # The full text is read by the Evidence Analyst from the
                # stored finding; it is not copied into the report, which
                # would otherwise carry a copy of every paper.
                if m is not None:
                    m.full_text = None

                r = (
                    RetractionResult(**rc[it.id])
                    if it.id in rc
                    else None
                )

                e = (
                    EvidenceResult(**ea[it.id])
                    if it.id in ea
                    else None
                )

                verdict, why, cav = decide(
                    it.claim,
                    it.citation,
                    m,
                    r,
                    e,
                )

            except Exception as exc:
                errors += 1
                verdict, why, cav = (
                    Verdict.UNRESOLVABLE,
                    "This citation could not be evaluated: "
                    + str(exc),
                    [],
                )
                m = r = e = None

            reports.append(
                CitationReport(
                    item_id=it.id,
                    claim=it.claim,
                    citation=it.citation,
                    verdict=verdict,
                    explanation=why,
                    caveats=cav,
                    publication_exists=bool(
                        m and m.status == "matched"
                    ),
                    match=m,
                    retraction=r,
                    evidence=e,
                )
            )

            progress(
                n,
                len(items),
                "Reviewed %d of %d citations" % (n, len(items)),
            )

        counts = {
            v.value: 0
            for v in Verdict
        }

        for rp in reports:
            counts[rp.verdict.value] += 1

        context = context or {}

        report = {
            "summary": dict(
                total=len(reports),
                **counts,
            ),
            "citations": [
                rp.model_dump(mode="json")
                for rp in reports
            ],
            "notes": notes,
            "generated_at": time.time(),
            "extraction": context.get("extraction"),
            "ai": context.get("ai"),
        }

        return {
            "notes": [],
            "errors": errors,
            "failed": [],
            "data": report,
        }
