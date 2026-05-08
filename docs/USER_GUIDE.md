# Guide utilisateur Aureum Flux Terminal

## Objectif

Aureum Flux Terminal aide a lire rapidement le marche `XAU/USD`:

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
- inventaire agents;
- Source Registry;
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

- PriceAgent;
- TechnicalAgent;
- MacroAgent;
- GeopoliticalOilShockAgent;
- SentimentNewsAgent;
- CorrelationAgent;
- FlowPositioningAgent.

ElliottWaveAgent est archive et absent du produit actif. RiskManagerAgent et OrchestratorAgent servent a l'audit et a la prudence; ils ne doivent pas bloquer seuls une position verrouillable.

## Outcomes possibles

- `open`: trade encore ouvert.
- `partial`: TP1 touche.
- `win`: TP2 ou TP3 touche.
- `loss`: SL touche.
- `expired`: validite depassee.
- `invalidated`: invalidation contextuelle ou manuelle future.

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
- La v3.0 ajoutera des statuts intermediaires `WATCH_BUY` et `WATCH_SELL` pour afficher les setups a surveiller sans forcer un trade.
- Elliott ne doit pas etre utilise comme argument de trade tant qu'il n'est pas refonde et revalide explicitement.
- Un regime Hormuz/Oil Shock peut inverser la lecture classique geopolitique -> gold.
- Si le petrole capte la liquidite et que le dollar monte, gold peut baisser malgre le risque geopolitique.
- Le spread, l'heure, la volatilite et le calendrier macro doivent etre verifies avant toute decision.
