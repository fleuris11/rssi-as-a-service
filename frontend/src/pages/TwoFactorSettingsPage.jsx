import { useCallback, useEffect, useState } from 'react'
import { twoFactorApi } from '../api/endpoints'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { SkeletonText } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'

const inputClass =
  'transition-smooth mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600'

function EnrollmentFlow({ onEnabled }) {
  const [step, setStep] = useState('start') // start | confirm | recovery-codes
  const [setupData, setSetupData] = useState(null)
  const [code, setCode] = useState('')
  const [recoveryCodes, setRecoveryCodes] = useState([])
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleStart() {
    setError('')
    setSubmitting(true)
    try {
      const response = await twoFactorApi.setup()
      setSetupData(response.data)
      setStep('confirm')
    } catch {
      setError("Impossible de démarrer l'activation.")
    } finally {
      setSubmitting(false)
    }
  }

  async function handleConfirm(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const response = await twoFactorApi.confirm(code)
      setRecoveryCodes(response.data.recovery_codes)
      setStep('recovery-codes')
    } catch {
      setError('Code invalide. Vérifiez votre application et réessayez.')
    } finally {
      setSubmitting(false)
    }
  }

  if (step === 'start') {
    return (
      <div>
        <p className="text-sm text-ink-600">
          La double authentification ajoute une vérification par code à chaque connexion, en plus
          de votre mot de passe.
        </p>
        {error && (
          <p className="mt-2 text-sm text-critical-strong" role="alert">
            {error}
          </p>
        )}
        <Button variant="primary" loading={submitting} onClick={handleStart} className="mt-4">
          Activer la double authentification
        </Button>
      </div>
    )
  }

  if (step === 'confirm') {
    return (
      <form onSubmit={handleConfirm} className="space-y-4">
        <p className="text-sm text-ink-600">
          Scannez ce QR code avec votre application d’authentification (Google Authenticator, Authy…),
          puis saisissez le code à 6 chiffres qu’elle affiche pour confirmer.
        </p>
        <img
          src={setupData.qr_code}
          alt="QR code d’enrôlement de la double authentification"
          className="h-40 w-40 rounded-md border border-ink-200"
        />
        <details className="text-xs text-ink-500">
          <summary className="cursor-pointer">Saisir la clé manuellement</summary>
          <code className="mt-1 block break-all rounded bg-ink-50 p-2">{setupData.secret}</code>
        </details>
        <div>
          <label className="block text-sm font-medium text-ink-700" htmlFor="confirm-code">
            Code à 6 chiffres
          </label>
          <input
            id="confirm-code"
            autoComplete="one-time-code"
            required
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="123456"
            className={inputClass}
          />
        </div>
        {error && (
          <p className="text-sm text-critical-strong" role="alert">
            {error}
          </p>
        )}
        <Button type="submit" variant="primary" loading={submitting}>
          Confirmer
        </Button>
      </form>
    )
  }

  // step === 'recovery-codes'
  return (
    <div className="space-y-4">
      <p className="text-sm font-medium text-ok-strong">Double authentification activée.</p>
      <p className="text-sm text-ink-600">
        Notez ces codes de récupération dans un endroit sûr : chacun permet une seule connexion si
        vous perdez l’accès à votre application d’authentification. Ils ne seront plus jamais
        affichés.
      </p>
      <ul className="grid grid-cols-2 gap-2 rounded-md bg-ink-50 p-4 font-mono text-sm">
        {recoveryCodes.map((recoveryCode) => (
          <li key={recoveryCode}>{recoveryCode}</li>
        ))}
      </ul>
      <Button variant="primary" onClick={onEnabled}>
        J’ai noté mes codes de récupération
      </Button>
    </div>
  )
}

function DisableFlow({ onDisabled }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [confirming, setConfirming] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await twoFactorApi.disable(password)
      onDisabled()
    } catch {
      setError('Mot de passe incorrect.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <p className="text-sm font-medium text-ok-strong">Double authentification activée.</p>
      {!confirming ? (
        <Button variant="danger" onClick={() => setConfirming(true)} className="mt-4">
          Désactiver la double authentification
        </Button>
      ) : (
        <form onSubmit={handleSubmit} className="mt-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-ink-700" htmlFor="disable-password">
              Confirmez avec votre mot de passe
            </label>
            <input
              id="disable-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
          </div>
          {error && (
            <p className="text-sm text-critical-strong" role="alert">
              {error}
            </p>
          )}
          <Button type="submit" variant="danger" loading={submitting}>
            Confirmer la désactivation
          </Button>
        </form>
      )}
    </div>
  )
}

export default function TwoFactorSettingsPage() {
  const { showToast } = useToast()
  const [enabled, setEnabled] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const response = await twoFactorApi.status()
      setEnabled(response.data.enabled)
    } catch {
      showToast({ type: 'error', message: 'Impossible de charger le statut de la double authentification.' })
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Sécurité du compte</h1>
        <p className="mt-1 text-sm text-ink-500">
          Double authentification (TOTP) — recommandée pour protéger votre compte.
        </p>
      </div>

      <Card>
        {loading && <SkeletonText lines={2} />}
        {!loading && enabled === false && <EnrollmentFlow onEnabled={load} />}
        {!loading && enabled === true && <DisableFlow onDisabled={load} />}
      </Card>
    </div>
  )
}
