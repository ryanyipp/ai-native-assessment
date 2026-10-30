import { lazy, Suspense } from 'react'
import Landing from './features/landing/Landing.tsx'

const App = lazy(() => import('./App.tsx'))

// Older links opened a run at /?run=ID; they now live under /workspace.
if (location.pathname === '/' && new URLSearchParams(location.search).has('run')) {
  history.replaceState(null, '', `/workspace${location.search}${location.hash}`)
}

export default function Root() {
  return location.pathname === '/' ? <Landing /> : <Suspense fallback={null}><App /></Suspense>
}
