import type { Health, Run, RunDetail } from './types'

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text()
    let detail = body
    try {
      detail = JSON.parse(body).detail ?? body
    } catch {
      /* plain text */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json() as Promise<T>
}

export const artifactUrl = (id: string) => `/api/artifacts/${id}`

export const api = {
  health: () => fetch('/api/health').then(json<Health>),
  listRuns: () => fetch('/api/runs').then(json<Run[]>),
  getRun: (id: string) => fetch(`/api/runs/${id}`).then(json<RunDetail>),
  createRun: (body: { target_url: string; goal: string; requirements: string[]; limits?: Partial<Run['limits']> }) =>
    fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(json<Run>),
}
