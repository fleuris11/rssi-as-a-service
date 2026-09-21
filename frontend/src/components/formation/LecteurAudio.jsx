import { Pause, Play, Square, Volume2 } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { choisirVoixFrancaise, fileDeLecture } from './lectureAudio'

/**
 * La lecture à voix haute d'un écran, par la synthèse du navigateur.
 *
 * Aucun appel réseau, aucun fichier : la voix est celle du système de
 * l'apprenant, et le texte ne quitte jamais son appareil. C'est ce qui permet
 * de lire un écran contextualisé — « vos 3 comptes compromis » — sans confier
 * les chiffres d'un client à un tiers (ADR-040).
 *
 * L'audio est une AIDE. Si le navigateur ne sait pas parler, ou si l'appareil
 * n'a aucune voix française, le cours reste entièrement utilisable : on
 * n'affiche rien, ou une phrase discrète, jamais une erreur.
 */

const CLE_VITESSE = 'rssi.formation.audio.vitesse'
const CLE_CONTINUER = 'rssi.formation.audio.continuer'
const VITESSES = [0.8, 1, 1.25]

function lirePreference(cle, defaut) {
  try {
    const valeur = localStorage.getItem(cle)
    return valeur === null ? defaut : JSON.parse(valeur)
  } catch {
    // Navigation privée, stockage bloqué : ce n'est pas une panne, c'est un
    // réglage en moins.
    return defaut
  }
}

function ecrirePreference(cle, valeur) {
  try {
    localStorage.setItem(cle, JSON.stringify(valeur))
  } catch {
    /* sans effet : la préférence ne sera pas retenue, le lecteur fonctionne */
  }
}

function moteur() {
  return typeof window !== 'undefined' ? window.speechSynthesis : undefined
}

export default function LecteurAudio({ blocs, cleEcran }) {
  const synthese = moteur()
  const [voix, setVoix] = useState([])
  const [voixChargees, setVoixChargees] = useState(false)
  const [etat, setEtat] = useState('inactif')
  const [vitesse, setVitesse] = useState(() => lirePreference(CLE_VITESSE, 1))
  const file = useRef([])
  const position = useRef(0)
  const interrompu = useRef(false)

  // Les voix arrivent de façon asynchrone sur plusieurs navigateurs : la
  // première interrogation renvoie une liste vide, remplie plus tard. Lire
  // une seule fois ferait conclure à tort « aucune voix française ».
  useEffect(() => {
    if (!synthese) {
      setVoixChargees(true)
      return undefined
    }
    const relever = () => {
      const disponibles = synthese.getVoices()
      if (disponibles.length > 0) {
        setVoix(disponibles)
        setVoixChargees(true)
      }
    }
    relever()
    synthese.addEventListener?.('voiceschanged', relever)
    // Repli pour les moteurs qui n'émettent jamais l'événement : au bout
    // d'une seconde, on se contente de ce qu'on a.
    const minuteur = setTimeout(() => setVoixChargees(true), 1000)
    return () => {
      synthese.removeEventListener?.('voiceschanged', relever)
      clearTimeout(minuteur)
    }
  }, [synthese])

  const arreter = useCallback(() => {
    interrompu.current = true
    synthese?.cancel()
    setEtat('inactif')
  }, [synthese])

  const voixFrancaise = choisirVoixFrancaise(voix)

  const enoncerDepuis = useCallback(
    (index) => {
      if (!synthese || interrompu.current) return
      if (index >= file.current.length) {
        setEtat('inactif')
        return
      }
      position.current = index
      const enonce = new SpeechSynthesisUtterance(file.current[index])
      if (voixFrancaise) {
        enonce.voice = voixFrancaise
        enonce.lang = voixFrancaise.lang
      }
      enonce.rate = vitesse
      enonce.onend = () => enoncerDepuis(index + 1)
      // Une erreur de moteur ne doit pas figer le lecteur sur « lecture ».
      enonce.onerror = () => setEtat('inactif')
      synthese.speak(enonce)
    },
    [synthese, voixFrancaise, vitesse]
  )

  const lire = useCallback(() => {
    if (!synthese) return
    synthese.cancel()
    interrompu.current = false
    file.current = fileDeLecture(blocs)
    if (file.current.length === 0) return
    setEtat('lecture')
    ecrirePreference(CLE_CONTINUER, true)
    enoncerDepuis(0)
  }, [synthese, blocs, enoncerDepuis])

  // Changement d'écran, ou sortie de la page : on coupe.
  //
  // C'est LE défaut classique de cette API — la voix poursuit le texte de
  // l'écran précédent pendant qu'on lit le suivant, et rien ne le signale.
  // La dépendance est `cleEcran` : elle change à chaque écran, le nettoyage
  // s'exécute donc entre les deux.
  useEffect(() => {
    return () => {
      interrompu.current = true
      moteur()?.cancel()
    }
  }, [cleEcran])

  // Reprise automatique à l'écran suivant, mais seulement pour qui écoutait.
  // Quelqu'un qui a coupé le son ne doit pas le voir revenir tout seul.
  useEffect(() => {
    setEtat('inactif')
    if (!synthese || !voixChargees || !voixFrancaise) return
    if (!lirePreference(CLE_CONTINUER, false)) return
    lire()
    // `lire` change à chaque rendu utile ; on ne veut déclencher que sur
    // l'écran et la disponibilité des voix.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cleEcran, voixChargees, Boolean(voixFrancaise)])

  // Chrome desktop suspend la synthèse au bout d'une quinzaine de secondes.
  // Le contournement connu est de la relancer périodiquement. Il ne
  // s'applique QUE pendant une lecture en cours : appelé sur une pause
  // volontaire, il la ferait repartir contre la volonté de l'apprenant.
  useEffect(() => {
    if (etat !== 'lecture' || !synthese) return undefined
    const battement = setInterval(() => {
      if (synthese.speaking && !synthese.paused) synthese.resume()
    }, 10000)
    return () => clearInterval(battement)
  }, [etat, synthese])

  function basculerPause() {
    if (!synthese) return
    if (etat === 'lecture') {
      synthese.pause()
      setEtat('pause')
    } else if (etat === 'pause') {
      synthese.resume()
      setEtat('lecture')
    }
  }

  function couper() {
    // Couper est un choix : il vaut pour les écrans suivants.
    ecrirePreference(CLE_CONTINUER, false)
    arreter()
  }

  function changerVitesse(nouvelle) {
    setVitesse(nouvelle)
    ecrirePreference(CLE_VITESSE, nouvelle)
    if (etat === 'lecture') {
      // Le débit d'un énoncé déjà en cours ne se change pas : on relance à
      // partir de l'énoncé courant, plutôt que du début de l'écran.
      const reprise = position.current
      interrompu.current = true
      synthese.cancel()
      setTimeout(() => {
        interrompu.current = false
        setEtat('lecture')
        enoncerDepuis(reprise)
      }, 0)
    }
  }

  // Le navigateur ne sait pas parler : rien à proposer, et rien à expliquer.
  if (!synthese) return null

  if (voixChargees && !voixFrancaise) {
    return (
      <p className="text-xs text-ink-500">Lecture audio indisponible sur cet appareil.</p>
    )
  }

  if (!voixChargees) return null

  return (
    <div className="flex flex-wrap items-center gap-2">
      {etat === 'inactif' ? (
        <button
          type="button"
          onClick={lire}
          className="inline-flex items-center gap-1.5 rounded-md border border-ink-200 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-50"
        >
          <Volume2 className="size-4" aria-hidden="true" />
          Écouter cet écran
        </button>
      ) : (
        <>
          <button
            type="button"
            onClick={basculerPause}
            className="inline-flex items-center gap-1.5 rounded-md border border-ink-200 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-50"
          >
            {etat === 'pause' ? (
              <Play className="size-4" aria-hidden="true" />
            ) : (
              <Pause className="size-4" aria-hidden="true" />
            )}
            {etat === 'pause' ? 'Reprendre' : 'Pause'}
          </button>
          <button
            type="button"
            onClick={couper}
            className="inline-flex items-center gap-1.5 rounded-md border border-ink-200 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-50"
          >
            <Square className="size-4" aria-hidden="true" />
            Arrêter
          </button>
        </>
      )}

      <fieldset className="flex items-center gap-1">
        <legend className="sr-only">Vitesse de lecture</legend>
        {VITESSES.map((valeur) => (
          <button
            key={valeur}
            type="button"
            aria-pressed={vitesse === valeur}
            onClick={() => changerVitesse(valeur)}
            className={`rounded-md px-2 py-1 text-xs font-medium ${
              vitesse === valeur
                ? 'bg-brand-600 text-white'
                : 'border border-ink-200 text-ink-600 hover:bg-ink-50'
            }`}
          >
            ×{valeur.toString().replace('.', ',')}
          </button>
        ))}
      </fieldset>
    </div>
  )
}
