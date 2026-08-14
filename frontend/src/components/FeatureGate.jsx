import { Lock } from 'lucide-react'
import { useEntitlements } from '../context/EntitlementsContext'
import Tooltip from './ui/Tooltip'

/**
 * Affiche une fonctionnalité hors offre en **désactivé**, jamais masquée.
 *
 * Choix produit : masquer laisserait croire que le produit ne sait pas le
 * faire, ce qui est à la fois faux et commercialement contre-productif. Le
 * client voit que la capacité existe, et quelle offre la lui donnerait.
 *
 * La garde réelle reste côté serveur : ce composant est un affichage, pas une
 * sécurité (les tests d'étanchéité vérifient qu'un appel direct à l'API est
 * refusé indépendamment de ce qu'affiche l'interface).
 */
export default function FeatureGate({ feature, children, mode = 'disable' }) {
  const { hasFeature, featureInfo } = useEntitlements()

  if (hasFeature(feature)) return children

  const info = featureInfo(feature)
  const requiredPlan = info?.required_plan
  const message = requiredPlan
    ? `Compris à partir de l’offre ${requiredPlan}.`
    : 'Non compris dans votre offre.'

  if (mode === 'badge') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-ink-100 px-2 py-0.5 text-xs font-medium text-ink-600">
        <Lock className="size-3" aria-hidden="true" />
        {requiredPlan || 'Hors offre'}
      </span>
    )
  }

  return (
    <Tooltip content={`${info?.teaser || ''} ${message}`.trim()}>
      <div
        // aria-disabled plutôt que de retirer l'élément : un lecteur d'écran
        // doit annoncer que la fonctionnalité existe et qu'elle est
        // indisponible, pas l'ignorer.
        aria-disabled="true"
        data-feature-locked={feature}
        className="pointer-events-none relative select-none opacity-55 grayscale"
      >
        {children}
        <span className="sr-only">{message}</span>
      </div>
    </Tooltip>
  )
}

/** Encart explicite, pour une section entière plutôt qu'un bouton. */
export function FeatureLockedNotice({ feature }) {
  const { hasFeature, featureInfo } = useEntitlements()
  if (hasFeature(feature)) return null

  const info = featureInfo(feature)
  return (
    <div className="flex items-start gap-3 rounded-lg border border-ink-200 bg-ink-50/70 px-4 py-3">
      <Lock className="mt-0.5 size-4 shrink-0 text-ink-500" aria-hidden="true" />
      <div>
        <p className="text-sm font-medium text-ink-800">{info?.label}</p>
        {info?.teaser && <p className="mt-0.5 text-sm text-ink-600">{info.teaser}</p>}
        {info?.required_plan && (
          <p className="mt-1.5 text-sm text-brand-800">
            Compris à partir de l’offre {info.required_plan}.
          </p>
        )}
      </div>
    </div>
  )
}
