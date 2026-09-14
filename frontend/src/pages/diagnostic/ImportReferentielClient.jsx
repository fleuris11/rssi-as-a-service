import { Download, FileUp } from 'lucide-react'
import { useState } from 'react'
import { assessmentsApi } from '../../api/endpoints'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Card, { CardHeader } from '../../components/ui/Card'
import { useToast } from '../../components/ui/Toast'
import { lireFichier, telechargerBlob } from '../admin/panels/referentiels/outils'

/**
 * Le client importe SON PROPRE référentiel (B4.15) — une charte interne, les
 * exigences d'un donneur d'ordre.
 *
 * Même modèle et même parcours en deux temps que la console : analyser, voir
 * les erreurs ou l'aperçu, puis confirmer. Le référentiel importé appartient
 * au client, n'entre pas au catalogue général, et aucun autre client ne le
 * voit. Son identifiant est imposé par le serveur.
 */
export default function ImportReferentielClient({ onImporte }) {
  const { showToast } = useToast()
  const [ouvert, setOuvert] = useState(false)
  const [nom, setNom] = useState('')
  const [contenu, setContenu] = useState('')
  const [nomFichier, setNomFichier] = useState('')
  const [erreurs, setErreurs] = useState([])
  const [apercu, setApercu] = useState(null)
  const [occupe, setOccupe] = useState(null)

  async function telechargerModele() {
    try {
      const reponse = await assessmentsApi.referentialTemplate()
      telechargerBlob(reponse.data, 'modele-referentiel.csv')
    } catch {
      showToast({ type: 'error', message: 'Le modèle n’a pas pu être téléchargé.' })
    }
  }

  async function choisirFichier(event) {
    const fichier = event.target.files?.[0]
    if (!fichier) return
    setNomFichier(fichier.name)
    setContenu(await lireFichier(fichier))
    setErreurs([])
    setApercu(null)
  }

  async function envoyer(confirmer) {
    setOccupe(confirmer ? 'confirmer' : 'analyser')
    try {
      const reponse = await assessmentsApi.importReferential({
        content: contenu,
        name: nom,
        ...(confirmer ? { confirm: true } : {}),
      })
      setErreurs([])
      if (confirmer) {
        showToast({
          type: 'success',
          message: 'Votre référentiel est importé. Il n’est visible que de votre entreprise.',
        })
        setOuvert(false)
        setApercu(null)
        setContenu('')
        setNomFichier('')
        setNom('')
        onImporte?.(reponse.data.slug)
      } else {
        setApercu(reponse.data.preview)
      }
    } catch (err) {
      const donnees = err.response?.data
      setApercu(null)
      setErreurs(
        donnees?.errors?.length
          ? donnees.errors
          : [
              {
                ligne: null,
                message:
                  err.response?.status === 403
                    ? 'Seul un administrateur de votre entreprise peut importer un référentiel.'
                    : donnees?.detail || 'Analyse impossible.',
              },
            ]
      )
    } finally {
      setOccupe(null)
    }
  }

  if (!ouvert) {
    return (
      <div>
        <Button variant="secondary" icon={FileUp} onClick={() => setOuvert(true)}>
          Importer votre propre référentiel
        </Button>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader
        title="Importer votre propre référentiel"
        description="Une charte interne, les exigences d’un donneur d’ordre… Il ne sera visible que de votre entreprise."
      />
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" icon={Download} onClick={telechargerModele}>
          Télécharger le modèle vide
        </Button>
        <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-brand-600">
          <FileUp className="size-4" aria-hidden="true" />
          <span>{nomFichier || 'Choisir un fichier (CSV ou JSON)'}</span>
          <input
            type="file"
            accept=".csv,.json,text/csv,application/json"
            className="sr-only"
            aria-label="Fichier du référentiel"
            onChange={choisirFichier}
          />
        </label>
      </div>
      <label className="mt-3 block text-xs text-ink-600">
        Nom du référentiel
        <input
          className="mt-1 w-full max-w-md rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
          value={nom}
          onChange={(event) => setNom(event.target.value)}
          placeholder="Exigences de notre donneur d’ordre"
        />
      </label>
      <div className="mt-3 flex gap-2">
        <Button
          variant="primary"
          disabled={!contenu || !nom.trim()}
          loading={occupe === 'analyser'}
          onClick={() => envoyer(false)}
        >
          Analyser le fichier
        </Button>
        <Button variant="ghost" onClick={() => setOuvert(false)}>
          Fermer
        </Button>
      </div>

      {erreurs.length > 0 && (
        <div role="alert" className="mt-4 rounded-md border border-critical-strong/40 p-3">
          <p className="text-sm font-medium text-critical-strong">
            {erreurs.length} problème{erreurs.length > 1 ? 's' : ''} à corriger — rien n’a été
            importé.
          </p>
          <ul className="mt-2 space-y-1 text-sm text-ink-700">
            {erreurs.map((erreur, index) => (
              <li key={`${erreur.ligne ?? 'x'}-${index}`}>
                {erreur.ligne ? <strong>Ligne {erreur.ligne} : </strong> : null}
                {erreur.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {apercu && (
        <div className="mt-4 rounded-md border border-ink-200 bg-canvas p-3">
          <p className="text-sm font-medium text-ink-800">{apercu.name}</p>
          <p className="mt-0.5 text-xs text-ink-500">
            {apercu.domain_count} domaine(s), {apercu.measure_count} mesure(s)
          </p>
          {apercu.will_update && (
            <p className="mt-2">
              <Badge variant="warning">
                Vous avez déjà un référentiel de ce nom : l’import le mettra à jour.
              </Badge>
            </p>
          )}
          <div className="mt-3 flex gap-2">
            <Button
              variant="primary"
              loading={occupe === 'confirmer'}
              onClick={() => envoyer(true)}
            >
              Confirmer l’import
            </Button>
            <Button variant="ghost" onClick={() => setApercu(null)}>
              Annuler
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}
