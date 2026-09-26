/**
 * LE LOGO, en un seul endroit.
 *
 * Il y avait un monogramme dessiné à la place, lisant « net ». C'était une
 * erreur de lecture d'une consigne — « le net monogramme » voulait dire *un
 * monogramme net*, c'est-à-dire lisible, pas un monogramme portant le mot
 * « net ». Le logo de la marque reprend sa place.
 *
 * **Pourquoi il paraissait flou avant.** Les fichiers servis mesuraient 64 px
 * de côté pour l'emblème, affichés à 32 : aucune marge sur un écran à forte
 * densité, et le dessin du bouclier est détaillé. Les fichiers sont désormais
 * découpés dans `og-image.webp`, où le logo fait 968 px de large, et servis en
 * trois densités (128 / 256 / 384).
 *
 * **Pourquoi il garde son fond sombre.** Le fond noir bleuté fait partie du
 * dessin : le halo, le reflet du socle et le contour chromé n'existent que
 * sur un fond sombre. Un détourage par luminance rendrait l'intérieur du
 * bouclier translucide — sur une page claire, le bouclier deviendrait blanc.
 * Sur la face d'instrument, le logo est donc posé sur une plaque graphite
 * assumée, de la matière du bâti ; sur le bâti, la plaque se confond avec le
 * fond et disparaît d'elle-même.
 */

/** L'emblème seul : bouclier, R, orbite. Là où la place manque. */
export function Embleme({ taille = 'size-9', className = '' }) {
  return (
    <img
      src="/logo-embleme.webp"
      srcSet="/logo-embleme.webp 1x, /logo-embleme@2x.webp 2x, /logo-embleme@3x.webp 3x"
      width="128"
      height="128"
      alt=""
      aria-hidden="true"
      // Le filet rend la plaque DELIBEREE : le fond du logo est plus sombre
      // que le bati, et sans bord l'ecart se lit comme une erreur de
      // decoupe. Avec un filet, c'est une plaque — la grammaire du produit.
      className={`${taille} shrink-0 rounded-sm object-cover ring-1 ring-bati-600 ${className}`}
    />
  )
}

/**
 * Le logo complet : emblème + « RSSI as Service » + la ligne de signature.
 *
 * À préférer partout où la largeur le permet. Un bouclier de 32 px demande au
 * lecteur de deviner la marque ; le bloc complet la donne.
 */
export function LogoComplet({ hauteur = 'h-9', className = '' }) {
  return (
    <img
      src="/logo-complet.webp"
      srcSet="/logo-complet.webp 1x, /logo-complet@2x.webp 2x"
      width="360"
      height="144"
      alt="RSSI as a Service"
      className={`${hauteur} w-auto rounded-sm ring-1 ring-bati-600 ${className}`}
    />
  )
}

/**
 * La marque telle qu'elle apparaît dans une barre : l'emblème et le nom.
 *
 * Le nom reste du TEXTE et non une image : il se sélectionne, se traduit, se
 * lit par un lecteur d'écran, et suit la graisse de la typographie du
 * produit. L'emblème, lui, porte l'identité.
 */
export default function Logo({ sombre = false, taille = 'size-9', className = '' }) {
  return (
    <span className={`flex items-center gap-2.5 ${className}`}>
      <Embleme taille={taille} />
      <span
        className={`font-display text-base font-semibold ${sombre ? 'text-craie' : 'text-ink-900'}`}
        style={{ fontVariationSettings: "'wdth' 92" }}
      >
        RSSI as a Service
      </span>
    </span>
  )
}
