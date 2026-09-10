import { useCallback } from 'react'
import { authApi } from '../api/endpoints'
import { useAuth } from './AuthContext'

/**
 * Le profil d'affichage de la personne connectée (V2-5, ADR-031).
 *
 * Pas de contexte supplémentaire : le profil vit sur l'utilisateur, et
 * `AuthContext` porte déjà l'utilisateur. Un second fournisseur créerait une
 * deuxième source de vérité pour la même information, et c'est ainsi que deux
 * écrans finissent par ne pas être d'accord sur le profil courant.
 *
 * **Ce que ce réglage ne fait pas** : il ne change aucun droit, et il ne
 * change aucune donnée. Le serveur renvoie exactement la même chose dans les
 * deux profils — c'est vérifié côté backend par un test qui compare les deux
 * réponses octet pour octet. Ce qui change ici est la mise en page : ce qu'on
 * déplie par défaut, et quel mot on met en premier.
 */
export const EXECUTIVE = 'executive'
export const TECHNICAL = 'technical'

export function useDisplayProfile() {
  const { user, setUser } = useAuth()
  const profile = user?.display_profile || EXECUTIVE

  const setProfile = useCallback(
    async (next) => {
      if (next === profile) return
      // Optimiste : le basculement doit être instantané, c'est un réglage
      // d'affichage. En cas d'échec réseau on revient à l'état précédent
      // plutôt que de laisser l'écran mentir sur ce qui est enregistré.
      setUser((current) => (current ? { ...current, display_profile: next } : current))
      try {
        const response = await authApi.setDisplayProfile(next)
        setUser(response.data)
      } catch {
        setUser((current) => (current ? { ...current, display_profile: profile } : current))
      }
    },
    [profile, setUser]
  )

  return {
    profile,
    isExecutive: profile === EXECUTIVE,
    isTechnical: profile === TECHNICAL,
    setProfile,
  }
}
