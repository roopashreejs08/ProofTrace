// Shared keyboard-focus ring. Applied to every interactive control so
// keyboard users can see where focus is, without changing how a control
// looks for mouse users (focus-visible only).
export const FOCUS =
  'focus-visible:outline-none focus-visible:ring-2 ' +
  'focus-visible:ring-indigo-500 focus-visible:ring-offset-2'


export function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-6 w-6"
          aria-hidden="true"
        >
          <path d="M12 3 20 7.5v9L12 21l-8-4.5v-9L12 3Z" />
          <path d="m8.5 12 2.2 2.2 4.8-5" />
        </svg>
      </div>

      <div>
        <div className="text-lg font-bold tracking-tight text-slate-900">
          ProofTrace
        </div>
        <div className="hidden text-xs text-slate-500 sm:block">
          Research integrity verification
        </div>
      </div>
    </div>
  )
}


// A shimmering placeholder used while data is loading. Marked
// aria-hidden so screen readers skip it; the surrounding region carries
// the live "loading" message instead.
export function Skeleton({ className = '' }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-lg bg-slate-200/70 ${className}`}
    />
  )
}


// A friendly, clearly-worded empty state with an optional action.
export function EmptyState({ title, children, action }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">

      <h2 className="font-semibold text-slate-800">{title}</h2>

      {children && (
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate-500">
          {children}
        </p>
      )}

      {action && <div className="mt-5">{action}</div>}

    </div>
  )
}

