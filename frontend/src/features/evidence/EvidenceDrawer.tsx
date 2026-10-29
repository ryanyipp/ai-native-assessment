import { ArrowRight, ChevronLeft, ChevronRight, Cpu, ExternalLink, Globe, Image, MousePointerClick, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { ScreenshotPreview } from '../../components/Screenshot'
import { Badge, Button, Field, Kbd, SectionTitle, Tooltip, cx } from '../../components/ui'
import { artifactUrl } from '../../lib/api'
import { fmtInt, fmtMs, fmtTime, fmtUsd } from '../../lib/format'
import { agentFor, describeAction, evidenceFor, modelCallFor, reasoningFor, stateById } from '../../lib/run-model'
import type { BrowserAction, RunDetail, ScreenState, Transition } from '../../lib/types'
import type { Selection } from '../flow-map/FlowMap'

function ArtifactLink({ detail, id, label, icon }: { detail: RunDetail; id: string | null | undefined; label: string; icon: ReactNode }) {
  if (!id) return <span className="text-slate-400">Not recorded</span>
  const ev = evidenceFor(detail, id)
  return (
    <a href={artifactUrl(id)} target="_blank" rel="noreferrer" data-artifact-id={id}
      className="group inline-flex max-w-full items-center gap-1.5 rounded text-accent-700 hover:underline">
      {icon}
      <span>{label}</span>
      <span className="truncate font-mono text-[11px] text-slate-400 group-hover:text-slate-500">{id}</span>
      {ev && <span className="sr-only">, sha256 {ev.sha256}</span>}
      <ExternalLink size={11} aria-hidden className="shrink-0" />
    </a>
  )
}

function Technical({ children, summary = 'Technical details' }: { children: ReactNode; summary?: string }) {
  return (
    <details className="group rounded-lg border border-slate-200 bg-slate-50/60">
      <summary className="cursor-pointer select-none rounded-lg px-3 py-2 text-xs font-medium text-slate-600 hover:text-slate-900">
        {summary}
      </summary>
      <div className="space-y-2 border-t border-slate-200 px-3 py-2">{children}</div>
    </details>
  )
}

function Json({ value }: { value: unknown }) {
  return (
    <pre className="max-h-56 overflow-auto rounded-md bg-slate-900 p-2.5 font-mono text-[11px] leading-relaxed text-slate-100">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

function StateChip({ state, onSelect }: { state: ScreenState | undefined; onSelect: (s: Selection) => void }) {
  if (!state) return <span className="text-slate-400">unknown</span>
  return (
    <button type="button" onClick={() => onSelect({ kind: 'state', id: state.id })}
      className="w-fit max-w-full truncate rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-left text-xs text-slate-800 hover:border-accent-500 hover:text-accent-700">
      {state.summary}
    </button>
  )
}

function recipeStep(a: BrowserAction) {
  if (a.type === 'fill') return `fill ${a.element_id} with "${a.value}"`
  if (a.type === 'navigate') return `open ${a.url}`
  if (a.type === 'click') return `click ${a.element_id}`
  return a.type
}

function TimingBar({ label, ms, tone, help, max }: { label: string; ms: number | null; tone: string; help: string; max: number }) {
  return (
  <div>
    <div className="flex items-baseline justify-between text-[13px]">
      <Tooltip content={help}><span tabIndex={0} className="text-slate-600 underline decoration-slate-300 decoration-dotted underline-offset-2">{label}</span></Tooltip>
      <span className="font-mono text-xs tabular-nums text-slate-900">{ms == null ? 'no model call' : fmtMs(ms)}</span>
    </div>
    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
      {ms != null && <div className={cx('h-full rounded-full', tone)} style={{ width: `${Math.max(2, (ms / max) * 100)}%` }} />}
    </div>
  </div>
)
}

/** Timing is shown as two separately measured spans; they are never summed into one number. */
function Timing({ browserMs, modelMs }: { browserMs: number; modelMs: number | null }) {
  const max = Math.max(browserMs, modelMs ?? 0, 1)
  return (
    <div className="space-y-2.5">
      <TimingBar max={max} label="Browser action" ms={browserMs} tone="bg-accent-500" help="Time the browser engine spent executing this command and waiting for the page to load." />
      <TimingBar max={max} label="Model decision" ms={modelMs} tone="bg-violet-500" help="Round-trip latency of the model call that chose this action. Measured separately from browser time." />
    </div>
  )
}

function TransitionEvidence({ detail, t, onSelect }: { detail: RunDetail; t: Transition; onSelect: (s: Selection) => void }) {
  const a = detail.actions.find((x) => x.id === t.action_result_id)
  const mc = modelCallFor(detail, t.model_call_id)
  const reasoning = reasoningFor(detail, t.model_call_id)
  const agent = a ? agentFor(detail, a.id) : null
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={t.ok ? 'green' : 'red'}>{t.ok ? 'Action succeeded' : 'Action failed'}</Badge>
          {agent && <Badge icon={<MousePointerClick size={11} />}>{agent}</Badge>}
        </div>
        <h2 className="text-base font-semibold leading-snug text-slate-900">{describeAction(t.action, a?.target_description)}</h2>
        <div className="grid grid-cols-[2.5rem_minmax(0,1fr)] items-center gap-x-2 gap-y-1 text-xs text-slate-500">
          <span>From</span><StateChip state={stateById(detail, t.source_state_id)} onSelect={onSelect} />
          <span className="flex items-center gap-1">To <ArrowRight size={11} aria-hidden /></span><StateChip state={stateById(detail, t.target_state_id)} onSelect={onSelect} />
        </div>
      </div>

      <ScreenshotPreview id={t.screenshot_artifact_id} alt={`Page after step ${t.step}`} caption={`Step ${t.step}: page after "${t.label}"`} />

      <section>
        <SectionTitle>Action</SectionTitle>
        <dl className="divide-y divide-slate-100">
          <Field label="Command"><code className="font-mono text-xs">{t.action.type}</code>{t.action.element_id && <span className="font-mono text-xs text-slate-500"> · {t.action.element_id}</span>}</Field>
          {a?.target_description && <Field label="Target">{a.target_description}</Field>}
          {t.action.value !== undefined && (
            <Field label="Input"><span className="whitespace-pre-wrap rounded bg-amber-50 px-1 font-mono text-xs text-amber-900 ring-1 ring-amber-200">{t.action.value}</span></Field>
          )}
          {t.action.url && <Field label="URL" mono>{t.action.url}</Field>}
          <Field label="Outcome">{t.ok ? 'Executed without error' : <span className="text-red-700">{a?.error ?? 'failed'}</span>}</Field>
          {a && <Field label="Page before" mono>{a.url_before}</Field>}
          {a && <Field label="Page after" mono>{a.url_after}</Field>}
          {a && <Field label="Started">{fmtTime(a.started_at)}</Field>}
        </dl>
      </section>

      <section>
        <SectionTitle>Timing</SectionTitle>
        <Timing browserMs={t.duration_ms} modelMs={mc ? mc.latency_ms : null} />
      </section>

      {mc && (
        <section>
          <SectionTitle>Model decision</SectionTitle>
          {reasoning && (
            <blockquote className="mb-2 border-l-2 border-violet-300 pl-3 text-[13px] italic leading-relaxed text-slate-700">{reasoning}</blockquote>
          )}
          <dl className="divide-y divide-slate-100">
            <Field label="Model" mono>{mc.model}{mc.provider && <span className="text-slate-500"> via {mc.provider}</span>}</Field>
            <Field label="Tokens"><span className="tabular-nums">{fmtInt(mc.prompt_tokens)} in · {fmtInt(mc.completion_tokens)} out</span></Field>
            <Field label="Reported cost"><span className="tabular-nums">{fmtUsd(mc.reported_cost_usd, 6)}</span></Field>
            {!mc.ok && <Field label="Error"><span className="text-red-700">{mc.error}</span></Field>}
          </dl>
        </section>
      )}

      <Technical>
        <dl>
          <Field label="Transition" mono>{t.id}</Field>
          <Field label="Action result" mono>{t.action_result_id}</Field>
          {mc && <Field label="Model call" mono>{mc.id}</Field>}
        </dl>
        <div className="flex flex-col gap-1.5 text-[13px]">
          <ArtifactLink detail={detail} id={t.screenshot_artifact_id} label="Screenshot" icon={<Image size={13} aria-hidden />} />
          <ArtifactLink detail={detail} id={a?.observation_artifact_id} label="Page observation" icon={<Globe size={13} aria-hidden />} />
          <ArtifactLink detail={detail} id={mc?.artifact_id} label="Prompt and response" icon={<Cpu size={13} aria-hidden />} />
        </div>
        <Json value={t.action} />
      </Technical>
    </div>
  )
}

function TrList({ items, empty, onSelect }: { items: Transition[]; empty: string; onSelect: (s: Selection) => void }) {
  return (
    items.length === 0 ? (
      <p className="text-[13px] text-slate-500">{empty}</p>
    ) : (
      <ul className="space-y-1">
        {items.map((t) => (
          <li key={t.id}>
            <button type="button" onClick={() => onSelect({ kind: 'transition', id: t.id })}
              className="flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left text-[13px] hover:bg-slate-100">
              <span className="w-6 shrink-0 text-right font-mono text-[11px] text-slate-500">{t.step}</span>
              <span className="truncate">{t.label}</span>
              {t.source_state_id === t.target_state_id && <Badge className="ml-auto">same state</Badge>}
            </button>
          </li>
        ))}
      </ul>
    )
  )
}

function StateEvidence({ detail, s, onSelect }: { detail: RunDetail; s: ScreenState; onSelect: (sel: Selection) => void }) {
  const incoming = detail.transitions.filter((t) => t.target_state_id === s.id).sort((a, b) => a.step - b.step)
  const outgoing = detail.transitions.filter((t) => t.source_state_id === s.id).sort((a, b) => a.step - b.step)
  return (
    <div className="space-y-5">
      <div className="space-y-1">
        <Badge tone="blue">Observed state</Badge>
        <h2 className="text-base font-semibold leading-snug text-slate-900">{s.summary}</h2>
        <p className="font-mono text-xs text-slate-500">{s.route}</p>
      </div>
      <ScreenshotPreview id={s.screenshot_artifact_id} alt={`Screenshot of ${s.summary}`} caption={`State: ${s.summary}`} />
      <section>
        <SectionTitle>Page</SectionTitle>
        <dl className="divide-y divide-slate-100">
          <Field label="Title">{s.title}</Field>
          <Field label="First URL" mono>{s.url}</Field>
          <Field label="First seen">Step {s.first_seen_step}</Field>
        </dl>
      </section>
      <section>
        <SectionTitle>Reached by</SectionTitle>
        <TrList items={incoming} empty="Starting page of the run." onSelect={onSelect} />
      </section>
      <section>
        <SectionTitle>Actions taken here</SectionTitle>
        <TrList items={outgoing} empty="No actions were taken from this state." onSelect={onSelect} />
      </section>
      <section>
        <SectionTitle>Replay recipe</SectionTitle>
        <ol className="space-y-1 text-[13px]">
          {s.setup_recipe.map((a, i) => (
            <li key={i} className="flex gap-2">
              <span className="w-4 shrink-0 text-right font-mono text-[11px] text-slate-400">{i + 1}</span>
              <span className="min-w-0 font-mono text-xs [overflow-wrap:anywhere]">{recipeStep(a)}</span>
            </li>
          ))}
        </ol>
        <p className="mt-1.5 text-xs text-slate-500">Element ids refer to the observation at that step. Replay by another worker is not implemented yet.</p>
      </section>
      <Technical>
        <dl>
          <Field label="State id" mono>{s.id}</Field>
          <Field label="Signature" mono>{s.signature}</Field>
          <Field label="Policy" mono>{s.signature_policy}</Field>
        </dl>
        <ArtifactLink detail={detail} id={s.screenshot_artifact_id} label="Screenshot" icon={<Image size={13} aria-hidden />} />
      </Technical>
    </div>
  )
}

export function EvidencePanel({ detail, selection, onSelect, onStep }: {
  detail: RunDetail
  selection: Selection
  onSelect: (s: Selection) => void
  onStep: (dir: -1 | 1) => void
}) {
  const t = selection?.kind === 'transition' ? detail.transitions.find((x) => x.id === selection.id) : undefined
  const s = selection?.kind === 'state' ? stateById(detail, selection.id) : undefined
  if (!t && !s) return null
  const steps = detail.transitions.length
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-2">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={() => onStep(-1)} aria-label="Previous step"><ChevronLeft size={15} /></Button>
          <span className="min-w-[5.5rem] text-center text-xs tabular-nums text-slate-600">
            {t ? `Step ${t.step} of ${steps}` : `State · step ${s!.first_seen_step}`}
          </span>
          <Button variant="ghost" size="sm" onClick={() => onStep(1)} aria-label="Next step"><ChevronRight size={15} /></Button>
          <span className="ml-1 hidden items-center gap-1 text-[11px] text-slate-400 xl:flex"><Kbd>←</Kbd><Kbd>→</Kbd> steps</span>
        </div>
        <Button variant="ghost" size="sm" onClick={() => onSelect(null)} aria-label="Close evidence"><X size={15} /></Button>
      </div>
      <div key={selection!.id} className="fl-enter min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {t && <TransitionEvidence detail={detail} t={t} onSelect={onSelect} />}
        {s && <StateEvidence detail={detail} s={s} onSelect={onSelect} />}
      </div>
    </div>
  )
}

