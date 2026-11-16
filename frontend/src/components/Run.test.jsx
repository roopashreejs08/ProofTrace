import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'

import Run from './Run'
import * as api from '../api'


vi.mock('../api', () => ({
  getInvestigation: vi.fn(),
  retryInvestigation: vi.fn(),
}))


const failed = {
  id: 'abc123',
  status: 'failed',
  error: 'The model returned an error.',
  agents: [],
  citation_count: 0,
  api_activity: [],
}


test('a failed run offers a retry that starts a new investigation', async () => {
  api.getInvestigation.mockResolvedValue(failed)
  api.retryInvestigation.mockResolvedValue({ id: 'new456' })

  const onRetry = vi.fn()

  render(<Run id="abc123" onRetry={onRetry} />)

  expect(
    await screen.findByText(/The investigation could not finish/)
  ).toBeInTheDocument()

  fireEvent.click(
    screen.getByRole('button', { name: /Retry this check/ })
  )

  await waitFor(() =>
    expect(api.retryInvestigation).toHaveBeenCalledWith('abc123')
  )

  await waitFor(() => expect(onRetry).toHaveBeenCalledWith('new456'))
})


test('a failed retry is reported, not swallowed', async () => {
  api.getInvestigation.mockResolvedValue(failed)
  api.retryInvestigation.mockRejectedValue(new Error('backend down'))

  render(<Run id="abc123" onRetry={() => {}} />)

  fireEvent.click(
    await screen.findByRole('button', { name: /Retry this check/ })
  )

  expect(
    await screen.findByText(/Could not start a retry: backend down/)
  ).toBeInTheDocument()
})
