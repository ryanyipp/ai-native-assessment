import { useCallback, useEffect, useState } from 'react'

const KEY = 'flowlens.sidebarWidth'
export const SIDEBAR_MIN = 320
const SIDEBAR_MAX = 760
const MAP_MIN = 420 // the map keeps at least this much width beside the sidebar
const DEFAULT = () => (window.innerWidth >= 1280 ? 440 : 400)

function clampWidth(w: number, container: number | null) {
  const max = Math.max(SIDEBAR_MIN, Math.min(SIDEBAR_MAX, (container ?? window.innerWidth) - MAP_MIN))
  return Math.round(Math.min(max, Math.max(SIDEBAR_MIN, w)))
}

/** Width of the right sidebar, saved in localStorage and kept within limits as the window changes. */
export function useSidebarWidth(containerRef: React.RefObject<HTMLElement | null>) {
  const [width, setWidthRaw] = useState(() => {
    const saved = Number(localStorage.getItem(KEY))
    return clampWidth(Number.isFinite(saved) && saved > 0 ? saved : DEFAULT(), null)
  })
  const max = () => clampWidth(Infinity, containerRef.current?.clientWidth ?? null)
  const setWidth = useCallback((w: number, save = true) => {
    const c = clampWidth(w, containerRef.current?.clientWidth ?? null)
    setWidthRaw(c)
    if (save) localStorage.setItem(KEY, String(c))
  }, [containerRef])
  useEffect(() => {
    const onResize = () => setWidthRaw((w) => clampWidth(w, containerRef.current?.clientWidth ?? null))
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [containerRef])
  return { width, setWidth, max, reset: () => { localStorage.removeItem(KEY); setWidthRaw(clampWidth(DEFAULT(), null)) } }
}

