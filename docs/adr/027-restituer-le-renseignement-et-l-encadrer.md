# ADR-027 — Restituer le renseignement, et l'encadrer

- **Statut** : accepté
- **Date** : 2026-09-09
- **Contexte** : amende l'ADR-014 §4 (masquage des identifiants), complète
  l'ADR-013 (intégration de la source) et l'ADR-017 (corrélation)

## Contexte

Le produit affichait, d'une compromission, à peu près trois choses : le type,
la gravité, et une adresse le plus souvent masquée. Un inventaire des charges
réelles, réalisé à partir des schémas des neuf points d'entrée et d'une
cassette enregistrée en production, donne le compte exact : **42 champs
documentés n'étaient jamais restitués.**

Ils n'étaient pas perdus. Ils étaient tous en base, dans
`BreachFinding.raw_data` — la charge du fournisseur, déjà masquée, conservée
depuis la première migration et **délibérément exclue du sérialiseur** au nom
de la minimisation (ADR-014). Le résultat est une inversion complète de
l'intention : la donnée la plus utile au client était stockée sans jamais lui
être montrée, pendant que le stockage, lui, n'avait rien minimisé.

Deux exemples de ce que le produit taisait :

- pour un poste infecté : le nom du logiciel voleur, le système du poste, le
  nom de la machine, le fichier de collecte, la date de l'infection ;
- pour un document fuité : son nom, son type, sa taille, le groupe qui l'a
  publié, l'organisation à laquelle il se rattache.

Un dirigeant à qui l'on dit « un mot de passe a fuité » ne peut rien faire.
Le même, à qui l'on dit « le poste PC-COMPTA-01 sous Windows 11 a été infecté
le 30 juin par RedLine, un logiciel qui recopie les mots de passe du
navigateur », sait quoi faire, dans quel ordre, et sur quelle machine.

## Décision 1 — Restituer par liste blanche, jamais par ouverture de `raw_data`

La solution évidente — exposer `raw_data` — est rejetée. Elle ferait sortir,
sans décision, tout ce que la source ajouterait demain, y compris ce qu'elle
ne devrait pas transmettre. Un module dédié (`finding_details.py`) déclare
donc, **point d'entrée par point d'entrée**, les champs restitués, avec pour
chacun trois choses :

1. un **libellé français** — `mal` ne veut rien dire, « Logiciel malveillant
   identifié » si ;
2. la **valeur**, formatée pour un lecteur non technique — une date en toutes
   lettres, une taille en mégaoctets, un type MIME traduit
   (`application/pdf` → « Document PDF ») ;
3. **ce que ça implique** — « Raccoon » n'informe personne ; « c'est un
   logiciel qui recopie les mots de passe enregistrés dans le navigateur »
   permet de décider.

Conséquence recherchée : **aucune migration, aucun nouveau scan**. La lecture
se fait sur `raw_data`, donc les fuites déjà en base — dont les 28 450 d'un
actif de production — deviennent complètes du jour au lendemain.

Certains champs sont **volontairement laissés de côté** : `iip`, `ip`, `mac`
(adresses réseau et matérielle du poste infecté — données personnelles, valeur
d'action nulle : on ne fait rien d'une adresse IP domestique), `pth` et
`malware_path` (chemins techniques), et `atr` (sémantique non confirmée par
le fournisseur — inventer un libellé pour un champ qu'on ne comprend pas est
pire que de le taire, car le dirigeant croirait savoir).

## Décision 2 — Démasquer les adresses, garder les secrets masqués

L'ADR-014 §4 ne conservait en clair que l'adresse d'un **membre de l'espace**.
Toute autre était réduite à une forme non réversible (« j.••••@ex••••.com »).

C'était protéger la mauvaise donnée. Un RSSI ne peut agir sans savoir **qui**
est concerné : prévenir la personne, vérifier si le compte est encore actif,
juger de la gravité — les trois demandent l'adresse. Et les adresses qui
comptent le plus sont précisément celles qui n'appartiennent à aucun membre :
un ancien salarié, une adresse personnelle utilisée au bureau, un
prestataire.

**Ce qui reste protégé, et ne bouge pas :** les mots de passe et les cookies
de session. Ils restent chiffrés au repos, masqués par défaut, et soumis aux
cinq conditions cumulatives de la révélation (ADR-014) : rôle administrateur,
ré-authentification fraîche, cloisonnement, limitation de débit, audit de
chaque tentative. La différence n'est pas de degré, elle est de nature : une
adresse ne donne accès à rien, un mot de passe ouvre un compte.

L'encadrement des adresses est donc **délibérément plus léger** :

- **rôle** : administrateur et contributeur voient l'adresse ; le rôle lecteur
  n'en voit que la forme masquée. Il est fait pour rendre compte, pas pour
  agir ;
- **trace** : chaque consultation ou export ayant servi des adresses en clair
  est enregistré (`IdentifierAccessAudit`) avec son auteur, sa date et les
  actifs concernés. Une ligne par accès, pas par adresse : sur un actif réel,
  l'affichage d'une page produirait sinon 28 450 lignes d'audit ;
- **lisibilité** : le journal est consultable par l'administrateur du tenant,
  pas seulement par l'éditeur. Une trace que le client ne peut pas lire ne lui
  prouve rien face à un salarié, un délégué à la protection des données ou un
  auditeur ;
- **transparence** : la politique de confidentialité le dit.

Exiger la ré-authentification pour lire la liste de ses propres fuites rendrait
le produit inutilisable au quotidien — et une garde qu'on contourne parce
qu'elle gêne ne protège personne.

**Les deux formes sont conservées en base.** Le choix se fait à la
restitution, pas au stockage : masquer en base revenait à trancher une fois
pour toutes, sans retour possible, ce qui se décide légitimement par rôle.

### Deux effets de bord, tous deux traités

**La pseudonymisation.** Ces adresses entrent dans le contexte envoyé au
modèle d'IA. Le collecteur de valeurs sensibles ne ramassait que les adresses
des **membres** — c'était suffisant tant que les autres étaient masquées avant
stockage. Il couvre désormais les identifiants des fuites, sur exactement le
même ensemble borné que celui parcouru par le constructeur de contexte (une
seule fonction définit cet ensemble, avec un tri déterministe : deux requêtes
renvoyant deux lots de vingt différents auraient laissé passer une adresse).

**La corrélation.** L'ADR-017 croise les identifiants pour signaler une
réutilisation possible, mais refusait les formes masquées — donc, en pratique,
ne croisait que les membres. Elle couvre maintenant toutes les adresses. C'est
un élargissement voulu : la réutilisation entre le compte personnel d'un
salarié et son accès professionnel est exactement le cas que l'ADR-017 voulait
rendre visible, et c'était celui que le masquage empêchait de voir.

## Décision 3 — Les documents : les métadonnées, jamais le document

La source renvoie, pour un document fuité, deux URL : `url_main_post` et
`url_for_breach`. Elles ne sont dans aucune liste blanche, et n'y seront pas.

Rediriger un client vers un fichier volé l'expose autant que nous : il
téléchargerait des données personnelles publiées illégalement, souvent celles
de ses propres clients, depuis une infrastructure contrôlée par un attaquant.

Ce qui est affiché à la place : le nom, le type, la taille, la date de
publication, le groupe qui publie, et **quelle donnée du client s'y rattache**
— assez pour identifier le document dans ses propres archives. Et une phrase
d'action qui dit le délai de 72 heures et, explicitement, de ne pas chercher à
télécharger la version publiée.

La garde est **structurelle** : c'est la liste blanche qui l'applique, pas une
règle de vigilance. Un test échoue si un champ interdit y est ajouté, et un
autre balaie la charge servie à la recherche des URL de la cassette.

> Si le besoin d'accéder au document se confirme, ce sera une décision
> d'architecture distincte, avec avis juridique. Elle n'est pas préparée ici.

## Décision 4 — Le nom de la source ne sort jamais, et c'est balayé

Un balayage existait déjà, mais **seulement sur les constantes de message
d'erreur**. Il ne voyait rien de ce qui part par le chemin normal : la liste
des fuites, le fil d'exposition, les textes de vulgarisation, les libellés des
champs restitués — c'est-à-dire la plus grande surface, et la moins gardée.

Le balayage porte désormais sur **la charge réellement servie** : chaque
chaîne de chaque réponse d'API est parcourue récursivement, ainsi que les
emails envoyés. Deux listes distinctes, et c'est délibéré :

- `FORBIDDEN_IN_CLIENT_MESSAGES` — large (« pool », « quota », « http »,
  chiffres), appliquée aux **messages d'erreur** ;
- `VENDOR_NAMES` — étroite (les noms de fournisseurs), appliquée à **tout**.

Une seule liste, large, appliquée partout, aurait été désactivée à la première
adresse de site contenant « http ». Une garde qu'on désactive ne garde rien.

## Conséquences

- Les fuites existantes deviennent complètes **sans migration ni rescan** —
  la restitution lit `raw_data`.
- Une migration de données remet malgré tout `identifier_plain` sur les fuites
  déjà en base, en le relisant depuis `raw_data` : rien n'est deviné ni
  ajouté, la donnée était dans la colonne d'à côté.
- `identifier_plain` et `identifier_masked` **ne sont plus exposés
  séparément** par l'API. Les laisser aurait contourné la garde de rôle : le
  lecteur aurait reçu l'adresse dans le champ voisin de celui qu'on lui
  masque. Un seul champ `identifier`, dont le serveur décide le contenu.
- La vulgarisation passe de deux parties à **trois** — ce que c'est, ce que ça
  implique, ce qu'il faut faire. Les deux premières se tuilaient, et l'action
  arrivait avant que le dirigeant ait mesuré ce qu'il risquait.
- Le paramètre `tenant_emails` disparaît du normaliseur et de l'ingestion : il
  n'y servait qu'à décider qui avait droit au clair. Il reste là où il garde
  un sens, la corrélation.

## Ce que cette décision ne fait pas

- Elle **ne crée pas d'export** de fuites. Le journal des accès distingue déjà
  consultation et export, mais aucun export client de compromissions n'existe
  à ce jour : la branche est en place, non exercée.
- Elle **ne réduit pas** ce qui est stocké. `raw_data` continue de tout
  conserver, y compris les champs non restitués. Réduire le stockage à ce qui
  est affiché serait une décision de rétention distincte — et irréversible.
- Elle **ne traduit pas les noms de logiciels malveillants inconnus**. Le
  glossaire couvre les huit familles les plus répandues ; au-delà, une phrase
  générique décrit ce que fait la catégorie entière, ce qui suffit à décider.
