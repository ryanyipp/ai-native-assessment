import { ArrowRight, ExternalLink, FileSearch, Film, History, Users, Waypoints } from 'lucide-react'
import type { ReactNode } from 'react'
import { buttonClass } from '../../lib/ui-utils'

const REPOSITORY_URL = 'https://github.com/ryanyipp/ai-native-assessment'

/**
 * To add the demo video: put the file in frontend/public/ (for example public/flowlens-demo.mp4)
 * and set src to '/flowlens-demo.mp4'. poster is optional. Controls are on and it never autoplays.
 */
const DEMO_VIDEO = null as { src: string; poster?: string } | null

const FEATURES: { icon: ReactNode; title: string; text: string }[] = [
  { icon: <Waypoints size={18} aria-hidden />, title: 'Map user journeys', text: 'See the pages, states and transitions the agents actually observed.' },
  { icon: <Users size={18} aria-hidden />, title: 'Test with cooperating agents', text: 'Explorers hand forms to a tester, and a verifier re-checks suspected issues.' },
  { icon: <FileSearch size={18} aria-hidden />, title: 'Inspect evidence-backed findings', text: 'Open the screenshots, actions and outcomes behind each finding.' },
]

function DemoVideo() {
  if (DEMO_VIDEO) {
    return (
      <video controls preload="metadata" playsInline poster={DEMO_VIDEO.poster} aria-label="FlowLens demo video" className="aspect-video w-full rounded-xl bg-slate-900">
        <source src={DEMO_VIDEO.src} />
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
    <div className="min-h-full bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-12 max-w-5xl items-center gap-2 px-4 sm:px-6">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-slate-900 text-white"><Waypoints size={14} aria-hidden /></span>
          <span className="text-sm font-semibold tracking-tight">FlowLens</span>
          <span className="hidden text-xs text-slate-500 sm:inline">AI website reviewer</span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 sm:px-6">
        <section className="fl-enter max-w-3xl pb-12 pt-14 sm:pt-20">
          <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight text-slate-900 sm:text-5xl">See how a website works—and what needs attention.</h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-slate-600 sm:text-lg">
            FlowLens agents explore website journeys, build an interactive flow map, test inputs and independently re-check suspected issues against your requirements.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <a href="/workspace" className={buttonClass('primary', 'lg')}>Start a review<ArrowRight size={16} aria-hidden /></a>
            <a href="/workspace?demos=1" className={buttonClass('secondary', 'lg')}><History size={16} aria-hidden />Explore recorded demos</a>
            <a href={REPOSITORY_URL} target="_blank" rel="noreferrer" className={buttonClass('ghost', 'lg')}>View source<ExternalLink size={14} aria-hidden /></a>
          </div>
        </section>

        <section aria-label="What FlowLens does" className="grid gap-4 md:grid-cols-3">
          {FEATURES.map((f) => (
            <article key={f.title} className="rounded-xl border border-slate-200 bg-white p-5">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-50 text-accent-700">{f.icon}</span>
              <h2 className="mt-3 text-sm font-semibold text-slate-900">{f.title}</h2>
              <p className="mt-1 text-[13px] leading-relaxed text-slate-600">{f.text}</p>
            </article>
          ))}
        </section>

        <section aria-labelledby="demo-video-title" className="mx-auto max-w-3xl py-12">
          <h2 id="demo-video-title" className="mb-4 text-lg font-semibold tracking-tight text-slate-900">Demo video</h2>
          <DemoVideo />
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <p className="mx-auto max-w-5xl px-4 py-5 text-xs text-slate-600 sm:px-6">A bounded website review. Results cover observed journeys, not the entire website.</p>
      </footer>
    </div>
  )
}
