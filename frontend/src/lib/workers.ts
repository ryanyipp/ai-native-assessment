// Worker views derived only from recorded actions and events. Nothing here is simulated.
import { agentFor } from './run-model'
import type { ActionResult, RunDetail, RunEvent, Task } from './types'

const ORDER = ['explorer-a', 'explorer-b', 'single-agent', 'input-tester', 'verifier']

export function workersOf(d: RunDetail): string[] {
  const seen = new Set<string>()
  for (const a of [...d.actions].sort((x, y) => x.step - y.step)) {
    const w = a.agent_id ?? agentFor(d, a.id)
    if (w) seen.add(w)
  }
  for (const m of d.model_calls) if (m.agent_id) seen.add(m.agent_id)
  seen.delete('coordinator')
  return [...seen].sort((a, b) => (ORDER.indexOf(a) + 99 * +(ORDER.indexOf(a) < 0)) - (ORDER.indexOf(b) + 99 * +(ORDER.indexOf(b) < 0)))
}

export function actionsOf(d: RunDetail, worker: string): ActionResult[] {
  return d.actions.filter((a) => (a.agent_id ?? agentFor(d, a.id)) === worker).sort((x, y) => x.step - y.step)
}

export type WorkerState = 'working' | 'waiting' | 'stopped' | 'finished'

export interface WorkerStatus {
  state: WorkerState
  label: string
  task: Task | null
  lastAction: ActionResult | null
  lastEvent: RunEvent | null
}

const ACTIVE = new Set(['queued', 'running'])

export function workerStatus(d: RunDetail, worker: string): WorkerStatus {
  const acts = actionsOf(d, worker)
  const lastAction = acts.at(-1) ?? null
  const evs = d.events.filter((e) => e.agent_id === worker && e.type !== 'model_call')
  const lastEvent = evs.at(-1) ?? null
  const claims = d.events.filter((e) => e.agent_id === worker && e.type === 'task_claimed')
  const lastClaim = claims.at(-1)
  let task: Task | null = null
  if (lastClaim) {
    const t = (d.tasks ?? []).find((x) => x.id === lastClaim.task_id)
    task = t ?? null
  }
  const running = ACTIVE.has(d.run.status)
  if (!running) return { state: 'finished', label: `Run ${d.run.status}`, task, lastAction, lastEvent }
  if (task && task.status === 'claimed' && task.owner === worker) {
    return { state: 'working', label: `Working on ${task.type.replace('_', ' ')} task`, task, lastAction, lastEvent }
  }
  if (lastEvent && ['result_rejected', 'late_action_rejected', 'lease_expired'].includes(lastEvent.type)) {
    return { state: 'stopped', label: 'Attempt revoked', task, lastAction, lastEvent }
  }
  if (claims.length === 0 && (d.tasks ?? []).length === 0) {
    // Sequential modes record no claims: active if this worker produced the latest action.
    const latest = [...d.actions].sort((x, y) => y.step - x.step)[0]
    const mine = latest && (latest.agent_id ?? agentFor(d, latest.id)) === worker
    return { state: mine ? 'working' : 'waiting', label: mine ? 'Acting in the browser' : 'Waiting for its turn', task, lastAction, lastEvent }
  }
  return { state: 'waiting', label: 'Waiting for a task', task, lastAction, lastEvent }
}

/** The screenshot that shows the page BEFORE `a`, if the same context recorded it right before. */
export function beforeShotFor(d: RunDetail, a: ActionResult): ActionResult | null {
  if (!a.target_box || !a.context_id) return null
  const prev = d.actions
    .filter((x) => x.context_id === a.context_id && x.step < a.step && x.screenshot_artifact_id)
    .sort((x, y) => y.step - x.step)[0]
  return prev && prev.url_after === a.url_before ? prev : null
}
