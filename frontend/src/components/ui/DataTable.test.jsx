import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import DataTable from './DataTable'

const COLONNES = [
  { cle: 'nom', entete: 'Entreprise' },
  { cle: 'offre', entete: 'Offre' },
  { cle: 'score', entete: 'Exposition', num: true },
  { cle: 'etat', entete: 'État', triable: false, rendu: (l) => <span>{l.etat}</span> },
]

const LIGNES = [
  { id: 'a', nom: 'Menuiserie Lambert', offre: 'Veille', score: 9, etat: 'Actif' },
  { id: 'b', nom: 'Clinique des Tilleuls', offre: 'Souverain', score: 81, etat: 'Actif' },
  { id: 'c', nom: 'Transports Vidal', offre: 'Pilotage', score: 18, etat: 'Essai' },
]

function afficher(props = {}) {
  return render(
    <DataTable
      colonnes={COLONNES}
      lignes={LIGNES}
      cleDeLigne={(l) => l.id}
      legende="Clients"
      {...props}
    />
  )
}

function nomsAffiches() {
  return within(screen.getByRole('table'))
    .getAllByRole('row')
    .slice(1)
    .map((ligne) => ligne.querySelector('td').textContent)
}

describe('DataTable', () => {
  it('rend les lignes dans l’ordre reçu, sans tri imposé', () => {
    afficher()

    // L'ordre du serveur porte un sens — le plus grave d'abord, le plus
    // récent d'abord. Le remplacer par un tri alphabétique le détruirait.
    expect(nomsAffiches()).toEqual([
      'Menuiserie Lambert',
      'Clinique des Tilleuls',
      'Transports Vidal',
    ])
  })

  it('trie dans les deux sens, puis rend l’ordre d’origine', async () => {
    afficher()
    const entete = screen.getByRole('button', { name: /Entreprise/ })

    await userEvent.click(entete)
    expect(nomsAffiches()[0]).toBe('Clinique des Tilleuls')

    await userEvent.click(entete)
    expect(nomsAffiches()[0]).toBe('Transports Vidal')

    await userEvent.click(entete)
    expect(nomsAffiches()).toEqual([
      'Menuiserie Lambert',
      'Clinique des Tilleuls',
      'Transports Vidal',
    ])
  })

  it('annonce le tri aux technologies d’assistance', async () => {
    afficher()
    const colonne = screen.getByRole('columnheader', { name: /Entreprise/ })

    expect(colonne).toHaveAttribute('aria-sort', 'none')
    await userEvent.click(screen.getByRole('button', { name: /Entreprise/ }))
    expect(colonne).toHaveAttribute('aria-sort', 'ascending')
  })

  it('trie les nombres comme des nombres, pas comme du texte', async () => {
    afficher()

    await userEvent.click(screen.getByRole('button', { name: /Exposition/ }))

    // Un tri textuel donnerait 18, 81, 9.
    expect(nomsAffiches()).toEqual([
      'Menuiserie Lambert',
      'Transports Vidal',
      'Clinique des Tilleuls',
    ])
  })

  it('ne propose pas de tri sur une colonne qui n’en veut pas', () => {
    afficher()
    expect(screen.queryByRole('button', { name: /État/ })).not.toBeInTheDocument()
  })

  it('filtre par la recherche', async () => {
    afficher({
      recherche: { label: 'Rechercher un client', extraire: (l) => [l.nom, l.offre] },
    })

    await userEvent.type(screen.getByLabelText('Rechercher un client'), 'tilleuls')

    expect(nomsAffiches()).toEqual(['Clinique des Tilleuls'])
  })

  it('filtre par une liste de choix', async () => {
    afficher({
      filtres: [
        {
          cle: 'etat',
          libelle: 'État',
          options: [
            { valeur: 'actif', libelle: 'Actifs', test: (l) => l.etat === 'Actif' },
            { valeur: 'essai', libelle: 'Essais', test: (l) => l.etat === 'Essai' },
          ],
        },
      ],
    })

    await userEvent.selectOptions(screen.getByLabelText('État'), 'essai')

    expect(nomsAffiches()).toEqual(['Transports Vidal'])
  })

  it('change la densité sans recharger', async () => {
    afficher()
    const table = screen.getByRole('table')

    expect(table).toHaveAttribute('data-densite', 'compacte')
    await userEvent.click(screen.getByRole('button', { name: 'Confortable' }))
    expect(table).toHaveAttribute('data-densite', 'confortable')
  })

  it('sélectionne une ligne, et toute la page', async () => {
    const onChange = vi.fn()
    afficher({
      selection: { valeurs: [], onChange, nommer: (l) => l.nom },
    })

    await userEvent.click(screen.getByLabelText('Sélectionner Transports Vidal'))
    expect(onChange).toHaveBeenCalledWith(['c'])

    await userEvent.click(screen.getByLabelText('Tout sélectionner sur cette page'))
    expect(onChange).toHaveBeenLastCalledWith(['a', 'b', 'c'])
  })

  it('pagine au-delà du seuil, et pas en deçà', async () => {
    const beaucoup = Array.from({ length: 5 }, (_, i) => ({
      id: `l${i}`,
      nom: `Client ${i}`,
      offre: 'Veille',
      score: i,
      etat: 'Actif',
    }))

    const { rerender } = afficher({ lignes: beaucoup, parPage: 2 })
    expect(screen.getByRole('button', { name: /Suivant/ })).toBeInTheDocument()
    expect(nomsAffiches()).toHaveLength(2)

    await userEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    expect(nomsAffiches()).toEqual(['Client 2', 'Client 3'])

    rerender(
      <DataTable colonnes={COLONNES} lignes={LIGNES} cleDeLigne={(l) => l.id} legende="Clients" />
    )
    expect(screen.queryByRole('button', { name: /Suivant/ })).not.toBeInTheDocument()
  })

  it('dit qu’il n’y a aucun résultat, et non que la liste est vide', async () => {
    afficher({
      recherche: { label: 'Rechercher un client', extraire: (l) => [l.nom] },
      titreVide: 'Aucun client',
    })

    await userEvent.type(screen.getByLabelText('Rechercher un client'), 'introuvable')

    // Les deux situations ne se disent pas pareil : « rien à voir » et
    // « votre recherche ne donne rien » appellent des gestes différents.
    expect(screen.getByText('Aucun résultat')).toBeInTheDocument()
    expect(screen.queryByText('Aucun client')).not.toBeInTheDocument()
  })
})
