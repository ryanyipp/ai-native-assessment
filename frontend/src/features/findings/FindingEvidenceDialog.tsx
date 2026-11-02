import * as Dialog from '@radix-ui/react-dialog'
import * as Tabs from '@radix-ui/react-tabs'
import { ChevronLeft, ChevronRight, Images, X } from 'lucide-react'
import { useState } from 'react'
import { ScreenshotPreview } from '../../components/Screenshot'
import { Badge, Button, Field } from '../../components/ui'
import { agentFor, describeAction, evidenceSequence, testCaseFor, wasAttempted, type SequenceItem } from '../../lib/run-model'
import { verificationMeta } from '../../lib/ui-utils'
import type { Finding, RunDetail, VerificationAttempt } from '../../lib/types'

const itemLabel = { setup: 'Setup', test: 'Tested action', check: 'Check page' } as const

function Sequence({ detail, items, resultLabel }: { detail: RunDetail; items: SequenceItem[]; resultLabel: string }) {
  const [index, setIndex] = useState(items.length - 1)  // opens on the last recorded action, the result when there is one
  const item = items[index]
  if (!item) return <p className="text-xs text-slate-500">No browser actions were recorded for this attempt.</p>
  const { action: a, kind, isResult } = item
  const agent = agentFor(detail, a.id)
  const check = a.action.type === 'inspect' && a.target_description
  const title = check ? check[0].toUpperCase() + check.slice(1) : describeAction(a.action, a.target_description)
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" disabled={index === 0} onClick={() => setIndex(index - 1)} aria-label="Previous action in this sequence"><ChevronLeft size={15} /> Previous</Button>
          <span className="text-xs tabular-nums text-slate-600" aria-live="polite">{index + 1} of {items.length}</span>
          <Button variant="ghost" size="sm" disabled={index === items.length - 1} onClick={() => setIndex(index + 1)} aria-label="Next action in this sequence">Next <ChevronRight size={15} /></Button>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={kind === 'test' ? 'blue' : undefined}>{itemLabel[kind]}</Badge>
          {isResult && <Badge tone="violet">{resultLabel}</Badge>}
          {!a.ok && <Badge tone="red">Action failed</Badge>}
        </div>
      </div>
      <p className="text-sm font-semibold leading-snug text-slate-900">{title}</p>
      <p className="text-xs text-slate-500">Original step {a.step}{agent ? ` · ${agent}` : ''}{a.context_id ? ' · ' : ''}
        {a.context_id && <span className="font-mono [overflow-wrap:anywhere]">{a.context_id}</span>}</p>
      {a.error && <p className="text-xs text-red-700">{a.error}</p>}
      <ScreenshotPreview id={a.screenshot_artifact_id} alt={`Page after step ${a.step}`} caption={`Step ${a.step}: ${title}`} />
    </div>
  )
}

function ReplayResult({ v }: { v: VerificationAttempt }) {
  const m = verificationMeta[v.outcome]
  return (
    <div className="space-y-1 rounded-lg bg-slate-50 px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={m.tone}>{m.label}</Badge>
        {v.result && <Badge tone={v.result.passed ? 'green' : 'red'}>Assertion {v.result.passed ? 'held' : 'failed'}, evaluated by code</Badge>}
      </div>
      {!v.result && <p className="font-medium text-slate-800">
        {wasAttempted(v) ? 'The test was not completed here, and no assertion was evaluated.' : 'No browser replay ran, and no assertion was evaluated.'}</p>}
      <p className="leading-relaxed text-slate-700">{v.reason}</p>
    </div>
  )
}

function attemptLabel(v: VerificationAttempt) {
  if (!wasAttempted(v)) return 'Assessment'
  return `Replay ${v.replay_index + 1}${v.result ? '' : ' (stopped)'}`
}

export function FindingEvidenceDialog({ f, detail, attempts }: { f: Finding; detail: RunDetail; attempts: VerificationAttempt[] }) {
  const tc = testCaseFor(detail, f.test_case_id)
  const assertion = attempts.find((a) => a.assertion)?.assertion
  const first = tc ? 'test' : attempts[0]?.id
  if (!first) return null
  const tabCls = 'border-b-2 border-transparent px-3 py-2 text-[13px] font-medium text-slate-600 data-[state=active]:border-accent-500 data-[state=active]:text-slate-900'
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <Button variant="secondary" size="sm"><Images size={14} aria-hidden /> View test and replays</Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-30 bg-slate-950/60 backdrop-blur-[2px]" />
        <Dialog.Content className="fl-enter fixed inset-4 z-30 mx-auto flex max-w-4xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl md:inset-y-8">
          <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-3">
            <div className="min-w-0">
              <Dialog.Title className="text-sm font-semibold leading-snug">{f.description}</Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-slate-500">Actions recorded for this finding only, in recorded order. Other agents' steps are left out.</Dialog.Description>
            </div>
            <Dialog.Close className="shrink-0 rounded-md p-1.5 text-slate-500 hover:bg-slate-100" aria-label="Close evidence"><X size={16} /></Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-3">
            <dl className="divide-y divide-slate-100 text-xs">
              <Field label="Finding"><Badge tone={verificationMeta[f.verification_status].tone}>{verificationMeta[f.verification_status].label}</Badge></Field>
              <Field label="Requirement">{f.requirement_text ? `${f.requirement_ref}: ${f.requirement_text}` : 'None supplied for this expectation'}</Field>
              {assertion && <Field label="Assertion" mono><span className="[overflow-wrap:anywhere]">{assertion.type} {JSON.stringify(assertion.params)}</span></Field>}
            </dl>
            <Tabs.Root defaultValue={first} className="mt-2">
              <Tabs.List aria-label="Test and replays" className="flex flex-wrap gap-1 border-b border-slate-200">
                {tc && <Tabs.Trigger value="test" className={tabCls}>Original test</Tabs.Trigger>}
                {attempts.map((v) => <Tabs.Trigger key={v.id} value={v.id} className={tabCls}>{attemptLabel(v)}</Tabs.Trigger>)}
              </Tabs.List>
              {tc && (
                <Tabs.Content value="test" className="space-y-3 pt-3">
                  <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-700">
                    <b className="text-slate-800">Tester saw:</b> {f.observed}
                    {tc.status !== 'executed' && <p className="mt-1 font-medium">This test did not complete: {tc.setup_error}</p>}
                  </div>
                  <Sequence detail={detail} resultLabel="Recorded result" items={evidenceSequence(detail, tc.action_result_ids, tc.setup_strategy, f.reproduction,
                    detail.transitions.find((t) => t.test_case_id === tc.id)?.action_result_id)} />
                </Tabs.Content>
              )}
              {attempts.map((v) => {
                const result = v.result ? detail.transitions.find((t) => t.verification_id === v.id)?.action_result_id : undefined
                return (
                  <Tabs.Content key={v.id} value={v.id} className="space-y-3 pt-3">
                    <ReplayResult v={v} />
                    <Sequence detail={detail} resultLabel="Assertion evaluated here" items={evidenceSequence(detail, v.action_result_ids, v.setup_strategy, f.reproduction, result)} />
                  </Tabs.Content>
                )
              })}
            </Tabs.Root>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
