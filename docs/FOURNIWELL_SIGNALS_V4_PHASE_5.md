# Fourniwell Signals v4 - Phase 5

Statut: livree le 2026-05-14.

Objectif: ajouter un moteur `News Reaction Engine` separe du scoring classique pour capter les flashs de marche recents sans laisser une headline declencher un trade seule.

## Ce qui est livre

### 1. FastNewsListener

- filtre uniquement les `NewsFact` recents;
- fenetre dure: 30 minutes;
- ignore les sources faibles, les opinions et les rumeurs;
- conserve un identifiant stable par event (`event_id`) base sur source, heure et titre;
- expose la latence event -> detection en secondes.

### 2. EventClassifier

Le classifieur detecte:

- escalation geopolitique: Iran, Israel, Hormuz, tankers, sanctions, attaques, blocage maritime;
- de-escalation geopolitique: accord, cessez-le-feu, truce, reopening;
- declarations Trump / White House / Netanyahu;
- surprise Fed dovish ou hawkish;
- surprise CPI / PCE / NFP.

La negation est prise en compte:

- `Iran rejects deal` devient escalation potentiellement BUY gold;
- `Iran agrees ceasefire` devient de-escalation potentiellement SELL gold.

### 3. PriceReactionDetector

Une news ne peut pas devenir exploitable seule. Le moteur exige confirmation par le marche:

- reaction XAU/USD;
- DXY;
- 10Y US;
- WTI/Brent quand l'event concerne geopolitique/oil.

Le moteur detecte aussi le `fade trap`: si le prix part dans le sens oppose a la news, le signal est bloque.

### 4. NewsReactionTradePlan

Un plan news est cree avec:

- `entry_type = NEWS_REACTION`;
- statut clair: `TRADE_READY`, `WATCH`, `NO_TRADE`, `SUSPENDED`, `NO_EVENT`;
- validite 15 ou 30 minutes;
- entry zone;
- SL serre autour du prix de reaction;
- TP1/TP2/TP3 bases sur le mouvement deja observe;
- R/R calcule;
- raisons et blocages separes.

Le plan `NEWS_REACTION` reste separe du trade tracker classique. Il ne remplace pas le chef de file et ne contourne pas les controles de source, sauf si toutes les confirmations news sont reunies.

### 5. Collision multi-event

Si plusieurs news recentes donnent des directions opposees, le moteur suspend le signal pendant 10 minutes:

- pas de trade automatique;
- statut `SUSPENDED`;
- raison affichee dans le dashboard.

### 6. Affichage dashboard

Ajoute dans le dashboard:

- une cellule `News Reaction` dans le strip principal;
- un panneau `News Reaction Engine` sur la page Desk;
- un panneau `News Reaction Engine` sur la page News Flow;
- les details de latence et blocage dans Inspector.

L'affichage indique explicitement:

- exploitable maintenant;
- non exploitable;
- aucun flash exploitable;
- suspendu.

## Limites assumees

- Le moteur utilise le cycle de refresh actuel du dashboard local; il ne lance pas encore un daemon VPS autonome.
- La boucle de surveillance parallele reelle sera finalisee au moment du deploiement H24, pour eviter d'ajouter un processus non supervise en local.
- Le moteur ne locke pas encore automatiquement un trade dans le ledger; il produit un setup `NEWS_REACTION` distinct pour validation humaine.

## Tests livres

Fichier: `tests/test_xauusd_agent.py`

Tests ajoutes:

- escalation Iran/Trump -> BUY;
- cessez-le-feu Iran/Israel -> SELL;
- Fed dovish surprise -> BUY;
- CPI hot -> SELL;
- NFP weak -> BUY;
- confirmation prix/cross-assets requise;
- niveaux SELL coherents: `TP3 < TP2 < TP1 < entry < SL`;
- collision multi-event -> `SUSPENDED`.

## Critere de reussite Phase 5

- Une news recente et directionnelle ne s'affiche comme exploitable que si le marche confirme.
- Une headline ancienne ou faible ne produit pas de setup.
- Une collision BUY/SELL bloque le signal.
- Les niveaux SL/TP respectent la direction.
- Le payload JSON contient `news_reaction_setup`.
