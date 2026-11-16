import { buildReportHtml, buildReportJson } from './reportExport'


const inv = {
  id: 'abc12345',
  status: 'completed',
  created_at: 1700000000,
  citation_count: 1,
  agents: [
    {
      agent: 'claim_extractor',
      status: 'completed',
      message: 'Found 1 pair',
    },
  ],
  api_activity: [
    { source: 'crossref', url: 'https://api.crossref.org/works', status: 200, ms: 12, cached: 0 },
  ],
  report: {
    summary: { total: 1, VERIFIED: 1 },
    notes: ['A note.'],
    extraction: { references_parsed: 1, unique_citations: 1, input_chars: 100 },
    ai: { enabled: true, used: 1, model: 'gemini-x' },
    citations: [
      {
        item_id: 'c1',
        claim: 'Claim one',
        citation: { marker: '[1]', raw_reference: 'Ref one' },
        verdict: 'VERIFIED',
        explanation: 'Looks fine',
        caveats: [],
        match: { status: 'matched', title: 'A study', authors: ['J Smith'], year: 2020 },
        retraction: { status: 'clear' },
        evidence: { stance: 'supports', confidence: 0.9, method: 'llm' },
      },
    ],
  },
}


test('json export includes the investigation and the report', () => {
  const data = buildReportJson(inv)

  expect(data.tool).toBe('ProofTrace')
  expect(data.investigation.id).toBe('abc12345')
  expect(data.report.citations[0].verdict).toBe('VERIFIED')
  expect(data.api_activity[0].source).toBe('crossref')
})


test('html export includes the shown content', () => {
  const html = buildReportHtml(inv)

  expect(html).toContain('Investigation report')
  expect(html).toContain('Claim one')
  expect(html).toContain('A study')
  expect(html).toContain('A note.')
  expect(html).toContain('crossref')
  expect(html).toContain('Verified')
})


test('html export reports full-text use when available', () => {
  const withFullText = {
    ...inv,
    report: {
      ...inv.report,
      ai: { ...inv.report.ai, full_text_mode: true, full_text: 1 },
      citations: [
        {
          ...inv.report.citations[0],
          evidence: {
            stance: 'supports',
            confidence: 0.9,
            method: 'llm',
            text_source: 'full_text',
          },
        },
      ],
    },
  }

  const html = buildReportHtml(withFullText)

  expect(html).toContain('Open-access full text')
  expect(html).toContain('Full-text mode:')
  expect(html).toContain('1 claim(s) were judged from the open-access')
})


test('html export escapes untrusted text', () => {
  const evil = {
    report: {
      summary: { total: 1 },
      citations: [
        {
          item_id: 'c1',
          claim: '<script>alert(1)</script>',
          citation: { marker: '[1]' },
          verdict: 'UNRESOLVABLE',
        },
      ],
    },
  }

  const html = buildReportHtml(evil)

  expect(html).not.toContain('<script>alert(1)</script>')
  expect(html).toContain('&lt;script&gt;')
})


test('html export works with only a report (no investigation)', () => {
  const html = buildReportHtml({ report: inv.report })

  expect(html).toContain('Claim one')
  expect(html).toContain('unknown')
})
