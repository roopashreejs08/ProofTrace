const BASE = import.meta.env.VITE_API_URL || ''

async function parse(res) {
  if (!res.ok) {
    let detail = ''

    try {
      detail = (await res.json()).detail
    } catch {
      // Ignore invalid or empty error responses.
    }

    if (Array.isArray(detail)) {
      detail =
        'Please paste between 20 and 300,000 characters of text.'
    }

    throw new Error(
      detail || res.statusText || 'Request failed'
    )
  }

  return res.json()
}

export const startInvestigation = (text) =>
  fetch(`${BASE}/api/investigations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text }),
  }).then(parse)

export const getInvestigation = (id) =>
  fetch(`${BASE}/api/investigations/${id}`).then(parse)

export const listInvestigations = () =>
  fetch(`${BASE}/api/investigations`).then(parse)

export const retryInvestigation = (id) =>
  fetch(`${BASE}/api/investigations/${id}/retry`, {
    method: 'POST',
  }).then(parse)

export const extractPdf = (file) => {
  const f = new FormData()

  f.append('file', file)

  return fetch(`${BASE}/api/extract-pdf`, {
    method: 'POST',
    body: f,
  }).then(parse)
}