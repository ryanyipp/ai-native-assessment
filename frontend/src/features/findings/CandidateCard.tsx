import { FlaskConical, ShieldCheck } from 'lucide-react'
import { Badge, Field, SectionTitle } from '../../components/ui'
import { Thumb } from '../../components/Screenshot'
import { artifactUrl } from '../../lib/api'
import { evidenceFor, testCaseFor } from '../../lib/run-model'
import { verificationMeta } from '../../lib/ui-utils'
import type { Finding, RunDetail, VerificationAttempt } from '../../lib/types'
import type { Selection } from '../flow-map/FlowMap'

const failureText: Record<string, string> = {
  setup: 'Setup failure (could not recreate the start conditions)',
  application: 'Application failure during the repeated actions',
  expectation: 'Expected behaviour not explicit',
  verifier: 'No valid assertion',
}

function EvidenceStrip({ ids, detail, label }: { ids: string[]; detail: RunDetail; label: string }) {
  const items = ids.map((id) => evidenceFor(detail, id)).filter(Boolean)
  const shots = items.filter((e) => e!.kind === 'screenshot')
  const other = items.filter((e) => e!.kind !== 'screenshot')
  if (items.length === 0) return <p className="text-xs text-slate-500">No evidence recorded.</p>
  return (
    <div className="space-y-1.5">
      {shots.length > 0 && (
        <ul className="flex gap-1.5 overflow-x-auto pb-1" aria-label={`${label} screenshots`}>
          {shots.slice(-4).map((e) => (
            <li key={e!.id} className="shrink-0">
              <a href={artifactUrl(e!.id)} target="_blank" rel="noreferrer" className="block rounded focus-visible:outline-2">
                <Thumb id={e!.id} alt={`${label} screenshot ${e!.path.split('/').pop()}`} className="h-14 w-24 rounded border border-slate-200" />
              </a>
            </li>
          ))}
        </ul>
      )}
      <p className="flex flex-wrap gap-x-2 text-[11px] text-slate-500">
        {other.slice(-3).map((e) => (
          <a key={e!.id} href={artifactUrl(e!.id)} target="_blank" rel="noreferrer" className="font-mono text-accent-700 hover:underline">
            {e!.kind}:{e!.id.slice(-6)}
          </a>
        ))}
        <span>{items.length} artifact{items.length === 1 ? '' : 's'}</span>
      </p>
    </div>
  )
}

function Attempt({ v, detail, onSelect }: { v: VerificationAttempt; detail: RunDetail; onSelect: (s: Selection) => void }) {
  const m = verificationMeta[v.outcome]
  const tr = detail.transitions.find((t) => t.verification_id === v.id)
  const obs = v.result?.observed ?? {}
  const shown = ['matching_messages', 'alert_messages', 'route', 'matches', 'field_value'].filter((k) => k in obs)
  return (
    <li className="space-y-2 rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs font-semibold">Replay {v.replay_index + 1}</span>
        <Badge tone={m.tone}>{m.label}</Badge>
        {v.failure_class && <Badge>{failureText[v.failure_class]}</Badge>}
        {v.result && <Badge tone={v.result.passed ? 'green' : 'red'}>Assertion {v.result.passed ? 'held' : 'failed'}</Badge>}
      </div>
      <p className="text-xs leading-relaxed text-slate-700">{v.reason}</p>
      <dl className="divide-y divide-slate-100 text-xs">
        <Field label="Context" mono>{v.context_id ?? '—'} (fresh)</Field>
        <Field label="Setup">{v.setup_ok ? `reached via ${v.setup_strategy}` : v.setup_error ?? 'not attempted'}</Field>
        {shown.length > 0 && (
          <Field label="Observed" mono>
            <span className="[overflow-wrap:anywhere]">{shown.map((k) => `${k}: ${JSON.stringify(obs[k])}`).join(' · ')}</span>
          </Field>
        )}
      </dl>
      <EvidenceStrip ids={v.evidence_refs} detail={detail} label={`Verifier replay ${v.replay_index + 1}`} />
      {tr && (
        <button type="button" onClick={() => onSelect({ kind: 'transition', id: tr.id })} className="text-xs font-medium text-accent-700 hover:underline">
          Show this replay on the map (step {tr.step}) →
        </button>
      )}
    </li>
  )
}

export function CandidateCard({ f, detail, onSelect }: { f: Finding; detail: RunDetail; onSelect: (s: Selection) => void }) {
  const m = verificationMeta[f.verification_status]
  const tc = testCaseFor(detail, f.test_case_id)
  const attempts = (detail.verifications ?? []).filter((v) => v.finding_id === f.id).sort((a, b) => a.replay_index - b.replay_index)
  const assertion = attempts.find((a) => a.assertion)?.assertion
  const testTr = tc && detail.transitions.find((t) => t.test_case_id === tc.id)
  return (
    <article className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" aria-label={`Finding ${f.id}`}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={m.tone}>{m.label}</Badge>
        <Badge>{f.kind === 'defect_candidate' ? 'Candidate defect' : 'Review observation'}</Badge>
        {f.requirement_ref && <Badge tone="blue">{f.requirement_ref}</Badge>}
        <span className="text-[11px] text-slate-500">reported by {f.reported_by}{f.verified_by ? ` · verified by ${f.verified_by}` : ''}</span>
      </div>
      <h2 className="text-sm font-semibold leading-snug">{f.description}</h2>
      {f.verification_reason && <p className="text-xs leading-relaxed text-slate-600">{f.verification_reason}</p>}
      <dl className="divide-y divide-slate-100">
        <Field label="Requirement">{f.requirement_text ? `${f.requirement_ref}: ${f.requirement_text}` : 'None supplied for this expectation'}</Field>
        <Field label="Inputs" mono><span className="[overflow-wrap:anywhere]">{JSON.stringify(f.inputs ?? {})}</span></Field>
        <Field label="Expected">{f.expected}</Field>
        <Field label="Tester saw">{f.observed}</Field>
        {f.source_finding_id && <Field label="Re-check of" mono>{f.source_finding_id}</Field>}
      </dl>

      <section>
        <SectionTitle aside={<FlaskConical size={14} className="text-slate-500" />}>Original suspicion: input tester evidence</SectionTitle>
        {tc ? (
          <div className="space-y-1.5">
            <p className="text-xs text-slate-600">
              Test case “{tc.label}” in context <span className="font-mono">{tc.context_id}</span>; tester verdict: <strong>{tc.tester_verdict ?? '—'}</strong>
            </p>
            <EvidenceStrip ids={tc.evidence_refs} detail={detail} label="Tester" />
            {testTr && (
              <button type="button" onClick={() => onSelect({ kind: 'transition', id: testTr.id })} className="text-xs font-medium text-accent-700 hover:underline">
                Show the test case on the map (step {testTr.step}) →
              </button>
            )}
          </div>
        ) : (
          <EvidenceStrip ids={f.evidence_refs} detail={detail} label="Original" />
        )}
      </section>

      <section>
        <SectionTitle aside={<ShieldCheck size={14} className="text-slate-500" />}>Independent verification</SectionTitle>
        {assertion ? (
          <dl className="mb-2 divide-y divide-slate-100 text-xs">
            <Field label="Assertion" mono><span className="[overflow-wrap:anywhere]">{assertion.type} {JSON.stringify(assertion.params)}</span></Field>
            <Field label="Expected value">{assertion.expected ?? '—'}</Field>
            <Field label="Chosen by">{assertion.chosen_by ?? '—'} · evaluated by code</Field>
          </dl>
        ) : null}
        {attempts.length === 0 ? (
          <p className="text-xs text-slate-500">No verification attempt recorded.</p>
        ) : (
          <ol className="space-y-2">{attempts.map((v) => <Attempt key={v.id} v={v} detail={detail} onSelect={onSelect} />)}</ol>
        )}
      </section>
    </article>
  )
}
