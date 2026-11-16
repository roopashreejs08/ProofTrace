import { fireEvent, render, screen } from '@testing-library/react'

import Results from './Results'


const report = {
  summary: {
    total: 1,
    VERIFIED: 1,
    RETRACTED: 0,
    'WEAK SUPPORT': 0,
    UNRESOLVABLE: 0,
    CONTRADICTED: 0,
  },

  notes: [],

  extraction: {
    input_chars: 44752,
    references_parsed: 28,
    unique_citations: 25,
    uncited_references: 3,
  },

  ai: {
    enabled: true,
    used: 0,
    lexical: 25,
    model: 'gemini-flash-latest',
    last_error: 'gemini-flash-latest: 503 UNAVAILABLE',
  },

  citations: [
    {
      item_id: 'c1',
      claim: 'Claim one',
      citation: { marker: '[1]', raw_reference: 'Ref one' },
      verdict: 'VERIFIED',
      explanation: 'Looks fine',
      caveats: [],

      match: {
        source: 'crossref',
        status: 'matched',
        title: 'A study',
        authors: ['J Smith'],
        year: 2020,
        doi: '10.1/x',
        checks: {
          title_coverage: 0.9,
          year_match: false,
          author_match: true,
        },
        discrepancies: ['Cited year 2019 differs from 2018.'],
      },

      retraction: {
        status: 'clear',
        sources: [],
        notices: [],
        corrections: [{ type: 'correction', doi: '10.1/corr' }],
        note: 'No retraction notice found.',
      },

      evidence: {
        stance: 'supports',
        confidence: 0.9,
        rationale: 'The abstract supports it.',
        method: 'llm',
        model: 'gemini-flash-latest',
        limitation: 'Judged from the abstract only.',
      },
    },
  ],
}


test('shows honest extraction and AI status', () => {
  render(<Results report={report} />)

  expect(
    screen.getByText(/Parsed 28 bibliography/)
  ).toBeInTheDocument()

  expect(
    screen.getByText(/model was unavailable so keyword fallback/)
  ).toBeInTheDocument()

  expect(
    screen.getByText(/Last AI error/)
  ).toBeInTheDocument()
})


test('says so when AI was on but no abstract was available', () => {
  const noAbstract = {
    ...report,
    ai: {
      enabled: true,
      used: 0,
      lexical: 0,
      skipped: 1,
      model: 'gemini-flash-latest',
    },
  }

  render(<Results report={noAbstract} />)

  expect(
    screen.getByText(/no matched paper had an abstract/)
  ).toBeInTheDocument()
})


test('shows full-text mode status honestly', () => {
  const withFullText = {
    ...report,
    ai: {
      ...report.ai,
      used: 25,
      lexical: 0,
      full_text_mode: true,
      full_text: 12,
      last_error: '',
    },
  }

  render(<Results report={withFullText} />)

  expect(
    screen.getByText(/Full-text mode/)
  ).toBeInTheDocument()

  expect(
    screen.getByText(
      /12 claim\(s\) were judged from the open-access full text/
    )
  ).toBeInTheDocument()
})


test('labels evidence that came from the full text', () => {
  const fullTextEvidence = {
    ...report,
    citations: [
      {
        ...report.citations[0],
        evidence: {
          ...report.citations[0].evidence,
          text_source: 'full_text',
        },
      },
    ],
  }

  render(<Results report={fullTextEvidence} />)

  fireEvent.click(
    screen.getByRole('button', { name: /Show evidence/ })
  )

  expect(screen.getByText('Evidence source')).toBeInTheDocument()

  // The badge and the evidence-source row both say "full text".
  expect(
    screen.getAllByText('Open-access full text').length
  ).toBeGreaterThan(0)
})


test('shows corrections and the AI method badge', () => {
  render(<Results report={report} />)

  fireEvent.click(
    screen.getByRole('button', { name: /Show evidence/ })
  )

  expect(screen.getByText('Corrections')).toBeInTheDocument()
  expect(screen.getByText('correction')).toBeInTheDocument()
  expect(
    screen.getByText(/AI analysis · gemini-flash-latest/)
  ).toBeInTheDocument()
  expect(screen.getByText('No')).toBeInTheDocument()
})


test('the analysis note is tucked away and printing is offered', () => {
  render(<Results report={report} />)

  // The methodology note is a collapsed disclosure, not a wall of text
  // sitting on top of the report.
  const heading = screen.getByText('How this run was analysed')

  expect(heading.closest('details')).not.toHaveAttribute('open')

  // A print / save-as-PDF option sits with the other exports.
  expect(
    screen.getByRole('button', { name: /Print \/ Save as PDF/ })
  ).toBeInTheDocument()
})
