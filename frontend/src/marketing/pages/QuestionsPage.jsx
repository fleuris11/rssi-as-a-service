import MarketingLayout from '../components/MarketingLayout'
import { TeteDePage } from '../atomes'
import { Fin, Questions } from '../sections'
import { useSeo } from '../useSeo'
import { useApparition } from '../useApparition'

/** Toutes les questions, sur une page qu'on peut chercher au clavier. */
export default function QuestionsPage() {
  useSeo({
    title: 'Questions fréquentes',
    description:
      'Hébergement, transmission à des tiers, conservation des mots de passe retrouvés, différence avec un prestataire informatique, conformité, blocage des attaques.',
    path: '/questions',
  })
  // Les cadres de capture arrivent quand on les regarde. Rien n'est
  // masque en attendant : voir useApparition.
  useApparition()

  return (
    <MarketingLayout>
      <TeteDePage
        titre="Questions fréquentes"
        chapeau="Y compris celles dont la réponse est « non »."
      />
      <Questions fond="creuse" pleinePage />
      <Fin />
    </MarketingLayout>
  )
}
