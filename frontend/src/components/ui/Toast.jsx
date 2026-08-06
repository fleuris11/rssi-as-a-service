import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'

const ToastContext = createContext(null)

const ICONS = { success: CheckCircle2, error: XCircle, warning: AlertTriangle, info: Info }
const ICON_COLOR = {
  success: 'text-ok-strong',
  error: 'text-critical-strong',
  warning: 'text-warning-strong',
  info: 'text-brand-600',
}

const AUTO_DISMISS_MS = 6000

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const nextId = useRef(0)

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((t) => t.id !== id))
  }, [])

  const showToast = useCallback(
    ({ type = 'info', message, action }) => {
      const id = nextId.current++
      setToasts((current) => [...current, { id, type, message, action }])
      setTimeout(() => dismiss(id), AUTO_DISMISS_MS)
      return id
    },
    [dismiss]
  )

  const value = useMemo(() => ({ showToast, dismiss }), [showToast, dismiss])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4 sm:inset-x-auto sm:right-4 sm:items-end"
      >
        {toasts.map((toast) => {
          const Icon = ICONS[toast.type]
          return (
            <div
              key={toast.id}
              role={toast.type === 'error' ? 'alert' : 'status'}
              className="animate-toast-in pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg bg-ink-900 p-4 text-sm text-white shadow-elevated"
            >
              <Icon className={`size-5 shrink-0 ${ICON_COLOR[toast.type]}`} aria-hidden="true" />
              <div className="flex-1">
                <p>{toast.message}</p>
                {toast.action && (
                  <button
                    type="button"
                    onClick={() => {
                      toast.action.onClick()
                      dismiss(toast.id)
                    }}
                    className="transition-smooth mt-2 font-medium text-accent-300 hover:text-accent-200"
                  >
                    {toast.action.label}
                  </button>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                aria-label="Fermer la notification"
                className="transition-smooth -m-1 shrink-0 rounded p-1 text-ink-400 hover:text-white"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}
