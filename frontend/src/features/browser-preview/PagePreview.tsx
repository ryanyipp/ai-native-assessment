import { Camera, ImageOff, Loader2, RefreshCw } from 'lucide-react'
import { Badge, Button, Callout } from '../../components/ui'
import { fmtTime } from '../../lib/format'
import type { PagePreview as Preview } from '../../lib/types'

export type PreviewState = { kind: 'idle'; cleared?: string } | { kind: 'loading'; url: string } | { kind: 'error'; url: string; message: string } |
  { kind: 'ready'; data: Preview }

/** Pre-run view: one real server-side screenshot of the target. Static: it cannot be clicked or typed into. */
export function PagePreview({ state, onRefresh, currentUrl }: { state: PreviewState; onRefresh: () => void; currentUrl: string }) {
  // The screenshot belongs to the URL it was captured for; if the target changed since, say so.
  const stale = state.kind === 'ready' && state.data.requested_url !== currentUrl.trim()
  return (
    <section aria-label="Browser preview" className="flex h-full min-h-0 flex-col bg-slate-100">
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-4 py-2 text-xs text-slate-600">
        <Camera size={14} aria-hidden />
        <span className="font-medium text-slate-800">Browser preview</span>
        <Badge>Static screenshot · not interactive</Badge>
        {state.kind === 'ready' && (
          <span className="min-w-0 truncate font-mono" title={state.data.final_url ?? state.data.requested_url}>
            {state.data.final_url ?? state.data.requested_url} · captured {fmtTime(state.data.captured_at)}
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
            {state.cleared && (
              <p className="max-w-sm text-xs text-slate-500" role="status">
                The previous screenshot (<span className="font-mono">{state.cleared}</span>) was cleared because the target origin changed.
              </p>
            )}
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
          <figure className="mx-auto max-w-[1000px]" data-testid="preview-figure" data-stale={stale || undefined}>
            {stale && (
              <div role="status" className="mb-2 flex flex-wrap items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                <span><strong>Out of date:</strong> this screenshot is of <span className="font-mono">{state.data.requested_url}</span>,
                  not the current target <span className="font-mono">{currentUrl.trim()}</span>.</span>
                <Button size="sm" variant="ghost" onClick={onRefresh}><RefreshCw size={13} />Capture the current target</Button>
              </div>
            )}
            {!state.data.ok && (
              <Callout tone="amber" title={state.data.image_png_base64 ? 'The page loaded with an error' : 'Blocked: the page left the approved origin'}>
                {state.data.error}{!state.data.image_png_base64 && ' Nothing from outside the approved origin was captured.'}
              </Callout>
            )}
            {state.data.image_png_base64 && (
              <img src={`data:image/png;base64,${state.data.image_png_base64}`}
                alt={`Screenshot of ${state.data.title || state.data.final_url}`}
                className={`w-full rounded-lg border border-slate-200 bg-white shadow-sm ${stale ? 'opacity-40 grayscale' : ''}`} />
            )}
            {state.data.image_png_base64 && (
              <figcaption className="mt-2 text-xs text-slate-600">
                “{state.data.title}” at {state.data.viewport.width}×{state.data.viewport.height}, captured once at {fmtTime(state.data.captured_at)}.
                It does not update and cannot be controlled.{' '}
                {state.data.profile === 'website'
                  ? 'It shows what a fresh browser sees. Runs also start each worker in a fresh browser context, but the website\'s own server data is shared, not isolated.'
                  : 'It shows the site\'s shared default data; runs give each worker a fresh test workspace, so a run may start from different data.'}
              </figcaption>
            )}
          </figure>
        )}
      </div>
    </section>
  )
}
