import { ArrowRightLeft, Bot, CheckCircle2, Users, XCircle } from 'lucide-react'
import { Badge, EmptyState } from '../../components/ui'
import { cx } from '../../lib/ui-utils'
import { fmtMs, fmtTime } from '../../lib/format'
import { agentFor, modelCallFor, phaseLabel, transitionForAction } from '../../lib/run-model'
import type { RunDetail } from '../../lib/types'
import type { Selection } from '../flow-map/FlowMap'

const HANDOFF_EVENTS: Record<string, string> = {
  form_discovered: 'Explorer discovered form',
  handoff_created: 'Handoff',
  test_executed: 'Test executed',
  candidate_reported: 'Candidate reported',
  assertion_selected: 'Assertion selected',
  verification_executed: 'Verification executed',
  result_accepted: 'Result accepted',
  result_rejected: 'Result rejected',
  task_blocked: 'Task blocked',
  frontier_deferred: 'New state deferred',
  task_queued: 'Task queued',
  task_claimed: 'Task claimed',
  task_completed: 'Task completed',
  task_failed: 'Task failed',
  task_retry: 'Task retried',
  task_unfinished: 'Task unfinished',
  fault_injected: 'Injected fault',
  lease_expired: 'Lease expired',
  context_fenced: 'Context closed',
  task_reassigned: 'Task reassigned',
  late_action_rejected: 'Late action refused',
  task_recovered: 'Task recovered',
}
const RECOVERY = new Set(['fault_injected', 'lease_expired', 'context_fenced', 'task_reassigned', 'late_action_rejected', 'result_rejected', 'task_recovered'])

const TASK_TONE: Record<string, string> = {
  ready: 'bg-slate-100 text-slate-700', claimed: 'bg-blue-50 text-blue-800', done: 'bg-emerald-50 text-emerald-800',
  blocked: 'bg-amber-50 text-amber-900', failed: 'bg-red-50 text-red-800', unfinished: 'bg-amber-50 text-amber-900',
  deferred: 'bg-slate-100 text-slate-700',
}
const TASK_LABEL: Record<string, string> = { ready: 'queued', claimed: 'claimed', done: 'completed' }

function TaskBoard({ detail }: { detail: RunDetail }) {
  const tasks = detail.tasks ?? []
  if (tasks.length === 0) return null
  const counts = Object.entries(tasks.reduce<Record<string, number>>((m, t) => ({ ...m, [t.status]: (m[t.status] ?? 0) + 1 }), {}))
  const handedOff = new Set((detail.handoffs ?? []).map((h) => h.task_id))
  return (
    <section aria-label="Tasks">
      <h3 className="mb-1.5 flex flex-wrap items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Tasks ({tasks.length})
        {counts.map(([s, n]) => (
          <span key={s} className={cx('rounded px-1.5 text-[11px] font-medium normal-case tracking-normal', TASK_TONE[s])}>{n} {TASK_LABEL[s] ?? s}</span>
        ))}
      </h3>
      <ol className="space-y-1 text-xs">
        {tasks.map((t) => (
          <li key={t.id} className="rounded-md border border-slate-100 px-2 py-1.5">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className={cx('rounded px-1.5 text-[11px] font-medium', TASK_TONE[t.status])}>{TASK_LABEL[t.status] ?? t.status}</span>
              <span className="font-medium text-slate-800">{t.type.replace('_', ' ')}</span>
              {t.owner ? <AgentChip id={t.owner} /> : <span className="text-[11px] text-slate-500">no owner</span>}
              {handedOff.has(t.id) && <span className="text-[11px] text-slate-600">handed off</span>}
              {(t.attempts ?? 0) > 1 && <span className="text-[11px] text-slate-600">attempt {t.attempts}/{t.max_attempts}</span>}
              {(t.expired_attempts ?? []).length > 0 && (
                <span className="rounded bg-amber-50 px-1.5 text-[11px] font-medium text-amber-900">
                  {t.expired_attempts!.length} expired lease{t.expired_attempts!.length > 1 ? 's' : ''}
                  {(t.excluded_workers ?? []).length > 0 && ` · excluded ${t.excluded_workers!.join(', ')}`}
                </span>
              )}
              {(t.depends_on ?? []).length > 0 && <span className="text-[11px] text-slate-600">waits for {t.depends_on!.length} task</span>}
            </div>
            <div className="mt-0.5 flex flex-wrap gap-x-2 text-[11px] text-slate-500">
              <span className="font-mono [overflow-wrap:anywhere]">{t.key}</span>
              {t.queued_by && <span>queued by {t.queued_by}</span>}
              {t.depth !== undefined && t.type === 'explore' && <span>depth {t.depth}</span>}
            </div>
            {t.note && <p className="mt-0.5 text-[11px] text-slate-600 [overflow-wrap:anywhere]">{t.note}</p>}
          </li>
        ))}
      </ol>
    </section>
  )
}

const agentTone: Record<string, string> = {
  'explorer-a': 'bg-sky-50 text-sky-800 ring-sky-200',
  'explorer-b': 'bg-teal-50 text-teal-800 ring-teal-200',
  'input-tester': 'bg-amber-50 text-amber-900 ring-amber-200',
  verifier: 'bg-violet-50 text-violet-800 ring-violet-200',
  coordinator: 'bg-slate-100 text-slate-700 ring-slate-200',
}

function AgentChip({ id }: { id: string | null }) {
  return (
    <span className={cx('inline-flex items-center rounded px-1.5 text-[11px] font-medium ring-1 ring-inset', agentTone[id ?? ''] ?? agentTone.coordinator)}>
      {id ?? 'unknown agent'}
    </span>
  )
}

/** Recorded browser actions and handoff events in order. Only recorded events are shown; nothing is simulated. */
export function RunActivity({ detail, selection, onSelect }: {
  detail: RunDetail
  selection: Selection
  onSelect: (s: Selection) => void
}) {
  const actions = [...detail.actions].sort((a, b) => a.step - b.step)
  const handoffs = detail.events.filter((e) => e.type in HANDOFF_EVENTS)
  const agents = [...new Set(actions.map((a) => agentFor(detail, a.id)).filter(Boolean))] as string[]
  if (actions.length === 0) {
    return <EmptyState icon={<Bot size={22} />} title="No actions recorded yet">Actions appear here as the explorer executes them.</EmptyState>
  }
  return (
    <div className="space-y-4 px-4 py-4">
      <div className="flex flex-wrap items-center gap-1.5 text-[13px] text-slate-600">
        <span>{actions.length} recorded actions by</span>
        {agents.map((a) => <Badge key={a} icon={<Bot size={11} />}>{a}</Badge>)}
      </div>
      <ol className="relative space-y-0.5 before:absolute before:bottom-3 before:left-[15px] before:top-3 before:w-px before:bg-slate-200">
        {actions.map((a) => {
          const t = transitionForAction(detail, a)
          const mc = modelCallFor(detail, t?.model_call_id)
          const first = detail.states.find((s) => s.first_seen_step === a.step)
          const target: Selection = t ? { kind: 'transition', id: t.id } : first ? { kind: 'state', id: first.id } : null
          const active = !!selection && !!target && selection.kind === target.kind && selection.id === target.id
          return (
            <li key={a.id} className="relative">
              <button type="button" disabled={!target} onClick={() => onSelect(target)} aria-current={active ? 'step' : undefined}
                className={cx('flex w-full items-start gap-3 rounded-lg px-1.5 py-2 text-left transition-colors',
                  active ? 'bg-accent-50' : 'hover:bg-slate-50')}>
                <span className={cx('relative z-10 mt-0.5 flex h-[19px] w-[19px] shrink-0 items-center justify-center rounded-full bg-white',
                  a.ok ? 'text-emerald-600' : 'text-red-600')}>
                  {a.ok ? <CheckCircle2 size={17} aria-label="succeeded" /> : <XCircle size={17} aria-label="failed" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="truncate text-[13px] font-medium text-slate-900">
                      <span className="mr-1.5 font-mono text-[11px] text-slate-500"><span className="sr-only">Step </span>{a.step}</span>{' '}
                      {t?.label ?? (a.step === 0 ? 'Open start URL' : a.action.type)}
                    </span>
                    <span className="shrink-0 font-mono text-[11px] text-slate-500">{fmtTime(a.started_at)}</span>
                  </span>
                  <span className="mt-0.5 flex flex-wrap gap-x-3 text-[11px] text-slate-500">
                    <AgentChip id={agentFor(detail, a.id)} />
                    {a.phase && a.phase !== 'explore' && <span>{phaseLabel[a.phase]}</span>}
                    {a.context_id && a.phase !== 'explore' && <span className="font-mono">{a.context_id.split(':').pop()}</span>}
                    <span>browser {fmtMs(a.duration_ms)}</span>
                    {mc ? <span>model {fmtMs(mc.latency_ms)}</span> : <span>{a.step === 0 ? 'from run config, no model call' : 'no model call'}</span>}
                  </span>
                  {a.error && <span className="mt-1 block text-[11px] text-red-700 [overflow-wrap:anywhere]">{a.error}</span>}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
      <TaskBoard detail={detail} />
      {handoffs.length > 0 ? (
        <section aria-label="Handoffs between workers">
          <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <ArrowRightLeft size={13} aria-hidden /> Handoffs and results ({handoffs.length})
          </h3>
          <ol className="space-y-1 text-xs">
            {handoffs.map((e) => (
              <li key={e.seq} className={cx('flex flex-wrap items-baseline gap-x-2 rounded-md px-1.5 py-1 hover:bg-slate-50',
                RECOVERY.has(e.type) && 'bg-amber-50/60', e.type === 'fault_injected' && 'ring-1 ring-inset ring-amber-300')}>
                <span className="font-mono text-[11px] text-slate-500">#{e.seq}</span>
                <AgentChip id={e.agent_id} />
                <span className="font-medium text-slate-800">{HANDOFF_EVENTS[e.type]}</span>
                <span className="min-w-0 flex-1 text-slate-600 [overflow-wrap:anywhere]">{e.message}</span>
              </li>
            ))}
          </ol>
          <p className="mt-2 text-[11px] text-slate-500">{detail.run.mode === 'queue_review'
            ? 'Recorded queue events: claims carry an attempt id and lease; lease expiry and reassignment arrive in the next checkpoint.'
            : 'Sequential handoffs (checkpoint 2). The shared queue is the queue_review mode.'}</p>
        </section>
      ) : (
        <div className="flex gap-2 rounded-lg border border-dashed border-slate-300 p-3 text-xs leading-relaxed text-slate-500">
          <Users size={15} className="mt-0.5 shrink-0" aria-hidden />
          <p>This run used one explorer. Handoffs to the input tester and verifier appear for review runs.</p>
        </div>
      )}
      <details className="text-xs">
        <summary className="cursor-pointer font-medium text-slate-600 hover:text-slate-900">Raw event log ({detail.events.length})</summary>
        <ol className="mt-2 max-h-72 space-y-0.5 overflow-auto rounded-md bg-slate-50 p-2 font-mono text-[11px]">
          {detail.events.map((e) => (
            <li key={e.seq} className="[overflow-wrap:anywhere]"><span className="text-slate-500">#{e.seq}</span> <span className="text-slate-600">{e.type}</span> {e.message}</li>
          ))}
        </ol>
      </details>
    </div>
  )
}
