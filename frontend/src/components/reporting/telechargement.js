/**
 * Période et téléchargement des exports du rapport (V2-3, partagés au lot C).
 *
 * Le tableau de bord et la page Rapports exportent la MÊME chose : deux
 * façons de composer les paramètres finiraient par produire un PDF qui ne
 * couvre pas la période affichée à l'écran.
 */

export function parametresDePeriode(periode, personnalisee) {
  return periode === 'custom'
    ? { period: 'custom', start: personnalisee.start, end: personnalisee.end }
    : { period: periode }
}

/** Une plage personnalisée incomplète ne déclenche aucun calcul serveur. */
export function periodePrete(periode, personnalisee) {
  return periode !== 'custom' || Boolean(personnalisee.start && personnalisee.end)
}

/**
 * Enregistre la réponse d'un export. Le nom du fichier vient du serveur :
 * c'est lui qui connaît la période et le nom du client.
 */
export function telechargerReponse(reponse, nomParDefaut) {
  const entete = reponse.headers?.['content-disposition'] || ''
  const nom = /filename="([^"]+)"/.exec(entete)?.[1] || nomParDefaut
  const url = URL.createObjectURL(new Blob([reponse.data]))
  const lien = document.createElement('a')
  lien.href = url
  lien.download = nom
  lien.click()
  URL.revokeObjectURL(url)
}
