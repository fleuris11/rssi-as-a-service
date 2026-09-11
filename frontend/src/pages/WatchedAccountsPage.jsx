import { Plus, Radar, ShieldCheck, Trash2, UserRoundSearch } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { threatIntelligenceApi } from '../api/endpoints'
import ResultatsComptes from './watched/ResultatsComptes'
import FeatureGate, { FeatureLockedNotice } from '../components/FeatureGate'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card, { CardHeader } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'
import { useEntitlements } from '../context/EntitlementsContext'

const CATEGORIES = [
  { value: 'executive', label: 'Dirigeant ou mandataire social' },
  { value: 'employee', label: 'Collaborateur' },
  { value: 'client', label: 'Client ou partenaire' },
  { value: 'service', label: 'Compte technique ou de service' },
  { value: 'other', label: 'Autre' },
]

// Formulé dans les termes d'un dirigeant, pas dans ceux du RGPD : le
// rapprochement avec l'article 6 est fait dans l'ADR, pas dans une liste
// déroulante que personne ne comprendrait.
const BASES_LEGALES = [
  { value: 'own', label: 'C’est mon propre compte' },
  { value: 'company', label: 'Compte professionnel fourni par mon entreprise' },
  { value: 'consent', label: 'La personne concernée m’a donné son accord' },
  { value: 'contract', label: 'Prévu au contrat qui me lie à cette personne' },
  { value: 'other', label: 'Autre situation, que je précise ci-dessous' },
]


function dateCourte(valeur) {
  return valeur ? new Date(valeur).toLocaleDateString('fr-FR') : '—'
}

/**
 * Le formulaire de déclaration (V2-6, ADR-033).
 *
 * La déclaration n'est pas un écran d'après ni une case perdue en bas : elle
 * est **dans** le formulaire d'ajout, au-dessus du bouton, et le bouton reste
 * inactif tant qu'elle n'est pas cochée. Faire surveiller l'adresse de
 * quelqu'un d'autre engage le client — il doit l'avoir lu au moment où il le
 * fait, pas dans des conditions générales acceptées il y a six mois.
 */
function FormulaireDeclaration({ declarationText, onCreated, onCancel }) {
  const { showToast } = useToast()
  const [valeur, setValeur] = useState('')
  const [libelle, setLibelle] = useState('')
  const [categorie, setCategorie] = useState('executive')
  const [base, setBase] = useState('company')
  const [finalite, setFinalite] = useState('')
  const [accepte, setAccepte] = useState(false)
  const [envoi, setEnvoi] = useState(false)

  const complet = valeur.trim() && finalite.trim() && accepte

  async function handleSubmit(event) {
    event.preventDefault()
    setEnvoi(true)
    try {
      const response = await threatIntelligenceApi.declareWatchedAccount({
        value: valeur.trim(),
        label: libelle.trim(),
        category: categorie,
        legal_basis: base,
        purpose: finalite.trim(),
        declaration_accepted: accepte,
      })
      onCreated(response.data)
      showToast({ type: 'success', message: 'Compte ajouté à la surveillance.' })
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible d’ajouter ce compte.',
      })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Ajouter un compte à surveiller"
        description="Une adresse email, indépendamment de vos noms de domaine."
      />
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="t-eyebrow" htmlFor="vip-valeur">
              Compte à surveiller
            </label>
            <input
              id="vip-valeur"
              type="text"
              required
              value={valeur}
              onChange={(event) => setValeur(event.target.value)}
              placeholder="prenom.nom@exemple.fr"
              className="mt-1 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="t-eyebrow" htmlFor="vip-libelle">
              Intitulé (facultatif)
            </label>
            <input
              id="vip-libelle"
              type="text"
              value={libelle}
              onChange={(event) => setLibelle(event.target.value)}
              placeholder="Directrice générale"
              className="mt-1 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="t-eyebrow" htmlFor="vip-categorie">
              De qui s’agit-il ?
            </label>
            <select
              id="vip-categorie"
              value={categorie}
              onChange={(event) => setCategorie(event.target.value)}
              className="mt-1 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
            >
              {CATEGORIES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="t-eyebrow" htmlFor="vip-base">
              À quel titre le surveillez-vous ?
            </label>
            <select
              id="vip-base"
              value={base}
              onChange={(event) => setBase(event.target.value)}
              className="mt-1 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
            >
              {BASES_LEGALES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="t-eyebrow" htmlFor="vip-finalite">
            Pourquoi surveillez-vous ce compte ?
          </label>
          <textarea
            id="vip-finalite"
            required
            rows={2}
            value={finalite}
            onChange={(event) => setFinalite(event.target.value)}
            placeholder="Exemple : compte exposé aux tentatives de fraude au virement, surveillance décidée en comité."
            className="mt-1 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
          />
          <p className="mt-1 text-xs text-ink-500">
            Cette finalité est conservée avec votre déclaration. C’est elle que vous montrerez si
            la personne concernée vous demande pourquoi son compte est surveillé.
          </p>
        </div>

        <div className="rounded-md border border-warning-strong/30 bg-warning-subtle/40 p-3">
          <label className="flex items-start gap-2.5 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={accepte}
              onChange={(event) => setAccepte(event.target.checked)}
              className="mt-0.5 size-4 shrink-0"
            />
            <span>{declarationText}</span>
          </label>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>
            Annuler
          </Button>
          {/* Inactif tant que la déclaration n'est pas cochée : elle est la
              condition de l'ajout, pas une formalité qu'on coche après. */}
          <Button type="submit" variant="primary" loading={envoi} disabled={!complet}>
            Déclarer et surveiller
          </Button>
        </div>
      </form>
    </Card>
  )
}

function LigneCompte({ compte, onRemove, onScan, occupe }) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-ink-800">
          {compte.value}
          {compte.label && <span className="text-ink-500"> — {compte.label}</span>}
        </p>
        <p className="mt-0.5 text-xs text-ink-500">
          {compte.category_label} · {compte.legal_basis_label} · déclaré le{' '}
          {dateCourte(compte.declared_at)}
          {compte.declared_by_email ? ` par ${compte.declared_by_email}` : ''}
        </p>
        <p className="mt-1 max-w-2xl text-xs italic text-ink-500">« {compte.purpose} »</p>
        <p className="mt-1 text-xs text-ink-400">
          Dernière analyse : {compte.last_scanned_at ? dateCourte(compte.last_scanned_at) : 'jamais'}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {compte.open_findings > 0 ? (
          <Badge variant="critical">{compte.open_findings} à traiter</Badge>
        ) : (
          <Badge variant="ok">Rien à signaler</Badge>
        )}
        <FeatureGate feature="watched_accounts">
          <Button
            variant="secondary"
            size="sm"
            icon={Radar}
            loading={occupe === `scan-${compte.id}`}
            onClick={() => onScan([compte.id])}
          >
            Analyser
          </Button>
        </FeatureGate>
        {/* Le retrait n'est JAMAIS gardé par l'offre : arrêter de traiter les
            données d'un tiers ne doit dépendre d'aucun abonnement. */}
        <Button
          variant="ghost"
          size="sm"
          icon={Trash2}
          loading={occupe === `remove-${compte.id}`}
          onClick={() => onRemove(compte)}
        >
          Retirer
        </Button>
      </div>
    </li>
  )
}

export default function WatchedAccountsPage() {
  const { showToast } = useToast()
  const { hasFeature } = useEntitlements()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [formulaireOuvert, setFormulaireOuvert] = useState(false)
  const [occupe, setOccupe] = useState(null)
  const toastRef = useRef(showToast)
  toastRef.current = showToast
  const inclus = hasFeature('watched_accounts')

  const charger = useCallback(async () => {
    setLoading(true)
    try {
      // Les resultats ne sont plus charges ici : `ResultatsComptes`
      // interroge l'API groupee et paginee lui-meme. Ramener les 3 222
      // lignes pour n'en afficher qu'une poignee etait precisement le
      // defaut — 1,6 Mo et 4,9 s pour un seul compte.
      const comptes = await threatIntelligenceApi.listWatchedAccounts()
      setData(comptes.data)
    } catch (err) {
      if (err.response?.status !== 402) {
        toastRef.current({ type: 'error', message: 'Impossible de charger les comptes surveillés.' })
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    charger()
  }, [charger])

  async function handleRemove(compte) {
    setOccupe(`remove-${compte.id}`)
    try {
      await threatIntelligenceApi.removeWatchedAccount(compte.id)
      await charger()
      showToast({ type: 'success', message: 'Surveillance arrêtée pour ce compte.' })
    } catch {
      showToast({ type: 'error', message: 'Impossible de retirer ce compte.' })
    } finally {
      setOccupe(null)
    }
  }

  async function handleScan(accountIds) {
    setOccupe(accountIds.length === 1 ? `scan-${accountIds[0]}` : 'scan-tous')
    try {
      await threatIntelligenceApi.scanWatchedAccounts(accountIds)
      showToast({
        type: 'success',
        message: 'Analyse lancée. Les résultats apparaîtront ici dans quelques minutes.',
      })
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible de lancer l’analyse.',
      })
    } finally {
      setOccupe(null)
    }
  }


  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  const comptes = data?.results ?? []
  const resume = data?.summary ?? { accounts: 0, open_findings: 0, critical_findings: 0 }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Comptes surveillés</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-500">
          Des comptes précis — vos dirigeants, un compte sensible — surveillés indépendamment de vos
          noms de domaine. Vous décidez quand lancer l’analyse.
        </p>
      </div>

      {/* Hors offre : l'encart explique et nomme l'offre. La liste reste
          visible en dessous — un client qui perd la fonctionnalité doit
          pouvoir continuer à RETIRER ce qu'il a déclaré. */}
      {!inclus && <FeatureLockedNotice feature="watched_accounts" />}

      <Card padding="p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap gap-6">
            <div>
              <p className="t-eyebrow">Comptes surveillés</p>
              <p className="font-display text-2xl font-semibold text-ink-900">{resume.accounts}</p>
            </div>
            <div>
              <p className="t-eyebrow">Résultats à traiter</p>
              <p className="font-display text-2xl font-semibold text-ink-900">
                {resume.open_findings}
              </p>
            </div>
            <div>
              <p className="t-eyebrow">Dernière analyse</p>
              <p className="mt-1.5 text-sm text-ink-700">{dateCourte(resume.last_scanned_at)}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <FeatureGate feature="watched_accounts">
              <Button
                variant="secondary"
                icon={Radar}
                loading={occupe === 'scan-tous'}
                disabled={comptes.length === 0}
                onClick={() => handleScan([])}
              >
                Analyser tous les comptes
              </Button>
            </FeatureGate>
            <FeatureGate feature="watched_accounts">
              <Button
                variant="primary"
                icon={Plus}
                onClick={() => setFormulaireOuvert((ouvert) => !ouvert)}
              >
                Ajouter un compte
              </Button>
            </FeatureGate>
          </div>
        </div>
        {/* Ces chiffres ne se mélangent jamais à ceux de l'exposition : ce ne
            sont pas les actifs du client (ADR-033). */}
        <p className="mt-3 flex items-start gap-1.5 text-xs text-ink-500">
          <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          Ces résultats sont comptés séparément de votre exposition : ce ne sont pas vos actifs,
          ce sont des comptes que vous surveillez.
        </p>
      </Card>

      {formulaireOuvert && inclus && (
        <FormulaireDeclaration
          declarationText={data?.declaration_text}
          onCancel={() => setFormulaireOuvert(false)}
          onCreated={() => {
            setFormulaireOuvert(false)
            charger()
          }}
        />
      )}

      <Card padding="p-0">
        <div className="p-5 pb-0">
          <CardHeader title="Comptes déclarés" />
        </div>
        {comptes.length === 0 ? (
          <div className="p-5 pt-0">
            <EmptyState
              icon={UserRoundSearch}
              title="Aucun compte surveillé"
              description="Ajoutez l’adresse d’un dirigeant ou d’un compte sensible pour savoir s’il apparaît dans une fuite."
            />
          </div>
        ) : (
          <ul className="divide-y divide-ink-100 px-5 pb-3">
            {comptes.map((compte) => (
              <LigneCompte
                key={compte.id}
                compte={compte}
                onRemove={handleRemove}
                onScan={handleScan}
                occupe={occupe}
              />
            ))}
          </ul>
        )}
      </Card>

      <ResultatsComptes comptes={comptes} resume={resume} />
    </div>
  )
}
