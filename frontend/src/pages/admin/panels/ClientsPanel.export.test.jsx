import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ClientsPanel from './ClientsPanel'

// L'export CSV des clients était un simple lien. L'API authentifie par jeton
// en en-tête : un lien part SANS lui, et le navigateur recevait un 401 au lieu
// du fichier — vérifié en production. Aucun test ne le couvrait : le fichier
// de test existant ne porte que sur des conversions d'unités.

vi.mock('../../../api/endpoints', () => ({
  platformApi: { exportCsv: vi.fn(), exportUrl: vi.fn(() => '/api/v1/platform/export/tenants/') },
}))
const showToast = vi.fn()
vi.mock('../../../components/ui/Toast', () => ({ useToast: () => ({ showToast }) }))

const { platformApi } = await import('../../../api/endpoints')

function afficher() {
  return render(<ClientsPanel tenants={[]} plans={[]} onRefresh={vi.fn()} />)
}

describe('ClientsPanel — export CSV', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    URL.createObjectURL = vi.fn(() => 'blob:clients')
    URL.revokeObjectURL = vi.fn()
  })

  it('exporte par le client authentifié, et non par un lien sans jeton', async () => {
    platformApi.exportCsv.mockResolvedValue({ data: new Blob(['nom;offre']) })
    afficher()

    await userEvent.click(screen.getByRole('button', { name: 'Exporter en CSV' }))

    await waitFor(() => expect(platformApi.exportCsv).toHaveBeenCalledWith('tenants'))
    expect(URL.createObjectURL).toHaveBeenCalled()
    expect(screen.queryByRole('link', { name: 'Exporter en CSV' })).not.toBeInTheDocument()
  })

  it('dit quand l’export échoue, au lieu de ne rien faire', async () => {
    platformApi.exportCsv.mockRejectedValue(new Error('401'))
    afficher()

    await userEvent.click(screen.getByRole('button', { name: 'Exporter en CSV' }))

    await waitFor(() =>
      expect(showToast).toHaveBeenCalledWith(expect.objectContaining({ type: 'error' }))
    )
  })
})
