import { describe, expect, it } from 'vitest'
import { minutesVersSaisie, saisieVersMinutes } from './ClientsPanel'

// Le produit stocke des MINUTES de bout en bout ; l'heure n'existe qu'à la
// saisie, parce que « 1440 minutes » ne se lit pas comme 24 h.
//
// Ces conversions sont le seul endroit du frontend où les deux unités se
// rencontrent, et c'est exactement le genre d'endroit où l'on multiplie ou
// divise par 60 au mauvais moment. L'erreur ne se voit pas : elle produit un
// délai plausible. D'où des tests sur les cas limites plutôt que sur le cas
// courant.

describe('minutesVersSaisie', () => {
  it('propose l’heure quand la valeur tombe juste', () => {
    expect(minutesVersSaisie(60)).toEqual({ valeur: 1, unite: 'heures' })
    expect(minutesVersSaisie(1440)).toEqual({ valeur: 24, unite: 'heures' })
  })

  it('reste en minutes quand l’heure ne représenterait pas la valeur', () => {
    expect(minutesVersSaisie(30)).toEqual({ valeur: 30, unite: 'minutes' })
    expect(minutesVersSaisie(90)).toEqual({ valeur: 90, unite: 'minutes' })
  })

  it('distingue « pas de surcharge » de « aucun délai »', () => {
    // Le piège central, et il se rejoue à chaque couche : `null` veut dire
    // « on applique le réglage de plateforme », `0` veut dire « aucun délai,
    // décidé pour ce client ». Les confondre appliquerait 24 h à un client à
    // qui l'exploitant vient d'accorder l'inverse.
    expect(minutesVersSaisie(null)).toEqual({ valeur: '', unite: 'minutes' })
    expect(minutesVersSaisie(undefined)).toEqual({ valeur: '', unite: 'minutes' })
    expect(minutesVersSaisie(0)).toEqual({ valeur: 0, unite: 'minutes' })
  })

  it('n’affiche jamais « 0 heure »', () => {
    // 0 % 60 === 0 : sans garde explicite, zéro serait présenté comme
    // « 0 heures », ce qui laisse croire à une valeur exprimée en heures.
    expect(minutesVersSaisie(0).unite).toBe('minutes')
  })
})

describe('saisieVersMinutes', () => {
  it('convertit les heures en minutes', () => {
    expect(saisieVersMinutes(2, 'heures')).toBe(120)
    expect(saisieVersMinutes(24, 'heures')).toBe(1440)
  })

  it('laisse les minutes telles quelles', () => {
    expect(saisieVersMinutes(30, 'minutes')).toBe(30)
    expect(saisieVersMinutes(90, 'minutes')).toBe(90)
  })

  it('rend null pour un champ vide, et zéro pour un zéro', () => {
    expect(saisieVersMinutes('', 'minutes')).toBeNull()
    expect(saisieVersMinutes(null, 'heures')).toBeNull()
    expect(saisieVersMinutes(0, 'minutes')).toBe(0)
    expect(saisieVersMinutes(0, 'heures')).toBe(0)
  })

  it('fait l’aller-retour sans rien perdre', () => {
    for (const minutes of [0, 1, 30, 59, 60, 90, 120, 1440]) {
      const { valeur, unite } = minutesVersSaisie(minutes)
      expect(saisieVersMinutes(valeur, unite)).toBe(minutes)
    }
  })
})
