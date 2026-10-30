import { lazy, StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import Landing from './features/landing/Landing.tsx'

const App = lazy(() => import('./App.tsx'))

// Older links opened a run at /?run=ID; they now live under /workspace.
if (location.pathname === '/' && new URLSearchParams(location.search).has('run')) {
  history.replaceState(null, '', `/workspace${location.search}${location.hash}`)
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {location.pathname === '/' ? <Landing /> : <Suspense fallback={null}><App /></Suspense>}
  </StrictMode>,
)
