// Read-only helpers that derive views from the real run records. Nothing is invented here.
import type { ActionResult, ModelCall, RunDetail, ScreenState, Transition } from './types'

export function transitionsByStep(d: RunDetail): Transition[] {
  return [...d.transitions].sort((a, b) => a.step - b.step)
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
