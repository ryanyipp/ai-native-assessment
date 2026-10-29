// Mirrors backend/src/flowlens/models/contracts.py. The backend owns the schema.

export type RunStatus = 'queued' | 'running' | 'completed' | 'partial' | 'failed' | 'interrupted'
export type Phase = 'explore' | 'input_test' | 'verify'
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
  exploration_calls?: number
  testing_calls?: number
  verification_calls?: number
  truncated_calls?: number
}

export interface FaultInjection { kind: string; worker: string; task_type: string; stall_s: number; times: number }

export interface Run {
  id: string
  target_url: string
  goal: string
  requirements: string[]
  model: string
  mode: 'single_explorer' | 'explore_test_verify' | 'reverify' | string
  target_build: string | null
  fault_injection?: FaultInjection | null
  limits: RunLimits
  status: RunStatus
  stop_reason: string | null
  provenance: Provenance
  usage: Usage
  created_at: string
  finished_at: string | null
}

export type BrowserAction = {
  type: string; element_id?: string; value?: string; url?: string
  test_case_id?: string; finding_id?: string; inputs?: Record<string, string>; assertion?: string; submit?: string | null
}

export interface ControlRef { role: string; name: string; input_type: string | null }
export interface SemanticStep { type: string; path: string | null; control: ControlRef | null; value: string | null }
export interface SetupRecipe {
  target_state_id: string; expected_signature: string; direct_path: string | null; steps: SemanticStep[]; data_isolation: string
}
export interface StateSighting { agent_id: string; phase: Phase; context_id: string | null; action_result_id: string | null }

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
  semantic_recipe?: SemanticStep[]
  discovered_by?: string
  phase?: Phase
  context_id?: string | null
  sightings?: StateSighting[]
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
  agent_id?: string
  phase?: Phase
  context_id?: string | null
  test_case_id?: string | null
  verification_id?: string | null
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
  target_box?: { x: number; y: number; width: number; height: number } | null
  agent_id?: string
  phase?: Phase
  context_id?: string | null
}

export interface Assertion {
  type: string; params: Record<string, unknown>; requirement_ref?: string | null; expected?: string | null; chosen_by?: string | null
}

export interface AssertionResult {
  assertion: Assertion
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
  requirement_ref?: string | null
  requirement_text?: string | null
  inputs?: Record<string, string>
  reproduction?: SetupRecipe | null
  reproduction_steps?: SemanticStep[]
  form_id?: string | null
  test_case_id?: string | null
  handoff_ids?: string[]
  verification_ids?: string[]
  verified_by?: string | null
  verification_reason?: string | null
  source_finding_id?: string | null
}

export interface Task {
  id: string; type: string; key: string; owner: string | null; status: string; input_refs: string[]; note: string | null
  attempt_id?: string | null; attempts?: number; max_attempts?: number; depends_on?: string[]; depth?: number
  queued_by?: string | null; payload?: Record<string, string>; lease_expires_at?: string | null
  created_at?: string; claimed_at?: string | null; finished_at?: string | null; result_refs?: string[]
  excluded_workers?: string[]; expired_attempts?: string[]
}

export interface DiscoveredForm {
  id: string; key: string; state_id: string; url: string; route: string; headings: string[]
  fields: { control: ControlRef; required: boolean; observed_value: string | null }[]
  submit_controls: ControlRef[]; discovered_by: string; action_result_id: string; evidence_refs: string[]
}

export interface Handoff {
  id: string; kind: 'form_to_tester' | 'candidate_to_verifier'; from_agent: string; to_agent: string; task_id: string
  source_state_id: string; form_id: string | null; finding_id: string | null; setup: SetupRecipe
  requirements: { id: string; text: string }[]; expected_behaviour: { text: string; source: string }[]
  evidence_refs: string[]; created_at: string
}

export interface TestCase {
  id: string; form_id: string; handoff_id: string; designed_by: string; label: string; inputs: Record<string, string>
  submit: ControlRef | null; requirement_ref: string | null; expected: string; expectation_source: string
  context_id: string | null; status: string; setup_strategy: string | null; setup_error: string | null
  action_result_ids: string[]; evidence_refs: string[]; observed: Record<string, unknown>
  resulting_state_id: string | null; tester_verdict: 'as_expected' | 'unexpected' | 'unclear' | null; tester_note: string | null
}

export interface VerificationAttempt {
  id: string; finding_id: string; handoff_id: string | null; verifier_id: string; replay_index: number; target_origin: string
  context_id: string | null; setup_ok: boolean; setup_strategy: string | null; setup_error: string | null
  failure_class: 'setup' | 'application' | 'expectation' | 'verifier' | null
  assertion: Assertion | null; result: AssertionResult | null; outcome: 'confirmed' | 'not_reproduced' | 'inconclusive'
  reason: string; action_result_ids: string[]; evidence_refs: string[]; model_call_id: string | null
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
  task_id?: string | null
  data: Record<string, unknown>
  created_at: string
}

export interface PagePreview {
  ok: boolean; error: string | null; requested_url: string; final_url: string; title: string; headings: string[]
  captured_at: string; viewport: { width: number; height: number }; image_png_base64: string
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
  finish_reason?: string | null
  agent_id?: string
  phase?: Phase
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
  tasks?: Task[]
  forms?: DiscoveredForm[]
  handoffs?: Handoff[]
  test_cases?: TestCase[]
  verifications?: VerificationAttempt[]
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
