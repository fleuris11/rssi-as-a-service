import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import LecteurAudio from './LecteurAudio'

const BLOCS = [
  { type: 'paragraphe', texte: 'Un message qui vous presse est un signal.' },
  { type: 'liste', items: ['Vérifiez l’adresse', 'Appelez'] },
]

function installerSynthese(voix) {
  const enonces = []
  const faux = {
    speaking: false,
    paused: false,
    getVoices: () => voix,
    // Volontairement SANS fin automatique : une fausse synthèse qui termine
    // toute seule vide la file avant la fin du test, l'état retombe à
    // « inactif », et les boutons Pause et Arrêter disparaissent sous les
    // doigts. Les tests qui ont besoin d'enchaîner appellent `terminer()`.
    speak: vi.fn((enonce) => enonces.push(enonce)),
    cancel: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }
  window.speechSynthesis = faux
  window.SpeechSynthesisUtterance = class {
    constructor(texte) {
      this.text = texte
    }
  }
  const terminer = () => {
    const dernier = enonces.at(-1)
    dernier?.onend?.()
  }
  return { faux, enonces, terminer }
}

describe('LecteurAudio', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    delete window.speechSynthesis
    delete window.SpeechSynthesisUtterance
    vi.restoreAllMocks()
  })

  it('n’affiche rien du tout quand le navigateur ne sait pas parler', () => {
    // L'audio est une aide : son absence ne doit rien changer au cours.
    const { container } = render(<LecteurAudio blocs={BLOCS} cleEcran="e1" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('propose la lecture quand une voix française existe', async () => {
    installerSynthese([{ name: 'France', lang: 'fr-FR' }])
    render(<LecteurAudio blocs={BLOCS} cleEcran="e1" />)

    expect(await screen.findByRole('button', { name: /Écouter cet écran/ })).toBeInTheDocument()
  })

  it('le dit sobrement quand l’appareil n’a aucune voix française', async () => {
    installerSynthese([{ name: 'Anglais', lang: 'en-US' }])
    render(<LecteurAudio blocs={BLOCS} cleEcran="e1" />)

    // Une phrase, jamais une erreur technique.
    expect(
      await screen.findByText('Lecture audio indisponible sur cet appareil.')
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Écouter/ })).not.toBeInTheDocument()
  })

  it('lit bloc par bloc, avec la voix française', async () => {
    const { enonces, terminer } = installerSynthese([
      { name: 'Anglais', lang: 'en-US' },
      { name: 'France', lang: 'fr-FR' },
    ])
    render(<LecteurAudio blocs={BLOCS} cleEcran="e1" />)

    await userEvent.click(await screen.findByRole('button', { name: /Écouter cet écran/ }))

    // Un énoncé à la fois : c'est ce qui évite qu'un moteur coupe un texte
    // long en plein milieu. Le suivant ne part qu'à la fin du précédent.
    expect(enonces.length).toBe(1)
    expect(enonces[0].text).toBe('Un message qui vous presse est un signal.')
    expect(enonces[0].voice.lang).toBe('fr-FR')

    terminer()
    await waitFor(() => expect(enonces.length).toBe(2))
    // Chaque entrée de liste est un énoncé distinct.
    expect(enonces[1].text).toBe('Vérifiez l’adresse')

    terminer()
    await waitFor(() => expect(enonces.length).toBe(3))
    expect(enonces[2].text).toBe('Appelez')
  })

  it('coupe la voix quand l’apprenant change d’écran', async () => {
    const { faux } = installerSynthese([{ name: 'France', lang: 'fr-FR' }])
    const { rerender } = render(<LecteurAudio blocs={BLOCS} cleEcran="e1" />)
    await userEvent.click(await screen.findByRole('button', { name: /Écouter cet écran/ }))

    faux.cancel.mockClear()
    rerender(<LecteurAudio blocs={BLOCS} cleEcran="e2" />)

    // Le défaut classique de cette API : la voix poursuit l'écran précédent.
    expect(faux.cancel).toHaveBeenCalled()
  })

  it('coupe la voix quand l’apprenant quitte la page', async () => {
    const { faux } = installerSynthese([{ name: 'France', lang: 'fr-FR' }])
    const { unmount } = render(<LecteurAudio blocs={BLOCS} cleEcran="e1" />)
    await userEvent.click(await screen.findByRole('button', { name: /Écouter cet écran/ }))

    faux.cancel.mockClear()
    unmount()
    expect(faux.cancel).toHaveBeenCalled()
  })

  it('retient que l’apprenant a coupé le son, et ne le rallume pas', async () => {
    const { faux } = installerSynthese([{ name: 'France', lang: 'fr-FR' }])
    const { rerender } = render(<LecteurAudio blocs={BLOCS} cleEcran="e1" />)

    await userEvent.click(await screen.findByRole('button', { name: /Écouter cet écran/ }))
    await userEvent.click(await screen.findByRole('button', { name: /Arrêter/ }))

    faux.speak.mockClear()
    rerender(<LecteurAudio blocs={BLOCS} cleEcran="e2" />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Écouter cet écran/ })).toBeInTheDocument()
    )
    expect(faux.speak).not.toHaveBeenCalled()
  })

  it('reprend tout seul à l’écran suivant pour qui écoutait', async () => {
    const { faux } = installerSynthese([{ name: 'France', lang: 'fr-FR' }])
    const { rerender } = render(<LecteurAudio blocs={BLOCS} cleEcran="e1" />)
    await userEvent.click(await screen.findByRole('button', { name: /Écouter cet écran/ }))

    faux.speak.mockClear()
    rerender(<LecteurAudio blocs={BLOCS} cleEcran="e2" />)

    await waitFor(() => expect(faux.speak).toHaveBeenCalled())
  })

  it('retient la vitesse choisie', async () => {
    installerSynthese([{ name: 'France', lang: 'fr-FR' }])
    render(<LecteurAudio blocs={BLOCS} cleEcran="e1" />)

    await userEvent.click(await screen.findByRole('button', { name: '×1,25' }))
    expect(JSON.parse(localStorage.getItem('rssi.formation.audio.vitesse'))).toBe(1.25)
  })

  it('met en pause et reprend', async () => {
    const { faux } = installerSynthese([{ name: 'France', lang: 'fr-FR' }])
    render(<LecteurAudio blocs={BLOCS} cleEcran="e1" />)

    await userEvent.click(await screen.findByRole('button', { name: /Écouter cet écran/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Pause' }))
    expect(faux.pause).toHaveBeenCalled()

    await userEvent.click(await screen.findByRole('button', { name: 'Reprendre' }))
    expect(faux.resume).toHaveBeenCalled()
  })
})
