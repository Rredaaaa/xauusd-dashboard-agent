# Fourniwell Signals v4.0 - Phase 4.5

Date: 2026-05-14
Statut: livree et testee
Objectif: fermer les oublis des phases 1 a 4 avant de lancer la Phase 5.

## Portee

La Phase 4.5 absorbe les recommandations qui ne doivent pas etre repoussees dans une phase intermediaire:

- hot-fixes Quality Gate, settings et mentions legacy;
- sources news exhaustives depuis `news.md`;
- feeds rapides et officiels avec fallback et logs d'erreur;
- timestamps de latence news: `feed_published_at`, `feed_detected_at`, `feed_processed_at`;
- hash de feed pour detecter le breaking/rejeu;
- PriceActionAgent avec swing M15;
- TechnicalAgent avec trigger de cloture M15 et TP adaptatifs en mode event;
- MacroAgent avec DGS3M/DGS30, densite macro et pre-event mode;
- GeopoliticalOilShockAgent avec regimes `Risk-On / Carry Trade` et `Stagflation Fear`;
- probabilites, composants et persistance des regimes;
- FlowPositioningAgent avec Producers/Merchants COT et percentiles;
- TrumpPoliticalStatementsAgent avec separation menace verbale / action sourcee;
- Data Quality ponderee par criticite source;
- audit log avec rotation/archivage local;
- criteres de validation chiffrables avant Phase 5.

## Sources ajoutees ou promues

Sources politiques / statements:

- Truth Social feed;
- Nitter Trump avec plusieurs mirrors;
- Nitter White House avec plusieurs mirrors;
- White House official feed.

Sources rapides:

- Reuters Top News;
- Reuters Business;
- Reuters Markets;
- Bloomberg Markets;
- AP Top;
- AP Business;
- CNBC Markets.

Sources officielles:

- Federal Reserve `press_all`;
- Fed speeches;
- Fed monetary policy;
- BEA RSS + release schedule;
- CFTC press feed + COT;
- ECB press feed;
- BOE news feed;
- BOJ news feed.

## Regles de fiabilite

- Les sources critiques prix, taux et COT sont ponderees plus fortement dans la Data Quality.
- `google_news_rss` est degrade en Tier 5 et ne doit plus porter seul un signal.
- IG Weekend Gold est Tier 3: proxy week-end, jamais prix spot officiel.
- Les erreurs de source sont journalisees dans `reports/source_errors.jsonl`.
- Les erreurs et audits JSONL sont rotates quand le fichier grossit.
- Si les feeds Trump/White House sont down, le dashboard doit signaler le mode degrade au lieu d'inventer un signal.

## Regimes de marche

Regimes geres:

- `Normal Macro`;
- `Safe-Haven Gold`;
- `Hormuz / Oil Shock`;
- `Dollar Liquidity Squeeze`;
- `De-escalation / Oil Relief`;
- `Risk-On / Carry Trade`;
- `Stagflation Fear`.

Chaque regime expose:

- `score`;
- `trend`: escalade, accalmie ou stable;
- `confirmed`: score fort ou persistance 3 snapshots;
- `probabilities`;
- `component_scores`.

## Macro Catalysts

La Phase 4.5 ajoute:

- DGS3M;
- DGS30;
- calendrier ECB/BOE/BOJ planifie;
- densite macro 24h;
- pre-event mode automatique avant event HIGH;
- conservation des champs forecast / previous / actual quand disponibles.

Le pre-event mode active un regime prudent sans attendre un spike de volatilite.

## Flow / COT

Le FlowPositioningAgent ne lit plus seulement Managed Money:

- percentile Managed Money 1 an / 5 ans;
- percentile Producers/Merchants 1 an / 5 ans;
- signal contrarien si Managed Money ou hedgers sont extremes;
- divergence COT / ETF conservee.

## Criteres de validation

Avant Phase 5:

- `python3 -m py_compile xauusd_agent.py news_facts.py` doit passer;
- `python3 -m unittest discover tests` doit passer;
- au moins 18 sources critiques/secondaires doivent etre configurables;
- aucun TradePlan ne doit passer avec R/R TP1 < 1.5;
- un event HIGH dans la fenetre pre-event doit activer Event Mode;
- les regimes `Risk-On / Carry Trade` et `Stagflation Fear` doivent etre testables;
- Producers/Merchants doit apparaitre dans COT/Flow;
- les erreurs de feed doivent etre journalisees sans casser le dashboard.

## Decision de passage

La Phase 5 ne doit commencer qu'apres:

- tests OK;
- documentation OK;
- commit Git dedie;
- push GitHub OK.
