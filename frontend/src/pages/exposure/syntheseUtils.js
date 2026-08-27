/**
 * Découpe la synthèse d'exposition en ses trois moments.
 *
 * Le prompt serveur (`EXPOSURE_SYNTHESIS_SYSTEM_PROMPT`) impose une structure
 * en 3 à 5 phrases : « d'abord une lecture d'ensemble en une phrase, puis les
 * corrélations notables si elles existent, puis LA priorité n°1 de la semaine,
 * formulée comme une action concrète. »
 *
 * On s'appuie donc sur la POSITION, pas sur des mots-clés : première phrase =
 * lecture d'ensemble, dernière = priorité, le milieu = corrélations. Chercher
 * « priorité » dans le texte casserait à la première reformulation du modèle ;
 * l'ordre, lui, est ce que le prompt garantit.
 *
 * Le découpage échoue proprement : une synthèse d'une seule phrase n'a pas de
 * priorité séparée (on n'affiche pas deux fois la même chose), et un texte
 * vide ne produit rien plutôt qu'un bloc vide.
 */
export function decouperSynthese(texte) {
  const propre = (texte || '').trim()
  if (!propre) return { lead: '', correlations: [], priorite: '' }

  // Découpage sur la ponctuation forte suivie d'une espace et d'une majuscule.
  // Volontairement conservateur : mieux vaut une phrase trop longue qu'une
  // coupure au milieu d'une adresse (« exemple.fr. Le reste » ne doit pas
  // couper « .fr »).
  const phrases = propre
    .split(/(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ«])/u)
    .map((p) => p.trim())
    .filter(Boolean)

  if (phrases.length === 0) return { lead: propre, correlations: [], priorite: '' }
  if (phrases.length === 1) return { lead: phrases[0], correlations: [], priorite: '' }

  return {
    lead: phrases[0],
    correlations: phrases.slice(1, -1),
    priorite: phrases[phrases.length - 1],
  }
}
