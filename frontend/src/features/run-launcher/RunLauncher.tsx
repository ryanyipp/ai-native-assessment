import { useState } from 'react'
import { api } from '../../lib/api'
import type { Health, Run } from '../../lib/types'

const DEFAULT_GOAL = 'Create a draft, save it, reload the page, and check whether the saved content persists.'

interface Props {
  health: Health | null
  onCreated: (run: Run) => void
}

export function RunLauncher({ health, onCreated }: Props) {
  const [targetUrl, setTargetUrl] = useState('http://localhost:5174/')
  const [goal, setGoal] = useState(DEFAULT_GOAL)
  const [requirements, setRequirements] = useState('')
  const [maxCost, setMaxCost] = useState(0.5)
  const [maxSteps, setMaxSteps] = useState(15)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const run = await api.createRun({
        target_url: targetUrl,
        goal,
        requirements: requirements.split('\n').map((r) => r.trim()).filter(Boolean),
        limits: { max_cost_usd: maxCost, max_steps: maxSteps },
      })
      onCreated(run)
    } catch (err) {
      setError(String((err as Error).message))
    } finally {
      setBusy(false)
    }
  }

  const input = 'w-full rounded border border-slate-300 px-2 py-1 text-sm'
  return (
    <form onSubmit={submit} className="space-y-2">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">New review run</h2>
      <label className="block text-xs font-medium">
        Target URL
        <input className={input} value={targetUrl} onChange={(e) => setTargetUrl(e.target.value)} />
      </label>
      <label className="block text-xs font-medium">
        Goal
        <textarea className={input} rows={3} value={goal} onChange={(e) => setGoal(e.target.value)} />
      </label>
      <label className="block text-xs font-medium">
        Requirements (one per line, optional)
        <textarea className={input} rows={2} value={requirements} onChange={(e) => setRequirements(e.target.value)} />
      </label>
      <div className="flex gap-2">
        <label className="block flex-1 text-xs font-medium">
          Max cost (US$)
          <input className={input} type="number" step="0.05" min="0.05" max="10" value={maxCost}
            onChange={(e) => setMaxCost(Number(e.target.value))} />
        </label>
        <label className="block flex-1 text-xs font-medium">
          Max steps
          <input className={input} type="number" min="1" max="60" value={maxSteps}
            onChange={(e) => setMaxSteps(Number(e.target.value))} />
        </label>
      </div>
      {health && (
        <p className="text-xs text-slate-500">
          Model <code>{health.model}</code> · key {health.api_key_configured ? 'configured' : 'missing'} · spent US$
          {health.spent_reported_usd.toFixed(4)} of US${health.budget_usd} pool
        </p>
      )}
      {error && <p className="rounded bg-red-50 p-2 text-xs text-red-700">{error}</p>}
      <button type="submit" disabled={busy || !health?.api_key_configured}
        className="w-full rounded bg-slate-900 py-1.5 text-sm font-medium text-white disabled:opacity-40">
        {busy ? 'Starting…' : 'Start live run'}
      </button>
    </form>
  )
}
