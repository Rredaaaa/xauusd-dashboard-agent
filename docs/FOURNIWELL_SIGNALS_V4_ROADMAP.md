# Fourniwell Signals v4.0 - Roadmap officielle

Version: 1.1
Date: 2026-05-14
Ancien nom: Aureum Flux Terminal
Nouveau nom produit: Fourniwell Signals
Source de reference principale: `aureum_flux_v3_inspection_report_2026-05-12.md`
Sources de correction Phase 4.5:

- `/Users/reda/Desktop/fourniwell_v4_critique_phases_1-4_et_roadmap_phase5plus.md`
- `/Users/reda/Desktop/news.md`

## 1. Objectif v4.0

Fourniwell Signals v4.0 doit transformer le terminal actuel en un systeme de signaux XAU/USD plus strict, plus lisible, plus fiable et preparable a un usage SaaS.

La v4.0 ne doit pas etre une simple mise a jour visuelle. Elle doit corriger:

- la qualite des sources;
- la vitesse et la fiabilite du flux news;
- la logique des agents;
- le scoring;
- le trade locking;
- le risk management;
- les niveaux SL/TP;
- les strategies de detection;
- l'interface utilisateur finale;
- la preparation utilisateurs / abonnement;
- le deploiement VPS H24.

## 2. Principe directeur

Fourniwell Signals ne doit pas afficher du bruit.

Une information ne doit apparaitre sur la vue principale que si elle est:

- recente;
- sourcee;
- utile;
- directionnelle ou explicitement marquee comme non exploitable;
- comprehensible par un utilisateur final.

Tout le detail technique doit rester dans la page Inspector, reservee a l'admin.

## 3. Regle d'exhaustivite

A partir de cette version 1.1, les recommandations de Claude ne doivent plus etre traitees partiellement.

Regles:

- aucune recommandation critique ne doit etre repoussee sans decision explicite;
- aucune phase intermediaire non officielle ne doit etre creee;
- les recommandations orphelines sont absorbees dans la Phase 4.5;
- la Phase 5 ne peut pas commencer tant que la Phase 4.5 n'est pas livree, testee et documentee;
- un item ne peut etre coche dans la checklist que s'il est implemente, teste et documente.

## 4. Criteres de succes v4.0

La livraison v4.0 est validee seulement si:

- le systeme ne verrouille plus de trade avec R/R inferieur a 1.5;
- les trades sont bloques apres une serie de pertes;
- les news tier 4/5 et les vieilles analyses ne polluent plus la page News;
- les news recentes importantes sont visibles avec titre, source, heure, resume et impact XAU/USD;
- les sources critiques news sont surveillees en direct ou en fallback documente;
- les agents faibles ne votent plus dans le scoring;
- le RiskManagerAgent calcule un vrai risque;
- le TradeQualityGate explique clairement pourquoi un trade est accepte ou refuse;
- les SL/TP sont bases sur des niveaux techniques et non sur un simple multiplicateur mecanique;
- le dashboard principal reste simple: prix, biais, signal, chart, trade locked;
- l'Inspector contient le bruit technique sans le montrer aux viewers;
- la version peut etre deployee sur VPS avec protection d'acces;
- la calibration/backtest donne des metriques exploitables avant production.

## 5. Etat des phases deja lancees

### Phase 0 - Rebranding et base propre

Statut: livre.

Objectif: repartir sur une base controlee avant de modifier le moteur.

Livrables:

- rebranding officiel Fourniwell Signals;
- documentation v4 initiale;
- checklist exhaustive v4;
- etat Git controle avant Phase 1.

### Phase 1 - Stopper les mauvais trades

Statut: livre le 2026-05-13 dans `docs/FOURNIWELL_SIGNALS_V4_PHASE_1.md`.

Objectif: empecher immediatement le systeme de verrouiller des trades faibles.

Actions livrees:

- `minimum_risk_reward = 1.5`;
- `trade_threshold = 65`;
- `minimum_agent_confidence = 65`;
- `scoring_mode = balanced`;
- cooldown apres loss;
- cooldown apres win;
- maximum trades / 24h;
- circuit breaker apres serie de pertes;
- blocage data quality faible;
- debut de blocage macro high impact;
- cap confidence TechnicalAgent;
- neutralisation SentimentNewsAgent si source faible ou vieille;
- retrait OrchestratorAgent legacy du scoring.

Points a reprendre en Phase 4.5:

- parametrage explicite des fenetres macro avant/apres event HIGH;
- raisons de blocage dans payload;
- nettoyage complet des mentions legacy;
- correction duplication `RISK [high] Gate`.

### Phase 2 - Quality Gate, cooldown et ledger

Statut: livre le 2026-05-13 dans `docs/FOURNIWELL_SIGNALS_V4_PHASE_2.md`.

Objectif: rendre la validation des trades plus stricte, auditable et dependante de l'historique recent.

Actions livrees:

- cooldown differentiel par outcome;
- validite dynamique des TradePlans;
- reduction de validite en mode event;
- ledger append-only;
- audit log `reports/trade_gate_audit.jsonl`;
- evenements de trade traces.

Points a reprendre en Phase 4.5:

- completer le Quality Gate;
- blocage dur direction contraire au regime fort;
- enrichissement audit log;
- lecture Inspector des refus;
- rotation/archivage du log.

### Phase 3 - News Flow v4

Statut: livre le 2026-05-13 dans `docs/FOURNIWELL_SIGNALS_V4_PHASE_3.md`.

Objectif: remplacer le flux news actuel, juge inutilisable.

Actions livrees:

- sources officielles partielles;
- AP/CNBC;
- recherches Reuters/Bloomberg via Google News;
- filtrage des sources faibles;
- rejet forecast/prediction/outlook/analysis;
- tri par publication;
- deduplication renforcee;
- affichage plus propre des news.

Points a reprendre en Phase 4.5:

- ajouter toutes les sources manquantes du rapport `news.md`;
- remplacer le plus possible Reuters/Bloomberg Google News par feeds directs;
- ajouter Trump/Truth Social/Nitter;
- ajouter Fed `press_all`;
- ajouter BEA/CFTC/ECB/BOE/BOJ;
- creer `CRITICAL_FAST_FEEDS`;
- ajouter polling rapide;
- ajouter detection breaking par hash;
- ajouter fallback et mode degrade.

### Phase 4 - Rebuild des agents

Statut: livre le 2026-05-13 dans `docs/FOURNIWELL_SIGNALS_V4_PHASE_4.md`.

Objectif: faire en sorte que chaque agent ait un role utile et mesurable.

Actions livrees:

- `PriceAgent` remplace par `PriceActionAgent`;
- TechnicalAgent plus prudent;
- MacroAgent enrichi avec fraicheur FRED;
- GeopoliticalOilShockAgent directionnel;
- SentimentNewsAgent pondere par source/fraicheur;
- CorrelationAgent plus explicable;
- FlowPositioningAgent avec divergence COT/ETF;
- EventFactsAgent plus strict;
- TrumpPoliticalStatementsAgent directionnel;
- RiskManagerAgent enrichi.

Points a reprendre en Phase 4.5:

- swing high/low M15;
- confirmation cloture M15;
- macro surprise;
- courbe des taux complete;
- regime Risk-On et Stagflation Fear;
- persistance/probabilite des regimes;
- correlation glissante;
- breakdown correlations;
- COT Producers/Merchants;
- data quality ponderee par criticite.

## 6. Prochaine phase officielle

La prochaine phase a lancer est:

`Phase 6 - Refonte Trade Levels`

Phase 4.5 a ete livree et testee le 2026-05-14. Phase 5 a ete livree le 2026-05-14 avec `News Reaction Engine`, signal `NEWS_REACTION`, confirmation prix/cross-assets et affichage dashboard.

## 7. Phase 4.5 - Redressement exhaustif avant Phase 5

Statut: livree le 2026-05-14.

Objectif: fermer tous les oublis des Phases 1 a 4 et absorber toutes les recommandations de Claude qui etaient proposees en phases intermediaires.

Cette phase absorbe les recommandations orphelines et evite toute phase intermediaire non officielle.

### 7.1 Hot-fixes immediats

Actions:

- supprimer toute mention `ancien moteur` du payload, du dashboard et des resumes;
- corriger la duplication `RISK [high] Gate:`;
- verifier que `min_data_quality = 60` est bien dans settings, exemple et validation;
- ajouter `no_trade_window_minutes_before_high_macro = 30`;
- ajouter `no_trade_window_minutes_after_high_macro = 15`;
- afficher les raisons de blocage dans le payload;
- afficher les raisons de blocage dans Inspector;
- bloquer un trade si sa direction contredit un regime fort confirme;
- verifier que l'ancien `OrchestratorAgent` ne participe plus au scoring actif;
- conserver uniquement les aliases necessaires pour compatibilite historique.

Validation:

- 0 occurrence `ancien moteur`;
- 0 duplication `RISK [high] Gate`;
- tests settings OK;
- payload de trade refuse lisible.

### 7.2 Quality Gate complet

Actions:

- exiger au moins 3 agents decisionnels valides;
- refuser les trades avec trop de contradictions;
- bloquer si data quality sous seuil;
- bloquer si regime fort oppose a la direction;
- bloquer avant et apres event macro HIGH selon settings;
- bloquer si cooldown actif;
- bloquer si circuit breaker actif;
- bloquer si R/R < 1.5;
- journaliser:
  - raison principale;
  - raisons secondaires;
  - agents validants;
  - agents contradictoires;
  - regime actif;
  - score data quality;
  - R/R potentiel.

Validation:

- tests TradeQualityGate;
- cas BUY refuse en regime SELL fort;
- cas SELL refuse en regime BUY fort;
- cas macro window refuse;
- cas R/R faible refuse.

### 7.3 Sources news exhaustives

Actions:

- ajouter sources Trump / politique US:
  - Truth Social RSS;
  - Nitter `realDonaldTrump`;
  - Nitter `WhiteHouse`;
  - fallback sur plusieurs mirrors Nitter;
  - fallback degrade Google News Trump si tous les feeds Trump tombent;
- ajouter Federal Reserve:
  - `speeches.xml`;
  - `press_monetary.xml`;
  - `press_all.xml`;
- ajouter macro US:
  - BLS;
  - BEA;
  - Treasury;
  - CFTC press releases;
- ajouter metaux:
  - WGC;
- ajouter medias rapides directs:
  - AP business;
  - AP top;
  - CNBC markets;
  - Reuters top;
  - Reuters business;
  - Reuters markets;
  - Bloomberg markets;
- ajouter banques centrales etrangeres:
  - ECB;
  - BOE;
  - BOJ;
- garder Google News seulement comme fallback/degraded discovery;
- reclasser Google News RSS en tier 5;
- reclasser IG Weekend Gold en tier 3 proxy week-end;
- documenter le tier, la criticite et l'usage de chaque source.

Validation:

- test de parsing par famille de source;
- au moins 18/22 sources valides quand le reseau le permet;
- latence cible < 3s par feed direct accessible;
- statut degrade visible si une source critique tombe.

### 7.4 Gestion d'erreur sources et SourceRegistry

Actions:

- creer ou enrichir `reports/source_errors.jsonl`;
- logger:
  - source;
  - URL;
  - erreur;
  - timestamp;
  - criticite;
  - retry_count;
- marquer une source comme:
  - OK;
  - STALE;
  - DEGRADED;
  - DOWN;
- afficher dans Inspector:
  - derniere update;
  - age de la source;
  - statut;
  - tier;
  - criticite;
  - derniere erreur;
- ponderer la data quality par criticite:
  - gold spot, FRED, CFTC = poids fort;
  - sources techniques principales = poids fort;
  - ETF/news secondaires = poids faible;
  - Google News fallback = poids faible;
- ajouter delai depuis dernier refresh par source.

Validation:

- test source DOWN;
- test source STALE;
- test data quality ponderee;
- Inspector affiche les statuts.

### 7.5 Prerequis News Reaction Engine

Actions:

- creer `CRITICAL_FAST_FEEDS`;
- separer les feeds critiques des feeds normaux;
- ajouter polling rapide pour sources critiques;
- ajouter detection breaking par hash de feed;
- stocker pour chaque news:
  - `feed_published_at`;
  - `feed_detected_at`;
  - `feed_processed_at`;
  - `source_latency_seconds`;
  - `processing_latency_seconds`;
- detecter si tous les feeds Trump sont down;
- afficher mode degrade:
  - `Trump feeds degraded`;
  - `News Reaction Engine degraded`;
- ne pas encore creer de trade news en Phase 4.5;
- preparer seulement les donnees pour Phase 5.

Validation:

- test hash nouvelle news;
- test hash identique ignore;
- test fallback Nitter;
- test fallback Google News degrade;
- test timestamps non vides.

### 7.6 PriceActionAgent complet

Actions:

- detecter swing high M15;
- detecter swing low M15;
- exposer niveaux swing dans l'evidence agent;
- detecter position du prix dans le range;
- detecter niveau psychologique proche;
- preparer ces niveaux pour Phase 6 TradeLevels.

Validation:

- fixtures M15 swing high/low;
- agent ne score pas fort sans structure claire.

### 7.7 TechnicalAgent complet

Actions:

- exiger cloture M15 au-dessus/sous trigger;
- refuser trigger non confirme;
- detecter structure:
  - trend;
  - range;
  - breakout;
  - pullback;
  - reversal;
- adapter lecture technique a la structure;
- preparer SL/TP par structure pour Phase 6;
- conserver cap confidence 85;
- reduire confidence si contradictions intra-timeframe.

Validation:

- test close M15 confirme BUY;
- test wick sans close refuse;
- test range;
- test breakout;
- test reversal.

### 7.8 MacroAgent complet

Actions:

- ajouter macro surprise quand disponible:
  - actual;
  - consensus;
  - previous;
  - surprise = actual - consensus;
- ajouter trajectoire des 3 dernieres publications quand disponible;
- ajouter DGS3M;
- ajouter 30Y;
- renforcer lecture yield curve;
- conserver FRED DGS10, DGS2, DFII10, T10YIE;
- clarifier veto macro HIGH;
- ajouter calendrier macro US quand disponible;
- preparer consensus/previous pour events majeurs:
  - CPI;
  - PCE;
  - NFP;
  - FOMC;
  - GDP;
  - jobless claims.

Validation:

- test surprise hawkish;
- test surprise dovish;
- test donnees absentes => agent neutre/degrade;
- test yield curve.

### 7.9 Macro Catalysts et Event Mode

Actions:

- ajouter calendrier ECB/BOJ/BOE si disponible;
- calculer macro density 24h:
  - 0-1 HIGH = normal;
  - 2 HIGH = caution;
  - 3+ HIGH = high density;
- ajouter alerte 1h avant event HIGH;
- activer pre-event mode 30 min avant catalyseur HIGH;
- bloquer nouveaux trades pendant 15 min apres catalyseur HIGH;
- adapter TP en mode event:
  - TP1 = 1.65 x ATR;
  - TP2 = 3.15 x ATR;
- journaliser historique event mode.

Validation:

- test pre-event 30 min;
- test blocage 15 min apres;
- test TP event plus larges;
- test macro density.

### 7.10 GeopoliticalOilShockAgent et regimes

Actions:

- mesurer tendance du regime:
  - escalade;
  - accalmie;
  - stable;
- ajouter cooldown 4h sur changement de regime;
- ajouter regime `Risk-On / Carry Trade`;
- ajouter regime `Stagflation Fear`;
- documenter score brut par composant:
  - headlines;
  - oil;
  - DXY;
  - VIX;
  - yields;
  - gold reaction;
- ajouter persistance:
  - regime observe 3 fois consecutivement = confirme;
- exposer probabilite de chaque regime dans payload;
- renforcer poids du regime confirme dans l'orchestrator;
- eviter les flips de regime trop frequents.

Validation:

- test Risk-On;
- test Stagflation Fear;
- test persistance 3 confirmations;
- test cooldown 4h.

### 7.11 CorrelationAgent complet

Actions:

- calculer correlation glissante 30j par actif;
- reduire poids si correlation faible;
- reduire poids si correlation vient de casser;
- detecter `correlation breakdown`;
- adapter poids selon regime;
- documenter confirmations et contradictions;
- eviter que silver/miners dominent en regime ou leur correlation casse.

Validation:

- test correlation forte;
- test breakdown;
- test poids regime.

### 7.12 FlowPositioningAgent complet

Actions:

- ajouter percentile Managed Money 1 an;
- ajouter percentile Managed Money 5 ans;
- ajouter logique contrarienne aux extremes;
- ajouter COT Producers/Merchants;
- detecter extremes Producers/Merchants;
- agreger GLD + IAU + SLV si disponible;
- ponderer CFTC/ETF;
- clarifier divergence COT vs ETF;
- reduire confidence si flow contradictoire.

Validation:

- test Managed Money extreme long;
- test Managed Money extreme short;
- test Producers/Merchants extreme;
- test COT bullish mais ETF outflow.

### 7.13 TrumpPoliticalStatementsAgent complet

Actions:

- distinguer:
  - menace verbale;
  - action officielle signee;
  - declaration confirmee par source fiable;
  - rumeur/agregateur;
- mesurer convergence des declarations sur 24h;
- reduire score d'une declaration isolee;
- augmenter score de plusieurs declarations convergentes;
- lier chaque statement a:
  - source;
  - heure;
  - sujet;
  - impact oil;
  - impact DXY;
  - impact XAU/USD;
  - niveau de confirmation.

Validation:

- test menace isolee faible;
- test action officielle forte;
- test 3 declarations convergentes.

### 7.14 EventFacts et News Facts

Actions:

- recalibrer `build_trader_action`;
- regles:
  - score 4/4 + tier <= 2 => WATCH/TRADE selon confirmation marche;
  - score 2-3/4 + tier <= 2 => WATCH avec trigger;
  - score 0-1/4 ou tier > 2 => WAIT ou ignore;
- masquer les faits sans impact trading;
- afficher dans News:
  - titre;
  - source;
  - heure;
  - resume concret;
  - impact XAU/USD;
  - bullish/bearish/mixte;
  - confiance;
- supprimer les phrases vagues;
- ne pas repeter la meme analyse sur plusieurs cartes.

Validation:

- test fait fort;
- test fait moyen;
- test fait faible ignore;
- test resume lisible.

### 7.15 Audit log, Inspector et rotation

Actions:

- enrichir `trade_gate_audit.jsonl`;
- ajouter rotation/archivage:
  - rotation hebdomadaire ou par taille;
  - archivage local apres 90 jours;
- ajouter lecture Inspector:
  - trades refuses dernieres 24h;
  - raisons de refus;
  - agent dominant;
  - R/R;
  - regime;
  - source quality;
  - cooldown/circuit breaker;
- preparer export CSV.

Validation:

- test rotation;
- test lecture dernieres 24h;
- test audit refuse avec raisons.

### 7.16 Validation chiffree Phase 4.5

La Phase 4.5 n'est validee que si:

- tous les tests existants passent;
- nouveaux tests Phase 4.5 passent;
- 0 occurrence `ancien moteur`;
- 0 duplication `RISK [high] Gate`;
- au moins 18/22 sources retournent un contenu valide quand accessibles;
- latence cible des feeds directs < 3s quand reseau OK;
- les feeds critiques down declenchent un mode degrade visible;
- les timestamps news sont presents;
- le nombre de trades generes sur 24h est compare avant/apres;
- expectancy 24-48h post Phase 4.5 est mesuree si donnees disponibles;
- 0 regression sur les trades locked;
- checklist mise a jour sans cocher de faux positif.

### 7.17 Livrables Phase 4.5

- code agents et news corrige;
- sources news completes;
- fallback et mode degrade;
- SourceRegistry enrichi;
- Quality Gate complet;
- Event Mode + pre-event mode;
- regimes enrichis;
- audit log enrichi;
- tests unitaires;
- documentation:
  - `docs/FOURNIWELL_SIGNALS_V4_PHASE_4_5.md`;
  - `docs/SOURCES_AND_SCORING.md`;
  - `docs/V4_INSPECTION_ACTION_CHECKLIST.md`;
  - `docs/USER_GUIDE.md` si impact utilisateur;
- commit dedie;
- push GitHub.

## 8. Phase 5 - News Reaction Engine

Statut: livree le 2026-05-14.

Objectif: capter les vraies news qui bougent le marche, apres que les sources et prerequis Phase 4.5 soient en place.

Composants a creer:

- `FastNewsListener`;
- `EventClassifier`;
- `PriceReactionDetector`;
- `NewsReactionTradePlan`;
- boucle parallele de surveillance news.

Le moteur doit detecter:

- declarations Trump;
- declarations White House;
- declarations Netanyahu / Israel / Iran;
- sanctions;
- cessez-le-feu;
- attaque;
- blocage maritime;
- surprise Fed;
- surprise CPI/NFP/PCE.

Regles fondamentales:

- aucune news ne doit declencher un trade seule;
- il faut confirmer avec XAU/USD, oil, DXY et reaction prix;
- detecter fade trap;
- detecter negation dans les titres;
- suspendre en cas de collision multi-event;
- ne pas trader si marche ferme ou liquidite insuffisante;
- logger latence event -> detection -> trade.

Livrable:

- signaux news courts;
- validite 15-30 min;
- affichage clair: event exploitable ou non exploitable;
- trade type `NEWS_REACTION` separe des trades classiques.

Livraison effective:

- `FastNewsListener`: filtre les NewsFacts Tier 1-3 recents sur 30 minutes;
- `EventClassifier`: detecte escalation/de-escalation geopolitique, Fed dovish/hawkish, macro surprise CPI/PCE/NFP, declarations Trump/White House/Netanyahu;
- detection negation: `rejects deal` != `accepts deal`;
- `PriceReactionDetector`: confirme par XAU/USD, DXY, 10Y US et WTI/Brent quand applicable;
- detection `fade trap`;
- collision multi-event BUY/SELL -> `SUSPENDED` 10 minutes;
- `NewsReactionTradePlan`: entry type `NEWS_REACTION`, validite 15-30 min, SL serre, TP1/TP2/TP3, R/R;
- payload `news_reaction_setup`;
- affichage Desk, News Flow et Inspector;
- tests unitaires Trump/Iran/Fed-style, ceasefire, confirmation prix, niveaux SELL et collision.

## 9. Phase 6 - Refonte Trade Levels

Objectif: remplacer les SL/TP mecaniques par des niveaux de marche.

Actions:

- calculer SL/TP selon:
  - swing high/low;
  - pivots;
  - range;
  - breakout;
  - ATR;
  - niveaux psychologiques;
  - structure H1/H4/M15;
- ajouter niveaux psychologiques XAU/USD:
  - 00;
  - 50;
  - 25 si volatilite elevee;
- ajouter strategie de TP partiels:
  - TP1 = 50%;
  - TP2 = 30%;
  - TP3 = 20%;
- adapter SL/TP par setup:
  - trend continuation;
  - range;
  - breakout;
  - mean reversion;
  - pivot rejection;
  - news reaction;
- verifier direction:
  - BUY: SL < entry < TP1 < TP2 < TP3;
  - SELL: TP3 < TP2 < TP1 < entry < SL;
- verifier R/R apres calcul;
- refuser tout trade avec R/R < 1.5;
- ajouter validite dynamique:
  - M5: 2h;
  - M15: 4h;
  - H1: 12h;
  - H4: 24h;
  - D1: 72h.

Livrable:

- niveaux plus realistes;
- moins de SL/TP absurdes;
- trade plan mieux justifie.

## 10. Phase 7 - Multi-Strategy Engine

Objectif: ne plus dependre d'une seule logique directionnelle.

Strategies a creer:

- Trend continuation;
- Range trading;
- Breakout du jour;
- Mean reversion;
- Pivot rejection;
- News reaction.

Chaque strategie doit avoir:

- conditions d'entree;
- SL propre;
- TP propre;
- R/R minimum;
- validite;
- cooldown;
- confidence;
- session preferee.

Sessions:

- Asian session;
- London open;
- London-NY overlap;
- NY close.

Priorite:

1. NewsReaction si event confirme;
2. TrendContinuation en London-NY overlap;
3. Breakout du jour en London open;
4. RangeTrading en Asian session;
5. MeanReversion sur RSI/extreme;
6. PivotRejection si aucune priorite superieure.

Livrable:

- plusieurs types de setups;
- moins de trades forces en range;
- meilleur choix du setup dominant.

## 11. Phase 8 - Calibration et backtest

Objectif: arreter les poids arbitraires et valider si le systeme peut etre rentable.

Actions:

- collecter ou preparer un dataset historique XAU/USD;
- reconstruire payloads historiques si possible;
- rejouer les decisions;
- mesurer:
  - win rate;
  - expectancy;
  - drawdown;
  - nombre de trades;
  - R moyen;
  - performance par setup;
  - performance par agent;
- calibrer les poids agents;
- permettre poids 0 pour agents defaillants;
- caper le poids maximum d'un agent;
- logger chaque decision dans `reports/orchestrator_decisions.jsonl`:
  - score final;
  - contribution par agent;
  - verdict;
  - top 3 raisons.

Livrable:

- rapport backtest/calibration;
- poids justifies;
- Go/No-Go pour interface finale et production.

## 12. Phase 9 - Interface Fourniwell Signals

Objectif: rendre le produit lisible pour un utilisateur final.

Structure cible:

### Page 1 - Signal

- Prix XAU/USD.
- Chef de file.
- Biais.
- Confiance.
- TradingView live chart.
- Signal locked.
- Entry / SL / TP / validite.
- Raison courte du signal.
- Badge session courante.
- Badge News Reaction active si applicable.

### Page 2 - Agents

- Agents actifs.
- Boutons ON/OFF.
- Score.
- Confidence.
- Resume court.
- Contribution au signal.
- Fraicheur de chaque agent.
- Fiabilite source.

### Page 3 - News

- News recentes seulement.
- Source.
- Heure.
- Resume.
- Impact XAU/USD.
- Bullish / Bearish / Mixte.
- Badge source tier.
- Badge BREAKING / RECENT / OLD.
- Pas de bruit interne.

### Page 4 - Trades

- Trades actifs.
- Historique.
- Win / loss / expired.
- R multiple.
- Pourquoi le trade a gagne ou perdu.
- Filtre par setup.
- Export CSV.

### Page 5 - Inspector

- Sources.
- Debug agents.
- Logs.
- Contradictions.
- Data quality.
- Audit log.
- Orchestrator decisions.
- Visible uniquement admin.

Livrable:

- dashboard propre;
- separation viewer/admin;
- interface vendable.

## 13. Phase 10 - Preparation SaaS

Objectif: preparer les utilisateurs lecture seule et l'abonnement mensuel.

Actions:

- authentification;
- roles:
  - admin;
  - viewer;
- dashboard lecture seule pour abonnes;
- reglages visibles uniquement admin;
- preparation Stripe;
- protection du dashboard public;
- sessions securisees;
- logs d'utilisation;
- politique de confidentialite;
- CGU;
- disclaimer trading;
- dashboard demo;
- notifications email/Telegram si trade cree.

Livrable:

- Fourniwell Signals pret pour abonnement mensuel.

## 14. Phase 11 - QA, replay et validation

Objectif: valider avant de croire le systeme.

Actions:

- tests unitaires agents;
- tests TradeQualityGate;
- tests News Flow;
- tests fixtures Trump / Iran / Fed / CPI / NFP / PCE;
- replay du ledger;
- comparaison v3 vs v4;
- verification R/R;
- verification cooldown;
- verification circuit breaker;
- verification UI mobile/desktop;
- tests de charge;
- tests de resilience sources down;
- verification VPS;
- criteres Go/No-Go:
  - win rate cible documente;
  - expectancy positive;
  - max drawdown controle;
  - latence news < 60s sur breaking;
  - 0 bug critique sur periode de test.

Livrable:

- rapport de validation v4;
- decision Go/No-Go production.

## 15. Phase 12 - Deploiement VPS

Objectif: mettre Fourniwell Signals en ligne proprement.

Actions:

- deploiement sur VPS Hostinger;
- service `systemd`;
- Nginx reverse proxy;
- domaine `fourniwell.com`;
- HTTPS Let's Encrypt;
- auto-renew certificat;
- protection par mot de passe temporaire;
- monitoring uptime;
- alertes serveur down;
- logs;
- sauvegardes ledger;
- backup automatique;
- procedure rollback;
- procedure de mise a jour sans downtime;
- plan de disaster recovery.

Livrable:

- Fourniwell Signals accessible H24 en ligne.

## 16. Ordre officiel

1. Phase 0 - Rebranding et base propre. Statut: livre.
2. Phase 1 - Stopper les mauvais trades. Statut: livre.
3. Phase 2 - Quality Gate, cooldown et ledger. Statut: livre.
4. Phase 3 - News Flow v4. Statut: livre partiel, a completer par Phase 4.5.
5. Phase 4 - Rebuild des agents. Statut: livre partiel, a completer par Phase 4.5.
6. Phase 4.5 - Redressement exhaustif avant Phase 5. Statut: livree le 2026-05-14.
7. Phase 5 - News Reaction Engine. Statut: livree le 2026-05-14.
8. Phase 6 - Refonte Trade Levels.
9. Phase 7 - Multi-Strategy Engine.
10. Phase 8 - Calibration et backtest.
11. Phase 9 - Interface Fourniwell Signals.
12. Phase 10 - Preparation SaaS.
13. Phase 11 - QA, replay et validation.
14. Phase 12 - Deploiement VPS.

## 17. Regles de gouvernance

- Aucune phase ne commence sans etat Git documente.
- Toute phase doit avoir un commit dedie.
- Aucun deploiement VPS avant validation QA minimum.
- Toute source tier 4/5 doit etre exclue du scoring.
- Google News ne doit servir que de fallback/degraded discovery.
- Toute decision de trade doit pouvoir etre expliquee depuis le payload.
- Le dashboard viewer ne doit jamais afficher le bruit interne.
- L'Inspector peut contenir le detail technique, mais il doit etre reserve admin.
- Toute recommandation Claude ajoutee a la roadmap doit etre soit livree, soit marquee explicitement non livree avec raison.

## 18. Decision actuelle

Cette roadmap v1.1 devient la base de travail v4.0 apres validation utilisateur.

La prochaine phase officielle est:

`Phase 6 - Refonte Trade Levels`

Phase 5 est livree. La prochaine phase officielle est Phase 6, sauf correction critique de validation Phase 5.
