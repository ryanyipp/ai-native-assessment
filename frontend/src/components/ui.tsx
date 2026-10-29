import * as RTooltip from '@radix-ui/react-tooltip'
import { AlertTriangle, CheckCircle2, CircleDashed, CircleSlash, Loader2, PauseCircle, XCircle } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cx, provenanceOf, type Tone } from '../lib/ui-utils'
import type { Run, RunStatus } from '../lib/types'


type Variant = 'primary' | 'secondary' | 'ghost'
const variants: Record<Variant, string> = {
  primary: 'bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-300 disabled:text-slate-500',
  secondary: 'border border-slate-300 bg-white text-slate-800 hover:bg-slate-50 disabled:text-slate-500',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 disabled:text-slate-300',
}

export function Button({ variant = 'secondary', size = 'md', className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: 'sm' | 'md'
}) {
  return (
    <button
      type="button"
      {...rest}
      className={cx(
        'inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:cursor-not-allowed',
        size === 'sm' ? 'h-7 px-2 text-xs' : 'h-9 px-3 text-sm',
        variants[variant],
        className,
      )}
    />
  )
}

export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <RTooltip.Root delayDuration={250}>
      <RTooltip.Trigger asChild>{children}</RTooltip.Trigger>
      <RTooltip.Portal>
        <RTooltip.Content
          sideOffset={6}
          className="z-50 max-w-xs rounded-md bg-slate-900 px-2.5 py-1.5 text-xs leading-snug text-white shadow-lg"
        >
          {content}
          <RTooltip.Arrow className="fill-slate-900" />
        </RTooltip.Content>
      </RTooltip.Portal>
    </RTooltip.Root>
  )
}

const tones: Record<Tone, string> = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-200',
  blue: 'bg-accent-50 text-accent-700 ring-accent-100',
  green: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  red: 'bg-red-50 text-red-800 ring-red-200',
  violet: 'bg-violet-50 text-violet-800 ring-violet-200',
}

export function Badge({ tone = 'neutral', icon, children, className }: {
  tone?: Tone
  icon?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <span className={cx('inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset', tones[tone], className)}>
      {icon}
      {children}
    </span>
  )
}

const statusMeta: Record<RunStatus, { tone: Tone; label: string; icon: ReactNode; help: string }> = {
  queued: { tone: 'blue', label: 'Queued', icon: <CircleDashed size={12} />, help: 'Waiting to start.' },
  running: { tone: 'blue', label: 'Running', icon: <Loader2 size={12} className="animate-spin" />, help: 'Workers are acting in the browser.' },
  completed: { tone: 'green', label: 'Completed', icon: <CheckCircle2 size={12} />, help: 'The workflow finished within limits. This is not a verdict on the website.' },
  partial: { tone: 'amber', label: 'Partial', icon: <PauseCircle size={12} />, help: 'Stopped at a budget limit. Results are incomplete, not passing.' },
  failed: { tone: 'red', label: 'Failed', icon: <XCircle size={12} />, help: 'The run stopped on an error.' },
  interrupted: { tone: 'neutral', label: 'Interrupted', icon: <CircleSlash size={12} />, help: 'The backend stopped before the run finished. Records remain inspectable.' },
}

export function StatusBadge({ status, withTooltip = false }: { status: RunStatus; withTooltip?: boolean }) {
  const m = statusMeta[status]
  const badge = <Badge tone={m.tone} icon={m.icon}>{m.label}</Badge>
  return withTooltip ? <Tooltip content={m.help}><span tabIndex={0} className="inline-flex">{badge}</span></Tooltip> : badge
}

export function ProvenanceBadge({ run }: { run: Run }) {
  const p = provenanceOf(run)
  return (
    <Tooltip content={<>{p.help}{run.provenance.synthetic_fixture && ' Target: synthetic fixture data.'}</>}>
      <span tabIndex={0} className="inline-flex">
        <Badge tone={p.tone}>{p.label}</Badge>
      </span>
    </Tooltip>
  )
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-2">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{children}</h3>
      {aside}
    </div>
  )
}

export function Field({ label, children, mono }: { label: string; children: ReactNode; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3 py-1.5 text-[13px]">
      <dt className="text-slate-500">{label}</dt>
      <dd className={cx('min-w-0 break-words text-slate-900', mono && 'font-mono text-xs [overflow-wrap:anywhere]')}>{children}</dd>
    </div>
  )
}

export function EmptyState({ icon, title, children, action }: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <div className="text-slate-500">{icon}</div>
      <p className="text-sm font-medium text-slate-800">{title}</p>
      {children && <div className="max-w-sm text-[13px] leading-relaxed text-slate-500">{children}</div>}
      {action}
    </div>
  )
}

export function Callout({ tone = 'neutral', title, children }: { tone?: 'neutral' | 'amber' | 'red'; title: string; children: ReactNode }) {
  const style = {
    neutral: 'border-slate-200 bg-slate-50 text-slate-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-900',
    red: 'border-red-200 bg-red-50 text-red-900',
  }[tone]
  return (
    <div className={cx('rounded-lg border p-3 text-[13px] leading-relaxed', style)} role={tone === 'red' ? 'alert' : undefined}>
      <div className="mb-0.5 flex items-center gap-1.5 font-semibold">
        {tone !== 'neutral' && <AlertTriangle size={14} />}
        {title}
      </div>
      {children}
    </div>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded border border-slate-300 bg-white px-1 font-mono text-[10px] text-slate-600 shadow-[0_1px_0_var(--color-slate-300)]">{children}</kbd>
}
