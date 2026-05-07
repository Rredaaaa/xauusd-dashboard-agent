# Architecture

Le projet est encore concentre dans `xauusd_agent.py` pour rester simple a lancer en local. Le fichier contient plusieurs modules logiques, meme s'ils ne sont pas encore separes en packages Python.

## Flux general

1. Collecte des sources marche, macro, news, flux et politique.
2. Normalisation dans des dataclasses.
3. Construction de la Data Quality.
4. Preflight data et routage des sources.
5. Construction des agents passifs.
6. Orchestrateur v2 puis cible Orchestrateur v3.
7. Trade Quality Gate et Trade Ledger.
8. Payload JSON, rapport Markdown, dashboard HTML.
9. Inspector et audit log.

## Modules logiques

- Collecte prix: XAU/USD spot, IG Weekend Gold, DXY, taux, WTI/Brent, cross-assets.
- Collecte macro: FRED, Fed, BEA, CME FedWatch link.
- Collecte flux: CFTC COT, WGC ETF, BlackRock IAU.
- Collecte news: RSS, Google News/fallback, White House.
- Analyse technique: `TechnicalDecisionEngine`, EMA, RSI, MACD, volume, Chart Store OHLC.
- Analyse fondamentale: dollar, taux, macro, real yield.
- Analyse geopolitique: risk-off, Hormuz/Oil Shock, politique, oil/dollar liquidity.
- Agents passifs: Price, Technical, Macro, Geopolitical/Oil, Sentiment/News, Correlation, Flow/Positioning, Event Facts, Trump/Political Statements, Risk Manager, Orchestrator.
- Orchestrateur v2: pondération multi-agents, contre-signaux et Quality Gate.
- Preflight v3: statut `READY`, `DEGRADED`, `SOURCE_STALE`, `NO_TRADE_DATA` ou `OFFLINE`.
- Scoring v2.1: separation entre blockers et warnings. Un warning de source secondaire degrade la confiance; seul un blocage dur force `WAIT`.
- Chart Store: OHLC M5/M15/H1/H4/D1 pour qualite technique, affiche en Inspector.
- Charte principale v3: TradingView dans Market/Technical, pas la charte interne.
- Trade Ledger: signal locking append-only.
- Inspector: audit sources/agents/trades.

Note de passation v3.0:
- l'architecture v2 reste concentree dans `xauusd_agent.py`;
- la v3.0 a livre l'audit editorial, News Facts, Preflight, Chart Store, Phase 27A et Phase 27B;
- `ElliottWaveAgent` est archive dans la roadmap v3.0 et n'apparait plus dans les surfaces actives;
- Phase 27B a remplace Elliott par un `TechnicalDecisionEngine` auditable v1;
- la charte principale est TradingView dans Market/Technical;
- la decision v3 ajoutera les statuts `WATCH_BUY` et `WATCH_SELL` aux cotes de `BUY`, `SELL` et `WAIT` pour exposer les setups en surveillance sans forcer un trade;
- la roadmap detaillee est dans `docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md`.

## Dataclasses importantes

- `BriefingBundle`: paquet complet utilise par le rendu.
- `SourceSnapshot` / `DataQualitySnapshot`: gouvernance sources.
- `PreflightCheck` / `DataRoute`: statut de readiness avant decision.
- `ChartStore` / `ChartTimeframe`: qualite OHLC par timeframe.
- `AgentResult`: sortie d'un agent.
- `OrchestratorDecision`: decision globale multi-agents.
- `TradePlan` / `TradeLedgerSummary`: trades historises.

Regle de decision actuelle:
- source prix XAU/USD principale absente/stale = blocage dur;
- data quality tres faible = blocage dur;
- WGC ETF stale, Google News weak ou mode event modere = warning;
- RiskManagerAgent et OrchestratorAgent ne comptent pas comme contradictions directionnelles pour verrouiller un TradePlan; ElliottWaveAgent est absent du produit actif.
- `TradeRecommendation`: signal live.

## Fichiers generes

Le dossier `reports/` recoit:

- `xauusd_dashboard.html`
- `xauusd_data.json`
- `xauusd_report.md`
- `trade_ledger.jsonl`
- `audit_log.jsonl`
- `chart_store_cache.json`

Ces fichiers sont ignores par Git car ils changent a chaque execution.

## Serveur live

Le serveur local utilise `http.server.ThreadingHTTPServer`.

Endpoints:

- `/`: dashboard complet;
- `/fragment`: fragment HTML rafraichi par le client;
- `/api/live.json`: payload JSON live.

L'etat de l'onglet actif est conserve cote client via `localStorage` pour eviter que le refresh renvoie l'utilisateur au premier onglet.

## Points d'extension

- Extraire progressivement `xauusd_agent.py` en modules.
- Ajouter une API OHLC spot XAU/USD professionnelle.
- Integrer TradingView comme charte utilisateur principale.
- Ajouter `TechnicalDecisionEngine` pour remplacer Elliott.
- Ajouter alertes/notifications de TradePlan exploitable.
- Remplacer certains feeds news par des flux institutionnels plus fiables.
- Suivre le plan v3.0: `docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md`.
