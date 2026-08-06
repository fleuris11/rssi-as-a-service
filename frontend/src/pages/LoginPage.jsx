import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const inputClass =
  'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-500'

function CredentialsStep({ onSubmitted }) {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const result = await login(email, password)
      onSubmitted(result)
    } catch {
      setError('Email ou mot de passe incorrect.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 space-y-4">
      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={inputClass}
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="password">
          Mot de passe
        </label>
        <input
          id="password"
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
        className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 disabled:opacity-50"
      >
        {submitting ? 'Connexion…' : 'Se connecter'}
      </button>
    </form>
  )
}

function TwoFactorStep({ challengeToken, onBack }) {
  const { completeTwoFactorLogin } = useAuth()
  const navigate = useNavigate()
  const [useRecoveryCode, setUseRecoveryCode] = useState(false)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await completeTwoFactorLogin(
        challengeToken,
        useRecoveryCode ? { recoveryCode: code } : { code }
      )
      navigate('/tableau-de-bord')
    } catch {
      setError('Code invalide.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 space-y-4">
      <div>
        <label className="block text-sm font-medium text-slate-700" htmlFor="totp-code">
          {useRecoveryCode
            ? 'Code de récupération'
            : "Code à 6 chiffres de votre application d'authentification"}
        </label>
        <input
          id="totp-code"
          autoComplete="one-time-code"
          autoFocus
          required
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder={useRecoveryCode ? 'XXXX-XXXX' : '123456'}
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
        className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 disabled:opacity-50"
      >
        {submitting ? 'Vérification…' : 'Vérifier'}
      </button>
      <div className="flex justify-between text-xs text-slate-500">
        <button
          type="button"
          onClick={() => {
            setUseRecoveryCode((v) => !v)
            setCode('')
            setError('')
          }}
          className="underline"
        >
          {useRecoveryCode ? "Utiliser l'application d'authentification" : 'Utiliser un code de récupération'}
        </button>
        <button type="button" onClick={onBack} className="underline">
          Retour
        </button>
      </div>
    </form>
  )
}

export default function LoginPage() {
  const navigate = useNavigate()
  const [challenge, setChallenge] = useState(null)

  function handleCredentialsSubmitted(result) {
    if (result.mfaRequired) {
      setChallenge(result.challengeToken)
    } else {
      navigate('/tableau-de-bord')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">Connexion</h1>
        {challenge ? (
          <TwoFactorStep challengeToken={challenge} onBack={() => setChallenge(null)} />
        ) : (
          <CredentialsStep onSubmitted={handleCredentialsSubmitted} />
        )}
        {!challenge && (
          <p className="mt-4 text-center text-sm text-slate-500">
            Pas encore de compte ?{' '}
            <Link to="/inscription" className="font-medium text-slate-900 underline">
              Créer un compte
            </Link>
          </p>
        )}
      </div>
    </div>
  )
}
