import { Camera, ImageOff, Loader2, RefreshCw } from 'lucide-react'
import { Badge, Button, Callout } from '../../components/ui'
import { fmtTime } from '../../lib/format'
import type { PagePreview as Preview } from '../../lib/types'

export type PreviewState = { kind: 'idle' } | { kind: 'loading'; url: string } | { kind: 'error'; url: string; message: string } |
  { kind: 'ready'; data: Preview }

/** Pre-run view: one real server-side screenshot of the target. Static: it cannot be clicked or typed into. */
export function PagePreview({ state, onRefresh }: { state: PreviewState; onRefresh: () => void }) {
  return (
    <section aria-label="Browser preview" className="flex h-full min-h-0 flex-col bg-slate-100">
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-4 py-2 text-xs text-slate-600">
        <Camera size={14} aria-hidden />
        <span className="font-medium text-slate-800">Browser preview</span>
        <Badge>Static screenshot · not interactive</Badge>
        {state.kind === 'ready' && (
          <span className="min-w-0 truncate font-mono" title={state.data.final_url}>
            {state.data.final_url} · captured {fmtTime(state.data.captured_at)}
          </span>
        )}
        {state.kind !== 'idle' && state.kind !== 'loading' && (
          <Button size="sm" variant="ghost" className="ml-auto" onClick={onRefresh}><RefreshCw size={13} />Capture again</Button>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-4">
        {state.kind === 'idle' && (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-slate-600">
            <ImageOff size={26} aria-hidden className="text-slate-400" />
            <p className="max-w-sm">Choose <strong>Preview page</strong> to capture a real screenshot of the target in a fresh headless browser.
              Nothing is stored and no model is called.</p>
          </div>
        )}
        {state.kind === 'loading' && (
          <div className="flex h-full items-center justify-center gap-2 text-sm text-slate-600" role="status" aria-live="polite">
            <Loader2 size={16} className="motion-safe:animate-spin" aria-hidden /> Capturing {state.url} …
          </div>
        )}
        {state.kind === 'error' && (
          <Callout tone="red" title="Could not capture the page">{state.message}</Callout>
        )}
        {state.kind === 'ready' && (
          <figure className="mx-auto max-w-[1000px]">
            {!state.data.ok && <Callout tone="amber" title="The page loaded with an error">{state.data.error}</Callout>}
            <img src={`data:image/png;base64,${state.data.image_png_base64}`}
              alt={`Screenshot of ${state.data.title || state.data.final_url}`}
              className="w-full rounded-lg border border-slate-200 bg-white shadow-sm" />
            <figcaption className="mt-2 text-xs text-slate-600">
              “{state.data.title}” at {state.data.viewport.width}×{state.data.viewport.height}, captured once at {fmtTime(state.data.captured_at)}.
              It does not update and cannot be controlled. It shows the site's shared default data; runs give each worker a fresh test
              workspace where the target supports one, so a run may start from different data.
            </figcaption>
          </figure>
        )}
      </div>
    </section>
  )
}
