import type { Health, Run, RunDetail } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type FastApiDetail = string | { loc?: (string | number)[]; msg: string }[]

function describe(detail: FastApiDetail): string {
  if (typeof detail === 'string') return detail
  // Pydantic validation errors: "limits.max_steps: Input should be less than or equal to 60"
  return detail.map((d) => `${(d.loc ?? []).filter((p) => p !== 'body').join('.') || 'request'}: ${d.msg}`).join('; ')
}

async function request<T>(input: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(input, init)
  } catch {
    throw new ApiError(0, 'Cannot reach the FlowLens backend. Is it running on port 8000?')
  }
  if (!res.ok) {
    const body = await res.text()
    let message = body || res.statusText
    try {
      message = describe(JSON.parse(body).detail ?? body)
    } catch {
      /* plain-text body */
    }
    if (res.status >= 500 && !body) {
      message = 'Cannot reach the FlowLens backend. Is it running on port 8000?'
    }
    throw new ApiError(res.status, message)
  }
  return res.json() as Promise<T>
}

export const artifactUrl = (id: string) => `/api/artifacts/${id}`

export const api = {
  health: () => request<Health>('/api/health'),
  listRuns: () => request<Run[]>('/api/runs'),
  getRun: (id: string) => request<RunDetail>(`/api/runs/${encodeURIComponent(id)}`),
  createRun: (body: { target_url: string; goal: string; requirements: string[]; limits?: Partial<Run['limits']>; mode?: 'single_explorer' | 'explore_test_verify' | 'queue_review' }) =>
    request<Run>('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
}
