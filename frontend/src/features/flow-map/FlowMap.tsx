import { graphlib, layout } from '@dagrejs/dagre'
import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  MarkerType,
  MiniMap,
  Panel,
  Position,
  ReactFlow,
  getBezierPath,
  getSmoothStepPath,
  useReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { ChevronsDownUp, ChevronsUpDown, Flag, Image as ImageIcon, Layers, MousePointerClick, Navigation, PencilLine, RotateCw } from 'lucide-react'
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Thumb } from '../../components/Screenshot'
import { buildDecks, collapsedKeys, deckKey, type Deck } from '../../lib/decks'
import { cx } from '../../lib/ui-utils'
import type { RunDetail, ScreenState, Transition } from '../../lib/types'

export type Selection = { kind: 'state'; id: string } | { kind: 'transition'; id: string } | null

const NODE_W = 232
const NODE_H = 188
const DECK_PREFIX = 'deck:'

type StateNodeData = {
  state: ScreenState; selected: boolean; dimmed: boolean; isStart: boolean; showThumb: boolean
  deck?: { size: number; onCollapse: () => void } // set on the first state of an expanded multi-state deck
}
type DeckNodeData = {
  deck: Deck; selected: boolean; dimmed: boolean; isStart: boolean; showThumb: boolean; onExpand: () => void
}

const FINDING_TONE: Record<string, [string, string]> = {
  confirmed: ['bg-red-100 text-red-800', 'confirmed'],
  unverified: ['bg-amber-100 text-amber-900', 'unverified'],
  inconclusive: ['bg-slate-200 text-slate-800', 'inconclusive'],
  not_reproduced: ['bg-emerald-100 text-emerald-800', 'not reproduced'],
}

/** A collapsed deck: several observed states of one page or form, drawn as stacked cards. */
const DeckNode = memo(function DeckNode({ data }: NodeProps<Node<DeckNodeData>>) {
  const dk = data.deck
  const rep = dk.states[0]
  const findings = Object.entries(dk.findings).filter(([, n]) => n > 0)
  return (
    <div className={cx('relative transition-opacity duration-200', data.dimmed && 'opacity-70')} style={{ width: NODE_W }}>
      {/* Stacked-card edges behind the top card. */}
      <div aria-hidden className="absolute inset-0 translate-x-2 translate-y-2 rounded-xl border border-slate-200 bg-slate-50" />
      <div aria-hidden className="absolute inset-0 translate-x-1 translate-y-1 rounded-xl border border-slate-200 bg-white" />
      <div className={cx('relative overflow-hidden rounded-xl border bg-white shadow-sm',
        data.selected ? 'border-accent-500 shadow-[0_0_0_3px_var(--color-accent-100)]' : 'border-slate-300 hover:shadow-md')}>
        <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-slate-300" />
        {data.showThumb && <Thumb id={rep.screenshot_artifact_id} alt="" className="h-[92px] w-full border-b border-slate-100" />}
        <div className="space-y-1.5 px-3 py-2">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 text-[13px] font-semibold leading-tight text-slate-900">
              <span className="block truncate" title={dk.heading}>{dk.heading}</span>
              <span className="block truncate font-mono text-[10.5px] font-normal text-slate-500">{dk.route}</span>
            </div>
            {data.isStart && (
              <span className="inline-flex shrink-0 items-center gap-0.5 rounded bg-slate-900 px-1.5 py-0.5 text-[10px] font-medium text-white">
                <Flag size={10} aria-hidden /> Start
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-1 text-[10.5px]">
            <span className="inline-flex items-center gap-1 rounded bg-slate-900 px-1.5 py-0.5 font-medium text-white">
              <Layers size={10} aria-hidden />{dk.states.length} observed states
            </span>
            {dk.testCases > 0 && <span className="rounded bg-amber-50 px-1.5 py-0.5 font-medium text-amber-900 ring-1 ring-inset ring-amber-200">
              {dk.testCases} test{dk.testCases === 1 ? '' : 's'} recorded</span>}
            {findings.map(([st, n]) => (
              <span key={st} className={cx('rounded px-1.5 py-0.5 font-medium', FINDING_TONE[st]?.[0] ?? 'bg-slate-100')}>
                {n} {FINDING_TONE[st]?.[1] ?? st}
              </span>
            ))}
            {dk.active && <span className="rounded bg-emerald-50 px-1.5 py-0.5 font-medium text-emerald-800 ring-1 ring-inset ring-emerald-200">active</span>}
          </div>
          <button type="button" onClick={(e) => { e.stopPropagation(); data.onExpand() }} aria-expanded={false}
            className="nodrag inline-flex items-center gap-1 rounded-md border border-slate-200 px-1.5 py-0.5 text-[11px] font-medium text-slate-700 hover:bg-slate-50">
            <ChevronsUpDown size={12} aria-hidden />Expand {dk.states.length} states
            {dk.innerMoves > 0 && <span className="font-normal text-slate-500">· {dk.innerMoves} moves inside</span>}
          </button>
        </div>
        <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-slate-300" />
      </div>
    </div>
  )
})
type TransitionEdgeData = {
  transition: Transition
  loopIndex: number
  parallelIndex: number
  nodeH: number
  selected: boolean
  dimmed: boolean
  onSelect: (id: string) => void
}

function ActionIcon({ type }: { type: string }) {
  const props = { size: 11, 'aria-hidden': true, className: 'shrink-0 text-slate-500' } as const
  if (type === 'fill') return <PencilLine {...props} />
  if (type === 'reload') return <RotateCw {...props} />
  if (type === 'navigate') return <Navigation {...props} />
  return <MousePointerClick {...props} />
}

const PHASE_STROKE: Record<string, string> = { input_test: '#d97706', verify: '#7c3aed' }
const PHASE_SHORT: Record<string, string> = { input_test: 'test', verify: 'verify' }

const StateNode = memo(function StateNode({ data }: NodeProps<Node<StateNodeData>>) {
  const s = data.state
  const [heading, ...rest] = s.summary.split(' — ')
  const contexts = new Set((s.sightings ?? []).map((x) => x.context_id)).size
  return (
    <div
      className={cx(
        'overflow-hidden rounded-xl border bg-white shadow-sm transition-[box-shadow,opacity,border-color] duration-200',
        data.selected ? 'border-accent-500 shadow-[0_0_0_3px_var(--color-accent-100)]' : 'border-slate-200 hover:border-slate-300 hover:shadow-md',
        data.dimmed && 'opacity-70',
      )}
      style={{ width: NODE_W }}
    >
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-slate-300" />
      {data.showThumb && <Thumb id={s.screenshot_artifact_id} alt="" className="h-[108px] w-full border-b border-slate-100" />}
      <div className="space-y-1 px-3 py-2.5">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 text-[13px] font-semibold leading-tight text-slate-900">
            {heading}
            {rest.length > 0 && <span className="block truncate text-xs font-normal text-slate-600">{rest.join(' — ')}</span>}
          </div>
          {data.isStart && (
            <span className={cx('inline-flex shrink-0 items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium',
              data.dimmed ? 'bg-slate-200 text-slate-900' : 'bg-slate-900 text-white')}>
              <Flag size={10} aria-hidden /> Start
            </span>
          )}
        </div>
        {data.deck && (
          <button type="button" onClick={(e) => { e.stopPropagation(); data.deck!.onCollapse() }} aria-expanded
            className="nodrag inline-flex items-center gap-1 rounded-md border border-slate-200 px-1.5 py-0.5 text-[11px] font-medium text-slate-700 hover:bg-slate-50">
            <ChevronsDownUp size={12} aria-hidden />Collapse {data.deck.size} states of this page
          </button>
        )}
        <div className="flex items-center justify-between gap-2 font-mono text-[10.5px] text-slate-500">
          <span className="truncate">{s.route}</span>
          <span className="shrink-0">step {s.first_seen_step}</span>
        </div>
        {(s.discovered_by && s.discovered_by !== 'explorer-a') || contexts > 1 ? (
          <div className="flex flex-wrap gap-x-2 text-[10.5px] text-slate-600">
            {s.discovered_by && s.discovered_by !== 'explorer-a' && <span>found by {s.discovered_by}</span>}
            {contexts > 1 && <span>seen in {contexts} contexts</span>}
          </div>
        ) : null}
      </div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-slate-300" />
    </div>
  )
})

function TransitionEdge(props: EdgeProps<Edge<TransitionEdgeData>>) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, markerEnd } = props
  const d = data!
  const t = d.transition
  let path: string
  let lx: number
  let ly: number
  if (props.source === props.target) {
    // Self-loop drawn over the top of the node; stacked if several.
    const lift = d.nodeH / 2 + 46 + d.loopIndex * 36
    const top = sourceY - lift
    path = `M ${sourceX} ${sourceY} C ${sourceX + 46} ${sourceY}, ${sourceX + 30} ${top}, ${(sourceX + targetX) / 2} ${top} S ${targetX - 46} ${targetY}, ${targetX} ${targetY}`
    lx = (sourceX + targetX) / 2
    ly = top
  } else if (targetX < sourceX) {
    // Wrapped or backward edge: route orthogonally through the gap between rows.
    ;[path, lx, ly] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 14, offset: 28 + d.parallelIndex * 14 })
  } else {
    const curvature = 0.25 + d.parallelIndex * 0.25
    ;[path, lx, ly] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, curvature })
    ly += d.parallelIndex * 28
  }
  const phaseStroke = PHASE_STROKE[t.phase ?? '']
  const stroke = !t.ok ? 'var(--color-red-500)' : d.selected ? 'var(--color-accent-500)' : phaseStroke ?? 'var(--color-slate-400)'
  return (
    <>
      <BaseEdge
        path={path}
        markerEnd={markerEnd}
        style={{
          stroke,
          strokeWidth: d.selected ? 2.5 : 1.5,
          strokeDasharray: t.ok ? undefined : '5 4',
          opacity: d.dimmed ? 0.35 : 1,
          transition: 'opacity 200ms, stroke 200ms',
        }}
      />
      <EdgeLabelRenderer>
        <button
          type="button"
          onClick={() => d.onSelect(t.id)}
          aria-pressed={d.selected}
          title={t.label}
          style={{ transform: `translate(-50%, -50%) translate(${lx}px, ${ly}px)`, pointerEvents: 'all', zIndex: d.selected ? 2 : 1 }}
          className={cx(
            'nodrag nopan absolute flex max-w-[190px] items-center gap-1.5 rounded-full border bg-white py-0.5 pl-0.5 pr-2 text-[11px] shadow-sm transition-[opacity,box-shadow]',
            t.ok ? 'border-slate-200 text-slate-700' : 'border-red-300 text-red-800',
            d.dimmed && 'border-slate-100 text-slate-500 shadow-none',
            d.selected && 'border-accent-500 shadow-[0_0_0_3px_var(--color-accent-100)]',
          )}
        >
          <span className={cx('flex h-[18px] min-w-[18px] items-center justify-center rounded-full px-1 font-mono text-[10px] font-semibold',
            d.selected ? 'bg-accent-600 text-white' : t.ok ? 'bg-slate-100 text-slate-700' : 'bg-red-100 text-red-800')}>
            <span className="sr-only">Transition step </span>{t.step}
          </span>
          {PHASE_SHORT[t.phase ?? ''] && (
            <span className={cx('rounded px-1 text-[10px] font-semibold', t.phase === 'verify' ? 'bg-violet-100 text-violet-800' : 'bg-amber-100 text-amber-900')}>
              {PHASE_SHORT[t.phase!]}<span className="sr-only"> by {t.agent_id}</span>
            </span>
          )}
          <ActionIcon type={t.action.type} />
          <span className="truncate">{t.label.replace(/^(click|fill|test:|verify:) ?/, '')}</span>
          {!t.ok && <span className="sr-only"> (failed)</span>}
        </button>
      </EdgeLabelRenderer>
    </>
  )
}

const nodeTypes = { state: StateNode, deck: DeckNode }
const edgeTypes = { transition: TransitionEdge }

const COL_GAP = 170
const ROW_GAP = 150
const nodeHeight = (thumbs: boolean) => (thumbs ? NODE_H : 80)

/**
 * Layered left-to-right layout (dagre), then wrapped into rows.
 *
 * Dagre keeps branch and back-edge structure inside a rank. A long linear run in one
 * row would be fitted at an unreadable zoom, so ranks wrap into rows. The column count
 * is chosen to maximise the fit-to-view zoom for the measured panel size.
 * Self-loops are excluded from ranking and drawn over their node.
 */
function layoutStates(ids: string[], links: { id: string; source: string; target: string }[], size: { w: number; h: number }, thumbs: boolean) {
  const nodeH = nodeHeight(thumbs)
  const g = new graphlib.Graph({ multigraph: true })
  g.setGraph({ rankdir: 'LR', ranksep: 100, nodesep: 70 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const id of ids) g.setNode(id, { width: NODE_W, height: nodeH })
  for (const t of links) {
    if (t.source !== t.target) g.setEdge(t.source, t.target, { width: 150, height: 24 }, t.id)
  }
  layout(g)

  // Group nodes into ranks by their dagre x position.
  const xs = [...new Set(g.nodes().map((id) => Math.round(g.node(id).x)))].sort((a, b) => a - b)
  const ranks = xs.map((x) => g.nodes().filter((id) => Math.round(g.node(id).x) === x))
  const top = (id: string) => g.node(id).y - nodeH / 2

  const rowsFor = (k: number) => {
    const rows: string[][][] = []
    for (let i = 0; i < ranks.length; i += k) rows.push(ranks.slice(i, i + k))
    return rows.map((row) => {
      const ids = row.flat()
      const minTop = Math.min(...ids.map(top))
      const height = Math.max(...ids.map(top)) - minTop + nodeH
      return { row, minTop, height }
    })
  }

  let best = { k: Math.max(1, ranks.length), zoom: 0 }
  for (let k = 1; k <= Math.max(1, ranks.length); k++) {
    const rows = rowsFor(k)
    const width = k * NODE_W + (k - 1) * COL_GAP
    const height = rows.reduce((h, r) => h + r.height, 0) + rows.length * ROW_GAP
    const zoom = Math.min((size.w * 0.86) / width, (size.h * 0.86) / height, 1)
    if (zoom > best.zoom + 0.02) best = { k, zoom }
  }

  const pos = new Map<string, { x: number; y: number }>()
  let y = ROW_GAP // headroom for self-loops above the first row
  for (const { row, minTop, height } of rowsFor(best.k)) {
    row.forEach((rank, col) => {
      for (const id of rank) pos.set(id, { x: col * (NODE_W + COL_GAP), y: y + top(id) - minTop })
    })
    y += height + ROW_GAP
  }
  return { pos, columns: best.k }
}

function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [size, setSize] = useState({ w: 900, h: 600 })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => {
      // Round so tiny resizes do not trigger relayout.
      const w = Math.round(e.contentRect.width / 40) * 40
      const h = Math.round(e.contentRect.height / 40) * 40
      setSize((s) => (s.w === w && s.h === h ? s : { w, h }))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, size] as const
}

function recordIds(d: RunDetail) {
  return new Set([...d.states.map((s) => s.id), ...d.transitions.map((t) => t.id)])
}

function FitOnLayoutChange({ layoutKey }: { layoutKey: string }) {
  const rf = useReactFlow()
  useEffect(() => {
    const id = requestAnimationFrame(() => rf.fitView({ padding: 0.12, duration: 250 }))
    return () => cancelAnimationFrame(id)
  }, [layoutKey, rf])
  return null
}

export function FlowMap({ detail, selection, onSelect, showThumbs, onToggleThumbs, compact = false }: {
  detail: RunDetail
  selection: Selection
  onSelect: (s: Selection) => void
  showThumbs: boolean
  onToggleThumbs: () => void
  compact?: boolean // docked mini map: no legend or toolbar
}) {
  const [wrapRef, size] = useSize<HTMLDivElement>()
  // Card decks (visual grouping only). Manual expand/collapse choices win over the automatic
  // default and are kept until the run changes.
  const [manual, setManual] = useState(() => ({ run: detail.run.id, map: new Map<string, boolean>() }))
  if (manual.run !== detail.run.id) setManual({ run: detail.run.id, map: new Map() })
  const decks = useMemo(() => buildDecks(detail), [detail])
  const collapsed = useMemo(() => collapsedKeys(decks, manual.map), [decks, manual])
  const [regrouping, setRegrouping] = useState(false)
  const regroupTimer = useRef<number | undefined>(undefined)
  const setDeck = useCallback((keys: string[], expanded: boolean) => {
    setManual((m) => {
      const map = new Map(m.map)
      for (const k of keys) map.set(k, expanded)
      return { run: m.run, map }
    })
    setRegrouping(true)
    window.clearTimeout(regroupTimer.current)
    regroupTimer.current = window.setTimeout(() => setRegrouping(false), 400)
  }, [])
  const multiDecks = useMemo(() => [...decks.values()].filter((dk) => dk.states.length > 1).map((dk) => dk.key), [decks])
  // Each state is drawn as itself or as its collapsed deck.
  const visibleId = useCallback((stateId: string) => {
    const s = detail.states.find((x) => x.id === stateId)
    const k = s ? deckKey(s) : ''
    return collapsed.has(k) ? DECK_PREFIX + k : stateId
  }, [detail, collapsed])
  const view = useMemo(() => {
    const ids = [...new Set(detail.states.map((s) => visibleId(s.id)))]
    // Moves between states inside one collapsed deck are counted on the deck instead of drawn.
    const links = detail.transitions
      .map((t) => ({ id: t.id, source: visibleId(t.source_state_id), target: visibleId(t.target_state_id), inner: t.source_state_id !== t.target_state_id }))
      .filter((l) => !(l.inner && l.source === l.target && l.source.startsWith(DECK_PREFIX)))
    return { ids, links }
  }, [detail, visibleId])
  const { pos: positions, columns } = useMemo(() => layoutStates(view.ids, view.links, size, showThumbs), [view, size, showThumbs])
  const startId = useMemo(() => [...detail.states].sort((a, b) => a.first_seen_step - b.first_seen_step)[0]?.id, [detail])

  // Records accepted after the map first rendered are marked new so they animate once.
  // The first render of a run (including old runs) marks nothing as new.
  const [track, setTrack] = useState(() => ({ detail, run: detail.run.id, known: recordIds(detail), fresh: new Set<string>() }))
  if (track.detail !== detail) {
    const ids = recordIds(detail)
    if (track.run !== detail.run.id) setTrack({ detail, run: detail.run.id, known: ids, fresh: new Set() })
    else {
      const add = [...ids].filter((id) => !track.known.has(id))
      setTrack({ detail, run: track.run, known: ids, fresh: add.length ? new Set([...track.fresh, ...add]) : track.fresh })
    }
  }
  const fresh = track.fresh
  const [follow, setFollow] = useState(true)

  const { nodes, edges } = useMemo(() => {
    // Highlight the selection's neighbourhood so the eye can follow it.
    const selT = selection?.kind === 'transition' ? detail.transitions.find((t) => t.id === selection.id) : undefined
    const focusStates = new Set<string>()
    const focusEdges = new Set<string>()
    if (selT) {
      focusStates.add(selT.source_state_id).add(selT.target_state_id)
      focusEdges.add(selT.id)
    } else if (selection?.kind === 'state') {
      focusStates.add(selection.id)
      for (const t of detail.transitions) {
        if (t.source_state_id === selection.id || t.target_state_id === selection.id) {
          focusEdges.add(t.id)
          focusStates.add(t.source_state_id).add(t.target_state_id)
        }
      }
    }
    const hasFocus = selection !== null
    const focusVisible = new Set([...focusStates].map(visibleId))
    const selectedVisible = selection?.kind === 'state' ? visibleId(selection.id) : null

    const deckNodes: Node<DeckNodeData>[] = [...collapsed].map((k) => {
      const dk = decks.get(k)!
      const id = DECK_PREFIX + k
      return {
        id, type: 'deck', position: positions.get(id) ?? { x: 0, y: 0 },
        className: 'fl-deck-in',
        ariaLabel: `Deck: ${dk.heading}, ${dk.states.length} observed states, route ${dk.route}. Activate to expand.`,
        data: { deck: dk, selected: selectedVisible === id, dimmed: hasFocus && !focusVisible.has(id),
          isStart: dk.states.some((s) => s.id === startId), showThumb: showThumbs, onExpand: () => setDeck([k], true) },
      }
    })
    const stateNodes: Node<StateNodeData>[] = detail.states.filter((s) => !collapsed.has(deckKey(s))).map((s) => ({
      id: s.id,
      type: 'state',
      position: positions.get(s.id) ?? { x: 0, y: 0 },
      className: fresh.has(s.id) ? 'fl-new-node' : undefined,
      ariaLabel: `State: ${s.summary}, route ${s.route}`,
      data: {
        state: s,
        selected: selection?.kind === 'state' && selection.id === s.id,
        dimmed: hasFocus && !focusStates.has(s.id),
        isStart: s.id === startId,
        showThumb: showThumbs,
        deck: (() => {
          const dk = decks.get(deckKey(s))
          return dk && dk.states.length > 1 && dk.states[0].id === s.id
            ? { size: dk.states.length, onCollapse: () => setDeck([dk.key], false) } : undefined
        })(),
      },
    }))
    const nodes: Node[] = [...stateNodes, ...deckNodes]
    const shown = new Set(view.links.map((l) => l.id))
    const loops = new Map<string, number>()
    const pairs = new Map<string, number>()
    const edges: Edge<TransitionEdgeData>[] = [...detail.transitions]
      .filter((t) => shown.has(t.id))
      .sort((a, b) => a.step - b.step)
      .map((t) => {
        const source = visibleId(t.source_state_id)
        const target = visibleId(t.target_state_id)
        const self = source === target
        const key = self ? source : `${source}>${target}`
        const bucket = self ? loops : pairs
        const index = bucket.get(key) ?? 0
        bucket.set(key, index + 1)
        const selected = selection?.kind === 'transition' && selection.id === t.id
        return {
          id: t.id,
          source,
          target,
          type: 'transition',
          className: fresh.has(t.id) ? 'fl-new-edge' : undefined,
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: !t.ok ? '#ef4444' : selected ? '#3b6ef5' : PHASE_STROKE[t.phase ?? ''] ?? '#94a3b8' },
          data: {
            transition: t,
            loopIndex: self ? index : 0,
            parallelIndex: self ? 0 : index,
            nodeH: nodeHeight(showThumbs),
            selected,
            dimmed: hasFocus && !focusEdges.has(t.id),
            onSelect: (id: string) => onSelect({ kind: 'transition', id }),
          },
        }
      })
    return { nodes, edges }
  }, [detail, positions, selection, onSelect, startId, showThumbs, fresh, collapsed, decks, visibleId, view, setDeck])

  return (
    <div ref={wrapRef} className={cx('h-full w-full', regrouping && 'fl-regroup')}>
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodeClick={(_, n) => (n.id.startsWith(DECK_PREFIX) ? setDeck([n.id.slice(DECK_PREFIX.length)], true) : onSelect({ kind: 'state', id: n.id }))}
      onEdgeClick={(_, e) => onSelect({ kind: 'transition', id: e.id })}
      onPaneClick={() => onSelect(null)}
      onMoveStart={(e) => { if (e) setFollow(false) }}
      nodesConnectable={false}
      nodesDraggable
      minZoom={0.2}
      maxZoom={2}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      proOptions={{ hideAttribution: true }}
    >
      {follow && <FitOnLayoutChange layoutKey={`${detail.run.id}:${detail.states.length}:${columns}:${showThumbs}:${size.w}x${size.h}:${view.ids.length}`} />}
      <Background gap={20} size={1} color="var(--color-slate-200)" />
      <Controls showInteractive={false} position="bottom-left" className="!rounded-md !border !border-slate-200 !shadow-sm" fitViewOptions={{ padding: 0.2, duration: 250 }} />
      {detail.states.length >= 8 && <MiniMap
        position="bottom-right"
        pannable
        zoomable
        ariaLabel="Map overview"
        nodeColor={(n) => ((n.data as StateNodeData).selected ? '#3b6ef5' : n.type === 'deck' ? '#64748b' : '#cbd5e1')}
        nodeBorderRadius={6}
        className="!rounded-md !border !border-slate-200 !shadow-sm"
        style={{ width: 160, height: 100 }}
      />}
      {!compact && <Panel position="top-left" className="!m-3">
        <MapToolbar showThumbs={showThumbs} onToggleThumbs={onToggleThumbs} follow={follow} onToggleFollow={() => setFollow((f) => !f)}
          phases={new Set(detail.transitions.map((t) => t.phase ?? 'explore'))}
          decks={multiDecks.length > 0 ? {
            total: multiDecks.length, collapsed: collapsed.size,
            expandAll: () => setDeck(multiDecks, true), collapseAll: () => setDeck(multiDecks, false),
          } : null} />
      </Panel>}
    </ReactFlow>
    </div>
  )
}

function MapToolbar({ showThumbs, onToggleThumbs, phases, follow, onToggleFollow, decks }: {
  showThumbs: boolean; onToggleThumbs: () => void; phases: Set<string>; follow: boolean; onToggleFollow: () => void
  decks: { total: number; collapsed: number; expandAll: () => void; collapseAll: () => void } | null
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-slate-200 bg-white/95 py-1 pl-2.5 pr-1 text-[11px] text-slate-600 shadow-sm backdrop-blur">
      <span className="flex items-center gap-1.5"><span className="h-px w-4 bg-slate-400" aria-hidden />{phases.size > 1 ? 'Explorer' : 'Action'}</span>
      {phases.has('input_test') && <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-amber-600" aria-hidden />Input test</span>}
      {phases.has('verify') && <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-violet-600" aria-hidden />Verification</span>}
      <span className="flex items-center gap-1.5"><span className="h-px w-4 border-t border-dashed border-red-500" aria-hidden />Failed</span>
      <span className="hidden text-slate-500 sm:inline">Observed states only, not full coverage</span>
      <button type="button" onClick={onToggleThumbs} aria-pressed={showThumbs}
        className="inline-flex h-6 items-center gap-1 rounded-md border border-slate-200 px-1.5 font-medium text-slate-700 hover:bg-slate-50 aria-pressed:bg-slate-900 aria-pressed:text-white aria-pressed:border-slate-900">
        <ImageIcon size={12} aria-hidden />Thumbnails
      </button>
      <button type="button" onClick={onToggleFollow} aria-pressed={follow}
        title="Re-fit the map as new pages are accepted. Turns off when you pan or zoom."
        className="inline-flex h-6 items-center gap-1 rounded-md border border-slate-200 px-1.5 font-medium text-slate-700 hover:bg-slate-50 aria-pressed:bg-slate-900 aria-pressed:text-white aria-pressed:border-slate-900">
        Follow new pages
      </button>
      {decks && (
        <span className="inline-flex items-center gap-1" role="group" aria-label="Card decks">
          <span className="text-slate-500" aria-live="polite">{decks.collapsed} of {decks.total} decks collapsed</span>
          <button type="button" onClick={decks.expandAll} disabled={decks.collapsed === 0}
            className="inline-flex h-6 items-center gap-1 rounded-md border border-slate-200 px-1.5 font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            <ChevronsUpDown size={12} aria-hidden />Expand all
          </button>
          <button type="button" onClick={decks.collapseAll} disabled={decks.collapsed === decks.total}
            className="inline-flex h-6 items-center gap-1 rounded-md border border-slate-200 px-1.5 font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            <ChevronsDownUp size={12} aria-hidden />Collapse all
          </button>
        </span>
      )}
    </div>
  )
}
