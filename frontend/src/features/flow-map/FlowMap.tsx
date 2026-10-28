import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  getBezierPath,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useMemo } from 'react'
import { artifactUrl } from '../../lib/api'
import type { RunDetail, ScreenState, Transition } from '../../lib/types'

export type Selection = { kind: 'state'; id: string } | { kind: 'transition'; id: string } | null

type StateNodeData = { state: ScreenState; selected: boolean }
type TransitionEdgeData = { transition: Transition; index: number; selected: boolean; onSelect: (id: string) => void }

function StateNode({ data }: NodeProps<Node<StateNodeData>>) {
  const s = data.state
  return (
    <div className={`w-56 overflow-hidden rounded-lg border-2 bg-white shadow-sm ${data.selected ? 'border-pink-500' : 'border-slate-300'}`}>
      <Handle type="target" position={Position.Left} />
      {s.screenshot_artifact_id && (
        <img src={artifactUrl(s.screenshot_artifact_id)} alt={`Screenshot of ${s.summary}`}
          className="h-28 w-full border-b border-slate-200 object-cover object-top" />
      )}
      <div className="p-2">
        <div className="text-xs font-semibold leading-tight">{s.summary}</div>
        <div className="mt-1 font-mono text-[10px] text-slate-500">{s.route} · first seen step {s.first_seen_step}</div>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

function TransitionEdge(props: EdgeProps<Edge<TransitionEdgeData>>) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, markerEnd } = props
  const t = data!.transition
  let path: string
  let labelX: number
  let labelY: number
  if (t.source_state_id === t.target_state_id) {
    // Self-loop: arc over the node, stacked by index.
    const h = 60 + data!.index * 34
    path = `M ${sourceX} ${sourceY} C ${sourceX + 70} ${sourceY - h - 80}, ${targetX - 70} ${targetY - h - 80}, ${targetX} ${targetY}`
    labelX = (sourceX + targetX) / 2
    labelY = sourceY - h - 30
  } else {
    ;[path, labelX, labelY] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition })
    labelY += data!.index * 26
  }
  const color = !t.ok ? '#dc2626' : data!.selected ? '#ec4899' : '#64748b'
  return (
    <>
      <BaseEdge path={path} markerEnd={markerEnd} style={{ stroke: color, strokeWidth: data!.selected ? 3 : 1.5 }} />
      <EdgeLabelRenderer>
        <button
          type="button"
          onClick={() => data!.onSelect(t.id)}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`, pointerEvents: 'all' }}
          className={`nodrag nopan absolute max-w-48 truncate rounded border bg-white px-1.5 py-0.5 text-[10px] shadow-sm ${
            t.ok ? 'border-slate-300' : 'border-red-400 text-red-700'
          } ${data!.selected ? 'ring-2 ring-pink-400' : ''}`}
          title={t.label}
        >
          {t.step}. {t.label}
        </button>
      </EdgeLabelRenderer>
    </>
  )
}

const nodeTypes = { state: StateNode }
const edgeTypes = { transition: TransitionEdge }

export function FlowMap({ detail, selection, onSelect }: {
  detail: RunDetail
  selection: Selection
  onSelect: (s: Selection) => void
}) {
  const { nodes, edges } = useMemo(() => {
    const ordered = [...detail.states].sort((a, b) => a.first_seen_step - b.first_seen_step)
    const nodes: Node<StateNodeData>[] = ordered.map((s, i) => ({
      id: s.id,
      type: 'state',
      position: { x: i * 320, y: i % 2 === 0 ? 140 : 300 },
      data: { state: s, selected: selection?.kind === 'state' && selection.id === s.id },
    }))
    const pairCount = new Map<string, number>()
    const edges: Edge<TransitionEdgeData>[] = detail.transitions.map((t) => {
      const key = `${t.source_state_id}->${t.target_state_id}`
      const index = pairCount.get(key) ?? 0
      pairCount.set(key, index + 1)
      return {
        id: t.id,
        source: t.source_state_id,
        target: t.target_state_id,
        type: 'transition',
        markerEnd: { type: MarkerType.ArrowClosed },
        data: {
          transition: t,
          index,
          selected: selection?.kind === 'transition' && selection.id === t.id,
          onSelect: (id: string) => onSelect({ kind: 'transition', id }),
        },
      }
    })
    return { nodes, edges }
  }, [detail, selection, onSelect])

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodeClick={(_, n) => onSelect({ kind: 'state', id: n.id })}
      onEdgeClick={(_, e) => onSelect({ kind: 'transition', id: e.id })}
      nodesConnectable={false}
      fitView
      fitViewOptions={{ padding: 0.25 }}
      proOptions={{ hideAttribution: false }}
    >
      <Background />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}
