import { ReactFlowProvider } from '@xyflow/react'
import { useCallback, useEffect, useState } from 'react'
import { EvidenceDrawer, FindingPanel } from './features/evidence/EvidenceDrawer'
import { FlowMap, type Selection } from './features/flow-map/FlowMap'
import { RunLauncher } from './features/run-launcher/RunLauncher'
import { api } from './lib/api'
import type { Health, Run, RunDetail } from './lib/types'

const ACTIVE = new Set(['queued', 'running'])

function provenanceLabel(run: Run) {
  const p = run.provenance
  if (p.mocked_model) return 'mocked model'
  if (p.playback) return 'playback'
  return p.live ? 'live' : 'not live'
}

function StatusBadge({ status }: { status: string }) {
  const color: Record<string, string> = {
    running: 'bg-blue-100 text-blue-800',
    queued: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    partial: 'bg-amber-100 text-amber-800',
    failed: 'bg-red-100 text-red-800',
    interrupted: 'bg-slate-200 text-slate-700',
  }
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${color[status] ?? ''}`}>{status}</span>
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [runId, setRunId] = useState<string | null>(() => new URLSearchParams(location.search).get('run'))
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [selection, setSelection] = useState<Selection>(null)
  const [error, setError] = useState<string | null>(null)

  const refreshRuns = useCallback(() => {
    api.listRuns().then(setRuns).catch((e) => setError(String(e.message)))
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [])

  useEffect(refreshRuns, [refreshRuns])

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    let timer: number | undefined
    const load = async () => {
      try {
        const d = await api.getRun(runId)
        if (cancelled) return
        setDetail(d)
        setError(null)
        if (ACTIVE.has(d.run.status)) timer = window.setTimeout(load, 1500)
        else refreshRuns()
      } catch (e) {
        if (!cancelled) setError(String((e as Error).message))
      }
    }
    load()
    const url = new URL(location.href)
    url.searchParams.set('run', runId)
    history.replaceState(null, '', url)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [runId, refreshRuns])

  const select = useCallback((s: Selection) => setSelection(s), [])
  const run = detail?.run

  return (
    <div className="flex h-full bg-slate-50 text-slate-900">
      <aside className="flex w-80 shrink-0 flex-col gap-4 overflow-y-auto border-r border-slate-200 bg-white p-3">
        <h1 className="text-lg font-bold">FlowLens</h1>
        <RunLauncher health={health} onCreated={(r) => { setSelection(null); setDetail(null); setRunId(r.id); refreshRuns() }} />
        <div>
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-500">Runs</h2>
          <ul className="space-y-1">
            {runs.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => { setSelection(null); setRunId(r.id) }}
                  className={`w-full rounded border px-2 py-1 text-left text-xs ${r.id === runId ? 'border-pink-400 bg-pink-50' : 'border-slate-200'}`}>
                  <div className="flex items-center justify-between font-mono">{r.id} <StatusBadge status={r.status} /></div>
                  <div className="text-slate-500">{new Date(r.created_at).toLocaleString()} · {provenanceLabel(r)}</div>
                </button>
              </li>
            ))}
            {runs.length === 0 && <li className="text-xs text-slate-500">No runs yet.</li>}
          </ul>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        {error && <div className="bg-red-50 p-2 text-xs text-red-700">{error}</div>}
        {run && detail ? (
          <>
            <header className="space-y-1 border-b border-slate-200 bg-white p-3 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono font-semibold">{run.id}</span>
                <StatusBadge status={run.status} />
                <span className="rounded bg-slate-100 px-1.5 py-0.5">{provenanceLabel(run)}</span>
                <span>{run.model}</span>
                <span>· {run.usage.model_calls} calls · {run.usage.total_tokens} tokens · reported US${run.usage.reported_cost_usd.toFixed(5)}
                  {run.usage.calls_without_cost > 0 && ` (${run.usage.calls_without_cost} calls without cost)`}</span>
              </div>
              <div className="text-slate-600">Goal: {run.goal}</div>
              {run.stop_reason && <div className="text-slate-600">Stopped: {run.stop_reason}</div>}
              <div className="text-slate-500">
                {detail.states.length} observed states, {detail.transitions.length} transitions. The map shows only what this run observed, not full site coverage.
              </div>
            </header>
            <div className="flex min-h-0 flex-1">
              <div className="min-w-0 flex-1" data-testid="flow-map">
                <ReactFlowProvider>
                  <FlowMap detail={detail} selection={selection} onSelect={select} />
                </ReactFlowProvider>
              </div>
              <div className="w-96 shrink-0 space-y-3 overflow-y-auto border-l border-slate-200 bg-white">
                {selection ? (
                  <EvidenceDrawer detail={detail} selection={selection} onClose={() => setSelection(null)} />
                ) : (
                  <p className="p-3 text-xs text-slate-500">Click a state or a transition label to open its evidence.</p>
                )}
                <div className="space-y-2 p-3">
                  {detail.findings.map((f) => <FindingPanel key={f.id} finding={f} />)}
                  <details className="text-xs">
                    <summary className="cursor-pointer font-semibold">Events ({detail.events.length})</summary>
                    <ol className="mt-1 space-y-0.5">
                      {detail.events.map((e) => (
                        <li key={e.seq} className="font-mono text-[10px]">#{e.seq} {e.type}: {e.message}</li>
                      ))}
                    </ol>
                  </details>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="m-auto text-sm text-slate-500">Start a run or pick one from the list.</div>
        )}
      </main>
    </div>
  )
}
