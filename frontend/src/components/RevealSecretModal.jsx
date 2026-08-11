import { Check, Copy, KeyRound, ShieldAlert } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { threatIntelligenceApi } from '../api/endpoints'
import Button from './ui/Button'
import Modal from './ui/Modal'

const AUTO_HIDE_SECONDS = 30

// Ré-authentification fraîche (ADR-014, mise à jour) : mot de passe OU code
// TOTP, jamais mis en cache — chaque révélation exige une preuve fraîche.
// Le secret déchiffré ne vit que dans l'état local de ce composant (jamais
// le state global/contexte), s'efface tout seul après AUTO_HIDE_SECONDS et à
// la fermeture de la modale.
export default function RevealSecretModal({ open, onClose, findingId }) {
  const [method, setMethod] = useState('password')
  const [password, setPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [secret, setSecret] = useState(null)
  const [secondsLeft, setSecondsLeft] = useState(AUTO_HIDE_SECONDS)
  const [copied, setCopied] = useState(false)
  const countdownRef = useRef(null)

  function resetState() {
    setMethod('password')
    setPassword('')
    setTotpCode('')
    setSubmitting(false)
    setError('')
    setSecret(null)
    setSecondsLeft(AUTO_HIDE_SECONDS)
    setCopied(false)
  }

  useEffect(() => {
    if (!open) resetState()
  }, [open])

  useEffect(() => {
    if (secret === null) return undefined
    setSecondsLeft(AUTO_HIDE_SECONDS)
    countdownRef.current = setInterval(() => {
      setSecondsLeft((current) => {
        if (current <= 1) {
          clearInterval(countdownRef.current)
          setSecret(null)
          return AUTO_HIDE_SECONDS
        }
        return current - 1
      })
    }, 1000)
    return () => clearInterval(countdownRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [secret !== null])

  function handleClose() {
    clearInterval(countdownRef.current)
    resetState()
    onClose()
  }

  async function handleSubmit(event) {
    event.preventDefault()
    // Garde anti-double-soumission : la vérification côté serveur prend
    // ~1,5 s (PBKDF2, 1 000 000 d'itérations — un coût de sécurité voulu),
    // largement de quoi laisser un second clic partir. Deux tentatives pour
    // un seul geste compteraient double dans le journal d'audit et contre
    // le rate limit de révélation.
    if (submitting) return
    setSubmitting(true)
    setError('')
    try {
      const response = await threatIntelligenceApi.revealFindingSecret(findingId, {
        password: method === 'password' ? password : '',
        totpCode: method === 'totp' ? totpCode : '',
      })
      setSecret(response.data.secret)
      setPassword('')
      setTotpCode('')
    } catch (err) {
      const status = err.response?.status
      if (status === 429) {
        setError('Trop de tentatives. Réessayez dans quelques instants.')
      } else {
        setError(err.response?.data?.detail || 'Ré-authentification invalide.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCopy() {
    if (!secret) return
    await navigator.clipboard.writeText(secret)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Modal open={open} onClose={handleClose} title="Révéler le mot de passe">
      <div className="mb-4 flex items-start gap-2 rounded-md bg-warning-subtle px-3 py-2 text-xs text-warning-strong">
        <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <p>
          Cet accès est tracé (qui, quand, depuis quelle adresse) dans le journal d’audit des
          révélations, consultable par les administrateurs.
        </p>
      </div>

      {secret === null ? (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex gap-2 rounded-md bg-ink-50 p-1 text-sm">
            <button
              type="button"
              onClick={() => setMethod('password')}
              className={`flex-1 rounded px-3 py-1.5 font-medium transition-smooth ${
                method === 'password' ? 'bg-surface shadow-sm text-ink-900' : 'text-ink-500'
              }`}
            >
              Mot de passe
            </button>
            <button
              type="button"
              onClick={() => setMethod('totp')}
              className={`flex-1 rounded px-3 py-1.5 font-medium transition-smooth ${
                method === 'totp' ? 'bg-surface shadow-sm text-ink-900' : 'text-ink-500'
              }`}
            >
              Code à 6 chiffres
            </button>
          </div>

          {method === 'password' ? (
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-ink-700">Votre mot de passe</span>
              <input
                type="password"
                autoFocus
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-md border border-ink-200 px-3 py-2 text-sm outline-none focus-visible:outline-2 focus-visible:outline-brand-600"
                autoComplete="current-password"
              />
            </label>
          ) : (
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-ink-700">Code de vérification</span>
              <input
                type="text"
                inputMode="numeric"
                autoFocus
                maxLength={6}
                value={totpCode}
                onChange={(event) => setTotpCode(event.target.value.replace(/\D/g, ''))}
                className="w-full rounded-md border border-ink-200 px-3 py-2 text-sm outline-none focus-visible:outline-2 focus-visible:outline-brand-600"
                autoComplete="one-time-code"
              />
            </label>
          )}

          {error && <p className="text-sm text-critical-strong">{error}</p>}

          {/* Le serveur met ~1,5 s à vérifier le mot de passe (PBKDF2). Sans
              message explicite, la modale paraît figée — en démonstration
              comme à l'usage, c'est le moment où l'on croit que ça a planté. */}
          {submitting && (
            <p className="text-sm text-ink-500" role="status" aria-live="polite">
              Vérification de votre identité…
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              type="button"
              onClick={handleClose}
              disabled={submitting}
            >
              Annuler
            </Button>
            <Button
              variant="primary"
              type="submit"
              icon={KeyRound}
              loading={submitting}
              disabled={submitting}
            >
              {submitting ? 'Vérification de votre identité…' : 'Vérifier et révéler'}
            </Button>
          </div>
        </form>
      ) : (
        <div className="space-y-4">
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-500">
              Secret exposé
            </p>
            <div className="flex items-center gap-2 rounded-md border border-ink-200 bg-ink-50 px-3 py-2">
              <code className="flex-1 break-all font-mono text-sm text-ink-900">{secret}</code>
              <Button variant="ghost" size="sm" icon={copied ? Check : Copy} onClick={handleCopy}>
                {copied ? 'Copié' : 'Copier'}
              </Button>
            </div>
            <p className="mt-1 text-xs text-ink-500">
              Masqué automatiquement dans {secondsLeft}s.
            </p>
          </div>
          <div className="flex justify-end">
            <Button variant="secondary" onClick={handleClose}>
              Fermer
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
