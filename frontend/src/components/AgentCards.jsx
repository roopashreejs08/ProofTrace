import { useState } from 'react'

import { FOCUS } from './ui'


const META = {
  claim_extractor: [
    'Claim Extractor',
    'Finds claims and the citations attached to them',
  ],

  paper_finder: [
    'Paper Finder',
    'Searches Crossref and OpenAlex, validates metadata',
  ],

  retraction_checker: [
    'Retraction Checker',
    'Checks Crossref, OpenAlex, Europe PMC and PubMed for notices',
  ],

  evidence_analyst: [
    'Evidence Analyst',
    'Compares each claim with the available abstract',
  ],

  verification_agent: [
    'Verification Agent',
    'Applies cautious rules and writes the report',
  ],
}


const STATUS = {
  waiting: {
    label: 'Waiting',
    cls: 'bg-slate-100 text-slate-600',
    bar: 'bg-slate-300',
  },

  running: {
    label: 'Running',
    cls: 'bg-indigo-100 text-indigo-700 animate-pulse',
    bar: 'bg-indigo-500',
  },

  completed: {
    label: 'Completed',
    cls: 'bg-emerald-100 text-emerald-700',
    bar: 'bg-emerald-500',
  },

  completed_with_errors: {
    label: 'Partial',
    cls: 'bg-amber-100 text-amber-800',
    bar: 'bg-amber-500',
  },

  failed: {
    label: 'Failed',
    cls: 'bg-red-100 text-red-700',
    bar: 'bg-red-500',
  },

  retrying: {
    label: 'Retrying',
    cls: 'bg-amber-100 text-amber-700 animate-pulse',
    bar: 'bg-amber-500',
  },
}


function isOk(status) {
  const n = Number(status)
  return Number.isFinite(n) && n >= 200 && n < 300
}


function ApiActivity({ rows }) {
  const [open, setOpen] = useState(false)

  if (!rows?.length) return null

  const sources = [
    ...new Set(rows.map((r) => r.source).filter(Boolean)),
  ]

  const failed = rows.filter((r) => !isOk(r.status))
  const cached = rows.filter((r) => r.cached).length

  const summary = [
    `${rows.length} recent call${rows.length === 1 ? '' : 's'}`,
    `${sources.length} source${sources.length === 1 ? '' : 's'}`,
  ]

  if (cached) {
    summary.push(`${cached} cached`)
  }

  summary.push(
    failed.length
      ? `${failed.length} failed`
      : 'all succeeded'
  )

  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">

      <div className="flex flex-wrap items-center justify-between gap-3">

        <div className="min-w-0">

          <h3 className="text-sm font-bold text-slate-800">
            Research API activity
          </h3>

          <p className="mt-1 text-xs text-slate-500">
            {summary.join(' · ')}
          </p>

        </div>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className={`shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 ${FOCUS}`}
        >
          {open ? 'Hide details' : 'Show details'}
        </button>

      </div>


      {failed.length > 0 && (
        <p className="mt-3 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">
          {failed.length} call{failed.length === 1 ? '' : 's'} did not
          return a result. Some citations may be unresolved because a
          source was unavailable, not because the paper is missing.
        </p>
      )}


      {open && (
        <div className="mt-4 space-y-2">

          <p className="text-xs text-slate-400">
            Showing the {rows.length} most recent request
            {rows.length === 1 ? '' : 's'}.
          </p>

          {rows.map((r, i) => (
            <div
              key={r.id || `${r.source}-${i}`}
              className="flex flex-wrap items-center gap-3 border-b border-slate-100 pb-2 text-xs last:border-0 last:pb-0"
            >

              <span className="min-w-20 font-semibold text-slate-700">
                {r.source}
              </span>

              <span className="min-w-0 flex-1 break-all text-slate-500">
                {(r.url || '').replace(/^https?:\/\//, '')}
              </span>

              <span
                className={
                  isOk(r.status)
                    ? 'rounded-md bg-slate-100 px-2 py-1 font-medium text-slate-600'
                    : 'rounded-md bg-amber-100 px-2 py-1 font-medium text-amber-800'
                }
              >
                {r.status}
              </span>

              <span className="text-slate-400">
                {r.cached ? 'cached' : `${r.ms} ms`}
              </span>

            </div>
          ))}

        </div>
      )}

    </section>
  )
}


export default function AgentCards({
  agents,
  citationCount,
  activity,
}) {
  return (
    <section>

      <div className="mb-5 flex flex-wrap items-center justify-between gap-2">

        <h2 className="text-lg font-bold text-slate-900">
          Agent investigation
        </h2>

        <span className="text-sm text-slate-500">
          {citationCount} claim-citation pairs found
        </span>

      </div>


      <div className="grid gap-4 md:grid-cols-2">

        {agents.map((a) => {
          const [name, role] = META[a.agent] || [a.agent, '']

          const st = STATUS[a.status] || STATUS.waiting

          // Report real progress. A clean "completed" is 100%; a
          // partial run shows the proportion of items it actually
          // processed, never a fake 100%.
          const done = a.progress_done || 0
          const total = a.progress_total || 0

          let pct = total
            ? Math.round((done / total) * 100)
            : 0

          if (a.status === 'completed') {
            pct = 100
          }

          return (
            <article
              key={a.agent}
              className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5"
            >

              <div className="mb-3 flex items-start justify-between gap-3">

                <div>
                  <h3 className="font-semibold text-slate-900">
                    {name}
                  </h3>

                  <p className="mt-1 text-xs text-slate-500">
                    {role}
                  </p>
                </div>

                <span
                  className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${st.cls}`}
                >
                  {st.label}
                </span>

              </div>


              <div className="mb-3 h-2 overflow-hidden rounded-full bg-slate-100">

                <div
                  className={`h-full rounded-full transition-all duration-500 ${st.bar}`}
                  style={{
                    width: `${Math.min(100, Math.max(0, pct))}%`,
                  }}
                />

              </div>


              <div className="flex items-center justify-between gap-3 text-xs">

                <span className="min-w-0 text-slate-500">
                  {a.message || 'Waiting to start'}
                </span>

                <span className="shrink-0 font-medium text-slate-600">
                  {pct}%
                </span>

              </div>

            </article>
          )
        })}

      </div>


      <ApiActivity rows={activity} />

    </section>
  )
}