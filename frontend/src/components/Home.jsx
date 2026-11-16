import { useRef, useState } from 'react'

import {
  extractPdf,
  startInvestigation,
} from '../api'

import { FOCUS } from './ui'


const SAMPLE = `Deep residual networks made it practical to train very deep image classifiers [1]. Deep learning has transformed speech recognition, vision and language processing [2]. A 1998 case series of twelve children was published in The Lancet [3]. Quantum gradient folding improves language model accuracy by 40% (Smithson, 2021).

References

[1] He K, Zhang X, Ren S, Sun J. Deep residual learning for image recognition. CVPR 2016. https://doi.org/10.1109/CVPR.2016.90

[2] LeCun Y, Bengio Y, Hinton G. Deep learning. Nature 2015. https://doi.org/10.1038/nature14539

[3] Wakefield AJ, et al. Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental disorder in children. Lancet 1998. https://doi.org/10.1016/S0140-6736(97)11096-0

[4] Smithson J. Quantum gradient folding in neural cognition. Journal of Imaginary Results 2021.`


const MAX_INPUT = 300000


export default function Home({ onStart }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const fileRef = useRef(null)


  const submit = async () => {
    setBusy(true)
    setErr('')

    try {
      const { id } = await startInvestigation(text)

      onStart(id)
    } catch (e) {
      setErr(e.message)
      setBusy(false)
    }
  }


  const upload = async (e) => {
    const f = e.target.files?.[0]

    if (!f) return

    setBusy(true)
    setErr('')

    try {
      const r = await extractPdf(f)

      setText(r.text)
    } catch (x) {
      setErr(x.message)
    }

    setBusy(false)

    e.target.value = ''
  }


  return (
    <div className="mx-auto max-w-4xl">

      <div className="mb-8 text-center">

        <div className="mb-3 inline-flex items-center rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
          RESEARCH INTEGRITY WORKSPACE
        </div>

        <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Don't just cite it. Verify it.
        </h1>

        <p className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-slate-600">
          Paste a research paragraph with its references.
          Five specialised agents check whether each source exists,
          whether it has been retracted, and what the available
          evidence says about the claim.
        </p>

      </div>


      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">

        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">

          <label
            htmlFor="research-text"
            className="text-sm font-semibold text-slate-800"
          >
            Research text and references
          </label>

          <span className="text-xs text-slate-400">
            Paste text or upload a PDF
          </span>

        </div>


        <textarea
          id="research-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={12}
          maxLength={MAX_INPUT}
          placeholder="Paste your research paragraph and its reference list here..."
          className="w-full resize-y rounded-xl border border-slate-200 p-4 text-sm leading-relaxed outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
        />


        <div className="mt-4 flex flex-wrap items-center gap-3">

          <button
            onClick={submit}
            disabled={busy || text.trim().length < 20}
            className={`rounded-xl bg-indigo-600 px-6 py-2.5 font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS}`}
          >
            {busy ? 'Working...' : 'Verify Citations'}
          </button>


          <button
            onClick={() => setText(SAMPLE)}
            disabled={busy}
            className={`rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 ${FOCUS}`}
          >
            Load sample
          </button>


          <button
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            className={`rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 ${FOCUS}`}
          >
            Upload PDF
          </button>


          <input
            ref={fileRef}
            type="file"
            accept="application/pdf"
            onChange={upload}
            className="hidden"
          />


          <span className="ml-auto text-xs text-slate-400">
            {text.length.toLocaleString()} / {MAX_INPUT.toLocaleString()}
          </span>

        </div>


        {err && (
          <p
            role="alert"
            className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700"
          >
            {err}
          </p>
        )}

      </div>


      <p className="mt-4 text-center text-xs text-slate-500">
        Data from Crossref, OpenAlex, Europe PMC and PubMed.
        Verdicts are leads for human review, not final judgements.
      </p>

    </div>
  )
}