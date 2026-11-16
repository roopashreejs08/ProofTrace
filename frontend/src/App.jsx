import { useState } from 'react'

import Home from './components/Home'
import Run from './components/Run'
import History from './components/History'

import { Logo, FOCUS } from './components/ui'


export default function App() {
  const [view, setView] = useState('home')
  const [invId, setInvId] = useState(null)

  const open = (id) => {
    setInvId(id)
    setView('run')
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">

      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6 sm:py-4">

          <button
            onClick={() => setView('home')}
            aria-label="Home"
            className={`rounded-xl ${FOCUS}`}
          >
            <Logo />
          </button>

          <nav className="flex shrink-0 gap-3 text-sm font-medium text-slate-600 sm:gap-5">

            <button
              onClick={() => setView('home')}
              className={`rounded-md hover:text-indigo-600 ${FOCUS}`}
            >
              New check
            </button>

            <button
              onClick={() => setView('history')}
              className={`rounded-md hover:text-indigo-600 ${FOCUS}`}
            >
              History
            </button>

          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">

        {view === 'home' && (
          <Home onStart={open} />
        )}

        {view === 'history' && (
          <History onOpen={open} onNew={() => setView('home')} />
        )}

        {view === 'run' && (
          <Run id={invId} onRetry={open} />
        )}

      </main>
    </div>
  )
}