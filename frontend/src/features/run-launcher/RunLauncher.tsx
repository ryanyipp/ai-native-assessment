import * as Dialog from '@radix-ui/react-dialog'
import { KeyRound, Play, X } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'
import { Button, Callout, cx } from '../../components/ui'
import { api } from '../../lib/api'
import { fmtUsd } from '../../lib/format'
import type { Health, Run } from '../../lib/types'

const DEFAULT_GOAL = 'Create a draft, save it, reload the page, and check whether the saved content persists.'

// Bounds mirror RunLimits in backend/src/flowlens/models/contracts.py.
const LIMITS = {
  max_cost_usd: { min: 0.05, max: 10, step: 0.05, label: 'Max cost per run (US$)' },
  max_steps: { min: 1, max: 60, step: 1, label: 'Max browser steps' },
  max_model_calls: { min: 1, max: 200, step: 1, label: 'Max model calls' },
  max_output_tokens: { min: 100, max: 4000, step: 50, label: 'Max output tokens per call' },
} as const
type LimitKey = keyof typeof LIMITS

function originOf(url: string) {
  try {
    return new URL(url).origin.toLowerCase()
  } catch {
    return null
  }
}

function FormField({ label, error, hint, children, id }: { label: string; error?: string; hint?: ReactNode; children: ReactNode; id: string }) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-[13px] font-medium text-slate-800">{label}</label>
      {children}
      {error ? (
        <p id={`${id}-err`} className="text-xs text-red-700">{error}</p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-slate-500">{hint}</p>
      ) : null}
    </div>
  )
}

const inputCls = (err?: string) =>
  cx(
    'w-full rounded-md border bg-white px-2.5 py-1.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2',
    err ? 'border-red-400 focus:ring-red-200' : 'border-slate-300 focus:border-accent-500 focus:ring-accent-100',
  )

export function RunLauncher({ health, open, onOpenChange, onCreated }: {
  health: Health | null
  open: boolean
  onOpenChange: (o: boolean) => void
  onCreated: (run: Run) => void
}) {
  const uid = useId()
  const [targetUrl, setTargetUrl] = useState('http://localhost:5174/')
  const [goal, setGoal] = useState(DEFAULT_GOAL)
  const [requirements, setRequirements] = useState('')
  const [limits, setLimits] = useState<Record<LimitKey, number>>({
    max_cost_usd: health?.default_run_budget_usd ?? 0.5,
    max_steps: 15,
    max_model_calls: 40,
    max_output_tokens: 800,
  })
  const [touched, setTouched] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const allowed = health?.allowed_origins.map((o) => o.toLowerCase()) ?? []
  const origin = originOf(targetUrl)
  const errors: Partial<Record<'url' | 'goal' | LimitKey, string>> = {}
  if (!origin || !/^https?:/.test(targetUrl)) errors.url = 'Enter a full http:// or https:// URL.'
  else if (health && !allowed.includes(origin)) errors.url = `${origin} is not an allowed target. Allowed: ${allowed.join(', ')}. Change FLOWLENS_ALLOWED_ORIGINS in .env to add one.`
  if (goal.trim().length < 5) errors.goal = 'Describe the goal in at least 5 characters.'
  else if (goal.length > 2000) errors.goal = 'Keep the goal under 2,000 characters.'
  for (const k of Object.keys(LIMITS) as LimitKey[]) {
    const v = limits[k]
    const b = LIMITS[k]
    if (!Number.isFinite(v) || v < b.min || v > b.max) errors[k] = `Between ${b.min} and ${b.max}.`
  }
  const remaining = health ? Math.max(0, health.budget_usd - health.spent_reported_usd) : null
  const canRun = !!health?.api_key_configured
  const show = (k: keyof typeof errors) => (touched ? errors[k] : undefined)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setTouched(true)
    setApiError(null)
    if (Object.keys(errors).length > 0 || !canRun) return
    setBusy(true)
    try {
      const run = await api.createRun({
        target_url: targetUrl.trim(),
        goal: goal.trim(),
        requirements: requirements.split('\n').map((r) => r.trim()).filter(Boolean),
        limits,
      })
      onCreated(run)
      onOpenChange(false)
    } catch (err) {
      setApiError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-950/40" />
        <Dialog.Content className="fl-enter fixed left-1/2 top-1/2 z-50 flex max-h-[calc(100vh-2rem)] w-[min(560px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
          <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
            <div>
              <Dialog.Title className="text-base font-semibold">New review run</Dialog.Title>
              <Dialog.Description className="mt-0.5 text-[13px] text-slate-500">
                One explorer drives a real browser with live model calls. This uses API credit.
              </Dialog.Description>
            </div>
            <Dialog.Close className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100" aria-label="Close">
              <X size={16} />
            </Dialog.Close>
          </div>
          <form id={`${uid}-form`} onSubmit={submit} noValidate className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
            <FormField id={`${uid}-url`} label="Target website" error={show('url')} hint="Only authorised local or staging origins are accepted.">
              <input id={`${uid}-url`} className={cx(inputCls(show('url')), 'font-mono text-[13px]')} value={targetUrl} inputMode="url" autoComplete="off" spellCheck={false}
                aria-invalid={!!show('url')} aria-describedby={show('url') ? `${uid}-url-err` : `${uid}-url-hint`}
                onChange={(e) => setTargetUrl(e.target.value)} />
            </FormField>
            <FormField id={`${uid}-goal`} label="Review goal" error={show('goal')}>
              <textarea id={`${uid}-goal`} className={inputCls(show('goal'))} rows={3} value={goal}
                aria-invalid={!!show('goal')} aria-describedby={show('goal') ? `${uid}-goal-err` : undefined}
                onChange={(e) => setGoal(e.target.value)} />
            </FormField>
            <FormField id={`${uid}-req`} label="Requirements (optional)" hint="One per line. Passed to the explorer as supplied expectations.">
              <textarea id={`${uid}-req`} className={inputCls()} rows={2} value={requirements} aria-describedby={`${uid}-req-hint`}
                placeholder="Saved drafts keep their title and caption after reload."
                onChange={(e) => setRequirements(e.target.value)} />
            </FormField>

            <details className="rounded-lg border border-slate-200" open={touched && LIMIT_KEYS.some((k) => errors[k])}>
              <summary className="cursor-pointer select-none px-3 py-2 text-[13px] font-medium text-slate-700">
                Budget and limits
                <span className="ml-2 font-normal text-slate-500">
                  {fmtUsd(limits.max_cost_usd, 2)} · {limits.max_steps} steps · {limits.max_model_calls} calls
                </span>
              </summary>
              <div className="grid grid-cols-2 gap-3 border-t border-slate-200 px-3 py-3">
                {LIMIT_KEYS.map((k) => (
                  <FormField key={k} id={`${uid}-${k}`} label={LIMITS[k].label} error={show(k)}>
                    <input id={`${uid}-${k}`} type="number" className={cx(inputCls(show(k)), 'tabular-nums')}
                      min={LIMITS[k].min} max={LIMITS[k].max} step={LIMITS[k].step} value={Number.isNaN(limits[k]) ? '' : limits[k]}
                      aria-invalid={!!show(k)}
                      onChange={(e) => setLimits((l) => ({ ...l, [k]: e.target.valueAsNumber }))} />
                  </FormField>
                ))}
                <p className="col-span-2 text-xs leading-relaxed text-slate-500">
                  Limits are checked before each model call, so a run can finish slightly over its cost limit (in-flight overshoot). Reaching a
                  limit marks the run partial, never passing.
                </p>
              </div>
            </details>

            <div className="rounded-lg bg-slate-50 px-3 py-2.5 text-xs text-slate-600">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <span>Model <code className="font-mono text-slate-900">{health?.model ?? 'unknown'}</code></span>
                <span className="inline-flex items-center gap-1">
                  <KeyRound size={12} aria-hidden /> API key {health ? (health.api_key_configured ? 'configured on server' : 'missing') : 'unknown'}
                </span>
                {remaining != null && (
                  <span>Credit pool {fmtUsd(health!.spent_reported_usd, 4)} spent of {fmtUsd(health!.budget_usd, 2)}</span>
                )}
              </div>
            </div>

            {!health && <Callout tone="red" title="Backend unreachable">Start the API on port 8000, then reopen this dialog.</Callout>}
            {health && !canRun && (
              <Callout tone="amber" title="Live runs unavailable">Set OPENROUTER_API_KEY in .env and restart the backend.</Callout>
            )}
            {apiError && <Callout tone="red" title="The server rejected the run">{apiError}</Callout>}
          </form>
          <div className="flex items-center justify-end gap-2 border-t border-slate-200 px-5 py-3">
            <Dialog.Close asChild><Button>Cancel</Button></Dialog.Close>
            <Button variant="primary" type="submit" form={`${uid}-form`} disabled={busy || !canRun}>
              <Play size={14} aria-hidden /> {busy ? 'Starting…' : 'Start live run'}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

const LIMIT_KEYS = Object.keys(LIMITS) as LimitKey[]
