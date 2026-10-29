import { ClipboardCheck, Info, SearchCheck } from 'lucide-react'
import { Badge, Callout, EmptyState, Field, SectionTitle } from '../../components/ui'
import { fmtInt, fmtUsd } from '../../lib/format'
import type { Finding, RunDetail } from '../../lib/types'
import type { Selection } from '../flow-map/FlowMap'

const claimText = { retained: 'Values retained', not_retained: 'Values not retained', unknown: 'Could not determine' }

type CheckRow = { field: string; expected: string; actual_value: string | null; matched: boolean }

function FindingCard({ f, detail, onSelect }: { f: Finding; detail: RunDetail; onSelect: (s: Selection) => void }) {
  const check = f.same_context_check
  const rows = (check?.observed.fields as CheckRow[] | undefined) ?? []
  const reload = detail.transitions.find((t) => t.action.type === 'reload')
  return (
    <article className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone="amber">Unverified</Badge>
        <Badge>Explorer observation</Badge>
        <Badge>{f.reported_by}</Badge>
      </div>
      <h2 className="text-sm font-semibold leading-snug">{f.description}</h2>
      <dl className="divide-y divide-slate-100">
        <Field label="Expected">{f.expected}</Field>
        <Field label="Agent claim">{f.agent_claim ? claimText[f.agent_claim] : '—'}</Field>
        <Field label="Agent summary">{f.observed}</Field>
      </dl>
      {check && (
        <div>
          <SectionTitle aside={<Badge tone={check.passed ? 'green' : 'red'}>{check.passed ? 'Values matched' : 'Mismatch'}</Badge>}>
            Same-session engine check
          </SectionTitle>
          <table className="w-full table-fixed text-left text-xs">
            <thead className="text-slate-500">
              <tr>
                <th className="w-20 py-1 font-medium">Field</th>
                <th className="py-1 font-medium">Entered</th>
                <th className="py-1 font-medium">After reload</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((r) => (
                <tr key={r.field}>
                  <td className="py-1.5">{r.field}</td>
                  <td className="py-1.5 font-mono [overflow-wrap:anywhere]">{r.expected}</td>
                  <td className={`py-1.5 font-mono [overflow-wrap:anywhere] ${r.matched ? '' : 'text-red-700'}`}>{r.actual_value ?? 'not found'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs leading-relaxed text-slate-500">
            Code compared these values in the same browser session the explorer used. It checks the explorer's own trace and is not an
            independent replay.
          </p>
        </div>
      )}
      {reload && (
        <button type="button" onClick={() => onSelect({ kind: 'transition', id: reload.id })}
          className="text-xs font-medium text-accent-700 hover:underline">
          Open the reload evidence (step {reload.step}) →
        </button>
      )}
    </article>
  )
}

export function FindingsPanel({ detail, onSelect }: { detail: RunDetail; onSelect: (s: Selection) => void }) {
  const r = detail.run
  const failed = detail.actions.filter((a) => !a.ok).length
  return (
    <div className="space-y-4 px-4 py-4">
      <Callout title="Completed is not the same as correct">
        A <strong>completed</strong> run means the explorer finished its goal within the limits. It does not verify the website. Findings
        stay <strong>unverified</strong> until an independent verifier replays them in a fresh browser. No verifier has run yet.
      </Callout>

      {detail.findings.length === 0 ? (
        <EmptyState icon={<SearchCheck size={22} />} title="No observations reported">
          {r.status === 'running' || r.status === 'queued'
            ? 'The explorer has not finished yet.'
            : 'The explorer did not report a result for this run. Check the stop reason and the activity list.'}
        </EmptyState>
      ) : (
        detail.findings.map((f) => <FindingCard key={f.id} f={f} detail={detail} onSelect={onSelect} />)
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <SectionTitle aside={<ClipboardCheck size={14} className="text-slate-500" />}>Recorded totals</SectionTitle>
        <dl className="divide-y divide-slate-100">
          <Field label="States">{detail.states.length} observed</Field>
          <Field label="Transitions">{detail.transitions.length} ({failed} failed actions)</Field>
          <Field label="Model calls">{r.usage.model_calls} of {r.limits.max_model_calls} allowed</Field>
          <Field label="Tokens">{fmtInt(r.usage.prompt_tokens)} in · {fmtInt(r.usage.completion_tokens)} out</Field>
          <Field label="Reported cost">{fmtUsd(r.usage.reported_cost_usd, 6)} of {fmtUsd(r.limits.max_cost_usd, 2)} run limit</Field>
        </dl>
        <p className="mt-2 flex gap-1.5 text-xs text-slate-500">
          <Info size={13} className="mt-0.5 shrink-0" aria-hidden />
          Counts cover what this run observed. They are not site coverage.
        </p>
      </section>
    </div>
  )
}
