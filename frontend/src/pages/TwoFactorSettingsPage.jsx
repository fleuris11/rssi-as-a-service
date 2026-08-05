import { useCallback, useEffect, useState } from 'react'
import { twoFactorApi } from '../api/endpoints'

const inputClass =
  'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-500'

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
        <p className="text-sm text-slate-600">
          La double authentification ajoute une vérification par code à chaque connexion, en plus
          de votre mot de passe.
        </p>
        {error && (
          <p className="mt-2 text-sm text-red-600" role="alert">
            {error}
          </p>
        )}
        <button
          type="button"
          onClick={handleStart}
          disabled={submitting}
          className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 disabled:opacity-50"
        >
          {submitting ? 'Préparation…' : 'Activer la double authentification'}
        </button>
      </div>
    )
  }

  if (step === 'confirm') {
    return (
      <form onSubmit={handleConfirm} className="space-y-4">
        <p className="text-sm text-slate-600">
          Scannez ce QR code avec votre application d’authentification (Google Authenticator, Authy…),
          puis saisissez le code à 6 chiffres qu’elle affiche pour confirmer.
        </p>
        <img
          src={setupData.qr_code}
          alt="QR code d’enrôlement de la double authentification"
          className="h-40 w-40 rounded-md border border-slate-200"
        />
        <details className="text-xs text-slate-500">
          <summary className="cursor-pointer">Saisir la clé manuellement</summary>
          <code className="mt-1 block break-all rounded bg-slate-50 p-2">{setupData.secret}</code>
        </details>
        <div>
          <label className="block text-sm font-medium text-slate-700" htmlFor="confirm-code">
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
          <p className="text-sm text-red-600" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 disabled:opacity-50"
        >
          {submitting ? 'Vérification…' : 'Confirmer'}
        </button>
      </form>
    )
  }

  // step === 'recovery-codes'
  return (
    <div className="space-y-4">
      <p className="text-sm font-medium text-emerald-700">Double authentification activée.</p>
      <p className="text-sm text-slate-600">
        Notez ces codes de récupération dans un endroit sûr : chacun permet une seule connexion si
        vous perdez l’accès à votre application d’authentification. Ils ne seront plus jamais
        affichés.
      </p>
      <ul className="grid grid-cols-2 gap-2 rounded-md bg-slate-50 p-4 font-mono text-sm">
        {recoveryCodes.map((recoveryCode) => (
          <li key={recoveryCode}>{recoveryCode}</li>
        ))}
      </ul>
      <button
        type="button"
        onClick={onEnabled}
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
      >
        J’ai noté mes codes de récupération
      </button>
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
      <p className="text-sm font-medium text-emerald-700">Double authentification activée.</p>
      {!confirming ? (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="mt-4 rounded-md border border-red-200 px-4 py-2 text-sm text-red-600 hover:border-red-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600"
        >
          Désactiver la double authentification
        </button>
      ) : (
        <form onSubmit={handleSubmit} className="mt-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-slate-700" htmlFor="disable-password">
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
            <p className="text-sm text-red-600" role="alert">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600 disabled:opacity-50"
          >
            {submitting ? 'Désactivation…' : 'Confirmer la désactivation'}
          </button>
        </form>
      )}
    </div>
  )
}

export default function TwoFactorSettingsPage() {
  const [enabled, setEnabled] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const response = await twoFactorApi.status()
      setEnabled(response.data.enabled)
    } catch {
      setLoadError('Impossible de charger le statut de la double authentification.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Sécurité du compte</h1>
        <p className="mt-1 text-sm text-slate-500">
          Double authentification (TOTP) — recommandée pour protéger votre compte.
        </p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        {loading && <p className="text-slate-500">Chargement…</p>}
        {loadError && <p className="text-sm text-red-600">{loadError}</p>}
        {!loading && !loadError && enabled === false && <EnrollmentFlow onEnabled={load} />}
        {!loading && !loadError && enabled === true && <DisableFlow onDisabled={load} />}
      </div>
    </div>
  )
}
