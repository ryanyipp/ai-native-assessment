import { ArrowRight, Bot, Compass, FlaskConical, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { cx } from '../../lib/ui-utils'
import { agentsOf, hasActed, workerStatus } from '../../lib/workers'
import type { RunDetail, RunEvent } from '../../lib/types'

const ICON: Record<string, typeof Compass> = {
  'explorer-a': Compass, 'explorer-b': Compass, 'input-tester': FlaskConical, verifier: ShieldCheck, 'single-agent': Bot,
}
const ROLE: Record<string, string> = {
  'explorer-a': 'Explorer A', 'explorer-b': 'Explorer B', 'input-tester': 'Input tester', verifier: 'Verifier', 'single-agent': 'Single agent',
}

function lastHandoffSeq(d: RunDetail) {
  return d.events.reduce((m, e) => (e.type === 'handoff_created' ? Math.max(m, e.seq) : m), 0)
}

/**
 * One labelled icon per agent in this workflow. States come from recorded claims, actions and
 * events: several workers can be active at once. A handoff animates only when a new
 * handoff_created event arrives; there is no invented progress.
 */
export function AgentStrip({ detail, selected, onSelect }: {
  detail: RunDetail
  selected: string | null
  onSelect: (worker: string) => void
}) {
  // Handoffs already present when the strip first renders (old runs) do not animate.
  const [seen, setSeen] = useState(() => ({ run: detail.run.id, seq: lastHandoffSeq(detail), fresh: null as RunEvent | null, detail }))
  if (seen.detail !== detail) {
    const latest = [...detail.events].reverse().find((e) => e.type === 'handoff_created') ?? null
    if (seen.run !== detail.run.id) setSeen({ run: detail.run.id, seq: lastHandoffSeq(detail), fresh: null, detail })
    else if (latest && latest.seq > seen.seq) setSeen({ run: seen.run, seq: latest.seq, fresh: latest, detail })
    else setSeen({ ...seen, detail })
  }
  const latest = [...detail.events].reverse().find((e) => e.type === 'handoff_created')
  const agents = agentsOf(detail)
  const statuses = agents.map((w) => ({ w, st: workerStatus(detail, w), acted: hasActed(detail, w) }))
  const working = statuses.filter((s) => s.st.state === 'working').length
  const running = ['queued', 'running'].includes(detail.run.status)
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2 border-b border-slate-200 bg-white px-4 py-2" aria-label="Agents">
      <ul className="flex flex-wrap items-center gap-1.5" role="list">
        {statuses.map(({ w, st, acted }) => {
          const Icon = ICON[w] ?? Bot
          const active = st.state === 'working'
          const received = seen.fresh?.data.to_agent === w
          const stateText = !acted ? (running ? 'not started' : 'did not run') : active ? 'active' : running ? 'waiting' : 'done'
          return (
            <li key={w}>
              <button type="button" onClick={() => onSelect(w)} aria-pressed={selected === w}
                title={`${ROLE[w] ?? w}: ${st.label}. Show its browser view.`}
                className={cx('group flex items-center gap-2 rounded-lg border px-2 py-1 text-left transition-colors',
                  selected === w ? 'border-slate-900 bg-slate-50' : 'border-transparent hover:bg-slate-50')}>
                <span key={received ? `r${seen.seq}` : 'x'} className={cx(
                  'relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-1 ring-inset',
                  active ? 'bg-emerald-50 text-emerald-700 ring-emerald-300 fl-agent-active'
                    : acted ? 'bg-slate-100 text-slate-700 ring-slate-200' : 'bg-white text-slate-400 ring-0 border border-dashed border-slate-300',
                  received && 'fl-agent-received')}>
                  <Icon size={16} aria-hidden />
                  {active && <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-white" aria-hidden />}
                </span>
                <span className="leading-tight">
                  <span className="block text-[12px] font-medium text-slate-900">{ROLE[w] ?? w}</span>
                  <span className={cx('block text-[11px]', active ? 'text-emerald-700' : 'text-slate-500')}>{stateText}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      <div className="flex min-w-0 flex-1 items-center gap-3 text-[11px] text-slate-600">
        {running && <span className="shrink-0 tabular-nums">{working} active now</span>}
        {latest && (
          <span key={seen.fresh?.seq ?? 'static'} className={cx('inline-flex min-w-0 items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5',
            seen.fresh?.seq === latest.seq && 'fl-handoff-new')} aria-live="polite">
            <span className="shrink-0 font-medium text-slate-700">Latest handoff</span>
            <span className="shrink-0">{String(latest.data.from_agent)}</span>
            <ArrowRight size={11} aria-hidden className="shrink-0" />
            <span className="shrink-0">{String(latest.data.to_agent)}</span>
            <span className="truncate text-slate-500">· {latest.data.kind === 'form_to_tester' ? 'form to test' : 'candidate to verify'}</span>
          </span>
        )}
      </div>
    </div>
  )
}
