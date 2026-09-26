import { Donnees, Fin, Questions } from '../sections'
import MarketingLayout from '../components/MarketingLayout'
import { TeteDePage } from '../atomes'
import { FAQ } from '../content'
import { useSeo } from '../useSeo'
import { useApparition } from '../useApparition'

/**
 * Vos données et ce que nous en faisons.
 *
 * Les six engagements de traitement, puis les questions de la FAQ qui portent
 * précisément là-dessus : hébergement, transmission à des tiers, durée de
 * conservation. Elles restent AUSSI dans /questions — la même réponse à deux
 * endroits vaut mieux qu'un visiteur qui ne la trouve pas.
 */
const QUESTIONS_DONNEES = FAQ.items.filter((item) =>
  /hébergées|services tiers|conservez-vous/i.test(item.question)
)

export default function SecuriteProduitPage() {
  useSeo({
    title: 'Vos données et ce que nous en faisons',
    description:
      'Cloisonnement entre clients, chiffrement des mots de passe retrouvés, consultation tracée, effacement à 90 jours, pseudonymisation avant analyse externe.',
    path: '/securite-du-produit',
  })
  // Les cadres de capture arrivent quand on les regarde. Rien n'est
  // masque en attendant : voir useApparition.
  useApparition()

  return (
    <MarketingLayout>
      <TeteDePage
        titre="Vous nous confiez des informations sur vos vulnérabilités"
        chapeau="Voici précisément comment elles sont traitées, et ce que nous nous interdisons."
      />
      <Donnees entete={false} />
      <Questions
        items={QUESTIONS_DONNEES}
        titre="Les questions qu’on nous pose là-dessus"
        chapeau="Hébergement, transmission à des tiers, durée de conservation : les trois mêmes, toujours."
        fond="creuse"
      />
      <Fin />
    </MarketingLayout>
  )
}
