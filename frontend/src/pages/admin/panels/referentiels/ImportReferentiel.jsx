import { Download, FileUp } from 'lucide-react'
import { useState } from 'react'
import { platformApi } from '../../../../api/endpoints'
import Badge from '../../../../components/ui/Badge'
import Button from '../../../../components/ui/Button'
import Card, { CardHeader } from '../../../../components/ui/Card'
import { useToast } from '../../../../components/ui/Toast'
import { CHAMP, lireFichier, telechargerBlob } from './outils'

/**
 * Importer un référentiel depuis un fichier (B2.3).
 *
 * Deux temps, jamais un seul : on ANALYSE, on montre toutes les erreurs avec
 * leur ligne ou l'aperçu de ce qui sera créé, et seulement ensuite on
 * confirme. Un référentiel fautif ne reste pas dans la console : il se propage
 * dans le questionnaire de tous les clients à qui on l'attribue.
 */
export default function ImportReferentiel({ onImporte }) {
  const { showToast } = useToast()
  const [contenu, setContenu] = useState('')
  const [nomFichier, setNomFichier] = useState('')
  const [meta, setMeta] = useState({
    name: '',
    slug: '',
    version: '',
    publisher: '',
    kind: 'licensed',
    licence_notice: '',
  })
  const [erreurs, setErreurs] = useState([])
  const [apercu, setApercu] = useState(null)
  const [occupe, setOccupe] = useState(null)
  const estJson = contenu.trimStart().startsWith('{')

  const champ = (cle) => ({
    value: meta[cle],
    onChange: (event) => setMeta((actuel) => ({ ...actuel, [cle]: event.target.value })),
  })

  async function telechargerModele() {
    try {
      const reponse = await platformApi.referentialTemplate()
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
      const reponse = await platformApi.importReferential({
        content: contenu,
        ...meta,
        ...(confirmer ? { confirm: true } : {}),
      })
      setErreurs([])
      if (confirmer) {
        showToast({ type: 'success', message: 'Référentiel importé.' })
        setApercu(null)
        setContenu('')
        setNomFichier('')
        onImporte?.(reponse.data.preview?.slug)
      } else {
        setApercu(reponse.data.preview)
      }
    } catch (err) {
      const donnees = err.response?.data
      setApercu(null)
      setErreurs(
        donnees?.errors?.length
          ? donnees.errors
          : [{ ligne: null, message: donnees?.detail || 'Analyse impossible.' }]
      )
    } finally {
      setOccupe(null)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Importer un référentiel"
        description="Remplissez le modèle, déposez le fichier : rien n’est créé avant que vous ayez vu l’aperçu et confirmé."
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

      {contenu && !estJson && (
        // Un CSV ne sait pas porter d'en-tête structuré : les informations du
        // référentiel se saisissent ici. Un JSON les porte lui-même.
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-ink-600">
            Nom
            <input className={CHAMP} {...champ('name')} />
          </label>
          <label className="text-xs text-ink-600">
            Identifiant
            <input className={CHAMP} placeholder="iso-27001-annexe-a" {...champ('slug')} />
          </label>
          <label className="text-xs text-ink-600">
            Version
            <input className={CHAMP} placeholder="2022" {...champ('version')} />
          </label>
          <label className="text-xs text-ink-600">
            Éditeur
            <input className={CHAMP} {...champ('publisher')} />
          </label>
          <label className="text-xs text-ink-600">
            Droits
            <select className={CHAMP} {...champ('kind')}>
              <option value="licensed">Soumis à droits</option>
              <option value="open">Libre de droits</option>
            </select>
          </label>
          <label className="text-xs text-ink-600">
            Mention de droits
            <input
              className={CHAMP}
              placeholder="Reproduit sous licence n°… — usage interne"
              {...champ('licence_notice')}
            />
          </label>
        </div>
      )}

      <div className="mt-4">
        <Button
          variant="primary"
          disabled={!contenu}
          loading={occupe === 'analyser'}
          onClick={() => envoyer(false)}
        >
          Analyser le fichier
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
          <p className="text-sm font-medium text-ink-800">
            {apercu.name} <span className="text-ink-400">v{apercu.version}</span>
          </p>
          <p className="mt-0.5 text-xs text-ink-500">
            {apercu.domain_count} domaine(s), {apercu.measure_count} mesure(s)
          </p>
          {apercu.will_update && (
            // Remplacer n'est pas créer : le questionnaire de ses clients va
            // changer, et c'est ce qu'on doit savoir avant de confirmer.
            <p className="mt-2">
              <Badge variant="warning">
                Ce référentiel existe déjà ({apercu.existing_measure_count} mesures) : l’import
                le mettra à jour pour tous ses clients.
              </Badge>
            </p>
          )}
          <ul className="mt-2 space-y-0.5 text-xs text-ink-600">
            {apercu.domains.map((domaine) => (
              <li key={domaine.code}>
                {domaine.name} — {domaine.measure_count} mesure(s)
              </li>
            ))}
          </ul>
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
