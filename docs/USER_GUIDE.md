# Guide utilisateur Fourniwell Signals

## Objectif

Fourniwell Signals, anciennement Aureum Flux Terminal, aide a lire rapidement le marche `XAU/USD`:

- direction live probable: `BUY`, `SELL`, `WAIT`, `WATCH_BUY`, `WATCH_SELL`, `TRADE_BUY`, `TRADE_SELL` ou `NO_TRADE`;
- score global et raisons;
- SL/TP proposes;
- sources et agents qui valident ou contredisent;
- Trade Plans historises si un signal est exploitable.

Le terminal est un outil d'analyse. Il ne remplace pas le jugement du trader.

## Pages cible Phase 30A

La prochaine structure UX officielle separe les pages trader et le bruit moteur.

### Desk

Vue de decision immediate:

- prix XAU/USD live;
- position du chef de file;
- biais global;
- charte TradingView;
- signal locked;
- statut du trade: aucun trade, setup surveille ou trade exploitable;
- SL/TP uniquement si les niveaux sont valides et le trade verrouillable.

Interdit dans Desk:
- textes longs;
- chaines marche;
- details de source;
- news neutres;
- termes internes de moteur;
- informations anciennes sans impact actuel.

### Agents

Vue de controle du scoring:

- score global;
- decision de l'Orchestrateur v3;
- position de chaque agent;
- poids de chaque agent;
- contradictions utiles;
- raison courte du statut final.

### News Flow

Vue flux d'information:

- flash infos recentes;
- politique;
- macro;
- geopolitique;
- petrole/dollar;
- source;
- heure;
- impact `BULLISH`, `BEARISH` ou `NEUTRAL`.

Regle: les informations `NEUTRAL`, anciennes, redondantes ou sans impact immediat sont cachees par defaut.

### Reports

Vue memoire:

- rapports Markdown/JSON;
- historique de decisions;
- trades locked;
- trades actifs;
- trades expires ou invalides;
- post-mortem quand disponible.

### Inspector

Vue moteur:

- Source Registry;
- Data Quality;
- Preflight;
- routes internes;
- chaines marche;
- validations internes;
- logs;
- audit;
- payload agents.

Tout ce qui sert au moteur mais pas a l'utilisateur final doit rester ici.

## Modules analytiques

Le Scenario Engine v3 explique:

- le scenario principal surveille;
- le scenario alternatif;
- le declencheur attendu;
- l'invalidation;
- les confirmations requises;
- les validations et contradictions.

Important: `WATCH_BUY` ou `WATCH_SELL` veut dire "setup surveille", pas "trade a prendre". Un trade verrouille reste gere par le Trade Tracker et le Quality Gate.

### Technical Decision Engine

Vue technique:

- EMA 20/50/100/200;
- RSI7/RSI14 cible v3;
- MACD 5/34/5;
- volume;
- Chart Store OHLC M5/M15/H1/H4/D1 en diagnostic;
- scenarios hausse/baisse/attente;
- Technical Decision Engine: direction, structure, trigger, invalidation, SL et TP.

Note: Elliott Wave est archive dans la roadmap v3.0. Depuis la Phase 27, il n'apparait plus dans le dashboard, le payload public, l'Inspector ou l'orchestrateur. Il ne doit pas etre lu comme une preuve de decision.

### Technical Decision Engine v3

Le moteur technique remplace Elliott par des regles auditables:

- `Market Structure`: swing highs/lows, HH/HL, LH/LL, BOS, CHoCH, retest, range high/low.
- `Trend`: EMA 20/50/100/200, pente des EMA, alignement M15/H1/H4/D1.
- `Momentum`: RSI7/RSI14, MACD, divergence RSI/prix, acceleration ou deceleration.
- `Volatility`: ATR14, range du jour vs ATR, compression/expansion, volume spike proxy.
- `Levels`: high/low jour et veille, open, sessions Asia/London/NY, VWAP si disponible, pivots P/R1/R2/S1/S2.
- `Liquidity`: sweep de high/low recent, fausse cassure, retour dans range, distance au prochain niveau.
- `Cross confirmation`: DXY, US10Y, 10Y real yield, WTI/Brent, Silver, GDX/GDXJ, VIX/GVZ.

Les statuts attendus sont:

- `WATCH_BUY`: setup haussier en preparation, trigger pas encore confirme.
- `BUY`: `WATCH_BUY` + trigger confirme + invalidation claire + risk/reward acceptable + Preflight non bloquant.
- `WATCH_SELL`: setup baissier en preparation, trigger pas encore confirme.
- `SELL`: `WATCH_SELL` + trigger confirme + invalidation claire + risk/reward acceptable + Preflight non bloquant.
- `WAIT`: range sale, contradiction forte, volatilite anormale, source bloquante ou prix trop loin du niveau d'entree.

### Macro

Vue macro:

- DXY;
- taux US;
- FRED DGS10/DGS2/T10YIE/DFII10;
- calendrier Fed/BEA;
- MacroAgent.

### Geopolitics & Flows

Vue risque externe:

- geopolitique;
- regime de volatilite;
- stress politique petrole/dollar;
- ETF flows;
- Event Facts;
- Trump / White House;
- headlines expliquees.

### Inspector

Vue d'audit:

- sources actives;
- dernier refresh;
- sources missing/stale/weak;
- Preflight;
- Chart Store;
- agents actifs;
- sorties recentes des agents;
- trades crees;
- outcomes des trades;
- data quality score;
- Decision Gate et Trade Gate.

Cet onglet sert a comprendre pourquoi une decision ou un trade existe.

### Reports

Vue exports:

- rapport Markdown;
- payload JSON;
- daily report v3;
- signal report;
- trade report;
- post-mortem report;
- replay report;
- news audit;
- source quality audit;
- Trade Ledger;
- Inspector.

## Signal live vs Trade Plan

### Signal live

Le signal live est calcule a chaque refresh. Il depend du prix, des sources, du regime, des agents, du Scenario Engine v3 et de l'Orchestrateur v3. Il peut passer de `BUY` a `WATCH_BUY`, `WAIT` ou `NO_TRADE`, si le contexte change.

Depuis la mise a jour scoring du 07/05/2026, un warning ne force plus automatiquement `WAIT`. Le terminal distingue:

- blocage dur: prix XAU/USD principal absent/stale, data quality trop faible, contradiction directionnelle majeure, RR insuffisant ou regime extreme;
- warning: source secondaire stale, news weak, data quality degradee mais exploitable, mode event modere;
- setup surveille: `WATCH_BUY` ou `WATCH_SELL` garde une direction probable sans verrouiller un trade;
- signal exploitable: `TRADE_BUY` ou `TRADE_SELL` exige sources, confirmations, invalidation et risk/reward suffisants;
- signal valide avec confiance reduite: `BUY` ou `SELL` reste possible dans les surfaces de synthese, mais les warnings sont visibles dans Decision/Inspector.

Depuis Fourniwell Signals v4 Phase 1:

- le terminal verrouille moins de trades et bloque les signaux moyens;
- `TRADE_*` exige score >= `65/100`, trois agents decisionnels valides, confidence agent >= `65/100`, data quality >= `60/100` et RR TP1 >= `1.50R`;
- une contradiction isolee devient un warning, trois contradictions bloquent;
- les vrais stop restent intacts: source critique bloquee, data quality faible, direction absente, SL/TP incoherents, RR sous `1.50R`, regime geopolitique/petrole fort ou macro HIGH proche.

### Trade Plan

Un Trade Plan est cree uniquement quand le Trade Quality Gate valide le signal. Il fige:

- date de creation;
- direction;
- entry/reference price;
- zone d'entree;
- SL;
- TP1/TP2/TP3;
- agents validant;
- agents contradictoires;
- sources;
- regime;
- raisons d'invalidation;
- outcome.

Le Trade Plan est stocke dans:

```text
reports/trade_ledger.jsonl
```

Il n'est pas modifie retroactivement par le signal live. Si le prix atteint SL ou TP, une nouvelle ligne append-only met a jour son outcome.

Le Trade Quality Gate compte seulement les agents decisionnels pour confirmer ou contredire une direction:

- PriceActionAgent;
- TechnicalAgent;
- MacroAgent;
- GeopoliticalOilShockAgent;
- SentimentNewsAgent;
- CorrelationAgent;
- FlowPositioningAgent.

ElliottWaveAgent est supprime du produit actif. OrchestratorAgent legacy est retire du scoring. RiskManagerAgent sert a la prudence; OrchestratorDecision v3 reste la structure de synthese.

## Replay v3

Le replay permet de relire les TradePlan avec les snapshots de prix historiques du terminal:

```bash
python xauusd_agent.py --replay --replay-output reports/v3/replay_report.md
```

Il compare chaque TradePlan aux prix stockes dans `reports/audit_log.jsonl` et produit:

- outcome rejoue;
- prix apres 1h/2h/4h/24h si les snapshots existent;
- R favorable/adverse maximal;
- raison du resultat.

Le replay ne cree pas de trade. Il sert a mesurer si le terminal s'ameliore.

## Settings locaux

Le comportement peut etre ajuste sans modifier le code:

```bash
python xauusd_agent.py --init-settings
```

Le fichier local est:

```text
config/aureum_settings.json
```

Parametres importants:

- `scoring_mode`: `balanced` par defaut, `conservative` possible;
- `trade_threshold`: score minimum pour verrouiller un TradePlan;
- `minimum_risk_reward`: RR minimum;
- `minimum_agent_confidence`: confiance minimale d'un agent validant;
- `min_data_quality`: seuil minimum pour autoriser un TradePlan;
- `cooldown_minutes`, `cooldown_after_loss_minutes`, `cooldown_after_win_minutes`, `cooldown_after_expired_minutes`: evite de creer plusieurs trades similaires ou de reprendre trop vite apres outcome;
- `max_trades_per_24h`, `circuit_breaker_after_n_losses`: limites de securite;
- `active_agents`: agents actifs dans le terminal. Depuis la Phase 35, ils peuvent etre actives/desactives depuis la page Agents avec un bouton ON/OFF devant chaque agent.

## Outcomes possibles

- `open`: trade encore ouvert.
- `partial`: TP1 touche.
- `win`: TP2 ou TP3 touche.
- `loss`: SL touche.
- `expired`: validite depassee.
- `invalidated`: invalidation contextuelle ou manuelle future.

Depuis la Phase 2 v4, la validite d'un trade est dynamique: M5 = 2h, M15 = 4h, H1 = 12h, H4 = 24h, D1 = 72h. En regime event actif, cette duree est reduite de 25%. Le terminal garde aussi un audit append-only dans `reports/trade_gate_audit.jsonl` pour expliquer les creations, refus, expirations et outcomes.

## Audit log

Chaque generation ajoute une ligne dans:

```text
reports/audit_log.jsonl
```

Ce fichier trace:

- decision;
- regime;
- data quality;
- issues sources;
- sorties agents;
- gate trades;
- trades.

## Regles de prudence

- `BUY` ou `SELL` ne veut pas dire entrer au marche sans verification.
- `WAIT` veut dire que le terminal refuse de valider une direction exploitable.
- `DEGRADED` ne veut pas toujours dire trade impossible: cela peut vouloir dire trade possible avec confiance reduite si le prix principal et le RR sont exploitables.
- `WATCH_BUY` et `WATCH_SELL` affichent des setups a surveiller sans forcer un trade.
- Elliott ne doit pas etre utilise comme argument de trade: il est supprime du produit actif.
- Un regime Hormuz/Oil Shock peut inverser la lecture classique geopolitique -> gold.
- Si le petrole capte la liquidite et que le dollar monte, gold peut baisser malgre le risque geopolitique.
- Le spread, l'heure, la volatilite et le calendrier macro doivent etre verifies avant toute decision.
