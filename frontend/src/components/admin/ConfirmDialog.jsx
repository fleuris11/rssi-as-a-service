import { AlertTriangle } from 'lucide-react'
import { useEffect, useState } from 'react'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

/**
 * Confirmation avant une action impactante ou destructive.
 *
 * Deux niveaux volontairement distincts :
 *
 * - **confirmation simple** : on résume ce qui va se passer, l'utilisateur
 *   valide. Suffisant pour ce qui se défait (archiver, suspendre).
 * - **confirmation par saisie** (``confirmText``) : réservée à l'irréversible.
 *   Retaper le nom de l'objet est le seul garde-fou qui résiste à un clic
 *   machinal — et la suppression définitive d'une entreprise détruit ses
 *   diagnostics, ses actifs et son historique.
 *
 * Le résumé n'est pas décoratif : « êtes-vous sûr ? » ne dit pas ce qui va
 * arriver, et c'est justement la question que se pose l'utilisateur.
 */
export default function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  summary,
  consequences = [],
  confirmLabel = 'Confirmer',
  confirmText = '',
  danger = false,
  loading = false,
}) {
  const [typed, setTyped] = useState('')

  useEffect(() => {
    if (open) setTyped('')
  }, [open])

  const blocked = Boolean(confirmText) && typed.trim() !== confirmText

  return (
    <Modal open={open} onClose={onClose} title={title}>
      <div className="space-y-4">
        {summary && <p className="text-sm text-ink-700">{summary}</p>}

        {consequences.length > 0 && (
          <div
            className={`rounded-md border px-4 py-3 ${
              danger ? 'border-critical-200 bg-critical-50' : 'border-ink-200 bg-ink-50'
            }`}
          >
            <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ink-600">
              <AlertTriangle className="size-3.5" aria-hidden="true" />
              Ce qui va se passer
            </p>
            <ul className="space-y-1">
              {consequences.map((line) => (
                <li key={line} className="text-sm text-ink-700">
                  — {line}
                </li>
              ))}
            </ul>
          </div>
        )}

        {confirmText && (
          <div>
            <label
              className="block text-sm font-medium text-ink-700"
              htmlFor="confirm-dialog-input"
            >
              Retapez « {confirmText} » pour confirmer
            </label>
            <input
              id="confirm-dialog-input"
              type="text"
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              autoComplete="off"
              className="transition-smooth mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600"
            />
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={loading}>
            Annuler
          </Button>
          <Button
            variant={danger ? 'danger' : 'primary'}
            onClick={onConfirm}
            disabled={blocked || loading}
            loading={loading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
