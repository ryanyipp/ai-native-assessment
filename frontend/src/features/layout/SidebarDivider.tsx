import { useRef, useState } from 'react'
import { SIDEBAR_MIN, type useSidebarWidth } from '../../lib/sidebarWidth'

/**
 * Vertical divider between the map and the sidebar. Drag with a pointer, or focus it and use
 * Left/Right (Shift for larger steps), Home/End for the limits, Enter to reset. Hidden when the
 * sidebar stacks below the map on narrow screens.
 */
export function SidebarDivider({ width, setWidth, max, reset }: ReturnType<typeof useSidebarWidth>) {
  const drag = useRef<{ x: number; w: number } | null>(null)
  const [dragging, setDragging] = useState(false)
  const onPointerDown = (e: React.PointerEvent) => {
    drag.current = { x: e.clientX, w: width }
    setDragging(true)
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current) return
    // The sidebar is on the right: dragging left widens it.
    setWidth(drag.current.w + (drag.current.x - e.clientX), false)
  }
  const end = (e: React.PointerEvent) => {
    if (!drag.current) return
    drag.current = null
    setDragging(false)
    e.currentTarget.releasePointerCapture(e.pointerId)
    setWidth(width)
  }
  const onKeyDown = (e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 64 : 16
    const next = { ArrowLeft: width + step, ArrowRight: width - step, Home: SIDEBAR_MIN, End: max() }[e.key]
    if (next !== undefined) { e.preventDefault(); setWidth(next) }
    else if (e.key === 'Enter') { e.preventDefault(); reset() }
  }
  return (
    <div role="separator" aria-orientation="vertical" aria-label="Resize sidebar" tabIndex={0}
      aria-valuenow={width} aria-valuemin={SIDEBAR_MIN} aria-valuemax={max()}
      aria-valuetext={`Sidebar ${width} pixels wide`}
      title="Drag to resize the sidebar. Keyboard: Left/Right arrows (Shift for larger steps), Home/End, Enter to reset."
      onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={end} onPointerCancel={end}
      onKeyDown={onKeyDown} onDoubleClick={reset}
      data-testid="sidebar-divider"
      className="group relative z-10 -mx-1 hidden w-2 shrink-0 cursor-col-resize touch-none select-none focus-visible:outline-none lg:block">
      <span aria-hidden className={`absolute inset-y-0 left-1/2 w-px -translate-x-1/2 transition-colors ${dragging ? 'bg-accent-500' : 'bg-slate-200 group-hover:bg-accent-400 group-focus-visible:bg-accent-500'}`} />
      <span aria-hidden className="absolute left-1/2 top-1/2 h-8 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-slate-300 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
    </div>
  )
}
