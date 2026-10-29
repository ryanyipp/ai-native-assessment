export const fmtMs = (ms: number | null | undefined) =>
  ms == null ? '—' : ms >= 1000 ? `${(ms / 1000).toFixed(ms >= 10000 ? 0 : 1)} s` : `${ms} ms`

export const fmtUsd = (v: number | null | undefined, digits = 4) => (v == null ? 'not reported' : `US$${v.toFixed(digits)}`)

export const fmtInt = (n: number) => n.toLocaleString('en-US')

export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })

export const fmtDateTime = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

export function shortUrl(url: string) {
  try {
    const u = new URL(url)
    return `${u.host}${u.pathname}${u.search}`
  } catch {
    return url
  }
}
