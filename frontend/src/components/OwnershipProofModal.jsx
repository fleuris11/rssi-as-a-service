import { Check, Copy, Globe, Mail, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { monitoringApi } from '../api/endpoints'
import Button from './ui/Button'
import Modal from './ui/Modal'

// ADR-026. Trois méthodes, parce qu'aucune n'est disponible pour tout le
// monde : une PME dont le site est chez un hébergeur mutualisé n'a pas
// toujours la main sur sa zone DNS ; une autre ne peut pas déposer de fichier
// sur un site tenu par un prestataire ; une troisième n'a plus accès aux
// adresses génériques de son domaine. Proposer une seule méthode aurait
// simplement déplacé le blocage.
const METHODES = [
  {
    id: 'dns_txt',
    libelle: 'Enregistrement DNS',
    icone: Globe,
    resume: 'Vous avez accès à la zone DNS du domaine.',
  },
  {
    id: 'http_file',
    libelle: 'Fichier sur le site',
    icone: ShieldCheck,
    resume: 'Vous pouvez déposer un fichier à la racine du site.',
  },
  {
    id: 'email',
    libelle: 'Email de validation',
    icone: Mail,
    resume: 'Vous relevez une adresse d’administration du domaine.',
  },
]

function ValeurACopier({ etiquette, valeur }) {
  const [copie, setCopie] = useState(false)

  async function copier() {
    await navigator.clipboard.writeText(valeur)
    setCopie(true)
    setTimeout(() => setCopie(false), 2000)
  }

  return (
    <div>
      <p className="t-eyebrow mb-1">{etiquette}</p>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded-md bg-ink-50 px-3 py-2 text-xs text-ink-800">
          {valeur}
        </code>
        <Button
          variant="secondary"
          size="sm"
          icon={copie ? Check : Copy}
          onClick={copier}
          aria-label={`Copier ${etiquette}`}
        >
          {copie ? 'Copié' : 'Copier'}
        </Button>
      </div>
    </div>
  )
}

/**
 * Prouver la possession d'un domaine avant d'activer sa surveillance continue.
 *
 * Les consignes ne sont pas écrites ici : elles viennent du serveur
 * (`instructions`), pour que l'écran, l'email de vérification et le support
 * disent exactement la même chose. Recopier le texte côté client garantirait
 * qu'un jour les deux divergent — c'est déjà arrivé sur la grille tarifaire.
 */
export default function OwnershipProofModal({ open, onClose, asset, onProven }) {
  const [etat, setEtat] = useState(null)
  const [methode, setMethode] = useState(null)
  const [preuve, setPreuve] = useState(null)
  const [code, setCode] = useState('')
  const [adresse, setAdresse] = useState('')
  const [occupe, setOccupe] = useState(false)
  const [erreur, setErreur] = useState('')
  const [echec, setEchec] = useState('')

  const charger = useCallback(async () => {
    if (!asset) return
    try {
      const response = await monitoringApi.ownership(asset.id)
      setEtat(response.data)
      setAdresse(response.data.email_choices?.[0] ?? '')
    } catch {
      setErreur('Impossible de charger l’état de cet actif.')
    }
  }, [asset])

  useEffect(() => {
    if (!open) {
      setMethode(null)
      setPreuve(null)
      setCode('')
      setErreur('')
      setEchec('')
      return
    }
    charger()
  }, [open, charger])

  async function ouvrirPreuve(id) {
    setOccupe(true)
    setErreur('')
    setEchec('')
    try {
      const response = await monitoringApi.startOwnershipProof(asset.id, {
        method: id,
        email_recipient: id === 'email' ? adresse.split('@')[0] : '',
      })
      setMethode(id)
      setPreuve(response.data)
    } catch (err) {
      setErreur(err.response?.data?.detail || 'La vérification n’a pas pu être ouverte.')
    } finally {
      setOccupe(false)
    }
  }

  async function verifier() {
    setOccupe(true)
    setErreur('')
    setEchec('')
    try {
      const response = await monitoringApi.verifyOwnershipProof(asset.id, preuve.id, { code })
      if (response.data.verified) {
        onProven?.()
        onClose()
        return
      }
      // Un échec de vérification n'est pas une erreur : c'est une étape du
      // parcours. Le message du serveur dit ce qui manque — l'afficher tel
      // quel vaut mieux qu'un « échec » générique.
      setEchec(response.data.proof?.last_error || 'La preuve n’a pas encore été trouvée.')
      setPreuve(response.data.proof)
    } catch (err) {
      setErreur(err.response?.data?.detail || 'La vérification a échoué.')
    } finally {
      setOccupe(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Prouver la possession du domaine">
      <p className="mb-4 text-sm text-ink-500">
        La surveillance continue de{' '}
        <strong className="font-medium text-ink-800">{etat?.domain ?? asset?.value}</strong> demande
        d’en prouver la possession. Une analyse ponctuelle reste possible sans cette preuve.
      </p>

      {erreur && (
        <p role="alert" className="mb-4 rounded-md bg-critical-subtle px-3 py-2 text-sm text-critical-strong">
          {erreur}
        </p>
      )}

      {!preuve ? (
        <div className="space-y-2">
          {METHODES.map((m) => (
            <div key={m.id} className="rounded-md border border-ink-100 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <m.icone className="mt-0.5 size-5 shrink-0 text-ink-400" aria-hidden="true" />
                  <div>
                    <p className="text-sm font-medium text-ink-800">{m.libelle}</p>
                    <p className="text-xs text-ink-500">{m.resume}</p>
                  </div>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={occupe}
                  onClick={() => ouvrirPreuve(m.id)}
                >
                  Choisir
                </Button>
              </div>

              {m.id === 'email' && (etat?.email_choices?.length ?? 0) > 0 && (
                <label className="mt-3 block text-xs text-ink-500">
                  Adresse de destination
                  {/* Liste fermée : laisser saisir une adresse libre
                      reviendrait à demander au demandeur de s'écrire à
                      lui-même. */}
                  <select
                    value={adresse}
                    onChange={(event) => setAdresse(event.target.value)}
                    className="mt-1 w-full rounded-md border border-ink-200 px-2 py-1.5 text-sm text-ink-800"
                  >
                    {etat.email_choices.map((choix) => (
                      <option key={choix} value={choix}>
                        {choix}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-ink-700">{preuve.instructions?.how_to}</p>

          {methode === 'dns_txt' && (
            <>
              <ValeurACopier etiquette="Nom" valeur={preuve.instructions.record_name} />
              <ValeurACopier etiquette="Type" valeur={preuve.instructions.record_type} />
              <ValeurACopier etiquette="Valeur" valeur={preuve.instructions.record_value} />
            </>
          )}

          {methode === 'http_file' && (
            <>
              <ValeurACopier etiquette="Adresse du fichier" valeur={preuve.instructions.file_url} />
              <ValeurACopier etiquette="Contenu" valeur={preuve.instructions.file_content} />
            </>
          )}

          {methode === 'email' && (
            <label className="block text-sm text-ink-700">
              Code reçu par email
              <input
                type="text"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                className="mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm"
                autoComplete="off"
              />
            </label>
          )}

          {echec && (
            <p role="status" className="rounded-md bg-warning-subtle px-3 py-2 text-sm text-warning-strong">
              {echec}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setPreuve(null)} disabled={occupe}>
              Changer de méthode
            </Button>
            <Button onClick={verifier} disabled={occupe}>
              {occupe ? 'Vérification…' : 'Vérifier'}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
