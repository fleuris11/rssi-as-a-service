import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Download,
  GraduationCap,
  Loader2,
  RotateCcw,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { formationApi } from '../api/endpoints'
import ContenuEcran from '../components/formation/ContenuEcran'
import Button from '../components/ui/Button'

/**
 * Le parcours de l'apprenant (F1).
 *
 * Page PUBLIQUE : le salarié qui suit un cours n'a pas de compte, c'est le
 * jeton de son lien qui l'autorise. Elle vit donc hors de l'espace client,
 * sans barre latérale ni sélecteur d'entreprise — il n'y a rien d'autre à
 * atteindre depuis ici.
 *
 * Trois exigences d'ergonomie commandent la mise en page :
 * - la barre de progression est TOUJOURS visible (en-tête collant). Savoir
 *   combien il reste est ce qui fait terminer ;
 * - à la reprise, on dit où on reprend, au lieu de replacer quelqu'un au
 *   milieu d'un cours sans explication ;
 * - la navigation avant/arrière est libre, mais revenir en arrière ne fait
 *   jamais reculer la progression enregistrée.
 */
export default function FormationPage() {
  const { token } = useParams()
  const [etat, setEtat] = useState('chargement')
  const [session, setSession] = useState(null)
  const [vue, setVue] = useState('cours')
  const [index, setIndex] = useState(0)
  const [reponses, setReponses] = useState({})
  const [resultat, setResultat] = useState(null)
  const [annonce, setAnnonce] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState('')
  const [demandeEnvoyee, setDemandeEnvoyee] = useState(false)
  const titreRef = useRef(null)
  const premierRendu = useRef(true)

  useEffect(() => {
    let annule = false
    formationApi
      .session(token)
      .then(({ data }) => {
        if (annule) return
        setSession(data)
        setIndex(data.resume_index)
        setEtat('pret')
        if (data.certificate) {
          setVue('reussi')
        } else if (data.screens_completed > 0 && data.screens_completed < data.screens_total) {
          // L'annonce de reprise : dite une fois, et lue par les lecteurs
          // d'écran grâce à la région live plus bas.
          setAnnonce(
            `Vous reprenez à l’écran ${data.resume_index + 1} sur ${data.screens_total}.`
          )
        }
      })
      .catch(() => {
        if (!annule) setEtat('expire')
      })
    return () => {
      annule = true
    }
  }, [token])

  // Le titre de l'écran reçoit le focus à chaque changement : sans cela, une
  // personne au clavier ou au lecteur d'écran reste sur le bouton « Suivant »
  // et n'entend jamais le nouveau contenu. Pas au premier rendu, où déplacer
  // le focus serait intrusif.
  useEffect(() => {
    if (premierRendu.current) {
      premierRendu.current = false
      return
    }
    titreRef.current?.focus()
  }, [index, vue])

  const ecran = session?.screens?.[index]
  const total = session?.screens_total ?? 0
  const faits = session?.screens_completed ?? 0
  const avancement = total ? Math.round((faits / total) * 100) : 0

  const marquerTermine = useCallback(async () => {
    if (!ecran || ecran.completed) return session
    const { data } = await formationApi.marquerEcran(token, ecran.id)
    setSession(data)
    return data
  }, [ecran, token, session])

  async function suivant() {
    setErreur('')
    try {
      const misAJour = await marquerTermine()
      if (index + 1 < total) {
        setIndex(index + 1)
      } else if (misAJour?.quiz_unlocked) {
        setVue('quiz')
      }
    } catch {
      setErreur("Votre progression n’a pas pu être enregistrée. Vérifiez votre connexion.")
    }
  }

  function basculer(question, choixId) {
    setReponses((actuelles) => {
      const dejaChoisis = actuelles[question.id] ?? []
      if (question.kind === 'single') return { ...actuelles, [question.id]: [choixId] }
      return {
        ...actuelles,
        [question.id]: dejaChoisis.includes(choixId)
          ? dejaChoisis.filter((id) => id !== choixId)
          : [...dejaChoisis, choixId],
      }
    })
  }

  async function envoyerLeQuiz() {
    setErreur('')
    setEnvoi(true)
    try {
      const { data } = await formationApi.soumettreQuiz(token, reponses)
      setResultat(data)
      setVue('resultat')
    } catch (err) {
      setErreur(err.response?.data?.detail ?? "Le questionnaire n’a pas pu être envoyé.")
    } finally {
      setEnvoi(false)
    }
  }

  function revoirEcran(ecranId) {
    const position = session.screens.findIndex((e) => e.id === ecranId)
    if (position >= 0) {
      setIndex(position)
      setVue('cours')
      setResultat(null)
      setReponses({})
    }
  }

  async function telechargerLattestation() {
    const reponse = await formationApi.attestation(token)
    const url = URL.createObjectURL(new Blob([reponse.data], { type: 'application/pdf' }))
    const lien = document.createElement('a')
    lien.href = url
    lien.download = 'attestation-de-suivi.pdf'
    lien.click()
    URL.revokeObjectURL(url)
  }

  async function demanderUnAcces() {
    try {
      await formationApi.demanderAcces(token)
    } finally {
      // Le message est le même dans tous les cas : le salarié n'a pas à
      // connaître le rythme d'envoi, et l'échec ne doit pas l'inquiéter.
      setDemandeEnvoyee(true)
    }
  }

  if (etat === 'chargement') {
    return (
      <Cadre>
        <p className="flex items-center gap-2 text-sm text-ink-600">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          Chargement de votre formation…
        </p>
      </Cadre>
    )
  }

  if (etat === 'expire') {
    return (
      <Cadre>
        <h1 className="text-xl font-semibold text-ink-900">Ce lien n’est plus valable</h1>
        <p className="mt-3 text-ink-700">
          La période de formation est terminée, ou cet accès a été retiré.
        </p>
        {demandeEnvoyee ? (
          <p className="mt-4 flex items-start gap-2 rounded-lg border border-ok-200 bg-ok-50 p-3 text-sm text-ink-800">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok-strong" aria-hidden="true" />
            Votre demande a été transmise aux responsables de votre entreprise. Ils vous
            renverront un accès.
          </p>
        ) : (
          <>
            <p className="mt-2 text-sm text-ink-600">
              Vous pouvez demander un nouvel accès : votre entreprise en sera prévenue.
            </p>
            <Button className="mt-4 w-full sm:w-auto" onClick={demanderUnAcces}>
              Demander un nouvel accès
            </Button>
          </>
        )}
      </Cadre>
    )
  }

  return (
    <div className="min-h-screen bg-ink-50">
      {/* En-tête collant : la progression reste sous les yeux, y compris sur
          un téléphone où le contenu défile. */}
      <header className="sticky top-0 z-10 border-b border-ink-200 bg-white">
        <div className="mx-auto max-w-2xl px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-medium text-ink-700">
            <GraduationCap className="size-4 text-brand-700" aria-hidden="true" />
            <span className="truncate">{session.course_title}</span>
          </div>
          <div className="mt-2 flex items-center gap-3">
            <div
              className="h-2 flex-1 overflow-hidden rounded-full bg-ink-200"
              role="progressbar"
              aria-valuenow={avancement}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Progression dans le cours"
            >
              <div
                className="h-full rounded-full bg-brand-600 transition-all"
                style={{ width: `${avancement}%` }}
              />
            </div>
            <span className="shrink-0 text-sm tabular-nums text-ink-600">
              {vue === 'cours' ? `Écran ${index + 1} sur ${total}` : `${faits}/${total}`}
            </span>
          </div>
        </div>
      </header>

      {/* Région live : la reprise et les changements d'étape y sont annoncés
          aux lecteurs d'écran, qui ne voient pas la barre de progression. */}
      <p aria-live="polite" className="sr-only">
        {annonce}
      </p>

      <main className="mx-auto max-w-2xl px-4 py-6">
        {/* Un seul titre de niveau un, porté par la PAGE et non par l'une de
            ses vues. Il était d'abord placé dans la branche « cours » : les
            écrans du quiz et du résultat se retrouvaient donc sans titre de
            niveau un, ce qui prive un lecteur d'écran du repère qui dit où
            l'on est. Relevé par l'audit d'accessibilité en navigateur.
            Visuellement masqué : le bandeau collant affiche déjà le titre. */}
        <h1 className="sr-only">{session.course_title}</h1>
        {annonce && vue === 'cours' && (
          <p className="mb-4 rounded-lg border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-ink-800">
            {annonce}
          </p>
        )}

        {erreur && (
          <p role="alert" className="mb-4 rounded-lg bg-critical-50 px-4 py-3 text-sm text-critical-strong">
            {erreur}
          </p>
        )}

        {vue === 'cours' && ecran && (
          <article>
            <h2
              ref={titreRef}
              tabIndex={-1}
              className="text-2xl font-semibold text-ink-900 focus-visible:outline-2 focus-visible:outline-brand-600"
            >
              {ecran.title}
            </h2>
            <div className="mt-5">
              <ContenuEcran blocs={ecran.content} />
            </div>

            <nav
              className="mt-8 flex flex-col-reverse gap-3 sm:flex-row sm:justify-between"
              aria-label="Navigation dans le cours"
            >
              <Button
                variant="secondary"
                className="w-full sm:w-auto"
                disabled={index === 0}
                onClick={() => setIndex(index - 1)}
              >
                <ArrowLeft className="size-4" aria-hidden="true" />
                Précédent
              </Button>
              <Button className="w-full sm:w-auto" onClick={suivant}>
                {index + 1 < total ? 'Suivant' : 'Passer au questionnaire'}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Button>
            </nav>
          </article>
        )}

        {vue === 'quiz' && (
          <section>
            <h2
              ref={titreRef}
              tabIndex={-1}
              className="text-2xl font-semibold text-ink-900 focus-visible:outline-2 focus-visible:outline-brand-600"
            >
              Questionnaire
            </h2>
            <p className="mt-2 text-sm text-ink-600">
              {session.quiz.length} questions. Il faut {session.pass_threshold} % de bonnes
              réponses. Essai {session.attempts_used + 1} sur {session.attempts_allowed}.
            </p>

            <ol className="mt-6 space-y-6">
              {session.quiz.map((question, rang) => (
                <li key={question.id}>
                  <fieldset>
                    <legend className="font-medium text-ink-900">
                      {rang + 1}. {question.text}
                      {question.kind === 'multiple' && (
                        <span className="ml-2 text-sm font-normal text-ink-500">
                          (plusieurs réponses possibles)
                        </span>
                      )}
                    </legend>
                    <div className="mt-3 space-y-2">
                      {question.choices.map((choix) => (
                        <label
                          key={choix.id}
                          className="flex cursor-pointer items-start gap-3 rounded-lg border border-ink-200 bg-white p-3 hover:border-brand-400"
                        >
                          <input
                            type={question.kind === 'single' ? 'radio' : 'checkbox'}
                            name={question.id}
                            className="mt-1 size-4"
                            checked={(reponses[question.id] ?? []).includes(choix.id)}
                            onChange={() => basculer(question, choix.id)}
                          />
                          <span className="text-ink-800">{choix.text}</span>
                        </label>
                      ))}
                    </div>
                  </fieldset>
                </li>
              ))}
            </ol>

            <Button className="mt-8 w-full" loading={envoi} onClick={envoyerLeQuiz}>
              Valider mes réponses
            </Button>
          </section>
        )}

        {vue === 'resultat' && resultat && (
          <Resultat
            resultat={resultat}
            onRevoir={revoirEcran}
            onRecommencer={() => {
              setReponses({})
              setResultat(null)
              setVue('quiz')
            }}
            onTelecharger={telechargerLattestation}
          />
        )}

        {vue === 'reussi' && (
          <section className="text-center">
            <CheckCircle2 className="mx-auto size-10 text-ok-strong" aria-hidden="true" />
            <h2 ref={titreRef} tabIndex={-1} className="mt-3 text-2xl font-semibold text-ink-900">
              Vous avez déjà terminé ce cours
            </h2>
            <p className="mt-2 text-ink-700">
              Votre attestation de suivi reste disponible.
            </p>
            <Button className="mt-6 w-full sm:w-auto" onClick={telechargerLattestation}>
              <Download className="size-4" aria-hidden="true" />
              Télécharger mon attestation
            </Button>
          </section>
        )}
      </main>
    </div>
  )
}

function Resultat({ resultat, onRevoir, onRecommencer, onTelecharger }) {
  const essaisRestants = resultat.attempts_allowed - resultat.attempts_used
  return (
    <section>
      <h2 className="text-2xl font-semibold text-ink-900">
        {resultat.passed ? 'Cours validé' : 'Ce n’est pas encore validé'}
      </h2>
      <p className="mt-2 text-ink-700">
        Vous avez {resultat.score} % de bonnes réponses. Le seuil est fixé à{' '}
        {resultat.pass_threshold} %.
      </p>

      {resultat.passed ? (
        <Button className="mt-5 w-full sm:w-auto" onClick={onTelecharger}>
          <Download className="size-4" aria-hidden="true" />
          Télécharger mon attestation
        </Button>
      ) : (
        <div className="mt-5 rounded-lg border border-ink-200 bg-white p-4">
          {resultat.screens_to_review.length > 0 && (
            <>
              <h3 className="font-medium text-ink-900">À revoir avant de réessayer</h3>
              <p className="mt-1 text-sm text-ink-600">
                Seulement les écrans concernés par vos erreurs — pas tout le cours.
              </p>
              <ul className="mt-3 space-y-2">
                {resultat.screens_to_review.map((ecran) => (
                  <li key={ecran.id}>
                    <button
                      type="button"
                      onClick={() => onRevoir(ecran.id)}
                      className="w-full rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-left text-sm font-medium text-brand-800 hover:border-brand-400"
                    >
                      Écran {ecran.order} — {ecran.title}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
          {essaisRestants > 0 ? (
            <Button variant="secondary" className="mt-4 w-full" onClick={onRecommencer}>
              <RotateCcw className="size-4" aria-hidden="true" />
              Refaire le questionnaire ({essaisRestants} essai
              {essaisRestants > 1 ? 's' : ''} restant{essaisRestants > 1 ? 's' : ''})
            </Button>
          ) : (
            <p className="mt-4 text-sm text-ink-700">
              Vous avez utilisé vos essais. Demandez à votre responsable de vous en accorder un
              nouveau.
            </p>
          )}
        </div>
      )}

      <h3 className="mt-8 font-medium text-ink-900">Le détail, question par question</h3>
      <ol className="mt-3 space-y-4">
        {resultat.questions.map((question, rang) => (
          <li
            key={question.id}
            className={`rounded-lg border-l-4 bg-white p-4 ${
              question.correct ? 'border-ok-strong' : 'border-critical-strong'
            }`}
          >
            <p className="font-medium text-ink-900">
              <span className="sr-only">{question.correct ? 'Juste. ' : 'Faux. '}</span>
              {rang + 1}. {question.text}
            </p>
            {/* L'explication est donnée dans les deux cas : celui qui a bien
                répondu n'avait pas forcément la bonne raison. */}
            <p className="mt-2 text-sm leading-relaxed text-ink-700">{question.explanation}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}

function Cadre({ children }) {
  // `main` et non `div` : c'est la région principale de la page. Sans elle,
  // un lecteur d'écran n'a aucun repère pour sauter directement au contenu —
  // et il n'y a rien d'autre sur ces écrans. Défaut relevé par l'audit
  // d'accessibilité en navigateur réel, pas par les tests de composant.
  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-50 px-4">
      <main className="w-full max-w-md rounded-xl border border-ink-200 bg-white p-6 shadow-sm">
        {children}
      </main>
    </div>
  )
}
