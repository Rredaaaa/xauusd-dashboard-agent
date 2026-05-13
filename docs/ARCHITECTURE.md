# Architecture

Le projet est encore concentre dans `xauusd_agent.py` pour rester simple a lancer en local. Le fichier contient plusieurs modules logiques, meme s'ils ne sont pas encore separes en packages Python.

## Flux general

1. Collecte des sources marche, macro, news, flux et politique.
2. Normalisation dans des dataclasses.
3. Construction de la Data Quality.
4. Preflight data et routage des sources.
5. Construction des agents passifs.
6. Orchestrateur v3 dynamique.
7. Scenario Engine v3: scenario principal, alternatif, trigger, invalidation, confirmations.
8. Trade Quality Gate et Trade Ledger.
9. Replay v3 et Reports v3.
10. Settings locaux utilisateur.
11. Payload JSON, rapport Markdown, dashboard HTML.
12. Inspector et audit log.

## Modules logiques

- Collecte prix: XAU/USD spot, IG Weekend Gold, DXY, taux, WTI/Brent, cross-assets.
- Collecte macro: FRED, Fed, BEA, CME FedWatch link.
- Collecte flux: CFTC COT, WGC ETF, BlackRock IAU.
- Collecte news: RSS, Google News/fallback, White House.
- Analyse technique: `TechnicalDecisionEngine`, EMA, RSI, MACD, volume, Chart Store OHLC.
- Analyse fondamentale: dollar, taux, macro, real yield.
- Analyse geopolitique: risk-off, Hormuz/Oil Shock, politique, oil/dollar liquidity.
- Agents passifs: Price, Technical, Macro, Geopolitical/Oil, Sentiment/News, Correlation, Flow/Positioning, Event Facts, Trump/Political Statements, Risk Manager, Orchestrator.
- Orchestrateur v3: poids dynamiques multi-agents, contre-signaux, Quality Gate v3 et statuts `NO_TRADE`, `WATCH_*`, `TRADE_*`.
- Scenario Engine v3: traduit la decision en plan trader lisible sans creer automatiquement un trade.
- Preflight v3: statut `READY`, `DEGRADED`, `SOURCE_STALE`, `NO_TRADE_DATA` ou `OFFLINE`.
- Scoring v2.1: separation entre blockers et warnings. Un warning de source secondaire degrade la confiance; seul un blocage dur force `WAIT`.
- Profil v4 Phase 1: seuil trade a `65/100`, RR minimal `1.50R`, trois agents decisionnels valides, data quality minimale `60/100`, cooldown outcome et circuit breaker.
- Chart Store: OHLC M5/M15/H1/H4/D1 pour qualite technique, affiche en Inspector.
- Charte principale v3: TradingView dans `Desk`, pas la charte interne.
- Trade Ledger: signal locking append-only.
- Replay v3: rejoue les TradePlan avec `audit_log.jsonl`.
- Settings v3: `config/aureum_settings.json` ajuste seuils, agents actifs, cooldown et RR sans modifier le code.
- Reports v3: exports Markdown/JSON locaux dans `reports/v3/`.
- Inspector: audit sources/agents/trades.
- Phase 30A UX split: `Desk`, `Agents`, `News Flow`, `Reports`, `Inspector`.
- Noise Gate: la plomberie moteur reste dans Inspector ou invisible.

Note de passation v3.0:
- l'architecture v2 reste concentree dans `xauusd_agent.py`;
- la v3.0 a livre l'audit editorial, News Facts, Preflight, Chart Store, Phase 27A, Phase 27B, Phase 28, Phase 29, Phase 30A, Phase 30, Phase 31, Phase 32 et Phase 33;
- `ElliottWaveAgent` est supprime du code actif et n'apparait plus dans les surfaces actives;
- Phase 27B a remplace Elliott par un `TechnicalDecisionEngine` auditable v1;
- la charte principale est TradingView dans `Desk`;
- Phase 28 expose les statuts scenario `WATCH_BUY`, `WATCH_SELL`, `TRADE_BUY`, `TRADE_SELL` et `WAIT` pour montrer le prochain trigger sans forcer un trade;
- Phase 29 a livre l'Orchestrateur v3 dynamique: il ajuste les poids selon regime, qualite source, mode event et confirmation technique;
- Phase 30A a separe l'interface trader du bruit moteur;
- Phase 31 a ajoute le replay depuis `audit_log.jsonl`;
- Phase 32 a ajoute les settings locaux;
- Phase 33 a ajoute les exports Reports v3;
- la roadmap detaillee est dans `docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md`.

## Dataclasses importantes

- `BriefingBundle`: paquet complet utilise par le rendu.
- `SourceSnapshot` / `DataQualitySnapshot`: gouvernance sources.
- `PreflightCheck` / `DataRoute`: statut de readiness avant decision.
- `ChartStore` / `ChartTimeframe`: qualite OHLC par timeframe.
- `ScenarioPlan`: scenario principal, alternatif, trigger, invalidation, validations et contradictions.
- `AgentResult`: sortie d'un agent.
- `OrchestratorDecision`: decision globale multi-agents.
- `TradePlan` / `TradeLedgerSummary`: trades historises.
- `ReplayReport` / `ReplayTradeResult`: replay de TradePlan sur snapshots.
- `UserSettings` / `SettingsValidation`: configuration locale et validation.
- `ReportExport`: fichiers Reports v3 generes.

Regle de decision actuelle:
- source prix XAU/USD principale absente/stale = blocage dur;
- data quality tres faible = blocage dur;
- WGC ETF stale, Google News weak ou mode event modere = warning;
- RiskManagerAgent ne compte pas comme contradiction directionnelle pour verrouiller un TradePlan; OrchestratorAgent legacy et ElliottWaveAgent sont supprimes du produit actif.
- `TRADE_*` exige TechnicalDecisionEngine confirme, invalidation claire, confirmations decisionnelles et risk/reward minimum; sinon le terminal reste en `WATCH_*`, `WAIT` ou `NO_TRADE`.
- `TradeRecommendation`: signal live.

## Fichiers generes

Le dossier `reports/` recoit:

- `xauusd_dashboard.html`
- `xauusd_data.json`
- `xauusd_report.md`
- `trade_ledger.jsonl`
- `audit_log.jsonl`
- `chart_store_cache.json`
- `v3/`: daily report, signal report, trade report, post-mortem, news audit, source quality audit, replay report.

Le dossier `config/` peut recevoir:

- `aureum_settings.json`: settings locaux ignores par Git;
- `aureum_settings.example.json`: modele suivi par Git.

Ces fichiers sont ignores par Git car ils changent a chaque execution.

## Serveur live

Le serveur local utilise `http.server.ThreadingHTTPServer`.

Endpoints:

- `/`: dashboard complet;
- `/fragment`: fragment HTML rafraichi par le client;
- `/api/live.json`: payload JSON live.

L'etat de l'onglet actif est conserve cote client via `localStorage` pour eviter que le refresh renvoie l'utilisateur au premier onglet.

## UX active v3.0

Le dashboard doit etre structure en 5 pages:

- `Desk`: prix, chef de file, biais, TradingView, signal locked;
- `Agents`: scoring et positions agents;
- `News Flow`: flux d'informations recentes et utiles;
- `Reports`: rapports et historique trades;
- `Inspector`: details techniques, logs, source registry, preflight, data quality et bruit moteur.

Les calculs internes peuvent conserver des noms techniques, mais l'UI utilisateur ne doit pas afficher les termes internes, chaines marche, validations agent ou news neutres anciennes hors Inspector.

## Points d'extension

- Extraire progressivement `xauusd_agent.py` en modules.
- Ajouter une API OHLC spot XAU/USD professionnelle.
- Ajouter alertes/notifications de TradePlan exploitable.
- Remplacer certains feeds news par des flux institutionnels plus fiables.
- Industrialiser l'hebergement si le dashboard doit sortir du Mac local.
