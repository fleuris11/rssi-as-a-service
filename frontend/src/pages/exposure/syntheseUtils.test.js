import { describe, expect, it } from 'vitest'
import { decouperSynthese } from './syntheseUtils'

// La synthèse est l'élément le plus différenciant du produit en démonstration :
// c'est là qu'un dirigeant voit l'outil raisonner pour lui. Elle arrivait sous
// forme de dix lignes de prose non composée, qui interceptaient le regard
// avant le classement des actifs. On la recompose — sans jamais réécrire le
// texte du modèle.

describe('decouperSynthese', () => {
  it('met la première phrase en tête et la dernière en priorité', () => {
    const { lead, correlations, priorite } = decouperSynthese(
      'Votre exposition se concentre sur un actif. Deux comptes reviennent dans plusieurs fuites. Votre priorité immédiate : régénérer la clé de service.'
    )

    expect(lead).toBe('Votre exposition se concentre sur un actif.')
    expect(correlations).toEqual(['Deux comptes reviennent dans plusieurs fuites.'])
    expect(priorite).toBe('Votre priorité immédiate : régénérer la clé de service.')
  })

  it('s’appuie sur la position, pas sur le mot « priorité »', () => {
    // Le prompt impose l'ordre, pas une formule. Chercher un mot-clé casserait
    // à la première reformulation du modèle.
    const { priorite } = decouperSynthese(
      'Une lecture. Une corrélation. Commencez par changer le mot de passe de ce compte.'
    )

    expect(priorite).toBe('Commencez par changer le mot de passe de ce compte.')
  })

  it('ne duplique pas une synthèse d’une seule phrase', () => {
    const { lead, correlations, priorite } = decouperSynthese('Rien de notable cette semaine.')

    expect(lead).toBe('Rien de notable cette semaine.')
    expect(correlations).toEqual([])
    expect(priorite).toBe('')
  })

  it('gère deux phrases sans rien replier', () => {
    const { lead, correlations, priorite } = decouperSynthese('Une lecture. Une action.')

    expect(lead).toBe('Une lecture.')
    expect(correlations).toEqual([])
    expect(priorite).toBe('Une action.')
  })

  it('ne coupe pas au milieu d’un nom de domaine', () => {
    // « cabinet-durand-demo.fr » contient un point suivi de lettres : une
    // découpe naïve sur « . » produirait deux phrases dont une commençant
    // par « fr ».
    const { lead } = decouperSynthese(
      'Le foyer est https://www.cabinet-durand-demo.fr avec six fuites. Ensuite, agissez.'
    )

    expect(lead).toBe('Le foyer est https://www.cabinet-durand-demo.fr avec six fuites.')
  })

  it('ne produit rien sur un texte vide plutôt qu’un bloc vide', () => {
    expect(decouperSynthese('')).toEqual({ lead: '', correlations: [], priorite: '' })
    expect(decouperSynthese(null)).toEqual({ lead: '', correlations: [], priorite: '' })
  })
})
