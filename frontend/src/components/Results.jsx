import { useState } from 'react'

import { VERDICTS } from '../verdicts'
import {
  downloadReportHtml,
  downloadReportJson,
  printReportHtml,
} from '../reportExport'
import { EmptyState, FOCUS } from './ui'


const ORDER = [
  'VERIFIED',
  'WEAK SUPPORT',
  'RETRACTED',
  'UNRESOLVABLE',
  'CONTRADICTED',
]


const safe = (u) =>
  typeof u === 'string' &&
  (u.startsWith('https://') || u.startsWith('http://'))


const SEGMENTATION_LABELS = {
  numbered: 'numbered entries',
  unnumbered: 'author–year entries',
  'inline-numbered': 'inline numbered markers',
  llm: 'AI-assisted split (no clear separators)',
  none: 'no reference list was found',
}


const fmtTime = (ts) =>
  ts ? new Date(ts * 1000).toLocaleString() : null


function Stat({ label, value, cls }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">

      <div className={`text-2xl font-bold ${cls}`}>
        {value}
      </div>

      <div className="mt-1 text-xs font-medium text-slate-500">
        {label}
      </div>

    </div>
  )
}


function Row({ k, children }) {
  if (
    children === null ||
    children === undefined ||
    children === ''
  ) {
    return null
  }

  return (
    <div className="border-b border-slate-100 py-2 last:border-0">

      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        {k}
      </dt>

      <dd className="mt-1 break-words text-sm text-slate-700">
        {children}
      </dd>

    </div>
  )
}


function TextSourceBadge({ e }) {
  if (!e?.text_source) return null

  if (e.text_source === 'full_text') {
    return (
      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200">
        Open-access full text
      </span>
    )
  }

  return (
    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">
      Abstract only
    </span>
  )
}


function MethodBadge({ e }) {
  if (!e) return null

  if (e.method === 'llm') {
    return (
      <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-700 ring-1 ring-indigo-200">
        AI analysis{e.model ? ` · ${e.model}` : ''}
      </span>
    )
  }

  if (e.method === 'lexical') {
    return (
      <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800 ring-1 ring-amber-200">
        Keyword fallback
      </span>
    )
  }

  return null
}


function Evidence({ m, r, e }) {
  const hasPaper = m && m.title

  return (
    <div className="mt-4 space-y-4">

      <section className="rounded-xl border border-slate-200 p-4">

        <h4 className="mb-3 text-sm font-bold text-slate-800">
          Publication record
        </h4>

        {hasPaper ? (
          <dl>

            <Row k="Title">
              {m.title}
            </Row>

            <Row k="Authors">
              {m.authors?.slice(0, 6).join(', ')}
            </Row>

            <Row k="Year">
              {m.year}
            </Row>

            <Row k="Journal">
              {m.journal}
            </Row>

            <Row k="DOI">
              {m.doi}
            </Row>

            <Row k="Source">
              {m.source}
            </Row>

            <Row k="Match status">
              {m.status}
            </Row>

            <Row k="Title match">
              {m.checks?.title_coverage != null
                ? `${Math.round(m.checks.title_coverage * 100)}%`
                : null}
            </Row>

            <Row k="Year match">
              {m.checks?.year_match === true
                ? 'Yes'
                : m.checks?.year_match === false
                  ? 'No'
                  : null}
            </Row>

            <Row k="Author match">
              {m.checks?.author_match === true
                ? 'Yes'
                : m.checks?.author_match === false
                  ? 'No'
                  : null}
            </Row>

            {m.discrepancies?.length > 0 && (
              <Row k="Discrepancies">
                <ul className="list-disc space-y-1 pl-5 text-xs text-amber-800">
                  {m.discrepancies.map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ul>
              </Row>
            )}

            {safe(m.url) && (
              <div className="pt-3">

                <a
                  href={m.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`rounded text-sm font-semibold text-indigo-600 hover:text-indigo-800 ${FOCUS}`}
                >
                  Open original source ↗
                </a>

              </div>
            )}

          </dl>
        ) : (
          <p className="text-sm text-slate-500">
            No publication record was matched.
          </p>
        )}

      </section>


      <section className="rounded-xl border border-slate-200 p-4">

        <h4 className="mb-3 text-sm font-bold text-slate-800">
          Retraction check
        </h4>

        {r ? (
          <dl>

            <Row k="Status">
              {r.status}
            </Row>

            <Row k="Notices">
              {r.notices?.map((n) => n.type).filter(Boolean).join(', ')}
            </Row>

            <Row k="Corrections">
              {r.corrections?.map((n) => n.type).filter(Boolean).join(', ')}
            </Row>

            <Row k="Sources with a notice">
              {r.sources?.join(', ')}
            </Row>

            <Row k="Sources checked">
              {r.checked_sources?.join(', ')}
            </Row>

            <Row k="Last checked">
              {fmtTime(r.checked_at)}
            </Row>

            {r.source_urls?.filter(safe).length > 0 && (
              <Row k="Where to verify">
                <div className="flex flex-col gap-1">
                  {r.source_urls.filter(safe).map((u) => (
                    <a
                      key={u}
                      href={u}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`break-all rounded text-xs font-semibold text-indigo-600 hover:text-indigo-800 ${FOCUS}`}
                    >
                      {u}
                    </a>
                  ))}
                </div>
              </Row>
            )}

            <Row k="Note">
              {r.note}
            </Row>

          </dl>
        ) : (
          <p className="text-sm text-slate-500">
            Not checked.
          </p>
        )}

      </section>


      <section className="rounded-xl border border-slate-200 p-4">

        <div className="mb-3 flex flex-wrap items-center gap-2">

          <h4 className="text-sm font-bold text-slate-800">
            Claim evidence
          </h4>

          <TextSourceBadge e={e} />

          <MethodBadge e={e} />

        </div>

        {e ? (
          <dl>

            <Row k="Stance">
              {e.stance?.replaceAll('_', ' ')}
            </Row>

            <Row k="Evidence source">
              {e.text_source === 'full_text'
                ? 'Open-access full text'
                : e.text_source === 'abstract'
                  ? 'Abstract'
                  : null}
            </Row>

            <Row k="Confidence">
              {e.confidence != null
                ? `${Math.round(e.confidence * 100)}%`
                : null}
            </Row>

            <Row k="Rationale">
              {e.rationale}
            </Row>

            {e.quote && (
              <Row k="Supporting quote">
                <blockquote className="border-l-2 border-indigo-300 pl-3 italic text-slate-600">
                  {e.quote}
                </blockquote>
              </Row>
            )}

            <Row k="Limitation">
              {e.limitation}
            </Row>

            {e.gemini_error && (
              <Row k="AI error">
                <span className="text-xs text-amber-700">
                  {e.gemini_error}
                </span>
              </Row>
            )}

          </dl>
        ) : (
          <p className="text-sm text-slate-500">
            No evidence analysed.
          </p>
        )}

      </section>

    </div>
  )
}


function CitationCard({ c }) {
  const [open, setOpen] = useState(false)

  const v =
    VERDICTS[c.verdict] || VERDICTS.UNRESOLVABLE

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">

      <div className="flex flex-wrap items-start justify-between gap-3">

        <div className="min-w-0 flex-1">

          <span className="text-xs font-bold text-indigo-600">
            {c.citation?.marker || 'Citation'}
          </span>

          <p className="mt-2 text-sm font-medium leading-relaxed text-slate-900">
            {c.claim}
          </p>

        </div>

        <span
          className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ring-1 ${v.cls}`}
        >
          {v.label}
        </span>

      </div>


      {c.citation?.raw_reference && (
        <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
          {c.citation.raw_reference}
        </p>
      )}


      <p className="mt-3 text-sm leading-relaxed text-slate-600">
        {c.explanation}
      </p>


      {c.caveats?.length > 0 && (
        <div className="mt-3 rounded-lg bg-amber-50 p-3">

          <p className="mb-2 text-xs font-bold text-amber-800">
            Caveats
          </p>

          <ul className="list-disc space-y-1 pl-5 text-xs text-amber-800">

            {c.caveats.map((x, i) => (
              <li key={i}>
                {x}
              </li>
            ))}

          </ul>

        </div>
      )}


      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className={`mt-4 rounded-md text-sm font-semibold text-indigo-600 hover:text-indigo-800 ${FOCUS}`}
      >
        {open ? 'Hide evidence' : 'Show evidence'}
      </button>


      {open && (
        <Evidence
          m={c.match}
          r={c.retraction}
          e={c.evidence}
        />
      )}

    </article>
  )
}


function StatusPanel({ ai, extraction }) {
  if (!ai && !extraction) return null

  return (
    <details className="group rounded-xl border border-slate-200 bg-white text-sm shadow-sm">

      <summary
        className={`flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl px-4 py-3 font-semibold text-slate-700 hover:bg-slate-50 ${FOCUS}`}
      >

        <span>How this run was analysed</span>

        <span className="text-xs font-normal text-slate-400 group-open:hidden">
          Show
        </span>

        <span className="hidden text-xs font-normal text-slate-400 group-open:inline">
          Hide
        </span>

      </summary>

      <ul className="space-y-1 border-t border-slate-100 px-4 py-3 text-xs text-slate-600">

        {extraction && (
          <li>
            Parsed {extraction.references_parsed} bibliography
            entries and {extraction.unique_citations} in-text
            citations from {extraction.input_chars?.toLocaleString?.()}
            {' '}characters
            {extraction.uncited_references
              ? ` (${extraction.uncited_references} uncited reference(s) were not checked)`
              : ''}
            .
          </li>
        )}

        {extraction?.segmentation && (
          <li>
            Reference list split by{' '}
            {SEGMENTATION_LABELS[extraction.segmentation] ||
              extraction.segmentation}
            .
          </li>
        )}

        {ai && (
          <li>
            AI evidence analysis:{' '}
            {ai.enabled
              ? ai.used > 0
                ? `on (${ai.used} claim(s) read by ${ai.model || 'the model'})`
                : ai.lexical > 0
                  ? 'on, but the model was unavailable so keyword fallback was used'
                  : 'on, but no matched paper had an abstract to assess'
              : 'off (no Gemini key configured), so keyword fallback was used'}
            .
          </li>
        )}

        {ai?.full_text_mode && (
          <li>
            Full-text mode:{' '}
            {ai.full_text > 0
              ? `on (${ai.full_text} claim(s) were judged from the open-access full text)`
              : 'on, but no matched paper had open-access full text, so abstracts were used'}
            .
          </li>
        )}

        {ai?.last_error && (
          <li className="text-amber-700">
            Last AI error: {ai.last_error}
          </li>
        )}

      </ul>

    </details>
  )
}


function DocumentBanner({ doc }) {
  if (!doc) return null

  const r = doc.retraction
  const status = r?.status

  const tone =
    status === 'retracted'
      ? 'border-rose-200 bg-rose-50 text-rose-800'
      : status === 'concern'
        ? 'border-amber-200 bg-amber-50 text-amber-800'
        : 'border-slate-200 bg-slate-50 text-slate-700'

  return (
    <div className={`rounded-xl border p-4 text-sm ${tone}`}>

      <p className="font-bold">The uploaded document itself</p>

      <p className="mt-1 break-words">
        DOI: {doc.doi}
        {status ? ` — retraction status: ${status}` : ''}
        {doc.error ? ` — check failed: ${doc.error}` : ''}
      </p>

      {r?.note && (
        <p className="mt-1 text-xs leading-relaxed">{r.note}</p>
      )}

      {r?.checked_at && (
        <p className="mt-1 text-xs">Last checked: {fmtTime(r.checked_at)}</p>
      )}

    </div>
  )
}


export default function Results({ report, inv }) {
  const [filter, setFilter] = useState('ALL')

  const summary = report.summary || {}
  const citations = report.citations || []

  // The export includes the whole investigation when available, so the
  // downloaded report matches everything shown on this page (plus the
  // agent runs and API activity). Falls back to the report alone.
  const full = inv || { report }


  const count = (verdict) => {
    const key = verdict.toLowerCase().replaceAll(' ', '_')

    return (
      summary[verdict] ??
      summary[key] ??
      citations.filter((c) => c.verdict === verdict).length
    )
  }


  const list = citations.filter(
    (c) => filter === 'ALL' || c.verdict === filter
  )


  const chip = (active) =>
    'rounded-full px-3 py-1.5 text-xs font-medium ring-1 transition ' +
    FOCUS + ' ' +
    (
      active
        ? 'bg-indigo-600 text-white ring-indigo-600'
        : 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-50'
    )


  return (
    <section className="space-y-6">

      <div className="flex flex-wrap items-start justify-between gap-3">

        <div>

          <h2 className="text-xl font-bold text-slate-900">
            Investigation report
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Results from the five research-integrity agents.
          </p>

        </div>


        <div className="flex flex-wrap gap-2">

          <button
            type="button"
            onClick={() => downloadReportHtml(full)}
            className={`rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 ${FOCUS}`}
          >
            Download report
          </button>

          <button
            type="button"
            onClick={() => downloadReportJson(full)}
            className={`rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 ${FOCUS}`}
          >
            Download JSON
          </button>

          <button
            type="button"
            onClick={() => printReportHtml(full)}
            className={`rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 ${FOCUS}`}
          >
            Print / Save as PDF
          </button>

        </div>

      </div>


      <StatusPanel
        ai={report.ai}
        extraction={report.extraction}
      />


      <DocumentBanner doc={report.document} />


      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-3">

  <Stat
    label="Total citations"
    value={summary.total ?? citations.length}
    cls="text-slate-800"
  />

  {ORDER.map((k) => (
    <Stat
      key={k}
      label={VERDICTS[k].label}
      value={count(k)}
      cls={VERDICTS[k].num}
    />
  ))}

</div>


      {report.notes?.map((n, i) => (
        <div
          key={i}
          className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
        >
          {n}
        </div>
      ))}


      <div className="flex flex-wrap gap-2">

        <button
          type="button"
          onClick={() => setFilter('ALL')}
          className={chip(filter === 'ALL')}
        >
          All ({citations.length})
        </button>


        {ORDER.map((k) => (
          <button
            type="button"
            key={k}
            onClick={() => setFilter(k)}
            className={chip(filter === k)}
          >
            {VERDICTS[k].label} ({count(k)})
          </button>
        ))}

      </div>


      <div className="space-y-4">

        {list.length > 0 ? (
          list.map((c) => (
            <CitationCard
              key={c.item_id}
              c={c}
            />
          ))
        ) : (
          <EmptyState
            title="No citations match this filter"
            action={
              <button
                type="button"
                onClick={() => setFilter('ALL')}
                className={`rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 ${FOCUS}`}
              >
                Show all citations
              </button>
            }
          >
            This run has no citations with the
            {' '}
            {VERDICTS[filter]?.label || filter}
            {' '}
            verdict. Clear the filter to see the full report.
          </EmptyState>
        )}

      </div>


      <p className="rounded-xl bg-slate-100 p-4 text-xs leading-relaxed text-slate-600">
        ProofTrace checks metadata, retraction records and claim
        evidence. Where an open-access full text is available it
        reads that; otherwise it reads the abstract. Either way,
        treat every verdict as a lead for human review. A paper
        that cannot be found is unresolvable, not proven fabricated.
      </p>

    </section>
  )
}