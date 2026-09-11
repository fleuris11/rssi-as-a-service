import { describe, expect, it } from 'vitest'
import { NAV_ITEMS, pageTitleFor } from './navigation'

// La page « Mes demandes » existait, était routée, ses appels d'API
// fonctionnaient — et elle n'était dans AUCUN menu. Le seul lien y menant
// était enfoui dans le panneau « hors offre » de `FeatureGate`, c'est-à-dire
// visible uniquement par un client qui butait sur une fonctionnalité non
// comprise dans son offre.
//
// Un client qui avait déposé une demande n'avait donc aucun moyen d'en
// retrouver l'état. Une demande sans retour est pire que pas de bouton :
// elle fait croire à un abandon.

describe('navigation', () => {
  it('donne un accès direct à « Mes demandes »', () => {
    const cibles = NAV_ITEMS.map((item) => item.to)

    expect(cibles).toContain('/mes-demandes')
  })

  it('chaque entrée porte un libellé et une icône', () => {
    for (const item of NAV_ITEMS) {
      expect(item.label, `entrée sans libellé : ${item.to}`).toBeTruthy()
      expect(item.icon, `entrée sans icône : ${item.to}`).toBeTruthy()
    }
  })

  it('la barre du haut sait nommer la page des demandes', () => {
    expect(pageTitleFor('/mes-demandes')).toBe('Mes demandes')
  })
})
