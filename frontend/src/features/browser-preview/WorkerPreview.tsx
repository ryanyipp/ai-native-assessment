import { Camera, MousePointerClick } from 'lucide-react'
import { useState } from 'react'
import { Thumb } from '../../components/Screenshot'
import { artifactUrl } from '../../lib/api'
import { fmtTime } from '../../lib/format'
import { describeAction, phaseLabel, transitionForAction } from '../../lib/run-model'
import { cx } from '../../lib/ui-utils'
import { beforeShotFor, workerStatus, workersOf, type WorkerState } from '../../lib/workers'
import type { ActionResult, RunDetail } from '../../lib/types'
import type { Selection } from '../flow-map/FlowMap'

const DOT: Record<WorkerState, string> = {
  working: 'bg-emerald-500', waiting: 'bg-slate-400', stopped: 'bg-amber-500', finished: 'bg-slate-300',
}

/** Highlight drawn on the screenshot taken BEFORE the action, from its recorded element bounds. */
function Highlight({ before, action }: { before: ActionResult; action: ActionResult }) {
  const [nat, setNat] = useState<{ w: number; h: number } | null>(null)
  const b = action.target_box!
  return (
    <div className="relative">
      <img src={artifactUrl(before.screenshot_artifact_id!)} alt={`Page before step ${action.step}`}
        onLoad={(e) => setNat({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
        className="block w-full rounded border border-slate-200" />
      {nat && (
        <span aria-hidden data-testid="click-highlight" className="pointer-events-none absolute rounded-sm ring-2 ring-accent-600 motion-safe:animate-pulse"
          style={{ left: `${(b.x / nat.w) * 100}%`, top: `${(b.y / nat.h) * 100}%`,
            width: `${(b.width / nat.w) * 100}%`, height: `${(b.height / nat.h) * 100}%` }} />
      )}
    </div>
  )
}

export function WorkerPreview({ detail, worker, onWorker, onSelect, compact = false }: {
  detail: RunDetail
  worker: string | null
  onWorker: (w: string) => void
  onSelect: (s: Selection) => void
  compact?: boolean
}) {
  const workers = workersOf(detail)
  const current = worker && workers.includes(worker) ? worker : workers[0] ?? null
  const [showWhere, setShowWhere] = useState(false)
  if (!current) {
    return <p className="p-4 text-sm text-slate-600">No worker has recorded a browser action yet.</p>
  }
  const st = workerStatus(detail, current)
  const a = st.lastAction
  const tr = a ? transitionForAction(detail, a) : undefined
  const before = a ? beforeShotFor(detail, a) : null
  const openEvidence = () => {
    if (tr) onSelect({ kind: 'transition', id: tr.id })
    else if (a) {
      const s = detail.states.find((x) => x.first_seen_step === a.step)
      if (s) onSelect({ kind: 'state', id: s.id })
    }
  }
  return (
    <section aria-label="Worker browser view" className="flex h-full min-h-0 flex-col bg-white">
      <div className="border-b border-slate-200 px-3 py-2">
        <div role="radiogroup" aria-label="Choose a worker to watch" className="flex flex-wrap gap-1">
          {workers.map((w) => {
            const s = workerStatus(detail, w)
            return (
              <button key={w} type="button" role="radio" aria-checked={w === current} onClick={() => onWorker(w)}
                className={cx('inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[12px] font-medium',
                  w === current ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 text-slate-700 hover:bg-slate-50')}>
                <span className={cx('h-1.5 w-1.5 rounded-full', DOT[s.state])} aria-hidden />
                {w}<span className="sr-only">, {s.label}</span>
              </button>
            )
          })}
        </div>
        <div className="mt-2 text-xs text-slate-700" aria-live="polite">
          <span className="font-medium">{st.label}</span>
          {st.task && st.state === 'working' && <span className="ml-1 font-mono text-slate-500">{st.task.key}</span>}
          {a && (
            <span className="block text-slate-600">
              Last recorded action: step {a.step} · {tr?.label ?? describeAction(a.action, a.target_description)}
              {a.phase && a.phase !== 'explore' ? ` · ${phaseLabel[a.phase]}` : ''} · {a.ok ? 'ok' : 'failed'} · {fmtTime(a.started_at)}
            </span>
          )}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-3">
        {a?.screenshot_artifact_id ? (
          <>
            <button type="button" onClick={openEvidence} className="block w-full text-left" aria-label={`Open evidence for step ${a.step}`}>
              {showWhere && before ? <Highlight before={before} action={a} />
                : <Thumb id={a.screenshot_artifact_id} alt={`Page after step ${a.step}`}
                    className={cx('w-full rounded border border-slate-200', compact ? 'max-h-52' : '')} />}
            </button>
            <p className="mt-1.5 flex items-start gap-1 text-[11px] leading-snug text-slate-600">
              <Camera size={12} className="mt-px shrink-0" aria-hidden />
              {showWhere && before
                ? `Screenshot recorded after step ${before.step} (the page before step ${a.step}), with the element step ${a.step} acted on outlined from its recorded bounds.`
                : `Screenshot recorded after step ${a.step}. It refreshes when this worker records another action; it is not live video.`}
            </p>
            {before ? (
              <button type="button" aria-pressed={showWhere} onClick={() => setShowWhere((v) => !v)}
                className="mt-1.5 inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50 aria-pressed:border-accent-600 aria-pressed:text-accent-700">
                <MousePointerClick size={12} aria-hidden />{showWhere ? 'Show page after the action' : `Show where step ${a.step} acted`}
              </button>
            ) : a.action.type === 'click' || a.action.type === 'fill' ? (
              <p className="mt-1 text-[11px] text-slate-500">No highlight: {a.target_box ? 'no screenshot of the page just before this action in the same session' : 'element bounds were not recorded for this action'}.</p>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-slate-600">This worker has not recorded a screenshot yet.</p>
        )}
      </div>
    </section>
  )
}
