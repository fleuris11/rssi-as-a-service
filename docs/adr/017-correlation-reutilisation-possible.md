# 017 — Corrélation « réutilisation possible »

- **Statut** : Adopté ; implémenté en Phase 8C
- **Date** : 2026-08-11

## Contexte

La question que se pose un dirigeant devant une fuite n'est pas « quel est le
type de cette fuite ? » mais « est-ce que ce mot de passe ouvre autre chose
chez moi ? ». C'est la question qui décide de l'urgence, et c'est aussi celle
qui vend le produit : sans elle, la plateforme énumère des faits ; avec elle,
elle raisonne.

Le problème est que la plateforme **ne peut pas** y répondre. Y répondre
supposerait de tester un identifiant sur un service — c'est-à-dire une
tentative d'authentification non sollicitée sur des systèmes tiers. C'est
interdit par le principe posé en ADR-010 (vérifications passives uniquement)
et ce serait, juridiquement, une intrusion.

Il fallait donc trancher entre « ne rien dire » et « dire quelque chose de
vrai qui aide quand même ».

## Options étudiées

**A. Tester les identifiants pour confirmer la réutilisation.**
Rejeté sans hésitation : intrusif, illégal sans autorisation du service cible,
et contraire à ADR-010. Mentionné ici uniquement pour que le rejet soit
explicite dans le dossier — c'est le genre de fonctionnalité qu'un
commercial peut réclamer de bonne foi.

**B. Ne rien signaler du tout.**
Rejeté : la plateforme dispose d'une information réelle et utile (le même
identifiant apparaît dans plusieurs fuites) qu'aucun dirigeant de TPE ne
croisera à la main. Se taire par prudence, c'est laisser le risque intact.

**C. Signaler que la question se pose, en le disant comme tel.**
Retenu. On ne prétend pas savoir : on indique où le doute est légitime, et
comment le lever.

## Décision

1. **Deux signaux, tous deux déterministes** (aucune IA — c'est un croisement
   d'identifiants, pas une inférence) :
   - **Exposition répétée** : le même identifiant apparaît dans plusieurs
     fuites du tenant. Le mot de passe est peut-être le même d'une fuite à
     l'autre — peut-être pas ; la plateforme ne peut pas le savoir.
   - **Service externe** : l'adresse professionnelle d'un membre apparaît
     dans la fuite d'un service qui n'appartient pas à l'entreprise. Si la
     personne y réutilisait son mot de passe professionnel, les accès de
     l'entreprise pourraient être atteignables.

2. **Vocabulaire imposé, vérifié par les tests.** On écrit « réutilisation
   possible », « à vérifier », « pourrait ». Jamais « confirmée »,
   « compromis », « avéré », « accès validé ». Les formulations sont
   centralisées dans `correlation.SIGNAL_DEFINITIONS` et une classe de tests
   dédiée refuse le vocabulaire interdit et exige une formulation d'hypothèse.
   La raison n'est pas cosmétique : un produit qui laisserait croire qu'il a
   testé un identifiant mentirait sur ce qu'il fait, et le premier
   utilisateur qui s'en aperçoit cesse de croire au reste de l'interface.

3. **Chaque signal dit comment lever le doute.** Un signal qui inquiète sans
   être actionnable est une nuisance. Le texte explique en une phrase
   pourquoi c'est une hypothèse, et l'action recommandée du finding est
   complétée : quand le mot de passe est encore disponible, elle propose
   explicitement de le révéler pour comparer — avec le rappel que cet accès
   est tracé. **C'est là que la révélation (ADR-014) prend tout son sens** :
   sa raison d'être n'est pas la curiosité, c'est de trancher une hypothèse.

4. **Prudence délibérée sur la normalisation des identifiants.** On normalise
   la casse et les espaces de bord, rien de plus. Pas de suppression des
   points dans la partie locale, pas de retrait des suffixes `+…` : ces
   règles sont propres à certains fournisseurs et pas à d'autres, et les
   appliquer partout fusionnerait des comptes réellement distincts. **Le coût
   d'un faux positif est ici bien supérieur à celui d'un faux négatif** — un
   lien inventé entre deux comptes sans rapport détruit la confiance, un lien
   manqué laisse simplement la situation inchangée.

5. **Le croisement n'utilise que des identifiants en clair**, c'est-à-dire —
   par construction (ADR-014 §4) — ceux des membres du tenant. Un identifiant
   masqué (`j.••••@ex••••.com`) est ambigu : plusieurs comptes distincts
   produisent le même masque, s'en servir comme clé de jointure fabriquerait
   des liens faux.

6. **Périmètre** : seuls les endpoints portant un identifiant de compte
   (`stealer`, `combo`, `creds`) sont croisés. Les signaux pré-incident
   (radar, dark web, surface d'attaque) décrivent une exposition publique,
   pas un compte — les y inclure n'aurait pas de sens.

## Conséquences

- Le produit gagne son argument le plus fort sans rien affirmer qu'il ne
  puisse démontrer.
- La corrélation est recalculée à la lecture du fil d'exposition plutôt que
  stockée : elle dépend de l'ensemble des fuites ouvertes du tenant, qui
  change à chaque ingestion et à chaque traitement. La stocker imposerait de
  l'invalider partout — pour un calcul qui reste peu coûteux (un croisement
  en mémoire sur les fuites d'un seul tenant).
- **Risque résiduel assumé** : la détection est nécessairement incomplète.
  Un même mot de passe utilisé sous deux adresses différentes ne sera pas
  détecté — c'est précisément le cas que seul un test d'identifiant
  révélerait, et qu'on refuse de faire. Le produit ne prétend pas à
  l'exhaustivité, et ne doit jamais laisser croire qu'une absence de signal
  vaut absence de réutilisation.
- Si le besoin d'une normalisation plus agressive apparaît (retours clients
  montrant des liens manqués évidents), il devra être tranché explicitement :
  c'est un arbitrage faux positifs / faux négatifs, pas un réglage technique.
