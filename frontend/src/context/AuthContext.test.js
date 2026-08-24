import { describe, expect, it } from 'vitest'
import { landingPathFor } from './AuthContext'

// Régression coûteuse et déroutante : un administrateur plateforme était
// envoyé sur le tableau de bord CLIENT après sa connexion. N'étant membre
// d'aucune entreprise — par construction (ADR-014, ADR-022) — il tombait sur
// « Aucune entreprise associée à votre compte », un écran vide sans le
// moindre lien vers sa propre console. Le produit paraissait cassé alors que
// tout fonctionnait ; seule l'URL exacte permettait d'y accéder.

describe('landingPathFor', () => {
  it('envoie un administrateur sans entreprise dans sa console', () => {
    expect(landingPathFor({ is_staff: true, memberships: [] })).toBe('/admin/plateforme')
  })

  it('laisse un administrateur membre d’une entreprise sur son tableau de bord', () => {
    // Il y va pour travailler ; la console reste à un clic dans son en-tête.
    expect(
      landingPathFor({ is_staff: true, memberships: [{ tenant_id: 'abc' }] })
    ).toBe('/tableau-de-bord')
  })

  it('envoie un client sur son tableau de bord', () => {
    expect(
      landingPathFor({ is_staff: false, memberships: [{ tenant_id: 'abc' }] })
    ).toBe('/tableau-de-bord')
  })

  it('ne renvoie jamais un non-administrateur vers la console', () => {
    // Même sans entreprise : la console lui serait refusée, et le rediriger
    // là-bas ne ferait que déplacer l'impasse.
    expect(landingPathFor({ is_staff: false, memberships: [] })).toBe('/tableau-de-bord')
  })

  it('reste sûr quand l’utilisateur n’est pas encore chargé', () => {
    expect(landingPathFor(null)).toBe('/tableau-de-bord')
    expect(landingPathFor(undefined)).toBe('/tableau-de-bord')
    expect(landingPathFor({})).toBe('/tableau-de-bord')
  })
})
