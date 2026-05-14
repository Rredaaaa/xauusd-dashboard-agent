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

## Hotfix categories news Phase 4.5

Le rapport `fourniwell_v4_phase45_bugs_categories_news.md` a identifie que les nouvelles categories Phase 4.5 etaient collectees mais encore rejetees par plusieurs anciens filtres.

Correction livree:

- mapping central `SOURCE_CATEGORY_TO_LOGICAL`;
- helper `logical_category(...)`;
- `filter_news_by_categories(...)` base sur les categories logiques;
- `headline_sort_key(...)` base sur categorie logique + source tier + breaking + publication;
- `pick_story_headlines(...)` base sur categorie logique;
- `find_story_for_categories(...)` base sur categorie logique;
- `build_event_facts(...)` accepte les categories `critical_*`, `fast_*`, `official_*`, `political_*` via mapping logique;
- `build_geopolitical_analysis(...)` recoit les nouvelles sources via `filter_news_by_categories`;
- `explain_headline_gold_impact(...)` reconnait les categories logiques;
- `EventFactsAgent` passe en `CAUTION` quand des faits qualifies existent mais que leur direction reste mixte, au lieu de rester `NEUTRAL`.

Validation locale apres hotfix:

- `python3 -m py_compile xauusd_agent.py news_facts.py`: OK;
- `python3 -m unittest discover tests`: 126 tests OK;
- regeneration `reports/xauusd_dashboard.html`, `reports/xauusd_report.md`, `reports/xauusd_data.json`: OK;
- payload de validation: 24 headlines, 6 NewsFacts, categories `critical_white_house_nitter`, `fast_bloomberg_markets`, `official_fed_press_all`;
- `EventFactsAgent`: `CAUTION`, score 87/100, confiance 87/100;
- `geopolitical_analysis.event_watch`: 5 elements.

## Hotfix scoring keywords Phase 4.5

Le rapport `fourniwell_v4_bug_keywords_scoring.md` a identifie que le pipeline news etait debloque mais que le scoring restait calibre pour l'ancien flux Google News. Les nouvelles sources directes produisaient donc trop de `score=0`, ce qui laissait le bruit protocolaire passer avant les vraies news.

Correction livree:

- extension des mots-cles geopolitique, Iran/Hormuz/oil, Fed, taux, DXY, risk-on/risk-off;
- ajout de `score_headline_v2(title, source, category, link)`;
- bonus source tier: source officielle Tier 1 et agence Tier 2;
- bonus categorie logique pour `geopolitical`, `macro_fed`, `macro_cpi`, `macro_nfp`;
- filtre bruit dans `should_skip_headline`: RT/protocole, emoji-only, ceremonies, nominations, contenus officiels non market-moving;
- detection d'inversion quand une headline rejette/denie un deal ou accord;
- tri des headlines par impact avant fraicheur dans les listes exploitables;
- `headline_sort_key` integre maintenant l'impact avant breaking/source/date.

Validation locale apres hotfix scoring:

- `python3 -m py_compile xauusd_agent.py news_facts.py`: OK;
- `python3 -m unittest discover tests`: 134 tests OK;
- regeneration dashboard/payload: OK;
- payload de validation: 15 headlines apres filtrage, 6 headlines scorees, 6 NewsFacts;
- 4 NewsFacts contiennent des mots-cles critiques (`Iran`, `nuclear`, `Hormuz`, `oil`, `ships`, `clash`);
- bruit protocolaire dans les NewsFacts: 0;
- `EventFactsAgent`: `BUY`, score 91/100, confiance 91/100.

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
