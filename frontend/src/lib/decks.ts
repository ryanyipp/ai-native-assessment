import type { RunDetail, ScreenState } from './types'

/**
 * Visual grouping of the map into "decks": observed states of the same page or form journey.
 *
 * States share a deck when they have the same route and the same main heading, i.e. the same
 * page or form seen with different field values, messages or validation. A different heading
 * (another page, a dialog, a confirmation screen) gives a different deck, so distinct pages
 * and dialogs stay identifiable. This is display only: no state, transition or evidence record
 * is changed, merged or hidden from the inspector.
 */
export interface Deck {
  key: string
  heading: string
  route: string
  states: ScreenState[] // ordered by first_seen_step; states[0] is the representative
  testCases: number // recorded test cases run on this page or form
  findings: Record<string, number> // verification status -> count, for findings on this page or form
  innerMoves: number // transitions that stay inside the deck
  active: boolean // a worker is working here now (never collapsed automatically)
}

export const headingOf = (s: ScreenState) => s.summary.split(' — ')[0].replace(/\s*\(\d+\/\d+ fields filled\)$/, '').trim()
export const deckKey = (s: ScreenState) => `${s.route}|${headingOf(s)}`

const ACTIVE = new Set(['queued', 'running'])

export function buildDecks(d: RunDetail): Map<string, Deck> {
  const byKey = new Map<string, ScreenState[]>()
  for (const s of [...d.states].sort((a, b) => a.first_seen_step - b.first_seen_step)) {
    const k = deckKey(s)
    byKey.set(k, [...(byKey.get(k) ?? []), s])
  }
  const stateDeck = new Map<string, string>()
  for (const [k, ss] of byKey) for (const s of ss) stateDeck.set(s.id, k)

  // Work in progress: a claimed task that names one of the deck's states, or the latest
  // recorded state while the run is active. Such decks are never collapsed automatically.
  const running = ACTIVE.has(d.run.status)
  const activeDecks = new Set<string>()
  if (running) {
    for (const t of d.tasks ?? []) {
      if (t.status !== 'claimed') continue
      const ids = JSON.stringify(t.payload ?? {})
      for (const [sid, k] of stateDeck) if (ids.includes(sid)) activeDecks.add(k)
    }
    const latest = [...d.states].sort((a, b) => b.first_seen_step - a.first_seen_step)[0]
    if (latest) activeDecks.add(stateDeck.get(latest.id)!)
    const lastT = [...d.transitions].sort((a, b) => b.step - a.step)[0]
    if (lastT) activeDecks.add(stateDeck.get(lastT.target_state_id) ?? '')
  }

  const formDeck = new Map<string, string>()
  for (const f of d.forms ?? []) {
    const k = stateDeck.get(f.state_id)
    if (k) formDeck.set(f.id, k)
  }
  const decks = new Map<string, Deck>()
  for (const [k, ss] of byKey) {
    decks.set(k, { key: k, heading: headingOf(ss[0]), route: ss[0].route, states: ss, testCases: 0, findings: {},
      innerMoves: 0, active: activeDecks.has(k) })
  }
  for (const tc of d.test_cases ?? []) {
    const k = formDeck.get(tc.form_id)
    if (k && tc.status === 'executed') decks.get(k)!.testCases++
  }
  for (const f of d.findings) {
    const k = f.form_id ? formDeck.get(f.form_id) : undefined
    if (!k) continue
    const fs = decks.get(k)!.findings
    fs[f.verification_status] = (fs[f.verification_status] ?? 0) + 1
  }
  for (const t of d.transitions) {
    const a = stateDeck.get(t.source_state_id)
    if (a && t.source_state_id !== t.target_state_id && a === stateDeck.get(t.target_state_id)) decks.get(a)!.innerMoves++
  }
  return decks
}

/** Collapsed decks: manual choices win; otherwise multi-state decks without active work collapse. */
export function collapsedKeys(decks: Map<string, Deck>, manual: Map<string, boolean>): Set<string> {
  const out = new Set<string>()
  for (const dk of decks.values()) {
    if (dk.states.length < 2) continue
    const m = manual.get(dk.key)
    if (m === undefined ? !dk.active : !m) out.add(dk.key)
  }
  return out
}
