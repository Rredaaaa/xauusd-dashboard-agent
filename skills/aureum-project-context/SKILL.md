---
name: aureum-project-context
description: Contexte complet de reprise Aureum Flux Terminal pour Claude. A lire avant toute phase v3.0.
category: project
---

# Aureum Flux Project Context

## Mission

Aureum Flux Terminal est un dashboard local XAU/USD. Il aide l'utilisateur a lire le marche, pas a trader automatiquement.

Objectif final:
- decision claire `BUY`, `SELL`, `WAIT`, `NO_TRADE`, `WATCH_BUY`, `WATCH_SELL`, `TRADE_BUY` ou `TRADE_SELL`;
- explication concrete du pourquoi;
- SL/TP seulement quand le Quality Gate valide un trade exploitable;
- historique append-only des trades et signaux;
- sources auditees dans Inspector.

## Etat actuel

La v2.0 est terminee apres Phase 18:
- dashboard multi-vues;
- design structurel refait;
- Inspector;
- Orchestrateur v3;
- Trade Ledger;
- agents passifs;
- sources FRED, CFTC, WGC/ETF, IG Weekend, WTI/Brent, Event Facts, Trump/Political Statements.

La suite est v3.0:
- Phase 19: audit documentation;
- Phase 20: audit editorial phrase par phrase;
- Phase 21: Explanation Layer;
- Phase 22: News Facts v3;
- Phase 24: Data Routing / Preflight;
- Phase 25: Chart Store OHLC;
- Phase 26: Elliott quarantine;
- Phase 27A: Elliott Removal + TradingView Chart, livree;
- Phase 27B: Technical Decision Engine v1, livree;
- Phase 28: Scenario Engine v3, livree;
- Phase 29: Orchestrator v3 dynamique, livree;
- Phase 30A: UX Product Split + Noise Gate, livree;
- Phase 30: Trade Tracker v3, livree;
- Phase 31: Replay v3, livree;
- Phase 32: Settings locaux, livree;
- Phase 33: Reports v3, livree;
- Phase 34: QA finale v3.0, livree.

## Regles non negociables

1. Aucune phase ne commence sans validation explicite utilisateur.
2. Avant phase: verifier Git/GitHub.
3. Apres phase: tests, commit, push.
4. Ne jamais lancer de trading automatique.
5. Ne pas mentionner de broker specifique dans l'interface.
6. Ne pas forcer un trade pour reduire `WAIT`.
7. Ne pas inclure Elliott dans le raisonnement utilisateur tant qu'il n'est pas refonde et explicitement revalide.
8. Les details techniques de source restent dans Inspector.
9. Le dashboard principal doit afficher le resultat utile, pas toute la plomberie.
10. Le skill `ui-ux-pro-max` doit etre utilise comme garde-fou UX pour Phase 30A et toute refonte visuelle suivante.

## Probleme principal v3

Le terminal affiche encore des phrases trop vagues. Exemple mauvais:

> Le theme Iran/Hormuz existe, mais le petrole ne confirme pas un choc.

Le terminal doit parler comme un analyste senior a un trader:

> Plusieurs titres mentionnent Iran/Hormuz, mais WTI et Brent reculent. Le marche ne price donc pas encore un choc petrole. Impact XAU/USD: prudence, pas de confirmation refuge. Action: attendre confirmation oil/DXY avant de valider un trade.

## Direction produit

Aureum Flux doit separer:
- `MARKET_BIAS`: direction probable;
- `WATCH_SETUP`: setup surveille, pas encore tradable;
- `TRADE_SETUP`: trade exploitable;
- `NO_TRADE`: aucune opportunite propre.

Le terminal doit etre capable de dire:

> Aucun trade exploitable, mais setup SELL surveille si cassure M15 sous support avec DXY confirme.

Depuis la Phase 29, l'Orchestrateur v3 ajuste les poids selon regime, data quality, mode event et confirmation technique. Il peut produire `NO_TRADE`, `WAIT`, `WATCH_BUY`, `WATCH_SELL`, `TRADE_BUY` ou `TRADE_SELL`.

## Direction UX Phase 30A

Skill installe:
- `ui-ux-pro-max`;
- repo: `https://github.com/nextlevelbuilder/ui-ux-pro-max-skill`;
- chemin local Codex: `/Users/reda/.codex/skills/ui-ux-pro-max`.

Structure cible:
- `Desk`: prix, chef de file, biais, TradingView, signal locked;
- `Agents`: scoring et positions agents;
- `News Flow`: informations recentes utiles uniquement;
- `Reports`: historique trades et exports;
- `Inspector`: bruit moteur, logs, sources, preflight, payloads et audit.

Regles Phase 30A:
- pas de termes internes hors Inspector;
- pas de chaines marche hors Inspector;
- pas de news neutres ou anciennes dans News Flow principal;
- pas de SL/TP affiches comme trade si les niveaux sont incoherents ou si le signal est seulement `WATCH_*`;
- toute plomberie utile au moteur doit rester dans Inspector ou invisible.

## Fichiers importants

- `xauusd_agent.py`: monolithe actuel.
- `tests/test_xauusd_agent.py`: tests existants.
- `docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md`: roadmap officielle v3.
- `reports/trade_ledger.jsonl`: ledger local ignore Git.
- `reports/audit_log.jsonl`: audit local ignore Git.

## Inspiration externe

Repo analyse: `HKUDS/Vibe-Trading`.

A reprendre:
- skills par domaine;
- data routing;
- preflight;
- swarm presets;
- replay/backtest;
- shadow account;
- settings;
- report generator.

A ne pas reprendre:
- UI React complete;
- multi-marche generaliste;
- Elliott simple du repo tel quel;
- strategy generator universel.

## Decision produit Phase 27

Elliott est archive pour la v3.0 active:
- Phase 27A l'a retire du dashboard, payload public, Inspector et orchestrateur;
- il ne doit plus etre affiche comme agent, preuve, contradiction ou raison de decision;
- la charte principale est une vraie charte TradingView;
- le Chart Store reste en Inspector pour l'audit des donnees OHLC;
- Phase 27B cree un `TechnicalDecisionEngine` base sur structure, indicateurs, niveaux, volatilite et confirmations.
- Phase 28 cree un `ScenarioEngine v3` qui expose scenario principal, scenario alternatif, declencheur, invalidation, confirmations, validations et contradictions dans l'onglet Decision.

Indicateurs techniques cibles:
- Market Structure: swing highs/lows, HH/HL, LH/LL, BOS, CHoCH, retest, range high/low;
- Trend: EMA 20/50/100/200, pente EMA, alignement M15/H1/H4/D1;
- Momentum: RSI7/RSI14, MACD, divergence RSI/prix;
- Volatility: ATR14, range du jour vs ATR, compression/expansion, volume spike;
- Levels: high/low jour et veille, open, sessions Asia/London/NY, VWAP si disponible, pivots;
- Liquidity: sweep, fausse cassure, retour dans range;
- Cross confirmation: DXY, US10Y, real yield, WTI/Brent, Silver, GDX/GDXJ, VIX/GVZ.

## Phase 23 Contract

### Role

Servir de contexte de reprise global avant toute phase v3.0.

### Inputs

- Roadmap officielle;
- etat Git/GitHub;
- historique des phases;
- contraintes utilisateur;
- docs projet.

### Outputs

- orientation de phase;
- rappel des regles non negociables;
- fichiers a lire;
- risques a surveiller.

### Methodologie

1. Lire le plan v3.
2. Verifier que v3.0 est toujours livree jusqu'a Phase 34.
3. Verifier Git/GitHub.
4. Identifier la prochaine action autorisee.
5. Ne jamais sauter une phase sans accord explicite.

### Limites

- Ce skill ne remplace pas la roadmap.
- Il ne donne pas de logique trading.
- Il ne doit pas justifier une modification hors phase.

### Bons exemples

- `Toute phase post-v3.0 commence seulement apres git clean, origin/main sync et accord utilisateur.`
- `Une evolution du scoring doit conserver Replay, Settings, Reports v3 et Trade Ledger.`

### Mauvais exemples

- Reintroduire Elliott dans le dashboard ou le scoring.
- Remplacer TradingView par une charte interne principale.
- Modifier le moteur alors que la phase demande seulement la documentation.
