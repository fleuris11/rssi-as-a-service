import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CardHeader } from './Card'

// Le défaut que ce test épingle : `subtitle` était passé par six en-têtes et
// ignoré en silence. Les questions des courbes de la page Rapports n'ont
// jamais été affichées, et aucun test ne cherchait leur PRÉSENCE — un seul
// vérifiait leur absence, ce qui passait pour une mauvaise raison.

describe('CardHeader', () => {
  it('affiche la description', () => {
    render(<CardHeader title="Titre" description="Ce que la carte montre." />)
    expect(screen.getByText('Ce que la carte montre.')).toBeInTheDocument()
  })

  it('affiche le sous-titre, que six en-têtes passaient sans effet', () => {
    render(<CardHeader title="Titre" subtitle="Le score baisse-t-il ?" />)
    expect(screen.getByText('Le score baisse-t-il ?')).toBeInTheDocument()
  })
})
