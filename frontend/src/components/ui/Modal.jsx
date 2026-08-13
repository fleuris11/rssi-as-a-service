import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

export default function Modal({ open, onClose, title, children, className = '' }) {
  const dialogRef = useRef(null)
  const previouslyFocused = useRef(null)
  // ``onClose`` est presque toujours une fonction recréée à chaque rendu du
  // parent. La garder dans les dépendances de l'effet ci-dessous relançait
  // celui-ci à CHAQUE rendu — donc à chaque frappe dans un champ de la
  // modale — et `dialogRef.current.focus()` volait le focus de l'input : on
  // ne pouvait taper qu'un seul caractère. Une ref garde l'appel à jour sans
  // faire de la fonction une dépendance.
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  // Effet de mise au point / restauration : dépend UNIQUEMENT de l'ouverture.
  useEffect(() => {
    if (!open) return undefined

    previouslyFocused.current = document.activeElement
    dialogRef.current?.focus()

    function handleKeyDown(event) {
      if (event.key === 'Escape') onCloseRef.current()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      previouslyFocused.current?.focus?.()
    }
  }, [open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Fermer"
        onClick={onClose}
        className="absolute inset-0 bg-ink-950/50 backdrop-blur-[2px]"
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
        className={`relative w-full max-w-lg rounded-lg bg-surface p-6 shadow-elevated outline-none ${className}`}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 id="modal-title" className="font-display text-lg font-semibold text-ink-900">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer"
            className="transition-smooth -m-1 rounded-md p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-700 focus-visible:outline-2 focus-visible:outline-brand-600"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
