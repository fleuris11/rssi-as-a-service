# ADR-039 — Former les salariés sans leur créer de compte

- **Statut** : accepté
- **Date** : 2026-09-17
- **Contexte** : Module Formation, lot 1 (F1). Prolonge la séparation
  catalogue/attribution d'[ADR-029](029-referentiels-multiples-et-attribution.md),
  reprend le mécanisme de jeton haché de la phase 11
  (`accounts.services.create_access_invitation`), et s'appuie sur la règle
  d'affichage d'[ADR-038](038-composition-du-perimetre-par-client.md).
- **⚠️ À faire valider par un juriste** : §7.

## Contexte

Une entreprise cliente veut former ses salariés : un cours court, un quiz, une
attestation. Le produit n'a jusqu'ici qu'un seul type d'utilisateur — un membre
d'une entreprise, avec un compte, un mot de passe, un rôle et l'accès aux
données de sécurité de son employeur.

Un salarié qui suit dix minutes de sensibilisation par trimestre n'est pas cet
utilisateur-là.

## Décision 1 — Le lien nominatif, pas le compte

Le salarié reçoit un **lien personnel**. Aucun compte n'est créé.

Trois raisons, dans l'ordre de leur poids réel :

1. **Le rôle le plus bas du produit est « Lecteur », et il lit tout.** Donner
   un compte à un salarié pour un cours lui donnerait, en l'état, la vue des
   compromissions de son employeur. Il aurait fallu un quatrième rôle **et**
   relire la garde de chaque vue existante pour vérifier qu'aucune ne traite
   « membre » comme un plancher suffisant — un audit transversal de toute
   l'API, déclenché par un module de formation.
2. **Le quota d'utilisateurs est vendu.** `Plan.max_users` vaut 3 par défaut.
   Une PME de quarante salariés consommerait quarante sièges d'une offre qui en
   vend trois. Soit la formation devient inachetable, soit le quota cesse de
   vouloir dire « utilisateurs » — et un compteur qui ment finit par tromper
   celui qui l'administre.
3. **La friction.** Un mot de passe à définir et à retenir un an, pour dix
   minutes de cours.

### Ce que le lien ne prouve pas, et qui doit être écrit

**Un lien ne prouve pas une identité.** Un salarié peut le transmettre à un
collègue qui fera le quiz à sa place.

Pour de la sensibilisation, c'est acceptable : l'objectif est que les gens
apprennent, pas de les surveiller. Pour une certification opposable, ce ne le
serait pas — et il faudrait alors des comptes.

Cette limite n'est pas seulement consignée ici : elle est **imprimée sur
l'attestation elle-même**, qui indique que le parcours a été réalisé au moyen
d'un lien personnel et que l'identité de la personne n'a pas été vérifiée.
C'est la seule place où elle sera lue par celui qui reçoit le document et se
demande ce qu'il vaut.

### Ce que le lien risque, et ce qu'il ne risque pas

Le jeton fait 256 bits, n'est stocké que **haché** (SHA-256, comme les liens
d'invitation), et ne donne accès qu'à **une inscription** : le contenu d'un
cours et la progression d'une personne. Le rayon de souffle d'un lien qui fuite
est « quelqu'un d'autre a suivi un e-learning à ma place ». Celui d'un
identifiant qui fuite, dans l'option « un compte par salarié », aurait été
l'exposition de l'entreprise.

## Décision 2 — Catalogue global, usage cloisonné, et versionnage dès F1

`Course` / `CourseVersion` / `Screen` / `Question` / `Choice` n'appartiennent à
personne : un cours écrit une fois sert tous les clients. `CourseAssignment`
dit ce qu'une entreprise peut proposer. Tout le reste est
`TenantScopedModel`. C'est le partage d'ADR-029, appliqué à un autre contenu.

**`CourseVersion` existe dès F1, alors que le studio n'arrive qu'en F2.** Le
versionnage est une propriété du modèle, pas une fonctionnalité de l'outil
d'édition : l'introduire après coup aurait demandé de rattacher des
inscriptions et des progressions déjà en base. Une inscription pointe vers une
**version** — republier un cours corrigé ne réécrit donc pas ce qu'ont suivi
les salariés déjà inscrits, et une attestation reste adossée au contenu
réellement suivi.

## Décision 3 — Une seule source de vérité pour la progression

Trois tables parlent d'avancement ; aucune ne répète l'autre.

| Question | Source unique |
|---|---|
| où en est-il dans le cours | les lignes de `ScreenProgress` |
| où en est-il du quiz | les lignes d'`Attempt` |
| a-t-il réussi | l'existence d'un `Certificate` |

`Enrollment` ne porte **ni curseur, ni compteur, ni date de fin**. Le point de
reprise est dérivé (le premier écran non terminé), le nombre d'essais se
compte, la réussite se lit à l'attestation. Un champ « dernier écran vu » se
désynchroniserait dès qu'une révision ciblée ou une reprise le mettrait à jour
ailleurs — et c'est toujours la copie qui finit par mentir.

Conséquence voulue : **revenir en arrière ne fait jamais reculer la
progression**. La navigation est libre, la progression enregistrée est la
progression réelle.

## Décision 4 — Des blocs typés, validés à l'écriture

Le contenu d'un écran est une liste de blocs typés (six types), et non du
Markdown. Le format et ses raisons sont documentés dans
[`docs/format_blocs_formation.md`](../format_blocs_formation.md), qui fait
contrat pour le studio de F2.

Le point de décision est **où** se fait la validation : dans `Screen.save()`,
donc sur tous les chemins d'écriture — la commande de chargement de F1 comme le
studio de F2. Un contenu mal formé est refusé par celui qui le crée, jamais
découvert par un salarié dans le train. Conséquence : la lecture ne valide
rien et ne peut pas échouer.

Un bloc `image` **exige** son texte alternatif. C'est ce que le Markdown ne
permettait pas : `![](photo.png)` est syntaxiquement valide, et c'est
exactement ce qui exclut un salarié qui utilise un lecteur d'écran.

## Décision 5 — « Attestation de suivi », et rien d'autre

Le document porte ce nom, jamais « certification » ni « habilitation ». Ces
deux mots ont un sens juridique que ce document n'a pas, et un client pourrait,
de parfaite bonne foi, produire une « certification » devant un assureur ou un
donneur d'ordre en croyant qu'elle vaut plus qu'elle ne vaut.

Il est **signé du nom de l'entreprise cliente**, pas du nôtre : c'est elle qui
forme ses salariés, nous fournissons l'outil. Le nom du fournisseur n'y figure
pas — un test l'épingle.

Tous les libellés sont **figés à l'émission** (nom, cours, version, entreprise,
score). Un cours renommé ne réécrit pas une attestation délivrée il y a huit
mois : c'est la différence entre une trace et une affirmation. Même
raisonnement que `AccessRequest.subject_label` et que le texte de déclaration
d'[ADR-033](033-comptes-designes.md).

Le PDF n'est pas stocké : il est réimprimé à la demande depuis ces champs. Rien
à sauvegarder, rien à purger, et deux impressions donnent le même document.

## Décision 6 — La validité suit la campagne, et l'expiration est une demande

Un lien vaut **jusqu'à l'échéance de la campagne, plus sept jours**.

Pas de durée fixe : sur une campagne de deux semaines, trente jours laisseraient
seize jours de lien vivant pour rien ; sur une campagne de deux mois, ils
obligeraient à renouveler au milieu. La marge existe pour le salarié qui s'y
prend le dernier jour et revient le lendemain — lui refuser l'accès à ce
moment-là ne protège rien et le fait abandonner.

Il est **révocable individuellement** et immédiatement : un salarié qui quitte
l'entreprise perd son accès sans attendre l'échéance.

### L'amendement au cadrage, et pourquoi

Le cadrage prévoyait qu'un salarié dont le lien a expiré puisse en redemander
un depuis la page d'expiration, envoyé à sa propre adresse. **Cela ne peut pas
fonctionner comme tel** : la validité découle de l'échéance de la campagne, donc
réémettre un jeton sur la même inscription produirait un lien tout aussi périmé.
Rendre l'accès suppose de déplacer l'échéance ou de réinscrire — deux décisions
de gestion.

La page d'expiration dépose donc une **demande adressée aux administrateurs du
client**, au plus une par jour et par inscription, et le message ne contient
aucun lien. C'est l'entreprise qui rouvre l'accès, pas un courriel automatique.
La page ne montre jamais d'erreur technique : une phrase, et un bouton.

## Décision 7 — Ce que le module traite comme données personnelles

Le nom et l'adresse d'un salarié sont ses données personnelles ; le responsable
de traitement est le client, pas nous — nous agissons sur ses instructions.

La déclaration formelle d'[ADR-033](033-comptes-designes.md) (base légale,
finalité, texte accepté figé) **n'est pas reprise ici**, et c'est délibéré : un
employeur qui forme ses salariés à la sécurité est dans une situation prévue et
banale, là où faire surveiller le compte d'un tiers ne l'est pas. Exiger la même
cérémonie pour inscrire quelqu'un à un cours de dix minutes découragerait
l'usage sans rien protéger.

Restent trois points **à faire valider par un juriste** avant une mise en
production commerciale large :

1. la mention portée par l'attestation suffit-elle à écarter toute lecture de
   « preuve de formation » opposable ?
2. la durée de conservation des attestations et des tentatives — aujourd'hui
   sans limite, puisqu'elles constituent la trace que l'entreprise a formé ses
   salariés ;
3. la clause de sous-traitance, déjà signalée par ADR-033, qui couvre désormais
   un second traitement.

## Conséquences

- Une nouvelle clé de registre, `training`, ajoutée aux offres « Pilotage » et
  « Souverain ». **Sans quota**, contrairement aux autres fonctionnalités à
  forte consommation : suivre un cours ne prend sur aucune ressource rare — pas
  d'appel externe, pas d'IA, pas de stockage. Un compteur aurait créé une
  rareté artificielle, et un client qui compte ses salariés avant de les former
  en forme moins.
- L'entrée « Formation » suit ADR-038 : désactivée hors offre, masquée si elle a
  été retirée à ce client.
- Un second chemin non authentifié apparaît dans l'API (`/formation/session/`),
  après le webhook CTI. Il est déclaré comme tel dans le client HTTP du
  frontend — sans quoi la session d'un collègue restée dans le navigateur ferait
  répondre 403 avant même d'atteindre la vue.
- `resoudre_session` devient le **deuxième et dernier** endroit du code autorisé
  à poser le contexte de cloisonnement, après le middleware. Il le pose depuis
  le client de l'inscription trouvée, jamais depuis ce qu'envoie l'appelant.
- Ce qui n'est **pas** dans F1, et l'assume : pas de studio, pas de rapports,
  pas de synthèse vocale, pas de contextualisation. Un cours de démonstration
  écrit en dur (`seed_training_demo`) valide le parcours.
