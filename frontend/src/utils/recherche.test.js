import { describe, expect, it } from 'vitest'
import { filtrerParTexte, normaliser } from './recherche'

describe('recherche', () => {
  it('ignore la casse et les accents', () => {
    expect(normaliser('  Sécurité ÉLEVÉE ')).toBe('securite elevee')
  })

  it('trouve dans n’importe lequel des champs désignés', () => {
    const lignes = [
      { client: 'Cabinet Durand', sujet: 'ISO 27001' },
      { client: 'Menuiserie Lambert', sujet: 'Surveillance continue' },
    ]

    expect(filtrerParTexte(lignes, 'durand', (l) => [l.client, l.sujet])).toHaveLength(1)
    expect(filtrerParTexte(lignes, 'iso', (l) => [l.client, l.sujet])).toHaveLength(1)
  })

  it('« securite » trouve « sécurité »', () => {
    const lignes = [{ titre: 'Politique de sécurité' }]
    expect(filtrerParTexte(lignes, 'securite', (l) => [l.titre])).toHaveLength(1)
  })

  it('une recherche vide garde tout', () => {
    const lignes = [{ a: 1 }, { a: 2 }]
    expect(filtrerParTexte(lignes, '   ', (l) => [l.a])).toBe(lignes)
  })

  it('un champ absent ne fait pas planter la recherche', () => {
    expect(filtrerParTexte([{ titre: null }], 'x', (l) => [l.titre, undefined])).toEqual([])
  })
})
