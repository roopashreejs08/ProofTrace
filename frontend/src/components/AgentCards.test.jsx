import { fireEvent, render, screen } from '@testing-library/react'

import AgentCards from './AgentCards'


const agents = [
  {
    agent: 'claim_extractor',
    status: 'completed',
    message: 'Found 5 pairs',
    progress_done: 5,
    progress_total: 5,
  },
  {
    agent: 'paper_finder',
    status: 'completed_with_errors',
    message: 'Finished, but 2 item(s) could not be fully checked.',
    progress_done: 3,
    progress_total: 5,
  },
]


test('partial work is shown honestly, not as 100%', () => {
  render(
    <AgentCards
      agents={agents}
      citationCount={5}
      activity={[]}
    />
  )

  expect(screen.getByText('Partial')).toBeInTheDocument()

  // 3 of 5 processed -> 60%, never a fake 100%.
  expect(screen.getByText('60%')).toBeInTheDocument()

  expect(
    screen.getByText(
      'Finished, but 2 item(s) could not be fully checked.'
    )
  ).toBeInTheDocument()
})


test('research API activity is summarised and details are collapsible', () => {
  render(
    <AgentCards
      agents={agents}
      citationCount={5}
      activity={[
        {
          id: 1,
          source: 'crossref',
          url: 'https://api.crossref.org/works',
          status: 200,
          ms: 120,
          cached: 0,
        },
        {
          id: 2,
          source: 'openalex',
          url: 'https://api.openalex.org/works',
          status: 503,
          ms: 800,
          cached: 0,
        },
      ]}
    />
  )

  expect(
    screen.getByText('Research API activity')
  ).toBeInTheDocument()

  // A calm one-line summary, not a raw log.
  expect(
    screen.getByText(/2 recent calls · 2 sources · 1 failed/)
  ).toBeInTheDocument()

  // The raw rows stay hidden until the user asks for them.
  expect(screen.queryByText('crossref')).not.toBeInTheDocument()

  fireEvent.click(
    screen.getByRole('button', { name: /Show details/ })
  )

  expect(screen.getByText('crossref')).toBeInTheDocument()
  expect(screen.getByText('openalex')).toBeInTheDocument()
})
