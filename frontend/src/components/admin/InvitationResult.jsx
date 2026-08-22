import { Check, Copy, Mail, MailX } from 'lucide-react'
import { useState } from 'react'
import Button from '../ui/Button'

/**
 * Ce qu'on montre après avoir invité quelqu'un.
 *
 * Le lien est affiché parce qu'aucun serveur d'envoi n'est forcément
 * configuré : sans lui, la console pourrait créer des comptes sans pouvoir
 * les remettre à personne. Quand l'envoi fonctionne, on le dit — et le lien
 * reste affiché, un email peut se perdre.
 *
 * Ce qui n'est JAMAIS affiché : un mot de passe. L'administrateur ne le
 * choisit pas, ne le lit pas et ne le transmet pas.
 */
export default function InvitationResult({ invitation }) {
  const [copied, setCopied] = useState(false)
  if (!invitation) return null

  async function copy() {
    await navigator.clipboard.writeText(invitation.invitation_url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2500)
  }

  return (
    <div className="rounded-lg border border-brand-200 bg-brand-50/60 px-4 py-3">
      <p className="flex items-center gap-2 text-sm font-medium text-ink-900">
        {invitation.email_sent ? (
          <>
            <Mail className="size-4 text-brand-700" aria-hidden="true" />
            Lien envoyé à {invitation.invitation_email}
          </>
        ) : (
          <>
            <MailX className="size-4 text-ink-500" aria-hidden="true" />
            Lien à transmettre à {invitation.invitation_email}
          </>
        )}
      </p>
      <p className="mt-1 text-sm text-ink-600">
        {invitation.email_sent
          ? 'Un email a été envoyé. Le lien ci-dessous reste utilisable si besoin.'
          : 'Aucun serveur d’envoi n’est configuré : transmettez ce lien par le canal de votre choix.'}{' '}
        Il est valable {invitation.expires_in_hours} heures et ne fonctionne qu’une fois.
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded-md bg-white px-3 py-2 text-xs text-ink-700 ring-1 ring-ink-200">
          {invitation.invitation_url}
        </code>
        <Button
          variant="secondary"
          size="sm"
          icon={copied ? Check : Copy}
          onClick={copy}
        >
          {copied ? 'Copié' : 'Copier'}
        </Button>
      </div>
    </div>
  )
}
