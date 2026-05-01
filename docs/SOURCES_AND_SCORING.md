# Sources et scoring

Ce document resume les sources utilisees par Aureum Flux Terminal et la maniere dont elles entrent dans l'analyse.

## Politique generale

Les sources sont classees par tiers:

- Tier 1: source officielle ou primaire.
- Tier 2: donnees financieres fiables ou media majeur.
- Tier 3: source specialisee a confirmer.
- Tier 4: agregateur, headline ou source faible.

Une source critique absente ou stale degrade la `Data Quality`. Un signal directionnel fort doit etre degrade si les sources critiques ne sont pas fiables.

## Sources prix

| Source | Usage | Agents |
| --- | --- | --- |
| Investing.com XAU/USD | Spot principal XAU/USD | PriceAgent, RiskManagerAgent, OrchestratorAgent |
| IG Weekend Gold | Proxy week-end indicatif | PriceAgent, RiskManagerAgent |
| Yahoo Finance GC=F | Proxy futures pour chandelles/volume | TechnicalAgent |

IG Weekend Gold est distinct du spot semaine. Il sert a lire le marche week-end, pas a remplacer le spot classique.

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

## Orchestrateur v2

L'Orchestrateur v2 combine les composants suivants:

- TechnicalAgent;
- ElliottWaveAgent;
- MacroAgent;
- GeopoliticalOilShockAgent;
- CorrelationAgent;
- FlowPositioningAgent;
- regime;
- data quality.

Il produit:

- verdict `BUY`, `SELL` ou `WAIT`;
- score `/100`;
- raisons principales;
- contre-signaux;
- Quality Gate final.

Le verdict `WAIT` est force si:

- score trop faible;
- data quality insuffisante;
- contradictions fortes;
- regime event dangereux;
- aucun avantage directionnel propre.

## Trade Quality Gate

Un Trade Plan n'est cree que si:

- verdict `BUY` ou `SELL`;
- score global suffisant;
- data quality suffisante;
- au moins deux agents valident;
- contradictions limitees;
- risk/reward exploitable;
- pas de regime special bloquant.

Sinon, le Trade Tracker affiche `WAIT` et explique pourquoi.

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
- `DEGRADED`: prudence.
- `WEAK`: signal a degrader fortement.

## Avertissement

Aucun score ne garantit une direction future. Le terminal aide a organiser l'information, mais le risque de perte reste total. Toute decision de trading doit etre controlee par l'utilisateur.
