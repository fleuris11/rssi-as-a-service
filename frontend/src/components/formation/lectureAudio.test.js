import { describe, expect, it } from 'vitest'
import {
  LONGUEUR_MAX_ENONCE,
  choisirVoixFrancaise,
  decouper,
  fileDeLecture,
  textesDesBlocs,
} from './lectureAudio'

describe('textesDesBlocs', () => {
  it('lit les blocs de texte dans l’ordre', () => {
    expect(
      textesDesBlocs([
        { type: 'titre', niveau: 3, texte: 'Un titre' },
        { type: 'paragraphe', texte: 'Un paragraphe.' },
        { type: 'citation', texte: 'Une citation.', source: 'ANSSI' },
      ])
    ).toEqual(['Un titre', 'Un paragraphe.', 'Une citation.'])
  })

  it('énonce chaque entrée d’une liste séparément', () => {
    // Huit items lus d'un trait sont incompréhensibles à l'oreille.
    expect(
      textesDesBlocs([{ type: 'liste', items: ['Premier', 'Deuxième', 'Troisième'] }])
    ).toEqual(['Premier', 'Deuxième', 'Troisième'])
  })

  it('lit le texte alternatif d’une image, qui est fait pour ça', () => {
    expect(
      textesDesBlocs([
        { type: 'image', source: '/formation/x.png', alternative: 'Un courriel douteux.' },
      ])
    ).toEqual(['Un courriel douteux.'])
  })

  it('ignore un bloc vide ou d’un type inconnu sans rien casser', () => {
    expect(
      textesDesBlocs([
        { type: 'paragraphe', texte: '   ' },
        { type: 'venu-du-futur', texte: 'Inconnu' },
        { type: 'paragraphe', texte: 'Gardé.' },
      ])
    ).toEqual(['Gardé.'])
  })
})

describe('decouper', () => {
  it('laisse un texte court tel quel', () => {
    expect(decouper('Une phrase courte.')).toEqual(['Une phrase courte.'])
  })

  it('coupe un texte long sur la ponctuation forte', () => {
    const phrase = `${'a'.repeat(120)}. ${'b'.repeat(120)}.`
    const morceaux = decouper(phrase)

    expect(morceaux.length).toBe(2)
    // Aucun morceau ne dépasse la limite : c'est ce qui évite que le moteur
    // s'arrête en plein milieu sans rien signaler.
    expect(morceaux.every((m) => m.length <= LONGUEUR_MAX_ENONCE)).toBe(true)
  })

  it('ne coupe jamais au milieu d’un mot, même trop long', () => {
    // Mieux vaut risquer une coupure du moteur que prononcer « votre entre —
    // prise ». Un énoncé insécable sort tel quel.
    const insecable = 'x'.repeat(400)
    expect(decouper(insecable)).toEqual([insecable])
  })
})

describe('fileDeLecture', () => {
  it('enchaîne blocs découpés et entrées de liste', () => {
    const file = fileDeLecture([
      { type: 'paragraphe', texte: `${'a'.repeat(150)}. ${'b'.repeat(150)}.` },
      { type: 'liste', items: ['Un', 'Deux'] },
    ])
    expect(file.length).toBe(4)
    expect(file.at(-1)).toBe('Deux')
  })
})

describe('choisirVoixFrancaise', () => {
  it('préfère fr-FR', () => {
    const voix = [
      { name: 'Anglais', lang: 'en-US' },
      { name: 'Québec', lang: 'fr-CA' },
      { name: 'France', lang: 'fr-FR' },
    ]
    expect(choisirVoixFrancaise(voix).name).toBe('France')
  })

  it('se rabat sur un autre français plutôt que rien', () => {
    // Mieux vaut un accent québécois que pas de voix du tout.
    expect(choisirVoixFrancaise([{ name: 'Québec', lang: 'fr-CA' }]).name).toBe('Québec')
  })

  it('rend null quand aucune voix française n’existe', () => {
    expect(choisirVoixFrancaise([{ name: 'Anglais', lang: 'en-US' }])).toBeNull()
    expect(choisirVoixFrancaise([])).toBeNull()
  })

  it('ne se fie pas au nom de la voix, qui diffère sur chaque système', () => {
    const voix = [{ name: 'Microsoft Hortense Desktop', lang: 'fr-FR' }]
    expect(choisirVoixFrancaise(voix).lang).toBe('fr-FR')
  })
})
