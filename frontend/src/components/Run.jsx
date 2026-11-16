import { useEffect, useState } from 'react'

import { getInvestigation, retryInvestigation } from '../api'
import AgentCards from './AgentCards'
import Results from './Results'
import { FOCUS, Skeleton } from './ui'


function LoadingInvestigation() {
  return (
    <div className="space-y-8" role="status" aria-live="polite">

      <span className="sr-only">Loading investigation...</span>

      <div className="mb-5 flex items-center justify-between gap-2">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-40" />
      </div>

      <div className="grid gap-4 md:grid-cols-2">

        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
          >

            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="w-full space-y-2">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-3 w-52" />
              </div>

              <Skeleton className="h-6 w-20 rounded-full" />
            </div>

            <Skeleton className="mb-3 h-2 w-full rounded-full" />

            <div className="flex items-center justify-between gap-3">
              <Skeleton className="h-3 w-40" />
              <Skeleton className="h-3 w-8" />
            </div>

          </div>
        ))}

      </div>

    </div>
  )
}


export default function Run({ id, onRetry }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [retrying, setRetrying] = useState(false)
  const [retryErr, setRetryErr] = useState('')


  useEffect(() => {
    let stop = false
    let timer


    const tick = async () => {
      try {
        const d = await getInvestigation(id)

        if (stop) return

        setData(d)
        setErr('')

        if (
          d.status === 'completed' ||
          d.status === 'failed'
        ) {
          return
        }

      } catch (e) {
        if (!stop) {
          setErr(e.message)
        }
      }

      if (!stop) {
        timer = setTimeout(tick, 1000)
      }
    }


    tick()


    return () => {
      stop = true
      clearTimeout(timer)
    }

  }, [id])


  const retry = async () => {
    setRetrying(true)
    setRetryErr('')

    try {
      const { id: next } = await retryInvestigation(id)

      onRetry?.(next)
    } catch (e) {
      setRetryErr(e.message)
      setRetrying(false)
    }
  }


  if (!data) {
    if (err) {
      return (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700"
        >
          <p className="font-semibold">
            Could not load this investigation.
          </p>
          <p className="mt-1">{err}</p>
        </div>
      )
    }

    return <LoadingInvestigation />
  }


  return (
    <div className="space-y-8">

      {err && (
        <div
          role="alert"
          className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
        >
          Connection problem: {err}. Retrying...
        </div>
      )}


      {data.status === 'failed' && (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 p-5"
        >

          <h2 className="font-bold text-red-800">
            The investigation could not finish
          </h2>

          <p className="mt-2 whitespace-pre-wrap text-sm text-red-700">
            {data.error || 'An unexpected error occurred.'}
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-3">

            <button
              type="button"
              onClick={retry}
              disabled={retrying}
              className={`rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS}`}
            >
              {retrying ? 'Starting a new run...' : 'Retry this check'}
            </button>

            <span className="text-xs text-red-700">
              A retry starts a fresh investigation and keeps this
              failed run in your history.
            </span>

          </div>

          {retryErr && (
            <p role="alert" className="mt-3 text-sm font-medium text-red-700">
              Could not start a retry: {retryErr}
            </p>
          )}

        </div>
      )}


      <AgentCards
        agents={data.agents || []}
        citationCount={data.citation_count ?? 0}
        activity={data.api_activity || data.activity || []}
      />


      {data.status === 'completed' && data.report && (
        <Results report={data.report} inv={data} />
      )}

    </div>
  )
}