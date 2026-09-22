import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { monitoringApi } from '../api/endpoints'

/**
 * L'ÉTAT DE SURVEILLANCE, pour le bandeau qui coiffe toute l'application.
 *
 * Le bandeau est présent sur chaque écran : c'est le signal public du pupitre,
 * et un signal qui n'apparaît que sur une page n'est pas un signal. Mais un
 * appel réseau par écran serait une dépense inutile, contraire à la sobriété
 * que le projet s'impose.
 *
 * D'où ce contexte : **un seul appel par session**, celui de la surveillance,
 * qui est le plus léger. Les écrans qui disposent déjà d'une lecture plus
 * riche — le tableau de bord, qui charge le score d'exposition — la
 * REMPLACENT par `preciser()`. Le bandeau affiche donc toujours ce qu'on sait
 * de mieux, sans jamais redemander.
 *
 * En cas d'échec, le bandeau reste muet plutôt que de mentir : pas de score,
 * pas de cran, la phrase dit simplement que le relevé n'est pas disponible.
 * Un produit de surveillance qui affiche « tout va bien » quand il n'a pas pu
 * regarder est pire qu'un produit qui se tait.
 */

const Contexte = createContext(null)

function pireEtatDeSurveillance(lignes) {
  let pire = 'calme'
  for (const ligne of lignes) {
    if (ligne.open_alerts?.some((a) => a.severity === 'critical')) return 'critique'
    if (ligne.open_alerts?.length > 0) pire = 'preoccupant'
    for (const controle of Object.values(ligne.latest_checks || {})) {
      if (controle?.status === 'critical') return 'critique'
      if (controle?.status === 'warning' && pire === 'calme') pire = 'surveille'
    }
  }
  return pire
}

function phrasePour(niveau, nombreActifs) {
  if (nombreActifs === 0) {
    return 'Aucun actif déclaré : il n’y a encore rien à surveiller.'
  }
  return {
    calme: `Rien à signaler sur vos ${nombreActifs} actifs surveillés.`,
    surveille: 'Un contrôle demande un œil cette semaine.',
    preoccupant: 'Une alerte est ouverte et attend une décision.',
    critique: 'Une action est à mener aujourd’hui.',
  }[niveau]
}

export function EtatSurveillanceProvider({ children }) {
  const [etat, setEtat] = useState({ chargement: true })

  const preciser = useCallback((valeurs) => {
    setEtat((precedent) => ({ ...precedent, ...valeurs, chargement: false }))
  }, [])

  useEffect(() => {
    let annule = false
    monitoringApi
      .dashboard()
      .then((reponse) => {
        if (annule) return
        const lignes = reponse.data?.results || reponse.data || []
        const niveau = pireEtatDeSurveillance(lignes)
        setEtat({
          chargement: false,
          niveau,
          phrase: phrasePour(niveau, lignes.length),
          action:
            lignes.length === 0
              ? { vers: '/surveillance', libelle: 'Déclarer un actif' }
              : { vers: '/tableau-de-bord', libelle: 'Voir le détail' },
        })
      })
      .catch(() => {
        if (annule) return
        // Muet plutôt que rassurant : un relevé manquant n'est pas un relevé
        // calme.
        setEtat({
          chargement: false,
          niveau: null,
          phrase: 'Le relevé du jour n’a pas pu être chargé.',
        })
      })
    return () => {
      annule = true
    }
  }, [])

  const valeur = useMemo(() => ({ ...etat, preciser }), [etat, preciser])
  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>
}

export function useEtatSurveillance() {
  return useContext(Contexte) ?? { chargement: true, preciser: () => {} }
}
