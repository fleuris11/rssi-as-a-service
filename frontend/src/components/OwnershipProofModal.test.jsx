import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import OwnershipProofModal from './OwnershipProofModal'

// ADR-026. Ce qui est vérifié ici, c'est ce qu'un test serveur ne peut pas
// voir : que le client reçoit une consigne exploitable, et qu'un échec de
// vérification lui dit ce qui manque au lieu d'un « échec » générique.

vi.mock('../api/endpoints', () => ({
  monitoringApi: {
    ownership: vi.fn(),
    startOwnershipProof: vi.fn(),
    verifyOwnershipProof: vi.fn(),
  },
}))

const { monitoringApi } = await import('../api/endpoints')

const ACTIF = { id: 7, value: 'https://acme.example' }

function servirEtat(surcharge = {}) {
  monitoringApi.ownership.mockResolvedValue({
    data: {
      asset_id: 7,
      domain: 'acme.example',
      state: 'declared',
      proven: false,
      proofs: [],
      email_choices: ['admin@acme.example', 'postmaster@acme.example'],
      ...surcharge,
    },
  })
}

const PREUVE_DNS = {
  id: 3,
  method: 'dns_txt',
  status: 'pending',
  last_error: '',
  instructions: {
    method: 'dns_txt',
    domain: 'acme.example',
    record_name: 'acme.example',
    record_type: 'TXT',
    record_value: 'rssi-verification=jeton-abc',
    how_to: 'Ajoutez cet enregistrement TXT à la zone DNS de acme.example.',
  },
}

describe('OwnershipProofModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue() } })
  })

  it('propose les trois méthodes, parce qu’aucune n’est disponible pour tout le monde', async () => {
    servirEtat()
    render(<OwnershipProofModal open asset={ACTIF} onClose={vi.fn()} />)

    expect(await screen.findByText('Enregistrement DNS')).toBeInTheDocument()
    expect(screen.getByText('Fichier sur le site')).toBeInTheDocument()
    expect(screen.getByText('Email de validation')).toBeInTheDocument()
  })

  it('rappelle que l’analyse ponctuelle reste possible sans preuve', async () => {
    // Sans cette phrase, l'écran se lit comme un mur : le client croit avoir
    // perdu l'accès à ses propres analyses.
    servirEtat()
    render(<OwnershipProofModal open asset={ACTIF} onClose={vi.fn()} />)

    expect(await screen.findByText(/analyse ponctuelle reste possible/)).toBeInTheDocument()
  })

  it('affiche la consigne exacte à publier, telle que le serveur la donne', async () => {
    servirEtat()
    monitoringApi.startOwnershipProof.mockResolvedValue({ data: PREUVE_DNS })
    render(<OwnershipProofModal open asset={ACTIF} onClose={vi.fn()} />)

    await userEvent.click((await screen.findAllByRole('button', { name: 'Choisir' }))[0])

    expect(await screen.findByText(/Ajoutez cet enregistrement TXT/)).toBeInTheDocument()
    expect(screen.getByText('rssi-verification=jeton-abc')).toBeInTheDocument()
  })

  it('dit ce qui manque quand la preuve n’est pas encore publiée', async () => {
    servirEtat()
    monitoringApi.startOwnershipProof.mockResolvedValue({ data: PREUVE_DNS })
    monitoringApi.verifyOwnershipProof.mockResolvedValue({
      data: {
        verified: false,
        state: 'declared',
        proof: {
          ...PREUVE_DNS,
          status: 'failed',
          last_error: 'Aucun enregistrement TXT n’a été trouvé sur ce domaine.',
        },
      },
    })
    render(<OwnershipProofModal open asset={ACTIF} onClose={vi.fn()} />)

    await userEvent.click((await screen.findAllByRole('button', { name: 'Choisir' }))[0])
    await userEvent.click(await screen.findByRole('button', { name: 'Vérifier' }))

    expect(await screen.findByText(/Aucun enregistrement TXT/)).toBeInTheDocument()
  })

  it('ferme et prévient le parent une fois la possession prouvée', async () => {
    servirEtat()
    monitoringApi.startOwnershipProof.mockResolvedValue({ data: PREUVE_DNS })
    monitoringApi.verifyOwnershipProof.mockResolvedValue({
      data: { verified: true, state: 'proven', proof: { ...PREUVE_DNS, status: 'verified' } },
    })
    const onClose = vi.fn()
    const onProven = vi.fn()
    render(<OwnershipProofModal open asset={ACTIF} onClose={onClose} onProven={onProven} />)

    await userEvent.click((await screen.findAllByRole('button', { name: 'Choisir' }))[0])
    await userEvent.click(await screen.findByRole('button', { name: 'Vérifier' }))

    await waitFor(() => expect(onProven).toHaveBeenCalled())
    expect(onClose).toHaveBeenCalled()
  })

  it('ne laisse choisir que les adresses d’administration du domaine', async () => {
    // Liste fermée : une adresse libre reviendrait à demander au demandeur de
    // s'écrire à lui-même, et la méthode ne prouverait plus rien.
    servirEtat()
    render(<OwnershipProofModal open asset={ACTIF} onClose={vi.fn()} />)

    const options = await screen.findAllByRole('option')
    expect(options.map((o) => o.textContent)).toEqual([
      'admin@acme.example',
      'postmaster@acme.example',
    ])
  })
})
