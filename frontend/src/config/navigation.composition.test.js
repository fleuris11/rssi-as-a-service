import { describe, expect, it } from 'vitest'
import { fonctionnalitesRetirees, navigationPourProfil } from './navigation'

// V2-8 (ADR-038). Deux absences qui ne se traitent pas pareil :
//
//   - hors offre        -> l'entrée reste, désactivée : c'est un levier commercial ;
//   - retirée au client -> l'entrée disparaît : on ne montre pas ce qu'on a retiré.
//
// Et une règle de cohérence : le plan d'action et les résultats n'existent que
// par le diagnostic. Les laisser afficherait un écran vide qui invite à faire
// un diagnostic auquel le client n'a pas droit.

const horsOffre = { key: 'watched_accounts', included: false, source: 'plan' }
const retiree = { key: 'watched_accounts', included: false, source: 'override' }
const ajoutee = { key: 'assistant', included: true, source: 'override' }

describe('fonctionnalitesRetirees', () => {
  it('ne retient que ce qui a été retiré à ce client', () => {
    expect(fonctionnalitesRetirees([horsOffre, ajoutee])).toEqual(new Set())
    expect(fonctionnalitesRetirees([retiree])).toEqual(new Set(['watched_accounts']))
  })

  it('ne tombe pas sans droits chargés', () => {
    expect(fonctionnalitesRetirees()).toEqual(new Set())
    expect(fonctionnalitesRetirees([])).toEqual(new Set())
  })
})

describe('navigationPourProfil avec un périmètre composé', () => {
  function cibles(retirees, technique = true) {
    const { principale, techniques } = navigationPourProfil(technique, retirees)
    return [...principale, ...techniques].map((item) => item.to)
  }

  it('laisse le menu entier quand rien n’est retiré', () => {
    expect(cibles(new Set())).toContain('/comptes-surveilles')
    expect(cibles(new Set())).toContain('/diagnostic')
  })

  it('retire l’écran de la fonctionnalité retirée', () => {
    expect(cibles(new Set(['watched_accounts']))).not.toContain('/comptes-surveilles')
  })

  it('retire aussi les écrans qui n’existent que par elle', () => {
    const restants = cibles(new Set(['anssi_assessment']))

    expect(restants).not.toContain('/diagnostic')
    expect(restants).not.toContain('/plan-action')
    // Le reste du menu est intact : on retire un périmètre, pas le produit.
    expect(restants).toContain('/tableau-de-bord')
    expect(restants).toContain('/documents')
  })

  it('ne retire rien pour une fonctionnalité seulement hors offre', () => {
    expect(cibles(fonctionnalitesRetirees([horsOffre]))).toContain('/comptes-surveilles')
  })

  it('range toujours les écrans techniques selon le profil', () => {
    const { principale, techniques } = navigationPourProfil(false, new Set(['anssi_assessment']))

    expect(techniques.map((i) => i.to)).toEqual(['/surveillance', '/compromissions'])
    expect(principale.map((i) => i.to)).not.toContain('/plan-action')
  })
})
