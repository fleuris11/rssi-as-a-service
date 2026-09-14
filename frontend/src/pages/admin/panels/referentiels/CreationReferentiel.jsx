import { useState } from 'react'
import { platformApi } from '../../../../api/endpoints'
import Button from '../../../../components/ui/Button'
import Card, { CardHeader } from '../../../../components/ui/Card'
import { useToast } from '../../../../components/ui/Toast'
import { CHAMP, versIdentifiant } from './outils'

const VIDE = { name: '', slug: '', version: '', publisher: '', kind: 'open', licence_notice: '' }

/**
 * Créer un référentiel à la main (B2.4), vide. Domaines et mesures s'ajoutent
 * ensuite un par un, depuis l'écran d'édition.
 */
export default function CreationReferentiel({ onCree }) {
  const { showToast } = useToast()
  const [valeurs, setValeurs] = useState(VIDE)
  // L'identifiant suit le nom tant qu'on ne l'a pas touché.
  const [identifiantManuel, setIdentifiantManuel] = useState(false)
  const [envoi, setEnvoi] = useState(false)

  const complet = valeurs.name.trim() && valeurs.slug.trim() && valeurs.version.trim()

  function changer(cle, valeur) {
    setValeurs((actuel) => {
      const suivant = { ...actuel, [cle]: valeur }
      if (cle === 'name' && !identifiantManuel) suivant.slug = versIdentifiant(valeur)
      return suivant
    })
  }

  async function creer(event) {
    event.preventDefault()
    setEnvoi(true)
    try {
      const reponse = await platformApi.createReferential(valeurs)
      showToast({ type: 'success', message: 'Référentiel créé. Ajoutez-y maintenant ses domaines.' })
      setValeurs(VIDE)
      setIdentifiantManuel(false)
      onCree?.(reponse.data.slug)
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Création impossible.',
      })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Créer un référentiel à la main"
        description="Pour un référentiel court ou interne, sans passer par un fichier."
      />
      <form onSubmit={creer} className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-ink-600">
          Nom
          <input
            className={CHAMP}
            value={valeurs.name}
            onChange={(event) => changer('name', event.target.value)}
          />
        </label>
        <label className="text-xs text-ink-600">
          Identifiant
          <input
            className={CHAMP}
            value={valeurs.slug}
            onChange={(event) => {
              setIdentifiantManuel(true)
              changer('slug', event.target.value)
            }}
          />
        </label>
        <label className="text-xs text-ink-600">
          Version
          <input
            className={CHAMP}
            value={valeurs.version}
            onChange={(event) => changer('version', event.target.value)}
          />
        </label>
        <label className="text-xs text-ink-600">
          Éditeur
          <input
            className={CHAMP}
            value={valeurs.publisher}
            onChange={(event) => changer('publisher', event.target.value)}
          />
        </label>
        <label className="text-xs text-ink-600">
          Droits
          <select
            className={CHAMP}
            value={valeurs.kind}
            onChange={(event) => changer('kind', event.target.value)}
          >
            <option value="open">Libre de droits</option>
            <option value="licensed">Soumis à droits</option>
          </select>
        </label>
        <label className="text-xs text-ink-600">
          Mention de droits
          <input
            className={CHAMP}
            value={valeurs.licence_notice}
            onChange={(event) => changer('licence_notice', event.target.value)}
          />
        </label>
        <div className="sm:col-span-2">
          <Button type="submit" variant="primary" disabled={!complet} loading={envoi}>
            Créer le référentiel
          </Button>
        </div>
      </form>
    </Card>
  )
}
