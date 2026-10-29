import * as Tabs from '@radix-ui/react-tabs'
import * as RTooltip from '@radix-ui/react-tooltip'
import { ReactFlowProvider } from '@xyflow/react'
import { Activity, ExternalLink, FileSearch, Info, Layers, Loader2, PanelLeft, Plus, RefreshCw, ScanSearch, Waypoints } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Badge, Button, Callout, EmptyState, ProvenanceBadge, StatusBadge, Tooltip } from './components/ui'
import { cx } from './lib/ui-utils'
import { EvidencePanel } from './features/evidence/EvidenceDrawer'
import { FindingsPanel } from './features/findings/FindingsPanel'
import { FlowMap, type Selection } from './features/flow-map/FlowMap'
import { RunActivity } from './features/run-activity/RunActivity'
import { RunHistory } from './features/run-history/RunHistory'
import { RunLauncher } from './features/run-launcher/RunLauncher'
import { api } from './lib/api'
import { fmtInt, fmtUsd, shortUrl } from './lib/format'
import { transitionsByStep } from './lib/run-model'
import type { Health, Run, RunDetail } from './lib/types'

const ACTIVE = new Set(['queued', 'running'])
type Tab = 'evidence' | 'activity' | 'findings'

function RunHeader({ detail }: { detail: RunDetail }) {
  const r = detail.run
  const active = ACTIVE.has(r.status)
  return (
    <header className="border-b border-slate-200 bg-white px-5 py-3">
      <div className="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1.5">
        <h1 className="min-w-0 max-w-full truncate text-[15px] font-semibold text-slate-900" title={r.goal}>{r.goal}</h1>
        <StatusBadge status={r.status} withTooltip />
        <ProvenanceBadge run={r} />
        <Badge>{r.mode === 'explore_test_verify' ? 'Explorer → tester → verifier' : r.mode === 'reverify' ? 'Re-check of a finding' : 'Single explorer'}</Badge>
        {r.target_build && (
          <Tooltip content="Evaluation-only label of the target build. It is recorded for comparison and never given to the agents.">
            <span tabIndex={0} className="inline-flex"><Badge tone="blue">build: {r.target_build}</Badge></span>
          </Tooltip>
        )}
      </div>
      <div className="mt-1.5 flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
        <span className="font-mono text-slate-500">{r.id}</span>
        <a href={r.target_url} target="_blank" rel="noreferrer" className="inline-flex min-w-0 items-center gap-1 hover:text-accent-700" title={r.target_url}>
          <span className="truncate font-mono">{shortUrl(r.target_url)}</span>
          <ExternalLink size={11} aria-hidden className="shrink-0" />
        </a>
        <span className="font-mono">{r.model}</span>
        <span className="tabular-nums">
          {r.usage.model_calls} calls · {fmtInt(r.usage.total_tokens)} tokens · {fmtUsd(r.usage.reported_cost_usd, 4)} reported
          {r.usage.calls_without_cost > 0 && ` (${r.usage.calls_without_cost} calls without cost)`}
        </span>
        {active && (
          <span className="inline-flex items-center gap-1 text-accent-700"><Loader2 size={12} className="animate-spin" aria-hidden />Updating every 1.5 s</span>
        )}
      </div>
      {r.stop_reason && (
        <p className={cx('mt-1.5 text-xs', r.status === 'completed' ? 'text-slate-600' : 'font-medium text-amber-800')}>
          <span className="text-slate-500">Stop reason:</span> {r.stop_reason}
          {r.status === 'completed' && <span className="text-slate-500"> (the run finished; this is not a verdict on the website)</span>}
        </p>
      )}
    </header>
  )
}

function MapSkeleton() {
  return (
    <div className="flex h-full items-center justify-center gap-10 p-10" aria-busy="true" aria-label="Loading run">
      {[0, 1, 2].map((i) => <div key={i} className="h-44 w-56 animate-pulse rounded-xl bg-slate-200/70" />)}
    </div>
  )
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [runId, setRunId] = useState<string | null>(() => new URLSearchParams(location.search).get('run'))
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [selection, setSelection] = useState<Selection>(null)
  const [tab, setTab] = useState<Tab>('evidence')
  const [launcherOpen, setLauncherOpen] = useState(false)
  const [railOpen, setRailOpen] = useState(() => window.innerWidth >= 1280)
  const [showThumbs, setShowThumbs] = useState(true)
  const [reloadKey, setReloadKey] = useState(0)
  const inspectorRef = useRef<HTMLDivElement>(null)

  const refreshRuns = useCallback(() => {
    api.listRuns().then(setRuns).catch(() => undefined).finally(() => setRunsLoading(false))
    api.health()
      .then((h) => { setHealth(h); setHealthError(null) })
      .catch((e: Error) => { setHealth(null); setHealthError(e.message) })
  }, [])
  useEffect(refreshRuns, [refreshRuns])

  // Load the selected run; poll only while it is active.
  useEffect(() => {
    if (!runId) return
    let cancelled = false
    let timer: number | undefined
    const load = async () => {
      try {
        const d = await api.getRun(runId)
        if (cancelled) return
        setDetail(d)
        setDetailError(null)
        if (ACTIVE.has(d.run.status)) timer = window.setTimeout(load, 1500)
        else refreshRuns()
      } catch (e) {
        if (!cancelled) setDetailError((e as Error).message)
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
  }, [runId, refreshRuns, reloadKey])

  const openRun = useCallback((id: string) => {
    setSelection(null)
    setDetail((d) => (d?.run.id === id ? d : null))
    setDetailError(null)
    setRunId(id)
    if (window.innerWidth < 1280) setRailOpen(false)
  }, [])

  const select = useCallback((s: Selection) => {
    setSelection(s)
    if (s) setTab('evidence')
  }, [])

  const ordered = useMemo(() => (detail ? transitionsByStep(detail) : []), [detail])

  const step = useCallback((dir: -1 | 1) => {
    if (!detail || ordered.length === 0) return
    let idx: number
    if (selection?.kind === 'transition') {
      idx = ordered.findIndex((t) => t.id === selection.id) + dir
    } else if (selection?.kind === 'state') {
      const s = detail.states.find((x) => x.id === selection.id)
      const after = ordered.findIndex((t) => t.step > (s?.first_seen_step ?? 0))
      idx = dir === 1 ? (after === -1 ? ordered.length - 1 : after) : (after === -1 ? ordered.length - 1 : after) - 1
    } else {
      idx = dir === 1 ? 0 : ordered.length - 1
    }
    idx = Math.max(0, Math.min(ordered.length - 1, idx))
    select({ kind: 'transition', id: ordered[idx].id })
  }, [detail, ordered, selection, select])

  // Arrow keys step through transitions; Escape clears the selection. Ignored while typing or in dialogs.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (el.closest('input, textarea, select, [role=dialog], [role=tablist]') || e.altKey || e.ctrlKey || e.metaKey) return
      if (e.key === 'ArrowRight' || e.key === ']') { e.preventDefault(); step(1) }
      else if (e.key === 'ArrowLeft' || e.key === '[') { e.preventDefault(); step(-1) }
      else if (e.key === 'Escape' && selection) setSelection(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [step, selection])

  const tabTrigger = (value: Tab, label: string, icon: React.ReactNode, count?: number) => (
    <Tabs.Trigger value={value}
      className="relative inline-flex h-10 items-center gap-1.5 px-1 text-[13px] font-medium text-slate-500 transition-colors hover:text-slate-900 data-[state=active]:text-slate-900 data-[state=active]:after:absolute data-[state=active]:after:inset-x-0 data-[state=active]:after:-bottom-px data-[state=active]:after:h-0.5 data-[state=active]:after:bg-slate-900">
      {icon}{label}
      {count !== undefined && <span className="rounded-full bg-slate-100 px-1.5 text-[10px] tabular-nums text-slate-600">{count}</span>}
    </Tabs.Trigger>
  )

  return (
    <RTooltip.Provider>
      <div className="flex h-full flex-col">
        {/* Top bar */}
        <header className="flex h-12 shrink-0 items-center gap-2 border-b border-slate-200 bg-white px-3">
          <Button variant="ghost" size="sm" onClick={() => setRailOpen((o) => !o)} aria-label={railOpen ? 'Hide run history' : 'Show run history'} aria-expanded={railOpen} aria-controls="run-rail">
            <PanelLeft size={16} />
          </Button>
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-slate-900 text-white"><Waypoints size={14} aria-hidden /></span>
            <span className="text-sm font-semibold tracking-tight">FlowLens</span>
            <span className="hidden text-xs text-slate-500 sm:inline">AI website reviewer</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {health ? (
              <Tooltip content={`Model calls are made only by the backend. Credit pool: ${fmtUsd(health.spent_reported_usd, 4)} spent of ${fmtUsd(health.budget_usd, 2)}.`}>
                <span tabIndex={0} className="hidden items-center gap-1.5 text-xs text-slate-600 md:inline-flex">
                  <span className={cx('h-1.5 w-1.5 rounded-full', health.api_key_configured ? 'bg-emerald-500' : 'bg-amber-500')} aria-hidden />
                  <span className="font-mono">{health.model}</span>
                  {!health.api_key_configured && <span className="text-amber-700">· key missing</span>}
                </span>
              </Tooltip>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs text-red-700" role="status">
                <span className="h-1.5 w-1.5 rounded-full bg-red-500" aria-hidden />Backend unreachable
              </span>
            )}
            <Button variant="primary" size="sm" onClick={() => setLauncherOpen(true)}><Plus size={14} aria-hidden />New run</Button>
          </div>
        </header>

        <div className="relative flex min-h-0 flex-1">
          {/* Run history rail */}
          <aside id="run-rail" aria-label="Runs"
            className={cx('z-20 flex w-72 shrink-0 flex-col border-r border-slate-200 bg-white transition-[margin] duration-200',
              'max-xl:absolute max-xl:inset-y-0 max-xl:left-0 max-xl:shadow-xl',
              railOpen ? 'ml-0' : '-ml-72 max-xl:invisible')}>
            <div className="flex items-center justify-between px-4 pb-1 pt-3">
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Run history</h2>
              <Tooltip content="Refresh"><Button variant="ghost" size="sm" onClick={refreshRuns} aria-label="Refresh run history"><RefreshCw size={13} /></Button></Tooltip>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <RunHistory runs={runs} activeId={runId} onOpen={openRun} loading={runsLoading} />
            </div>
          </aside>

          {/* Workspace */}
          <main className="flex min-w-0 flex-1 flex-col">
            {healthError && !detail && (
              <div className="p-4"><Callout tone="red" title="Cannot reach the backend">{healthError} Start it with <code className="font-mono">uvicorn flowlens.main:app --port 8000</code> from <code className="font-mono">backend/</code>.</Callout></div>
            )}
            {!runId ? (
              <EmptyState icon={<ScanSearch size={28} />} title="No run selected"
                action={<Button variant="primary" className="mt-2" onClick={() => setLauncherOpen(true)}><Plus size={14} />New run</Button>}>
                Pick a run from the history, or start a new review of an authorised local or staging site.
              </EmptyState>
            ) : detailError && !detail ? (
              <div className="p-6">
                <Callout tone="red" title={`Could not load ${runId}`}>
                  {detailError}
                  <div className="mt-2"><Button size="sm" onClick={() => setReloadKey((k) => k + 1)}><RefreshCw size={13} />Retry</Button></div>
                </Callout>
              </div>
            ) : !detail ? (
              <MapSkeleton />
            ) : (
              <>
                <RunHeader detail={detail} />
                {detailError && (
                  <div className="border-b border-red-200 bg-red-50 px-5 py-1.5 text-xs text-red-800" role="alert">
                    Updates paused: {detailError} <button type="button" className="ml-2 underline" onClick={() => setReloadKey((k) => k + 1)}>Retry</button>
                  </div>
                )}
                <div className="flex min-h-0 flex-1 max-lg:flex-col">
                  {/* Map: the largest region */}
                  <section aria-label="Website flow map" data-testid="flow-map" className="relative min-h-0 min-w-0 flex-1 bg-slate-50 max-lg:min-h-[55vh]">
                    {detail.states.length === 0 ? (
                      <EmptyState icon={<Layers size={24} />} title={ACTIVE.has(detail.run.status) ? 'Opening the target…' : 'No states recorded'}>
                        {ACTIVE.has(detail.run.status) ? 'States appear as the explorer observes pages.' : detail.run.stop_reason ?? 'This run recorded no browser states.'}
                      </EmptyState>
                    ) : (
                      <ReactFlowProvider>
                        <FlowMap detail={detail} selection={selection} onSelect={select} showThumbs={showThumbs} onToggleThumbs={() => setShowThumbs((v) => !v)} />
                      </ReactFlowProvider>
                    )}
                  </section>

                  {/* Inspector */}
                  <Tabs.Root value={tab} onValueChange={(v) => setTab(v as Tab)} ref={inspectorRef}
                    className="flex min-h-0 w-[400px] shrink-0 flex-col border-l border-slate-200 bg-white max-lg:w-full max-lg:border-l-0 max-lg:border-t xl:w-[440px]">
                    <Tabs.List aria-label="Run details" className="flex shrink-0 gap-5 border-b border-slate-200 px-4">
                      {tabTrigger('evidence', 'Evidence', <FileSearch size={14} aria-hidden />)}
                      {tabTrigger('activity', 'Activity', <Activity size={14} aria-hidden />, detail.actions.length)}
                      {tabTrigger('findings', 'Findings', <Info size={14} aria-hidden />, detail.findings.length)}
                    </Tabs.List>
                    <Tabs.Content value="evidence" className="min-h-0 flex-1 focus-visible:outline-none">
                      {selection ? (
                        <EvidencePanel detail={detail} selection={selection} onSelect={select} onStep={step} />
                      ) : (
                        <EmptyState icon={<FileSearch size={22} />} title="Select a state or an action"
                          action={ordered.length > 0 && <Button size="sm" className="mt-1" onClick={() => step(1)}>Start at step 1</Button>}>
                          Click a page on the map or an action label to see its screenshot, inputs, outcome and timing. Use ← and → to step through actions.
                        </EmptyState>
                      )}
                    </Tabs.Content>
                    <Tabs.Content value="activity" className="min-h-0 flex-1 overflow-y-auto focus-visible:outline-none">
                      <RunActivity detail={detail} selection={selection} onSelect={select} />
                    </Tabs.Content>
                    <Tabs.Content value="findings" className="min-h-0 flex-1 overflow-y-auto focus-visible:outline-none">
                      <FindingsPanel detail={detail} onSelect={select} />
                    </Tabs.Content>
                  </Tabs.Root>
                </div>
              </>
            )}
          </main>
        </div>

        <RunLauncher health={health} open={launcherOpen} onOpenChange={(o) => { setLauncherOpen(o); if (o) refreshRuns() }}
          onCreated={(r) => { refreshRuns(); openRun(r.id) }} />
      </div>
    </RTooltip.Provider>
  )
}
