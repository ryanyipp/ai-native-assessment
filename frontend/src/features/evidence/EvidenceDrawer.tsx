import { artifactUrl } from '../../lib/api'
import type { Finding, RunDetail } from '../../lib/types'
import type { Selection } from '../flow-map/FlowMap'

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-2 border-b border-slate-100 py-1 text-xs">
      <div className="text-slate-500">{label}</div>
      <div className="break-all">{children}</div>
    </div>
  )
}

function ArtifactLink({ id, label }: { id: string | null | undefined; label: string }) {
  if (!id) return <span className="text-slate-400">none</span>
  return (
    <a className="text-pink-600 underline" href={artifactUrl(id)} target="_blank" rel="noreferrer" data-artifact-id={id}>
      {label} ({id})
    </a>
  )
}

export function FindingPanel({ finding }: { finding: Finding }) {
  const check = finding.same_context_check
  return (
    <div className="space-y-1 rounded border border-amber-300 bg-amber-50 p-2">
      <div className="flex items-center gap-2 text-xs font-semibold">
        Explorer observation
        <span className="rounded bg-amber-200 px-1.5 py-0.5 text-[10px] uppercase">{finding.verification_status}</span>
      </div>
      <p className="text-xs">{finding.description}</p>
      <Row label="Agent claim">{finding.agent_claim}</Row>
      <Row label="Agent summary">{finding.observed}</Row>
      {check && (
        <Row label="Engine check">
          {check.passed ? 'values matched' : 'values did not match'} — same browser context, not independent
          verification
          <pre className="mt-1 overflow-auto rounded bg-white p-1 text-[10px]">{JSON.stringify(check.observed, null, 1)}</pre>
        </Row>
      )}
      <p className="text-[10px] text-slate-600">
        No independent verifier ran in this checkpoint, so this result is not a confirmed finding.
      </p>
    </div>
  )
}

export function EvidenceDrawer({ detail, selection, onClose }: {
  detail: RunDetail
  selection: Selection
  onClose: () => void
}) {
  if (!selection) return null
  const header = (title: string) => (
    <div className="mb-2 flex items-center justify-between">
      <h2 className="text-sm font-semibold">{title}</h2>
      <button type="button" onClick={onClose} className="text-xs text-slate-500 hover:text-slate-900" aria-label="Close evidence">
        ✕
      </button>
    </div>
  )

  if (selection.kind === 'state') {
    const s = detail.states.find((x) => x.id === selection.id)
    if (!s) return null
    return (
      <aside className="h-full overflow-y-auto p-3" aria-label="Evidence">
        {header('Screen state')}
        {s.screenshot_artifact_id && (
          <a href={artifactUrl(s.screenshot_artifact_id)} target="_blank" rel="noreferrer">
            <img src={artifactUrl(s.screenshot_artifact_id)} alt={`Screenshot of ${s.summary}`} className="mb-2 w-full rounded border" />
          </a>
        )}
        <Row label="Summary">{s.summary}</Row>
        <Row label="State id">{s.id}</Row>
        <Row label="Route">{s.route}</Row>
        <Row label="First URL">{s.url}</Row>
        <Row label="Signature">{s.signature} ({s.signature_policy})</Row>
        <Row label="Screenshot"><ArtifactLink id={s.screenshot_artifact_id} label="open" /></Row>
        <Row label="Setup recipe">
          <ol className="list-decimal pl-4">
            {s.setup_recipe.map((a, i) => (
              <li key={i} className="font-mono text-[10px]">{JSON.stringify(a)}</li>
            ))}
          </ol>
        </Row>
      </aside>
    )
  }

  const t = detail.transitions.find((x) => x.id === selection.id)
  if (!t) return null
  const a = detail.actions.find((x) => x.id === t.action_result_id)
  const mc = detail.model_calls.find((x) => x.id === t.model_call_id)
  const decision = detail.events.find((e) => e.type === 'decision' && e.data.model_call_id === t.model_call_id)
  const name = (id: string) => detail.states.find((s) => s.id === id)?.summary ?? id
  return (
    <aside className="h-full overflow-y-auto p-3" aria-label="Evidence">
      {header(`Transition · step ${t.step}`)}
      {t.screenshot_artifact_id && (
        <a href={artifactUrl(t.screenshot_artifact_id)} target="_blank" rel="noreferrer">
          <img src={artifactUrl(t.screenshot_artifact_id)} alt={`Screenshot after step ${t.step}`} className="mb-2 w-full rounded border" />
        </a>
      )}
      <Row label="Action">{t.label}</Row>
      <Row label="Command"><code className="text-[10px]">{JSON.stringify(t.action)}</code></Row>
      {t.action.value !== undefined && <Row label="Input">"{t.action.value}"</Row>}
      <Row label="Outcome">{t.ok ? 'ok' : <span className="text-red-700">failed: {a?.error}</span>}</Row>
      <Row label="From → to">{name(t.source_state_id)} → {name(t.target_state_id)}</Row>
      {a && (
        <>
          <Row label="Action result">{a.id}</Row>
          <Row label="URL before">{a.url_before}</Row>
          <Row label="URL after">{a.url_after}</Row>
          <Row label="Started">{new Date(a.started_at).toLocaleTimeString()}</Row>
          <Row label="Browser time">{a.duration_ms} ms</Row>
          <Row label="Observation"><ArtifactLink id={a.observation_artifact_id} label="json" /></Row>
        </>
      )}
      <Row label="Screenshot"><ArtifactLink id={t.screenshot_artifact_id} label="png" /></Row>
      {decision && <Row label="Agent reasoning">{decision.message}</Row>}
      {mc && (
        <>
          <Row label="Model call">
            <ArtifactLink id={mc.artifact_id} label="prompt + response" />
          </Row>
          <Row label="Model">{mc.model}{mc.provider ? ` via ${mc.provider}` : ''}</Row>
          <Row label="Model latency">{mc.latency_ms} ms</Row>
          <Row label="Tokens">{mc.prompt_tokens} in / {mc.completion_tokens} out</Row>
          <Row label="Reported cost">{mc.reported_cost_usd == null ? 'not reported' : `US$${mc.reported_cost_usd.toFixed(6)}`}</Row>
        </>
      )}
    </aside>
  )
}
