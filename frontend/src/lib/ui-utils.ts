import type { Run } from './types'

export type Tone = 'neutral' | 'blue' | 'green' | 'amber' | 'red' | 'violet'

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(' ')
}

/** Live, playback and mocked are separate provenance flags; show the strongest caveat. */
export function provenanceOf(run: Run): { label: string; tone: Tone; help: string } {
  const p = run.provenance
  if (p.mocked_model) return { label: 'Mocked model', tone: 'violet', help: 'A scripted stand-in replaced the model. Not a live run.' }
  if (p.playback) return { label: 'Playback', tone: 'violet', help: 'Replayed from saved evidence. No fresh browser or model execution.' }
  if (run.mode === 'reverify') return { label: 'Browser re-check', tone: 'neutral', help: 'Real Chromium replay of an earlier finding with its recorded assertion. No model call.' }
  if (p.live) return { label: 'Live', tone: 'green', help: 'Real Chromium and real model calls were executed for this run.' }
  return { label: 'Not live', tone: 'neutral', help: 'No live execution recorded.' }
}

export const verificationMeta: Record<string, { label: string; tone: Tone; help: string }> = {
  unverified: { label: 'Unverified', tone: 'amber', help: 'Only the reporting worker has observed this.' },
  confirmed: { label: 'Confirmed', tone: 'red', help: 'Every fresh replay violated the explicit requirement, as evaluated by code.' },
  not_reproduced: { label: 'Not reproduced', tone: 'green', help: 'Fresh replays met the requirement. This does not prove there is no intermittent bug.' },
  inconclusive: { label: 'Inconclusive', tone: 'neutral', help: 'Setup, evidence or the expected behaviour was insufficient for a verdict.' },
}
