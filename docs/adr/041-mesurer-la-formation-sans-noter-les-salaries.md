# ADR-041 — Mesurer la formation sans noter les salariés

- **Statut** : accepté
- **Date** : 2026-09-21
- **Contexte** : Module Formation, lot 3 (F3). Prolonge
  [ADR-039](039-former-les-salaries-sans-leur-creer-de-compte.md) et
  [ADR-040](040-studio-voix-et-contextualisation.md), et reprend la logique de
  déclaration de [ADR-033](033-comptes-designes.md).
- **⚠️ Le contrat de sous-traitance doit couvrir ce traitement** : voir §6.

## Contexte

Les deux premiers lots permettaient de former. Celui-ci permet de **mesurer**,
et c'est là que le module devient sensible : mesurer la formation de salariés,
c'est produire des données sur des personnes, dans une relation de
subordination, pour le compte de leur employeur.

Le produit peut techniquement tout faire : classer, comparer, afficher les
mauvais élèves. La question n'est pas ce qu'il peut faire, mais ce qu'il doit
refuser de faire.

## Décision 1 — Aucun classement des salariés par score

**Le score individuel n'est publié nulle part.** Ni dans la liste de suivi, ni
dans les exports, ni dans le rapport de comité.

Un module de sensibilisation qui produit un palmarès cesse d'être un outil de
prévention pour devenir un **outil de notation** : il alimenterait des
entretiens d'évaluation, des décisions de carrière, éventuellement des
sanctions — pour un quiz de six questions passé entre deux réunions.

La garantie est structurelle : la fonction qui rend le suivi nominatif ne
produit **que** quatre informations utiles à la relance — nom, adresse, cours,
état (pas commencé / en cours / terminé) — et un test épingle la liste exacte
des clés. Ajouter un score ferait rougir ce test.

Le score existe : il est dans l'attestation du salarié, qui lui appartient, et
dans la **moyenne** collective. Jamais dans une liste triable.

## Décision 2 — L'agrégé d'abord, le nominatif tracé

Tout ce que le module publie spontanément est collectif : participation,
réussite, moyenne, questions les plus ratées.

La liste par salarié existe pour **une seule raison** : savoir qui relancer.
Elle est donc :

- réservée aux **administrateurs** de l'entreprise ;
- **enregistrée à chaque consultation** (`NominativeAccessLog` : qui, quand,
  combien de lignes) ;
- **jamais chargée à l'ouverture de l'écran** — il faut cliquer. Une
  consultation tracée qui partirait d'un simple affichage de page remplirait le
  journal sans rien signifier ;
- accompagnée, dans la réponse même, de la phrase qui dit qu'elle est
  enregistrée.

Le journal d'accès **ne recopie pas** les données qu'il protège : il compte des
lignes, il ne les stocke pas. Un journal qui recopierait les noms serait un
second fichier du même traitement.

## Décision 3 — Les questions les plus ratées, plutôt que les salariés les plus faibles

C'est le même chiffre retourné, et ce n'est pas la même chose.

« Quatre salariés sur six ont raté la question sur l'urgence » désigne un sujet
mal expliqué. « Camille a raté quatre questions » désigne une personne. Le
module publie le premier et refuse le second.

Une question n'apparaît qu'à partir de **trois réponses**. En deçà, le chiffre
ne dit rien de statistique — et il désignerait quelqu'un.

## Décision 4 — Les relances, et le droit de les couper

Trois moments au plus : à mi-parcours, avant l'échéance, après. Chacun se coupe
séparément, et tout se coupe d'un bouton.

Trois garde-fous, dans le code et pas dans l'intention :

1. **une relance par nature et par inscription**, garantie par une contrainte
   d'unicité en base — pas par une condition qu'une tâche quotidienne pourrait
   réévaluer chaque jour ;
2. **un salarié qui a terminé ne reçoit plus rien** ;
3. **une seule relance par jour et par salarié**, même quand deux moments
   tombent le même jour sur une campagne courte.

Une relance qu'on ne peut pas couper devient du harcèlement — et le harcèlement
par un outil que l'employeur a acheté reste du harcèlement.

**Chaque relance porte un lien neuf**, qui remplace le précédent. Ce n'est pas
un choix de confort : le jeton n'est stocké que haché (ADR-039), on ne peut pas
rappeler le lien envoyé, seulement en émettre un autre. Le message le dit au
salarié. Effet secondaire utile : un lien qui dort dans une vieille boîte aux
lettres s'éteint à chaque relance.

## Décision 5 — Durée de conservation

| Donnée | Sort |
|---|---|
| Tentatives et réponses question par question | **effacées après 24 mois** (réglable), par une tâche mensuelle |
| Attestations | **conservées** |
| Journal des accès nominatifs | conservé avec les attestations |

Le partage n'est pas arbitraire. Les tentatives sont la partie **détaillée et
nominative** du traitement : qui a répondu quoi, et combien de fois. Passé deux
ans, elles ne servent plus ni à relancer, ni à prouver, ni à améliorer un
cours.

Les attestations, elles, **sont la preuve** que l'entreprise a formé ses
salariés. Les détruire lui retirerait le bénéfice du traitement qu'elle a mis
en œuvre, et c'est le document qu'un auditeur demandera. Leur effacement relève
d'une demande du salarié ou de la fin de la relation contractuelle — deux
événements que le produit ne connaît pas, et qu'il ne doit donc pas deviner.

## Décision 6 — Ce qui doit être validé par un juriste

Le client est **responsable de traitement**, nous sommes **sous-traitant** :
nous agissons sur ses instructions, sur les données de ses salariés.

Trois points **à faire couvrir par le contrat de sous-traitance**, et qui ne
relèvent pas du code :

1. **la finalité** : sensibilisation à la sécurité, à l'exclusion de toute
   évaluation professionnelle. C'est ce qui justifie l'absence de classement
   — et ce qui l'interdirait au client qui voudrait en produire un lui-même à
   partir des exports ;
2. **l'information des salariés** : ils doivent savoir que leur suivi est
   enregistré, par qui il est consultable, et combien de temps il est conservé.
   Le produit ne peut pas s'en charger à la place de l'employeur ;
3. **la durée de conservation** retenue ci-dessus, et le sort des attestations.

## Décision 7 — La formation prouve une mesure, elle ne la valide pas

Une campagne qui atteint **80 % de participation et 80 % de réussite**, sur au
moins **trois salariés**, peut renseigner la mesure de sensibilisation du guide
d'hygiène ANSSI (mesure 2).

**C'est une proposition.** Le produit refuse depuis le début de cocher une case
de conformité à la place de quelqu'un : une mesure renseignée sans qu'une
personne l'ait décidée est une affirmation que le client n'a pas faite, et
qu'il découvrirait devant un auditeur.

Le mécanisme, en conséquence :

- une proposition est créée, avec ses **chiffres figés** — relire le taux six
  mois plus tard donnerait un autre nombre, et la preuve ne prouverait plus ce
  qu'elle disait ;
- elle attend une confirmation humaine, et conserve **qui a tranché** ;
- elle se reporte dans le **diagnostic en cours** uniquement. Écrire dans un
  diagnostic terminé reviendrait à modifier un résultat déjà restitué ; en
  ouvrir un nouveau serait prendre la décision qu'on laisse au client ;
- la note déposée porte les chiffres et les dates, parce que c'est elle que
  lira l'auditeur ;
- une proposition **écartée n'est pas reproposée**. La reproposer chaque nuit
  ferait du produit un automate insistant.

## Conséquences

- Quatre tables nouvelles (`ReminderPolicy`, `ReminderLog`, `MeasureSuggestion`,
  `NominativeAccessLog`), quatre tâches planifiées, quatre types de
  notification branchés sur le centre livré au lot C.
- Le rapport de comité gagne un volet formation, **collectif uniquement** : ce
  document circule et s'archive.
- Une **campagne** n'est pas une table : c'est un cours et une échéance. Le
  couple suffit à distinguer deux campagnes, et éviter une table de plus évite
  d'avoir à la tenir à jour.
- Un défaut trouvé en construisant, et qui vaut avertissement : la fonction qui
  balaie les relances tourne **hors contexte de cloisonnement** (elle traverse
  tous les clients). Les managers cloisonnés y échouent fermé et rendent des
  ensembles vides — ce qui faisait repartir chaque relance tous les jours.
  C'est la contrainte d'unicité en base qui l'a révélé, et non un test :
  raison de plus pour que la garantie vive en base.
