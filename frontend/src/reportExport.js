import { VERDICTS } from './verdicts'


const ORDER = [
  'VERIFIED',
  'WEAK SUPPORT',
  'RETRACTED',
  'UNRESOLVABLE',
  'CONTRADICTED',
]


const AGENT_LABELS = {
  claim_extractor: 'Claim Extractor',
  paper_finder: 'Paper Finder',
  retraction_checker: 'Retraction Checker',
  evidence_analyst: 'Evidence Analyst',
  verification_agent: 'Verification Agent',
}


const esc = (v) =>
  String(v ?? '').replace(
    /[&<>"']/g,
    (c) => (
      {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[c]
    )
  )


const safeUrl = (u) =>
  typeof u === 'string' &&
  (u.startsWith('https://') || u.startsWith('http://'))


const fmtTime = (ts) =>
  ts ? new Date(ts * 1000).toLocaleString() : ''


const verdictCount = (summary, citations, v) => {
  const key = v.toLowerCase().replaceAll(' ', '_')

  return (
    summary[v] ??
    summary[key] ??
    citations.filter((c) => c.verdict === v).length
  )
}


function row(label, value) {
  if (value == null || value === '' || value === false) return ''

  return (
    '<tr><th>' + esc(label) + '</th><td>' + value + '</td></tr>'
  )
}


function listRow(label, items) {
  if (!items || !items.length) return ''

  return row(
    label,
    '<ul>' + items.map((x) => '<li>' + esc(x) + '</li>').join('') + '</ul>'
  )
}


function citationHtml(c) {
  const v = VERDICTS[c.verdict] || VERDICTS.UNRESOLVABLE
  const m = c.match || {}
  const r = c.retraction || {}
  const e = c.evidence || {}

  const parts = []

  parts.push(
    '<article class="cite">' +
      '<div class="cite-head">' +
        '<span class="marker">' +
          esc(c.citation?.marker || 'Citation') +
        '</span>' +
        '<span class="badge ' +
          esc(String(c.verdict).replaceAll(' ', '-').toLowerCase()) +
          '">' +
          esc(v.label) +
        '</span>' +
      '</div>' +
      '<p class="claim">' + esc(c.claim) + '</p>' +
      (c.citation?.raw_reference
        ? '<p class="ref">' + esc(c.citation.raw_reference) + '</p>'
        : '') +
      (c.explanation
        ? '<p class="explain">' + esc(c.explanation) + '</p>'
        : '')
  )

  if (c.caveats?.length) {
    parts.push(
      '<div class="caveats"><strong>Caveats</strong><ul>' +
        c.caveats.map((x) => '<li>' + esc(x) + '</li>').join('') +
      '</ul></div>'
    )
  }

  const matchRows = [
    row('Title', m.title ? esc(m.title) : ''),
    row('Authors', m.authors?.length ? esc(m.authors.join(', ')) : ''),
    row('Year', m.year ? esc(m.year) : ''),
    row('Journal', m.journal ? esc(m.journal) : ''),
    row('DOI', m.doi ? esc(m.doi) : ''),
    row('Source', m.source ? esc(m.source) : ''),
    row('Match status', m.status ? esc(m.status) : ''),
    row(
      'Title match',
      m.checks?.title_coverage != null
        ? esc(Math.round(m.checks.title_coverage * 100) + '%')
        : ''
    ),
    row(
      'Year match',
      m.checks?.year_match === true
        ? 'Yes'
        : m.checks?.year_match === false
          ? 'No'
          : ''
    ),
    row(
      'Author match',
      m.checks?.author_match === true
        ? 'Yes'
        : m.checks?.author_match === false
          ? 'No'
          : ''
    ),
    listRow('Discrepancies', m.discrepancies),
  ].filter(Boolean)

  parts.push(
    '<h4>Publication record</h4>' +
      (matchRows.length
        ? '<table class="kv">' + matchRows.join('') + '</table>'
        : '<p class="muted">No publication record was matched.</p>') +
      (safeUrl(m.url)
        ? '<p><a href="' + esc(m.url) + '">Open original source</a></p>'
        : '')
  )

  const retrRows = r.status
    ? [
        row('Status', esc(r.status)),
        row(
          'Notices',
          r.notices?.length
            ? esc(r.notices.map((n) => n.type).filter(Boolean).join(', '))
            : ''
        ),
        row(
          'Corrections',
          r.corrections?.length
            ? esc(
                r.corrections
                  .map((n) => n.type)
                  .filter(Boolean)
                  .join(', ')
              )
            : ''
        ),
        row(
          'Sources with a notice',
          r.sources?.length ? esc(r.sources.join(', ')) : ''
        ),
        row(
          'Sources checked',
          r.checked_sources?.length
            ? esc(r.checked_sources.join(', '))
            : ''
        ),
        row('Last checked', esc(fmtTime(r.checked_at))),
        row('Note', r.note ? esc(r.note) : ''),
      ].filter(Boolean)
    : []

  parts.push(
    '<h4>Retraction check</h4>' +
      (retrRows.length
        ? '<table class="kv">' + retrRows.join('') + '</table>'
        : '<p class="muted">Not checked.</p>') +
      (r.source_urls?.filter(safeUrl).length
        ? '<p class="muted">Where to verify: ' +
          r.source_urls
            .filter(safeUrl)
            .map((u) => '<a href="' + esc(u) + '">' + esc(u) + '</a>')
            .join(' · ') +
          '</p>'
        : '')
  )

  const evRows = e.stance
    ? [
        row('Stance', esc(String(e.stance).replaceAll('_', ' '))),
        row(
          'Evidence source',
          e.text_source === 'full_text'
            ? 'Open-access full text'
            : e.text_source === 'abstract'
              ? 'Abstract'
              : ''
        ),
        row(
          'Confidence',
          e.confidence != null
            ? esc(Math.round(e.confidence * 100) + '%')
            : ''
        ),
        row('Method', e.method ? esc(e.method) : ''),
        row('Model', e.model ? esc(e.model) : ''),
        row('Rationale', e.rationale ? esc(e.rationale) : ''),
        row('Supporting quote', e.quote ? '<em>' + esc(e.quote) + '</em>' : ''),
        row('Limitation', e.limitation ? esc(e.limitation) : ''),
        row('AI error', e.gemini_error ? esc(e.gemini_error) : ''),
      ].filter(Boolean)
    : []

  parts.push(
    '<h4>Claim evidence</h4>' +
      (evRows.length
        ? '<table class="kv">' + evRows.join('') + '</table>'
        : '<p class="muted">No evidence analysed.</p>')
  )

  parts.push('</article>')

  return parts.join('')
}


export function buildReportHtml(inv) {
  const report = inv?.report || {}
  const summary = report.summary || {}
  const citations = report.citations || []
  const notes = report.notes || []
  const extraction = report.extraction || {}
  const ai = report.ai || {}
  const doc = report.document
  const agents = inv?.agents || []
  const activity = inv?.api_activity || inv?.activity || []

  const generated = new Date().toLocaleString()

  const stats = [
    ['Total citations', summary.total ?? citations.length],
    ...ORDER.map((k) => [VERDICTS[k].label, verdictCount(summary, citations, k)]),
  ]

  const sources = [...new Set(activity.map((a) => a.source).filter(Boolean))]
  const failed = activity.filter((a) => {
    const n = Number(a.status)
    return !(Number.isFinite(n) && n >= 200 && n < 300)
  })
  const cached = activity.filter((a) => a.cached).length

  const activitySummary = activity.length
    ? `${activity.length} recent call${activity.length === 1 ? '' : 's'} · ` +
      `${sources.length} source${sources.length === 1 ? '' : 's'}` +
      (cached ? ` · ${cached} cached` : '') +
      (failed.length ? ` · ${failed.length} failed` : ' · all succeeded')
    : 'No external API calls recorded.'

  const extractionLine = extraction.references_parsed != null
    ? `Parsed ${extraction.references_parsed} bibliography entries and ` +
      `${extraction.unique_citations} in-text citations from ` +
      `${(extraction.input_chars || 0).toLocaleString()} characters` +
      (extraction.uncited_references
        ? ` (${extraction.uncited_references} uncited reference(s) were not checked)`
        : '') +
      '.'
    : ''

  const aiLine = ai.enabled
    ? ai.used > 0
      ? `On (${ai.used} claim(s) read by ${ai.model || 'the model'}).`
      : ai.lexical > 0
        ? 'On, but the model was unavailable so keyword fallback was used.'
        : 'On, but no matched paper had an abstract to assess.'
    : 'Off (no Gemini key configured), so keyword fallback was used.'

  const fullTextLine = ai.full_text_mode
    ? ai.full_text > 0
      ? `On (${ai.full_text} claim(s) were judged from the open-access ` +
        'full text).'
      : 'On, but no matched paper had open-access full text, so ' +
        'abstracts were used.'
    : 'Off, so every claim was judged from the abstract.'

  const agentRows = agents
    .map(
      (a) =>
        '<tr><td>' +
        esc(AGENT_LABELS[a.agent] || a.agent) +
        '</td><td>' +
        esc(a.status) +
        '</td><td>' +
        esc(a.message || '') +
        '</td></tr>'
    )
    .join('')

  const activityRows = activity
    .map(
      (a) =>
        '<tr><td>' +
        esc(a.source) +
        '</td><td class="url">' +
        esc((a.url || '').replace(/^https?:\/\//, '')) +
        '</td><td>' +
        esc(a.status) +
        '</td><td>' +
        esc(a.cached ? 'cached' : `${a.ms} ms`) +
        '</td></tr>'
    )
    .join('')

  const docHtml = doc
    ? '<section><h2>The uploaded document itself</h2><p>DOI: ' +
      esc(doc.doi) +
      (doc.retraction?.status
        ? ' — retraction status: ' + esc(doc.retraction.status)
        : '') +
      (doc.error ? ' — check failed: ' + esc(doc.error) : '') +
      '</p>' +
      (doc.retraction?.note
        ? '<p class="muted">' + esc(doc.retraction.note) + '</p>'
        : '') +
      (doc.retraction?.checked_at
        ? '<p class="muted">Last checked: ' +
          esc(fmtTime(doc.retraction.checked_at)) +
          '</p>'
        : '') +
      '</section>'
    : ''

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ProofTrace investigation report</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 40px 24px; background: #f8fafc; color: #1e293b;
    font: 15px/1.55 -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
  main { max-width: 900px; margin: 0 auto; }
  h1 { font-size: 24px; margin: 0 0 4px; }
  h2 { font-size: 16px; margin: 32px 0 12px; padding-bottom: 6px;
    border-bottom: 1px solid #e2e8f0; }
  h4 { font-size: 13px; margin: 16px 0 6px; color: #475569; }
  p { margin: 6px 0; }
  a { color: #4f46e5; }
  .muted { color: #64748b; font-size: 13px; }
  .note { background: #fffbeb; border: 1px solid #fde68a; color: #92400e;
    border-radius: 10px; padding: 10px 14px; margin: 8px 0; font-size: 13px; }
  .stats { display: flex; flex-wrap: wrap; gap: 10px; margin: 12px 0; }
  .stat { border: 1px solid #e2e8f0; background: #fff; border-radius: 10px;
    padding: 10px 14px; min-width: 120px; }
  .stat b { display: block; font-size: 22px; }
  .stat span { font-size: 12px; color: #64748b; }
  .cite { border: 1px solid #e2e8f0; background: #fff; border-radius: 12px;
    padding: 16px 18px; margin: 12px 0; page-break-inside: avoid; }
  .cite-head { display: flex; justify-content: space-between; align-items: center;
    gap: 12px; }
  .marker { font-weight: 700; color: #4f46e5; font-size: 13px; }
  .badge { font-size: 12px; font-weight: 600; border-radius: 999px;
    padding: 3px 10px; background: #eef2ff; color: #3730a3; white-space: nowrap; }
  .badge.retracted { background: #fee2e2; color: #991b1b; }
  .badge.verified { background: #d1fae5; color: #065f46; }
  .badge.contradicted { background: #ffedd5; color: #9a3412; }
  .badge.weak-support { background: #fef3c7; color: #92400e; }
  .badge.unresolvable { background: #f1f5f9; color: #334155; }
  .claim { font-weight: 600; margin-top: 8px; }
  .ref { background: #f8fafc; border-radius: 8px; padding: 8px 12px;
    font-size: 13px; color: #475569; }
  .explain { color: #475569; }
  .caveats { background: #fffbeb; border-radius: 8px; padding: 8px 12px;
    margin: 8px 0; font-size: 13px; color: #92400e; }
  table.kv { width: 100%; border-collapse: collapse; font-size: 13px; }
  table.kv th { text-align: left; vertical-align: top; color: #64748b;
    font-weight: 600; padding: 3px 12px 3px 0; white-space: nowrap; }
  table.kv td { padding: 3px 0; vertical-align: top; }
  table.kv ul { margin: 0; padding-left: 18px; }
  table.plain { width: 100%; border-collapse: collapse; font-size: 13px;
    background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; }
  table.plain th, table.plain td { text-align: left; padding: 6px 10px;
    border-bottom: 1px solid #eef2f7; }
  table.plain th { color: #64748b; font-weight: 600; }
  .url { word-break: break-all; color: #64748b; }
  footer { margin-top: 32px; font-size: 12px; color: #64748b;
    border-top: 1px solid #e2e8f0; padding-top: 12px; }
  @media print { body { background: #fff; padding: 0; }
    .cite, .stat { box-shadow: none; } }
</style>
</head>
<body>
<main>
  <header>
    <h1>ProofTrace — Investigation report</h1>
    <p class="muted">Results from the five research-integrity agents.</p>
    <p class="muted">
      Investigation <code>${esc(inv?.id || 'unknown')}</code>
      · Generated ${esc(generated)}
      · Status ${esc(inv?.status || 'completed')}
    </p>
  </header>

  <h2>Summary</h2>
  <div class="stats">
    ${stats
      .map(
        ([label, value]) =>
          '<div class="stat"><b>' +
          esc(value) +
          '</b><span>' +
          esc(label) +
          '</span></div>'
      )
      .join('')}
  </div>

  ${
    notes.length
      ? '<h2>Honesty notes</h2>' +
        notes
          .map((n) => '<div class="note">' + esc(n) + '</div>')
          .join('')
      : ''
  }

  ${docHtml}

  <h2>How this run was analysed</h2>
  ${extractionLine ? '<p>' + esc(extractionLine) + '</p>' : ''}
  <p>AI evidence analysis: ${esc(aiLine)}</p>
  <p>Full-text mode: ${esc(fullTextLine)}</p>
  ${
    extraction.segmentation
      ? '<p class="muted">Reference list split by: ' +
        esc(extraction.segmentation) +
        '.</p>'
      : ''
  }
  ${ai.last_error ? '<p class="muted">Last AI error: ' + esc(ai.last_error) + '</p>' : ''}

  ${
    agents.length
      ? '<h2>Agent runs</h2><table class="plain"><thead><tr>' +
        '<th>Agent</th><th>Status</th><th>Message</th></tr></thead><tbody>' +
        agentRows +
        '</tbody></table>'
      : ''
  }

  <h2>Research API activity</h2>
  <p class="muted">${esc(activitySummary)}</p>
  ${
    activityRows
      ? '<table class="plain"><thead><tr><th>Source</th><th>Request</th>' +
        '<th>Status</th><th>Time</th></tr></thead><tbody>' +
        activityRows +
        '</tbody></table>'
      : ''
  }

  <h2>Citations</h2>
  ${citations.map(citationHtml).join('')}

  <footer>
    ProofTrace checks metadata, retraction records and claim evidence.
    Where an open-access full text is available it reads that; otherwise
    it reads the abstract. Either way, treat every verdict as a lead for
    human review. A paper that cannot be found is unresolvable, not
    proven fabricated.
  </footer>
</main>
</body>
</html>`
}


export function buildReportJson(inv) {
  return {
    tool: 'ProofTrace',
    generated_at: new Date().toISOString(),
    investigation: {
      id: inv?.id || null,
      status: inv?.status || null,
      created_at: inv?.created_at || null,
      citation_count: inv?.citation_count ?? null,
    },
    agents: inv?.agents || [],
    api_activity: inv?.api_activity || inv?.activity || [],
    report: inv?.report || {},
  }
}


function reportFilename(inv, ext) {
  const stamp = new Date()
    .toISOString()
    .slice(0, 19)
    .replace(/[:T]/g, '-')

  const id = inv?.id ? String(inv.id).slice(0, 8) : 'report'

  return `prooftrace-report-${id}-${stamp}.${ext}`
}


function downloadText(filename, text, mime) {
  const blob = new Blob([text], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')

  a.href = url
  a.download = filename

  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)

  URL.revokeObjectURL(url)
}


export function downloadReportHtml(inv) {
  downloadText(
    reportFilename(inv, 'html'),
    buildReportHtml(inv),
    'text/html;charset=utf-8'
  )
}


export function downloadReportJson(inv) {
  downloadText(
    reportFilename(inv, 'json'),
    JSON.stringify(buildReportJson(inv), null, 2),
    'application/json;charset=utf-8'
  )
}


// Print the report, or save it as a PDF, by rendering the same
// print-styled HTML into an off-screen frame and handing it to the
// browser's print dialog. Kept off-screen so the page itself does not
// change, and removed again once the dialog has opened.
export function printReportHtml(inv) {
  const html = buildReportHtml(inv)

  const iframe = document.createElement('iframe')

  iframe.setAttribute('aria-hidden', 'true')
  iframe.setAttribute('title', 'ProofTrace report')
  iframe.style.position = 'fixed'
  iframe.style.right = '0'
  iframe.style.bottom = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = '0'

  document.body.appendChild(iframe)

  const doc = iframe.contentWindow?.document

  if (!doc) {
    // Defensive fallback: print the page itself.
    iframe.remove()
    window.print()
    return
  }

  const start = () => {
    const win = iframe.contentWindow

    if (win) {
      win.focus()
      win.print()
    }

    // Give the print dialog a moment, then drop the frame.
    window.setTimeout(() => iframe.remove(), 1000)
  }

  doc.open()
  doc.write(html)
  doc.close()

  if (doc.readyState === 'complete') {
    start()
  } else {
    iframe.onload = start
  }
}
