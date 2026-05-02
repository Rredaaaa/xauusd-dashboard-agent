# Architecture

Le projet est encore concentre dans `xauusd_agent.py` pour rester simple a lancer en local. Le fichier contient plusieurs modules logiques, meme s'ils ne sont pas encore separes en packages Python.

## Flux general

1. Collecte des sources marche, macro, news, flux et politique.
2. Normalisation dans des dataclasses.
3. Construction de la Data Quality.
4. Construction des agents passifs.
5. Orchestrateur v2.
6. Trade Quality Gate et Trade Ledger.
7. Payload JSON, rapport Markdown, dashboard HTML.
8. Inspector et audit log.

## Modules logiques

- Collecte prix: XAU/USD spot, IG Weekend Gold, DXY, taux, WTI/Brent, cross-assets.
- Collecte macro: FRED, Fed, BEA, CME FedWatch link.
- Collecte flux: CFTC COT, WGC ETF, BlackRock IAU.
- Collecte news: RSS, Google News/fallback, White House.
- Analyse technique: EMA, RSI, MACD, volume, Elliott Wave passif.
- Analyse fondamentale: dollar, taux, macro, real yield.
- Analyse geopolitique: risk-off, Hormuz/Oil Shock, politique, oil/dollar liquidity.
- Agents passifs: Price, Technical, Elliott Wave, Macro, Geopolitical/Oil, Sentiment/News, Correlation, Flow/Positioning, Event Facts, Trump/Political Statements, Risk Manager, Orchestrator.
- Orchestrateur v2: pondération multi-agents, contre-signaux et Quality Gate.
- Trade Ledger: signal locking append-only.
- Inspector: audit sources/agents/trades.

Note de passation v3.0:
- l'architecture v2 reste concentree dans `xauusd_agent.py`;
- la v3.0 doit commencer par l'audit editorial et la couche d'explication avant d'ajouter de nouveaux moteurs;
- `ElliottWaveAgent` est actuellement passif et experimental; il doit etre sorti du scoring ou refondu avec un vrai Chart Store OHLC multi-timeframe.

## Dataclasses importantes

- `BriefingBundle`: paquet complet utilise par le rendu.
- `SourceSnapshot` / `DataQualitySnapshot`: gouvernance sources.
- `AgentResult`: sortie d'un agent.
- `OrchestratorDecision`: decision globale multi-agents.
- `TradePlan` / `TradeLedgerSummary`: trades historises.
- `TradeRecommendation`: signal live.

## Fichiers generes

Le dossier `reports/` recoit:

- `xauusd_dashboard.html`
- `xauusd_data.json`
- `xauusd_report.md`
- `trade_ledger.jsonl`
- `audit_log.jsonl`

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
- Ajouter alertes/notifications de TradePlan exploitable.
- Remplacer certains feeds news par des flux institutionnels plus fiables.
- Suivre le plan v3.0: `docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md`.
