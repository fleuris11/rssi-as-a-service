import { useState } from 'react'

/**
 * Une capture réelle du produit si le fichier existe, sinon le substitut.
 *
 * `public/screenshots/README.md` décrivait trois emplacements de capture et la
 * marche à suivre pour les produire. **Aucun code ne lisait ces fichiers** :
 * déposer `exposition.png` ne changeait rien à la page. Le document décrivait
 * une intention, pas un comportement — quatrième occurrence du même motif sur
 * ce projet, après le README annonçant DKIM, le registre de fonctionnalités
 * sans gardes, et un commentaire de contraste faux.
 *
 * La correction rend le document vrai plutôt que de le réécrire : le fichier
 * est demandé, et s'il n'existe pas (404, chemin faux, image corrompue), on
 * retombe sur la reconstitution CSS. Déposer le PNG suffit donc réellement,
 * sans toucher au code — ce que le README promettait depuis le début.
 *
 * Le repli par `onError` plutôt qu'un inventaire codé en dur : un inventaire
 * serait une seconde chose à tenir à jour, donc une seconde chose à laisser
 * dériver.
 */
export default function CaptureProduit({ src, alt, children }) {
  const [echec, setEchec] = useState(false)

  if (!src || echec) return children

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      // `block` : sans lui, l'image reste une boîte en ligne et laisse
      // quelques pixels de blanc sous elle, dans le cadre.
      className="block w-full"
      onError={() => setEchec(true)}
    />
  )
}
