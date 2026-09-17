import { describe, expect, it } from 'vitest'
import { NAV_ITEMS, fonctionnalitesRetirees, navigationPourProfil } from './navigation'

/**
 * F1 : l'entrée « Formation » est une fonctionnalité d'offre comme les autres,
 * et suit donc la règle d'ADR-038 — désactivée hors offre, masquée quand elle
 * a été retirée à ce client.
 */
describe('navigation — Formation', () => {
  const formation = NAV_ITEMS.find((item) => item.to === '/formation')

  it('porte la clé du registre', () => {
    expect(formation).toBeDefined()
    expect(formation.fonctionnalite).toBe('training')
  })

  it('n’est pas un écran technique : elle reste en vue en profil dirigeant', () => {
    // Former ses salariés est une décision de dirigeant, pas une tâche
    // d'administrateur système.
    const { principale } = navigationPourProfil(false)
    expect(principale.map((item) => item.to)).toContain('/formation')
  })

  it('disparaît quand elle a été retirée à ce client', () => {
    const retirees = fonctionnalitesRetirees([
      { key: 'training', included: false, source: 'override' },
    ])
    const { principale, techniques } = navigationPourProfil(false, retirees)
    expect([...principale, ...techniques].map((item) => item.to)).not.toContain('/formation')
  })

  it('reste au menu quand elle est seulement hors offre', () => {
    // Hors offre, l'élément reste affiché et désactivé : c'est un levier
    // commercial, le client doit savoir que le produit sait le faire.
    const retirees = fonctionnalitesRetirees([
      { key: 'training', included: false, source: 'plan' },
    ])
    const { principale } = navigationPourProfil(false, retirees)
    expect(principale.map((item) => item.to)).toContain('/formation')
  })
})
