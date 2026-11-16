# Known limitations

These are honest limits of the current version. Where a limit could not
be removed yet, it is recorded here rather than papered over with a fake
100%.

## Verdicts are leads, not judgements

ProofTrace is a triage tool. Every verdict is a lead for a human to
review, not a final judgement about a paper or an author. The tool does
not decide that a paper is fabricated, plagiarised or fraudulent. When
no record can be found the result is `UNRESOLVABLE`, which means "could
not confirm", never "fake".

## Evidence comes from the abstract or the open-access full text

When **full-text mode** is on (the default), the Evidence Analyst tries
to read the whole paper for a matched citation instead of only its
abstract:

* Europe PMC's structured JATS XML is tried first, for articles that are
  open access and deposited in PMC;
* if that is unavailable, an OpenAlex open-access PDF is fetched and its
  text extracted.

When a full text is read, the report labels the evidence "Open-access
full text" and says how many claims were judged that way. When it is not
available — the paper is paywalled, has no open-access copy, or is only
indexed as an abstract — the tool falls back to the abstract and labels
it "Abstract only". Either way a claim can still be `WEAK SUPPORT` even
when the paper would support it, because:

* figures, tables and supplementary files are **not** read;
* PDF text extraction is imperfect (columns, equations and scanned pages
  may be garbled);
* the model still only sees a capped excerpt of the text.

Many matched papers have **no abstract and no open-access full text**. For
those the report says so plainly and does not claim the paper fails to
support anything. Abstracts are taken from Crossref or OpenAlex; when
neither carries one (common for some publishers, e.g. Nature), Europe PMC
is consulted, so fewer papers end up unassessable. Set
`full_text_mode = false` in the backend `.env` to keep every run
abstract-only.

## Coverage spans four databases, but is still incomplete

The Paper Finder looks in **Crossref, OpenAlex, Europe PMC and PubMed**,
so a work indexed only in the biomedical databases can still be found.
Even so, these databases do not index everything: books, theses, some
conference papers, non-English venues and very recent work may be
missing. A missing record **never proves fabrication** — the reference
may be incomplete, mistyped, or indexed elsewhere (for example with
DataCite). `UNRESOLVABLE` means the work could not be confirmed, nothing
more.

## Retraction data depends on source freshness

Retraction information comes from Crossref (with Retraction Watch data),
OpenAlex, Europe PMC and PubMed. A `clear` result means "no notice was
found at check time", not proof that the paper is valid. Notices are
added by publishers over time, so **absence of a notice is not proof of
validity**. The report records which sources responded and when the check
ran, and retraction data is cached for a shorter period than ordinary
metadata so a new notice is picked up sooner.

## Extraction handles common styles, not every format

The extractor copes with numbered (`[1]`, `[1].`, `1.`, `1)`),
inline-numbered and plain unnumbered reference lists, narrative citations
such as `Devlin et al. (2019)` and `(Smith, 2018)`, wrapped continuation
lines and page furniture. It still struggles with some formats:

* accented or particle surnames (for example `van der Berg`,
  `O'Brien`) when matching an author-year citation;
* unnumbered reference lists where a wrapped line is hard to tell apart
  from a new entry, and single undivided blobs (the AI splitter helps but
  is not perfect);
* scanned PDFs, which have no text layer and are rejected with a clear
  error — there is no OCR;
* suffix years (`2020a`/`2020b`) are not yet used to disambiguate.

### A sentence that cites several sources

Claims are extracted one sentence at a time. When a single sentence
cites more than one reference (for example `... guidance [1], and the
handbook [2]`), each reference is judged against the **whole sentence**,
so a model may report that the text supports only part of the claim. The
verdict stays cautious (`WEAK SUPPORT`), but the explanation is written
for the sentence, not for the individual reference. Splitting such a
sentence per reference is not yet done.

## AI output can be wrong

Gemini can misjudge an abstract or a full text. To reduce that risk:

* the prompt marks the claim and the source text as untrusted data and
  says not to follow instructions found inside them;
* the reply is parsed as JSON and the stance must be one of a fixed set;
* a quoted excerpt must be a real substring of the source text (full text
  or abstract), or it is dropped;
* confidence is capped when there is no supporting quote;
* a claim can only be `VERIFIED` when the AI actually read the text.

None of this makes the model infallible. Treat AI-driven verdicts as
leads.

## Only the first citations are processed

The bibliography is always parsed in full, but only the first
`MAX_CITATIONS` citations per run (default **200**) are fully verified,
to bound API and AI usage. The report says when this cap was hit and how
many bibliography entries were never cited in the text.

## AI availability

Gemini models are frequently retired or overloaded. The wrapper
auto-discovers a working model and retries once on 429/503, but some
calls still time out (45s per call). When every model fails, evidence
falls back to keyword overlap, which can never produce `VERIFIED`. The
model actually used is shown in the report.

## Not implemented

* OCR for scanned PDFs (a scanned upload is rejected with a clear error).
* Reading figures, tables and supplementary material, even in full-text
  mode.
* Author disambiguation beyond surname matching.
* Citation-context sentiment across a whole section.
* A separate **Retraction Watch CSV** loaded into its own SQLite table.
  Retraction Watch data is already reached through Crossref's update
  notices and OpenAlex's retraction flag, so a standalone import is not
  used. That keeps the signal fresh without shipping a dated snapshot.
