import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import Button from '../components/ui/Button'
import { useAuth } from '../context/AuthContext'

const inputClass =
  'transition-smooth mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600'

/**
 * Traduit un échec de connexion en message utile.
 *
 * Afficher « mot de passe incorrect » quel que soit le motif envoie
 * l'utilisateur retaper son mot de passe — ce qui, en cas de verrouillage,
 * prolonge le verrouillage. Le 401 reste volontairement générique (ne pas
 * révéler si un compte existe) ; les autres cas ont chacun une cause que
 * l'utilisateur peut lever lui-même.
 */
export function loginErrorMessage(error) {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail

  if (status === 429) {
    return detail || 'Trop de tentatives. Réessayez dans quelques instants.'
  }
  if (status === 403) {
    return 'Session précédente incohérente. Rechargez la page et réessayez.'
  }
  if (status === undefined) {
    return 'Serveur injoignable. Vérifiez que le service est démarré.'
  }
  return 'Email ou mot de passe incorrect.'
}

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
    } catch (err) {
      setError(loginErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 space-y-4">
      <div>
        <label className="block text-sm font-medium text-ink-700" htmlFor="email">
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
        <label className="block text-sm font-medium text-ink-700" htmlFor="password">
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
        <p className="text-sm text-critical-strong" role="alert">
          {error}
        </p>
      )}
      <Button type="submit" variant="primary" loading={submitting} className="w-full">
        Se connecter
      </Button>
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
        <label className="block text-sm font-medium text-ink-700" htmlFor="totp-code">
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
        <p className="text-sm text-critical-strong" role="alert">
          {error}
        </p>
      )}
      <Button type="submit" variant="primary" loading={submitting} className="w-full">
        Vérifier
      </Button>
      <div className="flex justify-between text-xs text-ink-500">
        <button
          type="button"
          onClick={() => {
            setUseRecoveryCode((v) => !v)
            setCode('')
            setError('')
          }}
          className="transition-smooth underline hover:text-brand-700"
        >
          {useRecoveryCode ? "Utiliser l'application d'authentification" : 'Utiliser un code de récupération'}
        </button>
        <button type="button" onClick={onBack} className="transition-smooth underline hover:text-brand-700">
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
    <AuthLayout>
      <h1 className="font-display text-2xl font-semibold text-ink-900">
        {challenge ? 'Vérification en deux étapes' : 'Connexion'}
      </h1>
      {challenge ? (
        <TwoFactorStep challengeToken={challenge} onBack={() => setChallenge(null)} />
      ) : (
        <CredentialsStep onSubmitted={handleCredentialsSubmitted} />
      )}
      {!challenge && (
        <p className="mt-4 text-center text-sm text-ink-500">
          Pas encore de compte ?{' '}
          <Link to="/inscription" className="font-medium text-brand-700 underline">
            Créer un compte
          </Link>
        </p>
      )}
    </AuthLayout>
  )
}
