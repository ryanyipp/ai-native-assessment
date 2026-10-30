import { Camera, Globe, KeyRound, Play, ShieldCheck, X } from 'lucide-react'
import { useId, useLayoutEffect, useRef, useState, type ReactNode, type TextareaHTMLAttributes } from 'react'
import { Button, Callout } from '../../components/ui'
import { cx } from '../../lib/ui-utils'
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

/**
 * Textarea that grows with its text up to maxRem, and can also be resized vertically by hand
 * (same cap). Once the user resizes it by hand, that height is kept: auto-grow stops for it.
 */
function AutoTextarea({ maxRem, className, value, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement> & { maxRem: number; value: string }) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const lastAuto = useRef<number | null>(null) // height this component last set
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    // A height different from the one we set means the user resized it: leave it alone.
    if (lastAuto.current !== null && Math.abs(el.offsetHeight - lastAuto.current) > 1) return
    const max = maxRem * parseFloat(getComputedStyle(document.documentElement).fontSize)
    const needed = el.scrollHeight + (el.offsetHeight - el.clientHeight)
    if (needed > el.offsetHeight) {
      const h = Math.min(needed, max)
      el.style.height = `${h}px`
      lastAuto.current = h
    } else if (lastAuto.current === null) {
      lastAuto.current = el.offsetHeight
    }
  }, [value, maxRem])
  return <textarea ref={ref} value={value} {...rest} style={{ maxHeight: `${maxRem}rem` }}
    className={cx(className, 'resize-y overflow-y-auto')} />
}

const inputCls = (err?: string) =>
  cx(
    'w-full rounded-md border bg-white px-2.5 py-1.5 text-sm text-slate-900 placeholder:text-slate-500 focus:outline-none focus:ring-2',
    err ? 'border-red-400 focus:ring-red-200' : 'border-slate-300 focus:border-accent-500 focus:ring-accent-100',
  )

/** Persistent run-settings panel (pre-run). The main area beside it shows the browser preview. */
export function RunLauncher({ health, onCreated, onPreview, previewBusy, onClose, targetUrl, onTargetUrl, onApproved }: {
  health: Health | null
  targetUrl: string
  onTargetUrl: (url: string) => void
  onApproved: () => void
  onCreated: (run: Run) => void
  onPreview: (url: string) => void
  previewBusy: boolean
  onClose?: () => void
}) {
  const uid = useId()
  const setTargetUrl = onTargetUrl
  const [ack, setAck] = useState(false)
  const [approving, setApproving] = useState(false)
  const [approveError, setApproveError] = useState<string | null>(null)
  const [goal, setGoal] = useState(DEFAULT_GOAL)
  const [requirements, setRequirements] = useState('')
  const [injectStall, setInjectStall] = useState(false)
  const [mode, setMode] = useState<'single_explorer' | 'explore_test_verify' | 'queue_review' | 'single_agent'>('single_explorer')
  const [limits, setLimits] = useState<Record<LimitKey, number>>({
    max_cost_usd: health?.default_run_budget_usd ?? 0.5,
    max_steps: 15,
    max_model_calls: 40,
    max_output_tokens: 800,
  })
  const [touched, setTouched] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const configured = health?.allowed_origins.map((o) => o.toLowerCase()) ?? []
  const approved = health?.approved_origins?.map((o) => o.toLowerCase()) ?? []
  const origin = originOf(targetUrl)
  const profile = origin && configured.includes(origin) ? 'fixture' : origin && approved.includes(origin) ? 'website' : null
  const needsApproval = !!health && !!origin && /^https?:/.test(targetUrl) && profile === null
  const errors: Partial<Record<'url' | 'goal' | LimitKey, string>> = {}
  if (!origin || !/^https?:/.test(targetUrl)) errors.url = 'Enter a full http:// or https:// URL.'
  else if (needsApproval) errors.url = `${origin} is not approved yet. Approve it below to preview it or start a run.`
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

  async function approve() {
    if (!origin) return
    setApproving(true)
    setApproveError(null)
    try {
      await api.approveOrigin(targetUrl.trim())
      setAck(false)
      onApproved()
    } catch (err) {
      setApproveError((err as Error).message)
    } finally {
      setApproving(false)
    }
  }

  async function revoke() {
    if (!origin) return
    try {
      await api.revokeOrigin(origin)
      onApproved()
    } catch (err) {
      setApproveError((err as Error).message)
    }
  }

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
        mode,
        ...(mode === 'queue_review' && injectStall ? { fault_injection: { worker: 'explorer-a', task_type: 'explore', stall_s: 75 } } : {}),
      })
      onCreated(run)
    } catch (err) {
      setApiError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <aside aria-labelledby={`${uid}-title`} className="flex min-h-0 w-[400px] shrink-0 flex-col border-r border-slate-200 bg-white max-lg:w-full max-lg:border-b max-lg:border-r-0">
          <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
            <div>
              <h2 id={`${uid}-title`} className="text-base font-semibold">New review run</h2>
              <p className="mt-0.5 text-[13px] text-slate-500">
                Settings stay here while you preview the target. Starting a run drives a real browser with live model calls and uses API credit.
              </p>
            </div>
            {onClose && (
              <button type="button" onClick={onClose} className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100" aria-label="Close run settings">
                <X size={16} />
              </button>
            )}
          </div>
          <form id={`${uid}-form`} onSubmit={submit} noValidate className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
            <FormField id={`${uid}-url`} label="Target website" error={needsApproval ? undefined : show('url')}
              hint={profile === 'fixture' ? 'Configured fixture origin: each worker gets its own test-data workspace.'
                : profile === 'website' ? 'Approved website: fresh browser context per worker; the site\'s server data is shared.'
                : 'Only origins configured in .env or approved here are accepted.'}>
              <input id={`${uid}-url`} className={cx(inputCls(show('url')), 'font-mono text-[13px]')} value={targetUrl} inputMode="url" autoComplete="off" spellCheck={false}
                aria-invalid={!!show('url')} aria-describedby={show('url') ? `${uid}-url-err` : `${uid}-url-hint`}
                onChange={(e) => { setTargetUrl(e.target.value); setAck(false); setApproveError(null) }} />
            </FormField>
            {needsApproval && (
              <div className="space-y-2 rounded-lg border border-amber-300 bg-amber-50/60 px-3 py-2.5 text-[13px]" role="group" aria-label="Approve target origin">
                <p className="flex items-center gap-1.5 font-medium text-slate-900"><Globe size={14} aria-hidden />Approve <code className="font-mono">{origin}</code>?</p>
                <ul className="list-disc space-y-0.5 pl-5 text-xs text-slate-700">
                  <li>Previews and runs may load pages on this origin only. Links or redirects to any other origin are blocked and not captured.</li>
                  <li>Agents act on the real site: typing, clicking and submitting are real. Use only a site you are authorised to test.</li>
                  <li>Each worker gets a fresh browser context (empty cookies and storage). Data the site stores on its server is not isolated
                    and may be shared with other workers, earlier runs and other people.</li>
                </ul>
                <label className="flex items-start gap-2 text-xs text-slate-800">
                  <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-0.5" />
                  I am authorised to test this site and understand that its server data is not isolated.
                </label>
                {approveError && <p className="text-xs text-red-700">{approveError}</p>}
                <Button type="button" size="sm" disabled={!ack || approving} onClick={approve}>
                  <ShieldCheck size={13} aria-hidden />{approving ? 'Approving…' : 'Approve this origin'}
                </Button>
              </div>
            )}
            {profile === 'website' && (
              <p className="-mt-2 text-xs text-slate-500">
                <code className="font-mono">{origin}</code> was approved in the launcher.{' '}
                <button type="button" className="underline hover:text-slate-800" onClick={revoke}>Revoke approval</button>
              </p>
            )}
            <FormField id={`${uid}-goal`} label="Review goal" error={show('goal')}>
              <AutoTextarea id={`${uid}-goal`} className={inputCls(show('goal'))} rows={3} value={goal} maxRem={16}
                aria-invalid={!!show('goal')} aria-describedby={show('goal') ? `${uid}-goal-err` : undefined}
                onChange={(e) => setGoal(e.target.value)} />
            </FormField>
            <FormField id={`${uid}-req`} label="Requirements (optional)" hint="One per line, optionally prefixed with an id such as R5. The tester and verifier only treat these as explicit expectations.">
              <AutoTextarea id={`${uid}-req`} className={inputCls()} rows={3} value={requirements} maxRem={20} aria-describedby={`${uid}-req-hint`}
                placeholder="Saved drafts keep their title and caption after reload."
                onChange={(e) => setRequirements(e.target.value)} />
            </FormField>
            <fieldset className="space-y-1.5">
              <legend className="text-[13px] font-medium text-slate-800">Workflow</legend>
              {([
                ['single_explorer', 'Explorer only', 'One explorer pursues the goal. Its result stays unverified.'],
                ['explore_test_verify', 'Explorer → input tester → verifier (sequential)', 'Forms the explorer opens are tested; suspected requirement violations are replayed in fresh sessions. Uses more model calls.'],
                ['queue_review', 'Shared queue: two explorers, tester, verifier', 'Workers claim tasks from one queue in separate browser contexts and data workspaces. Exploration stops at its budget share so testing and verification can run.'],
                ['single_agent', 'Single-agent baseline', 'One agent context explores, tests and checks its own findings (evaluation baseline; its checks are self-checks).'],
              ] as const).map(([value, label, hint]) => (
                <label key={value} className="flex cursor-pointer items-start gap-2 rounded-lg border border-slate-200 px-2.5 py-2 text-[13px] has-[:checked]:border-accent-500 has-[:checked]:bg-accent-50">
                  <input type="radio" name={`${uid}-mode`} value={value} checked={mode === value} onChange={() => setMode(value)} className="mt-0.5" />
                  <span><span className="font-medium text-slate-900">{label}</span><span className="block text-xs text-slate-600">{hint}</span></span>
                </label>
              ))}
            </fieldset>
            {mode === 'queue_review' && (
              <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-dashed border-amber-300 bg-amber-50/50 px-2.5 py-2 text-[13px]">
                <input type="checkbox" checked={injectStall} onChange={(e) => setInjectStall(e.target.checked)} className="mt-0.5" />
                <span><span className="font-medium text-slate-900">Inject a stall (labelled fault)</span>
                  <span className="block text-xs text-slate-600">explorer-a stops for 75 s after its first claim. The run is labelled as containing an injected failure.</span></span>
              </label>
            )}

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

            {!health && <Callout tone="red" title="Backend unreachable">Start the API on port 8000, then try again.</Callout>}
            {health && !canRun && (
              <Callout tone="amber" title="Live runs unavailable">Set OPENROUTER_API_KEY in .env and restart the backend.</Callout>
            )}
            {apiError && <Callout tone="red" title="The server rejected the run">{apiError}</Callout>}
          </form>
          <div className="sticky bottom-0 z-10 flex shrink-0 items-center justify-end gap-2 border-t border-slate-200 bg-white px-5 py-3" data-testid="launcher-actions">
            <Button type="button" disabled={previewBusy || !!errors.url} onClick={() => { setTouched(true); if (!errors.url) onPreview(targetUrl.trim()) }}
              title={needsApproval ? 'Approve the origin first' : undefined}>
              <Camera size={14} aria-hidden /> {previewBusy ? 'Capturing…' : 'Preview page'}
            </Button>
            <Button variant="primary" type="submit" form={`${uid}-form`} disabled={busy || !canRun || needsApproval}>
              <Play size={14} aria-hidden /> {busy ? 'Starting…' : 'Start live run'}
            </Button>
          </div>
    </aside>
  )
}

const LIMIT_KEYS = Object.keys(LIMITS) as LimitKey[]
