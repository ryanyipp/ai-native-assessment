import * as Dialog from '@radix-ui/react-dialog'
import { ExternalLink, ImageOff, Maximize2, X } from 'lucide-react'
import { useState } from 'react'
import { artifactUrl } from '../lib/api'
import { cx } from './ui'

export function MissingScreenshot({ className, reason = 'No screenshot recorded' }: { className?: string; reason?: string }) {
  return (
    <div className={cx('flex flex-col items-center justify-center gap-1 bg-slate-100 text-slate-400', className)}>
      <ImageOff size={18} aria-hidden />
      <span className="text-[11px]">{reason}</span>
    </div>
  )
}

/** Thumbnail that degrades to an explicit placeholder if the artifact is missing or fails to load. */
export function Thumb({ id, alt, className }: { id: string | null | undefined; alt: string; className?: string }) {
  const [broken, setBroken] = useState(false)
  if (!id || broken) return <MissingScreenshot className={className} reason={broken ? 'Screenshot unavailable' : undefined} />
  return (
    <img src={artifactUrl(id)} alt={alt} loading="lazy" onError={() => setBroken(true)}
      className={cx('object-cover object-top', className)} />
  )
}

/** Preview with an accessible full-size dialog (focus trapped, Esc to close). */
export function ScreenshotPreview({ id, alt, caption }: { id: string | null | undefined; alt: string; caption: string }) {
  if (!id) return <MissingScreenshot className="aspect-[16/10] w-full rounded-lg border border-slate-200" />
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button type="button" aria-label={`Enlarge screenshot: ${caption}`}
          className="group relative block w-full overflow-hidden rounded-lg border border-slate-200 bg-slate-100">
          <Thumb id={id} alt={alt} className="aspect-[16/10] w-full" />
          <span className="absolute right-2 top-2 rounded-md bg-slate-900/70 p-1 text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
            <Maximize2 size={14} aria-hidden />
          </span>
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-950/70 backdrop-blur-[2px]" />
        <Dialog.Content className="fl-enter fixed inset-4 z-50 flex flex-col overflow-hidden rounded-xl bg-white shadow-2xl md:inset-10">
          <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-2.5">
            <Dialog.Title className="truncate text-sm font-semibold">{caption}</Dialog.Title>
            <div className="flex shrink-0 items-center gap-1">
              <a href={artifactUrl(id)} target="_blank" rel="noreferrer"
                className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs text-slate-600 hover:bg-slate-100">
                Open PNG <ExternalLink size={12} aria-hidden />
              </a>
              <Dialog.Close className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100" aria-label="Close screenshot">
                <X size={16} />
              </Dialog.Close>
            </div>
          </div>
          <Dialog.Description className="sr-only">Full-size screenshot captured by the browser engine.</Dialog.Description>
          <div className="min-h-0 flex-1 overflow-auto bg-slate-100 p-4">
            <img src={artifactUrl(id)} alt={alt} className="mx-auto max-w-full rounded border border-slate-200 bg-white shadow" />
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
