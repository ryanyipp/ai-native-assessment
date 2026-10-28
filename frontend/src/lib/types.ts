// Mirrors backend/src/flowlens/models/contracts.py. The backend owns the schema.

export type RunStatus = 'queued' | 'running' | 'completed' | 'partial' | 'failed' | 'interrupted'
export type VerificationStatus = 'unverified' | 'confirmed' | 'not_reproduced' | 'inconclusive'

export interface Provenance {
  live: boolean
  playback: boolean
  injected_failure: boolean
  synthetic_fixture: boolean
  mocked_model: boolean
}

export interface RunLimits {
  max_steps: number
  max_model_calls: number
  max_cost_usd: number
  max_output_tokens: number
  max_duration_s: number
  max_states: number
}

export interface Usage {
  model_calls: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  reported_cost_usd: number
  calls_without_cost: number
}

export interface Run {
  id: string
  target_url: string
  goal: string
  requirements: string[]
  model: string
  mode: string
  limits: RunLimits
  status: RunStatus
  stop_reason: string | null
  provenance: Provenance
  usage: Usage
  created_at: string
  finished_at: string | null
}

export type BrowserAction = { type: string; element_id?: string; value?: string; url?: string }

export interface ScreenState {
  id: string
  run_id: string
  signature: string
  signature_policy: string
  route: string
  url: string
  title: string
  summary: string
  screenshot_artifact_id: string | null
  first_seen_step: number
  setup_recipe: BrowserAction[]
}

export interface Transition {
  id: string
  run_id: string
  step: number
  source_state_id: string
  target_state_id: string
  action: BrowserAction
  label: string
  action_result_id: string
  ok: boolean
  duration_ms: number
  screenshot_artifact_id: string | null
  model_call_id: string | null
}

export interface ActionResult {
  id: string
  step: number
  action: BrowserAction
  target_description: string | null
  ok: boolean
  error: string | null
  url_before: string
  url_after: string
  started_at: string
  duration_ms: number
  screenshot_artifact_id: string | null
  observation_artifact_id: string | null
}

export interface AssertionResult {
  assertion: { type: string; params: Record<string, unknown> }
  passed: boolean
  observed: Record<string, unknown>
  evaluated_by: 'engine'
}

export interface Finding {
  id: string
  kind: string
  reported_by: string
  description: string
  expected: string
  observed: string
  agent_claim: 'retained' | 'not_retained' | 'unknown' | null
  same_context_check: AssertionResult | null
  evidence_refs: string[]
  verification_status: VerificationStatus
  replay_recipe: BrowserAction[]
}

export interface Evidence {
  id: string
  kind: string
  path: string
  sha256: string
  media_type: string
}

export interface RunEvent {
  seq: number
  type: string
  message: string
  agent_id: string | null
  data: Record<string, unknown>
  created_at: string
}

export interface ModelCall {
  id: string
  step: number
  model: string
  provider: string | null
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  reported_cost_usd: number | null
  latency_ms: number
  ok: boolean
  error: string | null
  artifact_id: string | null
}

export interface RunDetail {
  run: Run
  states: ScreenState[]
  transitions: Transition[]
  actions: ActionResult[]
  findings: Finding[]
  events: RunEvent[]
  evidence: Evidence[]
  model_calls: ModelCall[]
}

export interface Health {
  ok: boolean
  model: string
  api_key_configured: boolean
  allowed_origins: string[]
  budget_usd: number
  spent_reported_usd: number
  default_run_budget_usd: number
}
