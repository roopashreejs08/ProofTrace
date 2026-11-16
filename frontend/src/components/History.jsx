import { useEffect, useState } from 'react'

import { listInvestigations } from '../api'
import { EmptyState, FOCUS, Skeleton } from './ui'


function LoadingHistory() {
  return (
    <section className="space-y-5" role="status" aria-live="polite">

      <span className="sr-only">Loading investigations...</span>

      <div className="space-y-2">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>

      <div className="space-y-3">

        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="mt-3 h-3 w-40" />
          </div>
        ))}

      </div>

    </section>
  )
}


export default function History({ onOpen, onNew }) {
  const [rows, setRows] = useState(null)
  const [err, setErr] = useState('')


  useEffect(() => {
    let active = true

    listInvestigations()
      .then((data) => {
        if (active) {
          setRows(data)
        }
      })
      .catch((e) => {
        if (active) {
          setErr(e.message)
          setRows([])
        }
      })

    return () => {
      active = false
    }
  }, [])


  if (!rows) {
    return <LoadingHistory />
  }


  if (!rows.length) {
    return (
      <EmptyState
        title="No investigations yet"
        action={
          onNew && (
            <button
              type="button"
              onClick={onNew}
              className={`rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 ${FOCUS}`}
            >
              Start a new check
            </button>
          )
        }
      >
        Every check you run is saved here so you can reopen it later.
        Paste a paragraph with its references and the five agents will
        go to work.

        {err && (
          <span role="alert" className="mt-3 block text-red-600">
            Could not load history: {err}
          </span>
        )}
      </EmptyState>
    )
  }


  return (
    <section className="space-y-5">

      <div>
        <h2 className="text-xl font-bold text-slate-900">
          Past investigations
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          Open a previous investigation to review its results.
        </p>
      </div>


      <div className="space-y-3">

        {rows.map((r) => (
          <button
            type="button"
            key={r.id}
            onClick={() => onOpen(r.id)}
            className={`block w-full rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-indigo-300 hover:shadow-md ${FOCUS}`}
          >

            <p className="font-medium leading-relaxed text-slate-800">
              {r.preview || 'Research investigation'}
            </p>

            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">

              <span>
                {r.created_at
                  ? new Date(r.created_at * 1000).toLocaleString()
                  : 'Date unavailable'}
              </span>

              <span>·</span>

              <span className="font-semibold uppercase">
                {r.status}
              </span>

            </div>

          </button>
        ))}

      </div>

    </section>
  )
}