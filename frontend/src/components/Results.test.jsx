import {
  fireEvent,
  render,
  screen,
} from '@testing-library/react'

import Results from './Results'


const report = {
  summary: {
    total: 2,
    VERIFIED: 1,
    RETRACTED: 1,
    'WEAK SUPPORT': 0,
    UNRESOLVABLE: 0,
    CONTRADICTED: 0,
  },

  notes: [
    'Example note',
  ],

  citations: [
    {
      item_id: 'c1',
      claim: 'Claim one',

      citation: {
        marker: '[1]',
        raw_reference: 'Ref one',
      },

      verdict: 'VERIFIED',
      explanation: 'Looks fine',
      caveats: [],

      match: null,
      retraction: null,
      evidence: null,
    },

    {
      item_id: 'c2',
      claim: 'Claim two',

      citation: {
        marker: '[2]',
      },

      verdict: 'RETRACTED',
      explanation: 'Has a notice',
      caveats: ['Be careful'],

      match: null,
      retraction: null,
      evidence: null,
    },
  ],
}


test('shows totals, notes and every citation', () => {
  render(<Results report={report} />)

  expect(
    screen.getByText('Total citations')
  ).toBeInTheDocument()

  expect(
    screen.getByText('Example note')
  ).toBeInTheDocument()

  expect(
    screen.getByText('Claim one')
  ).toBeInTheDocument()

  expect(
    screen.getByText('Claim two')
  ).toBeInTheDocument()
})


test('filter chips narrow the list', () => {
  render(<Results report={report} />)

  fireEvent.click(
    screen.getByRole('button', {
      name: /Retracted/,
    })
  )

  expect(
    screen.queryByText('Claim one')
  ).not.toBeInTheDocument()

  expect(
    screen.getByText('Claim two')
  ).toBeInTheDocument()
})