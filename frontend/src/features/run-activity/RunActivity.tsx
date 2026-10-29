import { Bot, CheckCircle2, Users, XCircle } from 'lucide-react'
import { Badge, EmptyState } from '../../components/ui'
import { cx } from '../../lib/ui-utils'
import { fmtMs, fmtTime } from '../../lib/format'
import { agentFor, modelCallFor, transitionForAction } from '../../lib/run-model'
import type { RunDetail } from '../../lib/types'
import type { Selection } from '../flow-map/FlowMap'

/** Recorded browser actions in order. Single explorer only: no simulated multi-agent lanes. */
export function RunActivity({ detail, selection, onSelect }: {
  detail: RunDetail
  selection: Selection
  onSelect: (s: Selection) => void
}) {
  const actions = [...detail.actions].sort((a, b) => a.step - b.step)
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
                    <span>{agentFor(detail, a.id) ?? 'unknown agent'}</span>
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
      <div className="flex gap-2 rounded-lg border border-dashed border-slate-300 p-3 text-xs leading-relaxed text-slate-500">
        <Users size={15} className="mt-0.5 shrink-0" aria-hidden />
        <p>This run used one explorer. A multi-agent timeline with claims, handoffs and recovery appears once the coordinator records those events.</p>
      </div>
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
