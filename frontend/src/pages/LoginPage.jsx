import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import Button from '../components/ui/Button'
import Champ from '../components/ui/Champ'
import { landingPathFor, useAuth } from '../context/AuthContext'

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
      <Champ
        label="Email"
        type="email"
        autoComplete="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <Champ
        label="Mot de passe"
        type="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      {error && (
        <p
          className="flex items-start gap-1.5 rounded-md bg-critical-subtle px-3 py-2 text-sm text-critical-strong"
          role="alert"
        >
          <span aria-hidden="true">▲</span>
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
      const user = await completeTwoFactorLogin(
        challengeToken,
        useRecoveryCode ? { recoveryCode: code } : { code }
      )
      navigate(landingPathFor(user))
    } catch {
      setError('Code invalide.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 space-y-4">
      <div>
        <Champ
          label={useRecoveryCode ? 'Code de récupération' : 'Code à six chiffres'}
          aide={
            useRecoveryCode
              ? 'L’un des codes notés lors de l’activation. Chacun ne sert qu’une fois.'
              : 'Celui qu’affiche votre application d’authentification en ce moment.'
          }
          autoComplete="one-time-code"
          autoFocus
          required
          inputMode={useRecoveryCode ? 'text' : 'numeric'}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder={useRecoveryCode ? 'XXXX-XXXX' : '123456'}
        />
      </div>
      {error && (
        <p
          className="flex items-start gap-1.5 rounded-md bg-critical-subtle px-3 py-2 text-sm text-critical-strong"
          role="alert"
        >
          <span aria-hidden="true">▲</span>
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
      // Chacun arrive dans SON espace : un administrateur plateforme sans
      // entreprise n'a rien à faire sur un tableau de bord client.
      navigate(landingPathFor(result.user))
    }
  }

  return (
    <AuthLayout>
      <h1 className="t-display">{challenge ? 'Vérification en deux étapes' : 'Connexion'}</h1>
      {!challenge && (
        <p className="t-meta mt-2">Accès à votre espace de surveillance.</p>
      )}
      {challenge ? (
        <TwoFactorStep challengeToken={challenge} onBack={() => setChallenge(null)} />
      ) : (
        <CredentialsStep onSubmitted={handleCredentialsSubmitted} />
      )}
      {!challenge && (
        <div className="mt-6 space-y-2 border-t border-ink-200 pt-5 text-sm text-ink-600">
          <p>
            <Link to="/mot-de-passe-oublie" className="text-brand-600 underline underline-offset-4">
              Mot de passe oublié ?
            </Link>
          </p>
          <p>
            Pas encore de compte ?{' '}
            <Link to="/inscription" className="text-brand-600 underline underline-offset-4">
              Créer un compte
            </Link>
          </p>
        </div>
      )}
    </AuthLayout>
  )
}
