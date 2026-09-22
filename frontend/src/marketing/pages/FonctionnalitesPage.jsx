import MarketingLayout from '../components/MarketingLayout'
import { TeteDePage } from '../atomes'
import {
  Alertes,
  Diagnostic,
  Differences,
  EgalementLivre,
  Fin,
  Fonctionnement,
} from '../sections'
import { useSeo } from '../useSeo'

/**
 * Le détail de ce que fait le produit.
 *
 * Cette page reçoit ce que l'accueil ne garde plus : les quatre différences,
 * les quatre envois, les quatre étapes du diagnostic, le fonctionnement en
 * quatre temps et les trois volets livrés en plus. **Rien n'a été supprimé de
 * la vitrine** — tout a été déplacé ici (inventaire : docs/design.md).
 */
export default function FonctionnalitesPage() {
  useSeo({
    title: 'Ce que fait le produit',
    description:
      'Signaux avant-coureurs, traduction en langage de direction, diagnostic ANSSI, météo quotidienne, formation des salariés : le détail de chaque fonctionnalité.',
    path: '/fonctionnalites',
  })

  return (
    <MarketingLayout>
      <TeteDePage
        titre="Ce que le produit surveille, et ce qu’il en fait"
        chapeau="Chaque affirmation de cette page correspond à une fonctionnalité qui existe dans le produit. Ce qui n’existe pas n’y est pas écrit."
      />
      <Differences />
      <Alertes />
      <Diagnostic />
      <Fonctionnement />
      <EgalementLivre />
      <Fin />
    </MarketingLayout>
  )
}
