import { History } from 'lucide-react'
import { EmptyState, StatusBadge, cx, provenanceOf } from '../../components/ui'
import { fmtDateTime, shortUrl } from '../../lib/format'
import type { Run } from '../../lib/types'

export function RunHistory({ runs, activeId, onOpen, loading }: {
  runs: Run[]
  activeId: string | null
  onOpen: (id: string) => void
  loading: boolean
}) {
  if (loading && runs.length === 0) {
    return (
      <div className="space-y-2 p-3" aria-busy="true" aria-label="Loading runs">
        {[0, 1, 2].map((i) => <div key={i} className="h-14 animate-pulse rounded-lg bg-slate-100" />)}
      </div>
    )
  }
  if (runs.length === 0) {
    return <EmptyState icon={<History size={20} />} title="No runs yet">Start a review run to see it here.</EmptyState>
  }
  return (
    <nav aria-label="Run history" className="p-2">
      <ul className="space-y-1">
        {runs.map((r) => {
          const p = provenanceOf(r)
          const active = r.id === activeId
          return (
            <li key={r.id}>
              <button type="button" onClick={() => onOpen(r.id)} aria-current={active ? 'page' : undefined}
                className={cx('w-full rounded-lg border px-2.5 py-2 text-left transition-colors',
                  active ? 'border-accent-500/40 bg-accent-50' : 'border-transparent hover:bg-slate-100')}>
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-mono text-[11.5px] text-slate-800">{r.id}</span>
                  <StatusBadge status={r.status} />
                </div>
                <div className="mt-1 truncate text-xs text-slate-600" title={r.goal}>{r.goal}</div>
                <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-slate-500">
                  <span>{fmtDateTime(r.created_at)}</span>
                  <span aria-hidden>·</span>
                  <span className={p.tone === 'violet' ? 'font-medium text-violet-700' : undefined}>{p.label}</span>
                  <span aria-hidden>·</span>
                  <span className="truncate">{shortUrl(r.target_url)}</span>
                </div>
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
