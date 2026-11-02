import { ArrowRight, ExternalLink, Film, History, Waypoints } from 'lucide-react'
import { useState } from 'react'
import { buttonClass } from '../../lib/ui-utils'

const REPOSITORY_URL = 'https://github.com/ryanyipp/ai-native-assessment'

/**
 * The demo video lives in frontend/public/flowlens-demo.mp4. If it fails to load, the placeholder shows.
 * Controls are on and it never autoplays.
 */
const DEMO_VIDEO = { src: '/flowlens-demo.mp4' } as { src: string; poster?: string } | null

function DemoVideo() {
  const [missing, setMissing] = useState(false)
  if (DEMO_VIDEO && !missing) {
    return (
      <video controls preload="metadata" playsInline poster={DEMO_VIDEO.poster} aria-label="FlowLens demo video" className="aspect-video w-full rounded-xl bg-slate-900 shadow-xl ring-1 ring-slate-900/10">
        <source src={DEMO_VIDEO.src} type="video/mp4" onError={() => setMissing(true)} />
      </video>
    )
  }
  return (
    <div className="flex aspect-video w-full items-center justify-center rounded-xl bg-slate-900 text-white"
      style={{ backgroundImage: 'radial-gradient(rgb(255 255 255 / 0.12) 1px, transparent 1px)', backgroundSize: '22px 22px' }}>
      <div className="flex flex-col items-center gap-3 px-6 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 ring-1 ring-white/20"><Film size={20} aria-hidden /></span>
        <p className="text-sm font-medium sm:text-base">Demo video coming soon.</p>
      </div>
    </div>
  )
}

export default function Landing() {
  return (
    <div className="relative min-h-full overflow-hidden bg-slate-50">
      <img src="/flow-background.svg" alt="" className="pointer-events-none absolute inset-0 hidden h-full w-full object-cover opacity-20 lg:block" />
      <header className="relative border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-12 max-w-6xl items-center gap-2 px-4 sm:px-6">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-slate-900 text-white"><Waypoints size={14} aria-hidden /></span>
          <span className="text-sm font-semibold tracking-tight">FlowLens</span>
          <span className="hidden text-xs text-slate-500 sm:inline">AI website reviewer</span>
        </div>
      </header>

      <main className="relative mx-auto max-w-6xl px-4 sm:px-6">
        <section className="fl-enter mx-auto flex max-w-4xl flex-col items-center pb-12 pt-14 text-center sm:pt-20">
          <div className="mb-8 flex items-center gap-4">
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-lg sm:h-20 sm:w-20"><Waypoints size={40} aria-hidden /></span>
            <span className="text-5xl font-bold tracking-tight text-slate-900 sm:text-6xl">FlowLens</span>
          </div>
          <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight text-slate-900 sm:text-5xl">Agents explore your site.<br />Code proves the bugs.</h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-slate-600 sm:text-lg">
            FlowLens agents explore website journeys, build an interactive flow map, test inputs and re-check suspected issues against your requirements.
          </p>
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row sm:flex-wrap">
            <a href="/workspace" className={buttonClass('primary', 'lg')}>Start a review<ArrowRight size={16} aria-hidden /></a>
            <a href="/workspace?demos=1" className={buttonClass('secondary', 'lg')}><History size={16} aria-hidden />Explore recorded demos</a>
            <a href={REPOSITORY_URL} target="_blank" rel="noreferrer" className={buttonClass('ghost', 'lg')}>View source<ExternalLink size={14} aria-hidden /></a>
          </div>
        </section>

        <section aria-labelledby="demo-video-title" className="mx-auto max-w-5xl pb-16">
          <h2 id="demo-video-title" className="mb-4 text-center text-lg font-semibold tracking-tight text-slate-900">Demo video</h2>
          <DemoVideo />
        </section>
      </main>

      <footer className="relative border-t border-slate-200 bg-white">
        <p className="mx-auto max-w-6xl px-4 py-5 text-center text-xs text-slate-600 sm:px-6">A bounded website review. Results cover observed journeys, not the entire website.</p>
      </footer>
    </div>
  )
}
