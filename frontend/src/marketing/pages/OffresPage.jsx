import MarketingLayout from '../components/MarketingLayout'
import { TeteDePage } from '../atomes'
import { FAQ } from '../content'
import { Fin, Offres, Questions } from '../sections'
import { useSeo } from '../useSeo'

/**
 * Les offres.
 *
 * La grille vient de l'API (`GET /api/v1/billing/plans/`) : modifier une offre
 * depuis l'administration doit se voir sans redéploiement. Le contenu statique
 * n'est qu'un repli, de forme identique à celle de l'API.
 */
const QUESTIONS_OFFRE = FAQ.items.filter((item) =>
  /prestataire informatique|installer|conformité|Bloquez-vous/i.test(item.question)
)

export default function OffresPage() {
  useSeo({
    title: 'Offres',
    description:
      'Veille, Pilotage, Souverain : ce que contient chaque offre, ce qui est compté, et les montants indicatifs.',
    path: '/offres',
  })

  return (
    <MarketingLayout>
      <TeteDePage
        titre="Trois offres, comparées colonne par colonne"
        chapeau="Les montants sont indicatifs et servent à situer un ordre de grandeur. La tarification définitive est établie au moment du devis."
      />
      <Offres />
      <Questions items={QUESTIONS_OFFRE} titre="Avant de comparer" fond="creuse" />
      <Fin />
    </MarketingLayout>
  )
}
