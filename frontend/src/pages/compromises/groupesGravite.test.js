import { describe, expect, it } from 'vitest'
import { grouperParGravite, libelleGroupe, teinteGravite } from './groupesGravite'

const fuite = (id, severity) => ({ id, severity })

describe('grouperParGravite', () => {
  it('classe par gravité, quel que soit l’ordre d’arrivée', () => {
    // Cas réel observé sur le jeu de démonstration : une fuite critique
    // arrivait après quatre fuites élevées.
    const groupes = grouperParGravite([
      fuite(1, 'high'),
      fuite(2, 'high'),
      fuite(3, 'critical'),
      fuite(4, 'attention'),
      fuite(5, 'high'),
    ])

    expect(groupes.map((g) => g.severite)).toEqual(['critical', 'high', 'attention'])
    expect(groupes[0].findings.map((f) => f.id)).toEqual([3])
    expect(groupes[1].findings.map((f) => f.id)).toEqual([1, 2, 5])
  })

  it('conserve l’ordre du serveur à l’intérieur d’un groupe', () => {
    // Le serveur trie déjà par date de fuite décroissante : le regroupement
    // ne doit pas défaire ce classement.
    const groupes = grouperParGravite([fuite(9, 'high'), fuite(3, 'high'), fuite(7, 'high')])
    expect(groupes[0].findings.map((f) => f.id)).toEqual([9, 3, 7])
  })

  it('n’affiche pas un groupe vide', () => {
    const groupes = grouperParGravite([fuite(1, 'critical')])
    expect(groupes).toHaveLength(1)
  })

  it('ne perd JAMAIS une gravité inconnue', () => {
    // Faire disparaître une fuite parce que le front ne connaît pas encore sa
    // gravité serait le pire défaut possible sur cette page : elle existe
    // précisément pour qu'aucune fuite ne passe inaperçue.
    const groupes = grouperParGravite([fuite(1, 'critical'), fuite(2, 'inedite')])

    expect(groupes.map((g) => g.severite)).toEqual(['critical', 'autre'])
    expect(groupes[1].findings.map((f) => f.id)).toEqual([2])
    expect(groupes[1].libelle).toContain('Autre gravité')
  })

  it('rend une liste vide pour une entrée vide ou absente', () => {
    expect(grouperParGravite([])).toEqual([])
    expect(grouperParGravite()).toEqual([])
  })
})

describe('libelleGroupe', () => {
  it('met le compte dans le séparateur, accordé au singulier', () => {
    expect(libelleGroupe('critical', 4)).toBe('Critique — 4 fuites')
    expect(libelleGroupe('high', 1)).toBe('Élevée — 1 fuite')
  })
})

describe('teinteGravite', () => {
  it('associe chaque gravité à son palier de risque', () => {
    expect(teinteGravite('critical')).toBe('var(--color-risk-critical)')
    expect(teinteGravite('high')).toBe('var(--color-risk-concern)')
    // L'olive du premier palier : « attention » n'est pas « préoccupant ».
    expect(teinteGravite('attention')).toBe('var(--color-risk-watch)')
  })

  it('retombe sur une teinte neutre plutôt que sur une couleur fausse', () => {
    expect(teinteGravite('inedite')).toBe('var(--color-ink-300)')
  })
})
