/**
 * Ce qu'il y a à lire dans un écran, et comment le découper.
 *
 * Séparé du composant pour être testable sans navigateur : le découpage est
 * la partie qui se trompe silencieusement, et c'est elle qu'on veut épingler.
 */

import { sansMarques } from './texteRiche'

//: Au-delà, plusieurs navigateurs coupent la lecture en plein milieu sans
//: rien signaler. La limite est prudente : le défaut est connu, son seuil
//: exact ne l'est pas, et il varie d'un moteur à l'autre.
export const LONGUEUR_MAX_ENONCE = 200

/**
 * Le texte d'un écran, bloc par bloc, dans l'ordre de lecture.
 *
 * Les images ne sont pas « sautées » au sens strict : on lit leur texte
 * alternatif. C'est précisément à ça qu'il sert — décrire ce que l'image
 * montre à qui ne la voit pas. Une image sans alternative est impossible
 * (le serveur la refuse à l'écriture), mais on se garde du cas.
 */
export function textesDesBlocs(blocs = []) {
  const morceaux = []
  for (const bloc of blocs) {
    switch (bloc.type) {
      case 'paragraphe':
      case 'titre':
      case 'encadre':
      case 'citation':
        morceaux.push(bloc.texte)
        break
      case 'liste':
        // Chaque entrée est un énoncé : une liste de huit items lue d'un
        // trait est incompréhensible à l'oreille.
        morceaux.push(...(bloc.items ?? []))
        break
      case 'image':
        if (bloc.alternative) morceaux.push(bloc.alternative)
        break
      default:
        break
    }
  }
  // Les marques de gras sont retirées : une voix qui prononce « étoile
  // étoile jamais étoile étoile » est pire que pas de voix du tout.
  return morceaux
    .filter((texte) => typeof texte === 'string' && texte.trim())
    .map((texte) => sansMarques(texte))
}

/**
 * Découpe un texte long en énoncés courts, sur la ponctuation forte.
 *
 * On ne coupe pas au milieu d'un mot : un énoncé plus long que la limite mais
 * insécable est renvoyé tel quel. Mieux vaut risquer une coupure du moteur
 * que produire « votre entre / prise ».
 */
export function decouper(texte, maximum = LONGUEUR_MAX_ENONCE) {
  const propre = texte.trim()
  if (propre.length <= maximum) return [propre]

  const phrases = propre.split(/(?<=[.!?…:])\s+/)
  const enonces = []
  let courant = ''
  for (const phrase of phrases) {
    if (!courant) {
      courant = phrase
    } else if (`${courant} ${phrase}`.length <= maximum) {
      courant = `${courant} ${phrase}`
    } else {
      enonces.push(courant)
      courant = phrase
    }
  }
  if (courant) enonces.push(courant)
  return enonces
}

/** La file d'énoncés d'un écran : blocs découpés, à la suite. */
export function fileDeLecture(blocs) {
  return textesDesBlocs(blocs).flatMap((texte) => decouper(texte))
}

/**
 * La voix française à utiliser, ou null.
 *
 * `fr-FR` d'abord, puis n'importe quel français (`fr-CA`, `fr-BE`) : mieux
 * vaut un accent québécois que pas de voix. Aucune préférence de marque —
 * les noms de voix diffèrent sur chaque système, et s'y fier casserait le
 * choix partout ailleurs.
 */
export function choisirVoixFrancaise(voix = []) {
  const francaises = voix.filter((v) => (v.lang ?? '').toLowerCase().startsWith('fr'))
  if (francaises.length === 0) return null
  return francaises.find((v) => (v.lang ?? '').toLowerCase() === 'fr-fr') ?? francaises[0]
}
