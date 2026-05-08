# Sources et scoring

Ce document resume les sources utilisees par Aureum Flux Terminal et la maniere dont elles entrent dans l'analyse.

## Politique generale

Les sources sont classees par tiers:

- Tier 1: source officielle ou primaire.
- Tier 2: donnees financieres fiables ou media majeur.
- Tier 3: source specialisee a confirmer.
- Tier 4: agregateur, headline ou source faible.

Une source absente, stale ou faible degrade la `Data Quality`, mais tout warning ne doit pas forcer `WAIT`. Depuis la mise a jour scoring du 07/05/2026, le moteur separe:

- blocage dur: prix XAU/USD principal absent/stale, data quality tres faible, direction absente, RR inexploitable ou contradiction directionnelle majeure;
- warning: source secondaire stale, news faible, data quality degradee mais utilisable, mode event modere;
- validation avec confiance reduite: signal `BUY`/`SELL` autorise, mais raisons de prudence affichees;
- TradePlan verrouille: uniquement si le Trade Quality Gate valide le signal et fige entry/SL/TP.

## Sources prix

| Source | Usage | Agents |
| --- | --- | --- |
| Investing.com XAU/USD | Spot principal XAU/USD | PriceAgent, RiskManagerAgent, OrchestratorAgent |
| IG Weekend Gold | Proxy week-end indicatif | PriceAgent, RiskManagerAgent |
| Yahoo Finance GC=F | Proxy futures pour Chart Store OHLC, volume et fallback technique | TechnicalAgent |
| TradingView widget | Charte utilisateur principale cible v3 | UI uniquement, pas source de scoring backend |

IG Weekend Gold est distinct du spot semaine. Il sert a lire le marche week-end, pas a remplacer le spot classique.
TradingView sert a afficher une vraie charte live dans le dashboard principal. Les calculs backend continuent d'utiliser les donnees auditees par SourceRegistry/Chart Store tant qu'aucune API officielle TradingView n'est integree.

## Sources macro

| Source | Usage | Agents |
| --- | --- | --- |
| FRED DGS10 | 10Y nominal US officiel | MacroAgent, RiskManagerAgent |
| FRED DGS2 | 2Y nominal US officiel | MacroAgent |
| FRED T10YIE | Breakeven inflation 10Y | MacroAgent |
| FRED DFII10 | 10Y reel officiel | MacroAgent, RiskManagerAgent |
| Federal Reserve calendar/RSS | FOMC, speeches, monetary policy | MacroAgent |
| BEA release schedule | Macro releases US | MacroAgent |
| CME FedWatch page | Reference officielle externe | MacroAgent |

FRED est prioritaire pour les taux. Yahoo `^TNX` reste un controle de marche.

## Sources flux et positionnement

| Source | Usage | Agents |
| --- | --- | --- |
| CFTC COT Gold | Positionnement futures COMEX | FlowPositioningAgent, RiskManagerAgent |
| World Gold Council ETF flows | Flows gold-backed ETF | FlowPositioningAgent, CorrelationAgent |
| BlackRock iShares IAU | Donnees IAU | FlowPositioningAgent |

Les flux peuvent confirmer ou contredire le signal. Exemple: COT bullish mais ETF en sorties = contradiction.

## Sources cross-asset

| Source | Instruments | Usage |
| --- | --- | --- |
| Yahoo Finance | DXY, USD/JPY, silver, GDX, GDXJ, AUD/USD, USD/CHF, TIP, S&P 500, GVZ, VIX, WTI/Brent | Correlations, confluence, regime oil/dollar |

Le moteur regarde les relations attendues avec gold:

- DXY et taux reels: relation souvent inverse.
- Silver, miners, TIP: relation souvent positive.
- WTI/Brent: utile surtout en regime geopolitique/oil shock.

## Sources news, geopolitique et politique

| Source | Usage | Agents |
| --- | --- | --- |
| Google News RSS / fallback feeds | Headlines dedup | SentimentNewsAgent, EventFactsAgent |
| Yahoo/Investing feeds | Headlines marche | SentimentNewsAgent |
| White House feed | Declarations officielles | TrumpPoliticalStatementsAgent |
| Reuters/AP via recherche RSS | Confirmation media majeure | EventFactsAgent, TrumpPoliticalStatementsAgent |

Les headlines seules ne suffisent pas. Les agents cherchent:

- fait concret;
- acteurs;
- lieux;
- theme;
- chaine marche;
- impact gold/oil/USD;
- niveau de confirmation.

## Orchestrateur v2 et transition v3

L'Orchestrateur v2 combine les composants suivants:

- TechnicalAgent;
- MacroAgent;
- GeopoliticalOilShockAgent;
- CorrelationAgent;
- FlowPositioningAgent;
- regime;
- data quality.

Decision v3.0:
- `ElliottWaveAgent` est archive. Il ne doit plus etre utilise comme composant de scoring, preuve, contradiction ou justification utilisateur.
- Phase 27A a retire Elliott du dashboard, payload JSON public, Inspector et orchestrateur.
- Phase 27B a introduit `TechnicalDecisionEngine` comme moteur technique actif v1.
- Phase 28 a introduit `ScenarioEngine v3`: il transforme le signal technique, les news, la macro, les correlations et la Data Quality en scenario principal, scenario alternatif, declencheur, invalidation et confirmations requises.
- Le Chart Store OHLC expose M5/M15/H1/H4/D1 dans l'Inspector pour verifier la qualite des donnees techniques.
- TradingView devient la charte utilisateur principale, tandis que Chart Store reste la source auditable des calculs internes.

Preflight v3:

- `READY`: sources critiques exploitables;
- `DEGRADED`: dashboard consultable, confiance reduite; ne bloque pas automatiquement un trade si le prix principal est exploitable;
- `SOURCE_STALE`: source bloquante trop ancienne, nouveau trade bloque;
- `NO_TRADE_DATA`: source bloquante absente, nouveau trade bloque;
- `OFFLINE`: sources critiques insuffisantes pour analyser un setup.

Source bloquante actuelle:

- `Investing.com XAU/USD`: prix principal et reference de TradePlan.

Sources importantes mais non bloquantes seules:

- WGC ETF flows stale;
- Google News RSS weak;
- COT/ETF/faits politiques partiels;
- Chart Store absent ou degrade: le `TechnicalDecisionEngine` passe en `WAIT` ou `WATCH` selon la qualite exploitable.

Il produit:

- verdict `BUY`, `SELL` ou `WAIT`;
- score `/100`;
- raisons principales;
- contre-signaux;
- Quality Gate final.

Le verdict `WAIT` est force si:

- score trop faible;
- data quality trop faible ou Preflight bloquant;
- contradictions directionnelles fortes entre composants decisionnels;
- regime event extreme;
- aucun avantage directionnel propre.

Le verdict `WAIT` ne doit pas etre force uniquement parce que:

- data quality est `DEGRADED` mais prix principal, macro et cross-assets restent exploitables;
- une source secondaire est stale;
- le mode event est modere;
- un agent d'audit ou archive contredit le signal.

## Technical Decision Engine cible v3

Le scoring technique v3 ne doit pas reposer sur une vague Elliott supposee. Il doit produire un statut technique base sur des preuves observables:

| Bloc | Indicateurs / preuves | Role dans le scoring |
| --- | --- | --- |
| Market Structure | swing highs/lows, HH/HL, LH/LL, BOS, CHoCH, retest, range high/low, premium/discount | definir la structure: trend, breakout, range, pullback ou reversal |
| Trend | EMA 20/50/100/200, pente EMA, alignement M15/H1/H4/D1, position prix vs EMA 50/200 | confirmer la direction dominante |
| Momentum | RSI7/RSI14, MACD ligne/signal/histogramme, divergence RSI/prix, acceleration/deceleration | confirmer ou refuser l'impulsion |
| Volatility | ATR14, ATR percentile, range du jour vs ATR, compression/expansion, volume spike proxy futures | verifier si l'entree et le SL sont exploitables |
| Levels | high/low jour, high/low veille, open, Asia/London/NY high/low, VWAP si disponible, pivots P/R1/R2/S1/S2 | definir trigger, invalidation, SL et TP |
| Liquidity / Execution | sweep high/low recent, stop hunt probable, fausse cassure, distance prochain niveau | eviter d'acheter/vendre dans une zone piege |
| Cross Confirmation | DXY, US10Y, 10Y real yield, WTI/Brent, Silver, GDX/GDXJ, VIX/GVZ | confirmer ou contredire la lecture technique |

Regles de direction:

- `WATCH_BUY`: contexte technique haussier en preparation, trigger absent.
- `BUY`: `WATCH_BUY` + trigger confirme + invalidation claire + risk/reward acceptable + Preflight non bloquant.
- `WATCH_SELL`: contexte technique baissier en preparation, trigger absent.
- `SELL`: `WATCH_SELL` + trigger confirme + invalidation claire + risk/reward acceptable + Preflight non bloquant.
- `WAIT`: range sale, contradiction forte, volatilite anormale, source bloquante ou prix trop loin du niveau d'entree.

Le score technique doit etre secondaire au statut. Un `62/100` sans trigger, invalidation et niveau exploitable reste un `WATCH` ou `WAIT`, pas un trade.

## Scenario Engine v3

Le Scenario Engine ne remplace pas le Quality Gate. Il traduit la decision en plan lisible:

- `scenario principal`: ce que le terminal surveille maintenant;
- `scenario alternatif`: ce qui invalide ou inverse l'hypothese;
- `declencheur`: condition technique minimale avant action;
- `invalidation`: niveau ou condition qui annule le scenario;
- `confirmations requises`: DXY, 10Y reel, oil, macro, News Facts ou momentum;
- `validations`: composants qui soutiennent le biais;
- `contradictions`: composants qui demandent prudence.

Regle de lecture:

- `WATCH_BUY` / `WATCH_SELL`: setup surveille, pas un trade verrouille;
- `TRADE_BUY` / `TRADE_SELL`: scenario techniquement confirme, encore soumis au Trade Quality Gate;
- `WAIT`: aucune structure exploitable ou contradictions trop fortes.

Une news peut devenir:

- declencheur si elle confirme le biais et la chaine de marche;
- contradiction si elle tire oil/dollar/liquidite contre le scenario;
- simple contexte si elle est faible ou non confirmee.

## Trade Quality Gate

Un Trade Plan n'est cree que si:

- verdict `BUY` ou `SELL`;
- score global suffisant ou statut v3 `TRADE_BUY` / `TRADE_SELL`;
- Preflight non bloquant;
- data quality exploitable, meme degradee si elle n'est pas bloquante;
- au moins deux agents decisionnels valident la direction;
- contradictions directionnelles limitees;
- risk/reward exploitable;
- pas de regime special bloquant.

Sinon, le Trade Tracker affiche `WAIT` et explique pourquoi.

Agents decisionnels utilises pour compter confirmations/contradictions de TradePlan:

- PriceAgent;
- TechnicalAgent;
- MacroAgent;
- GeopoliticalOilShockAgent;
- SentimentNewsAgent;
- CorrelationAgent;
- FlowPositioningAgent.

Agents exclus du comptage decisionnel:

- ElliottWaveAgent, archive et absent du produit actif;
- RiskManagerAgent, role de prudence;
- OrchestratorAgent, role d'audit/synthese.

## Data Quality

La Data Quality tient compte de:

- sources critiques missing;
- sources critiques stale;
- sources faibles;
- contradictions inter-sources;
- fraicheur des donnees.

Statuts:

- `HIGH`: qualite forte.
- `USABLE`: exploitable.
- `DEGRADED`: exploitable avec confiance/taille reduite si aucun blocage dur n'est actif.
- `WEAK`: signal a degrader fortement.

## Avertissement

Aucun score ne garantit une direction future. Le terminal aide a organiser l'information, mais le risque de perte reste total. Toute decision de trading doit etre controlee par l'utilisateur.
