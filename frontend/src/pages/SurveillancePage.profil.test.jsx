import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SurveillancePage from './SurveillancePage'

// Lot C, point 4 : « un même écran consulté dans les deux profils doit être
// visiblement différent, sinon l'interrupteur ne sert à rien ». Et point 1 :
// « un même fait reste le même fait ». Ce fichier tient les deux à la fois,
// sur un écran réel et non sur une primitive isolée.

let profilCourant = 'executive'

vi.mock('../context/useDisplayProfile', async () => {
  const reel = await vi.importActual('../context/useDisplayProfile')
  return {
    ...reel,
    useDisplayProfile: () => ({
      profile: profilCourant,
      isExecutive: profilCourant === 'executive',
      isTechnical: profilCourant === 'technical',
      setProfile: vi.fn(),
    }),
  }
})
vi.mock('../api/endpoints', () => ({
  monitoringApi: {
    dashboard: vi.fn(),
    assetCheckHistory: vi.fn(),
    updateAsset: vi.fn(),
    deleteAsset: vi.fn(),
    createAsset: vi.fn(),
  },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

const { monitoringApi } = await import('../api/endpoints')

const IMPACT = 'Il est plus facile pour un escroc d’écrire en votre nom.'
const ACTION = 'Faites compléter les enregistrements SPF et DMARC.'
const CONSTAT = 'v=DMARC1 absent'

function servir() {
  monitoringApi.dashboard.mockResolvedValue({
    data: [
      {
        asset: { id: 7, type: 'email_domain', value: 'durand.example', is_active: true },
        uptime_24h: null,
        latest_checks: {
          email_dns: { id: 1, status: 'warning', checked_at: '2026-09-12T06:00:05Z' },
        },
        open_alerts: [
          {
            id: 3,
            alert_type: 'email_misconfigured',
            severity: 'warning',
            opened_at: '2026-09-10T08:15:00Z',
            details: { dmarc: CONSTAT },
            meaning: IMPACT,
            recommended_action: ACTION,
          },
        ],
      },
    ],
  })
}

async function rendre(profil) {
  profilCourant = profil
  servir()
  const vue = render(<SurveillancePage />)
  await screen.findByText('durand.example')
  return vue
}

/** Le texte qu'on VOIT : tout ce qui n'est pas sous un élément masqué. */
function texteVisible(racine) {
  const morceaux = []
  const parcours = document.createTreeWalker(racine, NodeFilter.SHOW_TEXT)
  while (parcours.nextNode()) {
    const noeud = parcours.currentNode
    if (!noeud.parentElement.closest('[hidden]') && noeud.textContent.trim()) {
      morceaux.push(noeud.textContent.trim())
    }
  }
  return morceaux.join(' ')
}

describe('SurveillancePage dans les deux profils', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('est visiblement différente d’un profil à l’autre', async () => {
    const dirigeant = texteVisible((await rendre('executive')).container)
    document.body.innerHTML = ''
    const technique = texteVisible((await rendre('technical')).container)

    expect(dirigeant).not.toEqual(technique)
  })

  it('mène l’alerte avec son impact et son action pour le dirigeant', async () => {
    const { container } = await rendre('executive')

    const lecture = container.querySelector('[data-lecture]')
    expect(lecture.firstElementChild).toHaveTextContent(IMPACT)
    expect(screen.getByText(CONSTAT)).not.toBeVisible()
    // Vocabulaire courant devant, terme technique entre parenthèses.
    expect(screen.getByText(/Authenticité de vos emails/)).toBeInTheDocument()
    expect(screen.getByText('email_misconfigured')).not.toBeVisible()
  })

  it('mène avec le constat déplié et les champs bruts pour le technicien', async () => {
    const { container } = await rendre('technical')

    const lecture = container.querySelector('[data-lecture]')
    expect(lecture.firstElementChild).toHaveTextContent('Ce que le contrôle a constaté')
    expect(screen.getByText(CONSTAT)).toBeVisible()
    expect(screen.getByText('email_misconfigured')).toBeVisible()
    // L'horodatage précis de l'ouverture de l'alerte.
    expect(container).toHaveTextContent(/2026-09-10 \d\d:15:00 UTC/)
  })

  it('porte les mêmes faits dans les deux profils', async () => {
    const dirigeant = (await rendre('executive')).container.textContent
    document.body.innerHTML = ''
    const technique = (await rendre('technical')).container.textContent

    for (const fait of [IMPACT, ACTION, CONSTAT, 'durand.example', 'SPF / DMARC']) {
      expect(dirigeant).toContain(fait)
      expect(technique).toContain(fait)
    }
  })
})
