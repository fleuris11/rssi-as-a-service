import { CheckCircle2, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { invitationApi } from '../api/endpoints'
import AuthLayout from '../components/AuthLayout'
import Button from '../components/ui/Button'

const inputClass =
  'transition-smooth mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600'

/**
 * Définition du mot de passe depuis un lien d'invitation.
 *
 * Page volontairement publique : la personne invitée n'a précisément pas
 * encore de mot de passe. C'est le jeton de l'URL qui porte l'autorisation —
 * à usage unique et à durée limitée.
 *
 * L'administrateur qui a émis ce lien n'a jamais vu ni choisi ce mot de passe,
 * et ne le verra pas.
 */
export default function InvitationPage() {
  const { token } = useParams()
  const navigate = useNavigate()
  const [state, setState] = useState('checking')
  const [invitation, setInvitation] = useState(null)
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    invitationApi
      .check(token)
      .then((response) => {
        if (cancelled) return
        setInvitation(response.data)
        setState('ready')
      })
      .catch(() => {
        if (!cancelled) setState('invalid')
      })
    return () => {
      cancelled = true
    }
  }, [token])

  async function submit(event) {
    event.preventDefault()
    setError('')
    if (password !== confirmation) {
      setError('Les deux mots de passe ne correspondent pas.')
      return
    }
    setSubmitting(true)
    try {
      await invitationApi.accept(token, password)
      setState('done')
    } catch (err) {
      const data = err.response?.data
      // Les règles de robustesse viennent du serveur : les recopier ici les
      // ferait diverger au premier ajustement.
      const message =
        data?.password?.[0] || data?.detail || 'Ce mot de passe n’a pas été accepté.'
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  if (state === 'checking') {
    return (
      <AuthLayout title="Vérification du lien">
        <div className="flex items-center gap-2 text-sm text-ink-600">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          Vérification en cours…
        </div>
      </AuthLayout>
    )
  }

  if (state === 'invalid') {
    return (
      <AuthLayout title="Lien expiré">
        <p className="text-sm text-ink-700">
          Ce lien n’est plus valable. Il a peut-être déjà servi, ou sa durée de validité est
          écoulée.
        </p>
        <p className="mt-3 text-sm text-ink-600">
          Demandez un nouveau lien à la personne qui vous a ouvert cet accès.
        </p>
        <Link
          to="/connexion"
          className="mt-4 inline-block text-sm font-medium text-brand-800 underline"
        >
          Retour à la connexion
        </Link>
      </AuthLayout>
    )
  }

  if (state === 'done') {
    return (
      <AuthLayout title="Mot de passe défini">
        <p className="flex items-start gap-2 text-sm text-ink-700">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok-strong" aria-hidden="true" />
          Votre accès est prêt. Vous pouvez maintenant vous connecter.
        </p>
        <Button className="mt-4 w-full" onClick={() => navigate('/connexion')}>
          Se connecter
        </Button>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title={
        invitation?.purpose === 'reset'
          ? 'Nouveau mot de passe'
          : 'Définissez votre mot de passe'
      }
    >
      <p className="text-sm text-ink-600">
        Pour le compte <span className="font-medium text-ink-900">{invitation?.email}</span>.
      </p>

      <form onSubmit={submit} className="mt-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-ink-700" htmlFor="password">
            Mot de passe
          </label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-ink-700" htmlFor="confirmation">
            Confirmez le mot de passe
          </label>
          <input
            id="confirmation"
            type="password"
            autoComplete="new-password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            required
            className={inputClass}
          />
        </div>

        {error && <p className="text-sm text-critical-strong">{error}</p>}

        <Button type="submit" className="w-full" loading={submitting}>
          Valider
        </Button>
      </form>
    </AuthLayout>
  )
}
