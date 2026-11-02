// Read-only helpers that derive views from the real run records. Nothing is invented here.
import type { ActionResult, ModelCall, RunDetail, ScreenState, SetupRecipe, Transition, VerificationAttempt } from './types'

export function transitionsByStep(d: RunDetail): Transition[] {
  return [...d.transitions].sort((a, b) => a.step - b.step)
}

/** Every recorded step number, including setup and replay actions that add no move to the map. */
export function stepNumbers(d: RunDetail): number[] {
  return [...new Set([...d.actions.map((a) => a.step), ...d.transitions.map((t) => t.step)])].sort((a, b) => a - b)
}

/** What to show for a step: its map move if it has one, otherwise the recorded action. */
export function selectionForStep(d: RunDetail, step: number): { kind: 'transition' | 'action'; id: string } | null {
  const t = d.transitions.find((x) => x.step === step)
  if (t) return { kind: 'transition', id: t.id }
  const a = d.actions.find((x) => x.step === step)
  return a ? { kind: 'action', id: a.id } : null
}

/** True only when saved records show a browser replay began; a verifier review alone is not one. */
export function wasAttempted(v: VerificationAttempt) {
  return v.setup_ok || !!v.setup_strategy || !!v.setup_error || v.action_result_ids.length > 0
}

export interface SequenceItem { action: ActionResult; kind: 'setup' | 'test' | 'check'; isResult: boolean }

/**
 * One test's or replay's own actions, in recorded order. Built from saved action ids, never from step
 * numbers, because other agents' steps fall between them. The result action is linked through the map
 * move: a replay's closing check page is not in its saved action ids.
 */
export function evidenceSequence(d: RunDetail, ids: string[], strategy: string | null, recipe: SetupRecipe | null | undefined,
                                 resultId: string | null | undefined): SequenceItem[] {
  const setup = strategy === 'direct' ? 1 : strategy ? (recipe?.direct_path ? 1 : 0) + (recipe?.steps.length ?? 0) : 0
  const all = resultId && !ids.includes(resultId) ? [...ids, resultId] : ids
  return all.flatMap((id, i) => {
    const action = d.actions.find((a) => a.id === id)
    if (!action) return []
    const kind = i < setup ? 'setup' as const : action.action.type === 'inspect' ? 'check' as const : 'test' as const
    return [{ action, kind, isResult: id === resultId }]
  })
}

export function stateById(d: RunDetail, id: string): ScreenState | undefined {
  return d.states.find((s) => s.id === id)
}

export function modelCallFor(d: RunDetail, id: string | null | undefined): ModelCall | undefined {
  return id ? d.model_calls.find((m) => m.id === id) : undefined
}

/** Agent that recorded an action: the action record, else the action_executed event (old runs). */
export function agentFor(d: RunDetail, actionResultId: string): string | null {
  const a = d.actions.find((x) => x.id === actionResultId)
  if (a?.agent_id) return a.agent_id
  const ev = d.events.find((e) => e.type === 'action_executed' && e.data.action_result_id === actionResultId)
  return ev?.agent_id ?? null
}

export function reasoningFor(d: RunDetail, modelCallId: string | null | undefined): string | null {
  if (!modelCallId) return null
  return d.events.find((e) => e.type === 'decision' && e.data.model_call_id === modelCallId)?.message ?? null
}

export function evidenceFor(d: RunDetail, id: string | null | undefined) {
  return id ? d.evidence.find((e) => e.id === id) : undefined
}

export function transitionForAction(d: RunDetail, a: ActionResult): Transition | undefined {
  return d.transitions.find((t) => t.action_result_id === a.id)
}

export function describeAction(a: { type: string; value?: string; url?: string }, target?: string | null) {
  switch (a.type) {
    case 'click':
      return `Click ${target ?? 'element'}`
    case 'fill':
      return `Fill ${target ?? 'field'}`
    case 'navigate':
      return `Open ${a.url ?? 'page'}`
    case 'reload':
      return 'Reload page'
    case 'test_case':
      return 'Input test case'
    case 'verify_case':
      return 'Verification replay'
    default:
      return a.type
  }
}

export const phaseLabel: Record<string, string> = { explore: 'Exploration', input_test: 'Input test', verify: 'Verification' }

export function testCaseFor(d: RunDetail, id: string | null | undefined) {
  return id ? d.test_cases?.find((t) => t.id === id) : undefined
}

export function verificationFor(d: RunDetail, id: string | null | undefined) {
  return id ? d.verifications?.find((v) => v.id === id) : undefined
}
