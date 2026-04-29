# Aureum Flux Terminal 2.0 - Plan de conception et d'implementation

Version du document: 1.4
Date: 2026-04-29
Statut: roadmap stable mise a jour avec gouvernance des flux et suivi des trades
Objectif: servir de base officielle pour toutes les evolutions v2.0 du dashboard XAU/USD.

## 0. Stabilite du plan

A partir de cette version, ce document devient la reference stable du projet jusqu'a la livraison finale d'Aureum Flux Terminal 2.0.

Regles:
- les phases doivent etre executees dans l'ordre documente;
- aucune phase ne demarre sans validation explicite de l'utilisateur;
- avant chaque phase: verifier Git/GitHub;
- apres chaque phase finalisee: tests adaptes, commit et push GitHub;
- le plan ne doit plus etre modifie jusqu'a la livraison finale, sauf demande et validation explicites de l'utilisateur;
- les avis externes Claude/Antigravity sont integres dans cette version, mais la source officielle reste ce document.

## 1. Vision generale

Aureum Flux Terminal 2.0 doit devenir un terminal d'analyse XAU/USD plus fiable, plus lisible et plus institutionnel.

La version 1 affiche deja:
- un prix XAU/USD live;
- un score global;
- une position conseillee BUY ou SELL;
- des TP et SL;
- une lecture technique;
- une lecture fondamentale;
- une lecture geopolitique/sentiment;
- des headlines expliquees.

La version 2.0 doit aller plus loin:
- separer les vues en vrais onglets;
- fiabiliser les sources de donnees;
- eviter les phrases vagues;
- expliquer le "why" concret derriere chaque signal;
- integrer le regime special USA/Iran/Hormuz/Oil Shock;
- distinguer les faits confirmes, les headlines non confirmees et les hypotheses;
- afficher une decision rapide en premier, puis les preuves derriere cette decision.

## 2. Principe central de la v2.0

Le dashboard ne doit jamais afficher une conclusion sans expliquer:

1. Le fait concret detecte.
2. La source.
3. Pourquoi ce fait compte.
4. La chaine de transmission marche.
5. L'impact probable sur gold.
6. Le niveau de confiance.

Exemple interdit:

> Le risque geopolitique reste actif et soutient l'or.

Exemple attendu:

> AP rapporte que les Etats-Unis cherchent a ouvrir le detroit d'Hormuz et evoquent un risque de mines iraniennes. Pourquoi ca compte: Hormuz transporte une part majeure du petrole mondial; si les assureurs et transporteurs restent prudents, le petrole peut conserver une prime de risque. Chaine marche: Hormuz tendu -> WTI/Brent en hausse -> inflation/rendements/dollar potentiellement en hausse -> gold peut etre vendu pour liquidite a court terme. Impact gold: mixte a baissier tant que oil/DXY dominent.

### 2.1 Signal live vs trade plan

Aureum Flux ne doit jamais confondre le signal live avec un trade plan.

Le signal live represente la lecture actuelle du marche. Il peut changer avec le prix, les news, les regimes et les agents.

Un trade plan est une recommandation figee dans le temps. Quand le terminal valide une opportunite exploitable, il cree un Trade Snapshot avec prix, direction, entry, SL, TP, score, agents, sources, raisons et conditions d'invalidation.

Le prix live peut changer ensuite, mais le trade plan historique ne doit jamais etre ecrase par le refresh du dashboard.

Objectif:
- conserver la decision live;
- conserver les trades generes;
- pouvoir revenir plus tard et voir exactement quelle recommandation avait ete donnee;
- noter si le trade est win, loss, partial, expired ou invalidated;
- expliquer pourquoi le trade a gagne ou perdu.

## 3. Definition de Aureum Flux

`Aureum` signifie "or" ou "dore" en latin.  
`Flux` represente les flux qui influencent l'or:
- liquidite;
- dollar;
- taux;
- petrole;
- news;
- geopolitique;
- sentiment;
- positionnement;
- ETF;
- futures.

Aureum Flux Terminal signifie donc:

> Terminal d'analyse des flux qui influencent l'or.

Ce nom est une marque produit pour le dashboard. Ce n'est pas une source de donnees.

## 4. Structure cible du dashboard

La v2.0 doit fonctionner avec de vrais onglets. Un clic sur un bouton doit afficher une vue dediee, pas simplement descendre dans une longue page.

La structure officielle cible est:
- Dashboard;
- Market;
- Decision;
- Technical;
- Macro;
- Geopolitics & Flows;
- Reports.

Les anciens libelles `Scores`, `Fundamental` et `Sentiment` sont remplaces dans la cible v2.0:
- `Scores` devient `Decision`;
- `Fundamental` devient `Macro`;
- `Sentiment` devient `Geopolitics & Flows`.

### 4.1 Onglet Dashboard

Role: decision rapide.

Contenu:
- prix XAU/USD principal;
- source du prix affichee;
- prix week-end IG si marche classique ferme;
- verdict global: BUY, SELL ou WAIT;
- score global sur 100;
- confiance sur 100;
- SL, TP1, TP2;
- regime de marche actif;
- phrase de decision courte;
- alertes majeures.

Questions auxquelles cet onglet repond:
- Que dit le terminal maintenant?
- Est-ce BUY, SELL ou WAIT?
- Ou sont le SL et les TP?
- Pourquoi cette decision en une phrase?
- Est-ce un marche normal ou un regime special?

### 4.2 Onglet Market

Role: prix, contexte de marche et correlations directes.

Contenu:
- prix XAU/USD spot;
- prix IG Weekend Gold si applicable;
- spread, variation, range du jour;
- correlation DXY, US10Y, USD/JPY, Silver, miners, SPX, VIX/GVZ;
- WTI/Brent comme contexte cross-asset;
- divergences entre gold et actifs lies.

Questions auxquelles cet onglet repond:
- Quel prix doit-on utiliser maintenant?
- Quelle source donne ce prix?
- Les marches correles confirment-ils gold?
- Le petrole, le dollar ou les taux dominent-ils le mouvement?

### 4.3 Onglet Decision

Role: verdict, plan de risque et contradictions.

Contenu:
- verdict global BUY, SELL ou WAIT;
- score global;
- confiance;
- SL, TP1, TP2;
- regime dominant;
- raisons principales;
- raisons contre-signal;
- contradictions entre agents;
- conditions d'invalidation.

Questions auxquelles cet onglet repond:
- Quelle est la decision officielle du terminal?
- Quel risque est accepte?
- Qu'est-ce qui invalide le plan?
- Pourquoi ne pas simplement acheter ou vendre sans prudence?

### 4.4 Onglet Technical

Role: timing, structure de prix et Elliott Wave.

Contenu:
- graphique 5m;
- ligne de prix live;
- support/resistance;
- dernier prix;
- tableau multi-timeframe: 5m, 15m, 1H, 4H, 1D;
- EMA 20/50/100/200;
- RSI7;
- MACD 5/34/5;
- volume ratio;
- ATR14;
- Elliott Wave Agent;
- Fibonacci retracement/extension;
- verdict technique;
- raisons techniques concretes.

Questions auxquelles cet onglet repond:
- Le timing confirme-t-il le signal?
- Le prix est-il au-dessus ou sous les EMA?
- Les timeframes superieurs confirment-ils?
- Le volume soutient-il le mouvement?
- La structure Elliott donne-t-elle un scenario et une invalidation?

### 4.5 Onglet Macro

Role: dollar, taux, inflation et Fed.

Contenu:
- DXY;
- US 10Y nominal;
- US 10Y reel;
- breakeven inflation 10Y;
- Fed/FOMC;
- CPI/NFP/PCE si disponible;
- calendrier economique;
- impact des taux sur gold;
- impact du dollar sur gold;
- lecture macro finale.

Questions auxquelles cet onglet repond:
- Les taux soutiennent-ils ou freinent-ils l'or?
- Le dollar confirme-t-il le trade?
- Le marche price-t-il une Fed plus dovish ou hawkish?
- L'inflation pousse-t-elle gold ou les rendements?

### 4.6 Onglet Geopolitics & Flows

Role: faits politiques, guerre, Hormuz, Trump, sentiment, COT et ETF flows.

Contenu:
- regime politique actif;
- bloc USA/Iran/Hormuz;
- bloc Trump / White House;
- bloc petrole WTI/Brent;
- bloc VIX/GVZ;
- bloc COT;
- bloc ETF flows;
- bloc headlines confirmees;
- distinction entre fait confirme et rumeur/headline faible;
- impact direct sur gold.

Questions auxquelles cet onglet repond:
- Quel fait politique concret influence le marche?
- Est-ce confirme par une source fiable?
- Est-ce un regime safe-haven classique ou oil shock?
- Le capital va-t-il vers gold, oil ou dollar?
- Les flux institutionnels confirment-ils le signal global?

### 4.7 Onglet Reports

Role: rapport propre et export.

Contenu:
- resume complet;
- decision finale;
- details des sources;
- historique du dernier calcul;
- avertissement;
- export Markdown;
- export JSON;
- futur export PDF.

Questions auxquelles cet onglet repond:
- Que puis-je archiver?
- Quelles sources ont ete utilisees?
- Quelle etait la logique au moment du signal?

## 4.8 Affectation agents vers departements

L'affectation officielle des agents est:

| Departement | Agents |
| --- | --- |
| Market | `PriceAgent`, `CorrelationAgent` |
| Decision | `OrchestratorAgent`, `RiskManagerAgent` |
| Technical | `TechnicalAgent`, `ElliottWaveAgent` |
| Macro | `MacroAgent` |
| Geopolitics & Flows | `GeopoliticalOilShockAgent`, `SentimentNewsAgent`, `EventFactsAgent`, `TrumpPoliticalStatementsAgent`, `FlowPositioningAgent` |

Cette affectation est documentee pendant la Phase 2, mais les agents ne sont crees et branches qu'en Phase 5.

## 4.9 Elliott Wave Agent

`ElliottWaveAgent` appartient au departement `Technical`.

Base methodologique:
- Elliott Wave Forecast, "Elliott Wave Theory": https://elliottwave-forecast.com/elliott-wave-theory/

Role:
- detecter les impulsions `1-2-3-4-5`;
- detecter les corrections `A-B-C`;
- utiliser les pivots hauts/bas;
- utiliser Fibonacci retracement et extension;
- proposer un scenario principal;
- proposer un scenario alternatif;
- fournir une invalidation claire;
- ne jamais decider seul.

Regles minimales a respecter:
- la vague 2 ne doit pas depasser le depart de la vague 1;
- la vague 3 ne doit pas etre la plus courte des vagues 1, 3, 5;
- la vague 4 ne doit normalement pas revenir dans le territoire de la vague 1;
- la vague 5 doit etre surveillee avec divergence de momentum;
- une correction standard doit etre lue en `A-B-C`;
- les ratios Fibonacci doivent servir pour les retracements, extensions, targets et invalidations;
- l'agent doit accepter qu'un marche moderne puisse progresser en sequence corrective de 3 vagues sans forcer partout un schema parfait en 5 vagues.

Sortie attendue:

```json
{
  "agent": "elliott_wave",
  "bias": "SELL",
  "score": 68,
  "confidence": 62,
  "scenario": "ABC corrective decline",
  "invalidation": "Break above wave B high",
  "targets": ["100% extension", "161.8% extension"],
  "summary": "Correction C-wave possible while price remains below invalidation."
}
```

## 4.10 Fondation multi-agents

La v2.0 doit evoluer vers une architecture multi-agents progressive, mais sans casser le moteur actuel.

Principe:
- le scoring actuel reste le moteur principal tant que l'orchestrateur multi-agents n'est pas valide;
- les agents specialises sont d'abord ajoutes en mode passif;
- chaque agent produit un resultat structure et comparable;
- le dashboard affiche les lectures des agents sans remplacer immediatement le verdict principal;
- l'activation du multi-agents comme moteur principal se fait uniquement pendant la phase de refonte scoring global.

Agents cibles:
- `PriceAgent`: prix XAU/USD, IG Weekend Gold, spread, source, fraicheur;
- `TechnicalAgent`: EMA, RSI, MACD, timeframes, supports, resistances, ATR;
- `ElliottWaveAgent`: vagues Elliott, Fibonacci, scenario, invalidation;
- `MacroAgent`: DXY, taux nominaux, taux reels, inflation breakeven, Fed, calendrier macro;
- `GeopoliticalOilShockAgent`: Iran/USA, Hormuz, oil shock, sanctions, dollar liquidity;
- `SentimentNewsAgent`: headlines, event facts, confirmation level, tonalite marche;
- `CorrelationAgent`: oil, silver, miners, USD/JPY, SPX, VIX/GVZ, ETF/cross-assets;
- `FlowPositioningAgent`: CFTC COT, ETF flows, open interest, positionnement;
- `EventFactsAgent`: transformation des headlines en faits confirmes ou hypotheses;
- `TrumpPoliticalStatementsAgent`: declarations Trump/White House et validation des citations;
- `RiskManagerAgent`: transformation du contexte en BUY/SELL/WAIT, SL, TP1, TP2, confiance;
- `OrchestratorAgent`: comparaison des agents, detection des contradictions, decision finale.

Structure commune attendue:

```json
{
  "agent": "geopolitical_oil",
  "bias": "SELL",
  "score": 72,
  "confidence": 81,
  "summary": "Hormuz risk active, oil pressure stronger than gold hedge demand.",
  "evidence": [
    "WTI rising",
    "DXY rising",
    "Confirmed Hormuz headline"
  ],
  "risks": [
    "If oil fades and DXY weakens, gold can rebound"
  ],
  "updated_at": "2026-04-26T00:00:00Z"
}
```

Regle de securite:
- aucun agent passif ne doit modifier le verdict principal;
- les agents peuvent seulement informer, comparer et signaler les contradictions;
- l'orchestrateur ne devient moteur principal qu'apres validation explicite.

## 4.11 Decision d'architecture Phase 2

La Phase 2 n'est pas une refonte design complete et n'est pas un refactor backend massif.

Definition:
- Phase 2 = vrais onglets + departements officiels + refresh live stable + bandeau global;
- Phase 2 ne change pas le moteur de scoring;
- Phase 2 ne cree pas encore les agents;
- Phase 2 prepare les emplacements futurs des agents sans les activer;
- Phase 2 conserve les logiques IG Weekend Gold et Hormuz/Oil Shock existantes.

Decision sur le monolithe:
- ne pas lancer de decoupage massif `app.py` / `engine/` / `ui/` / `models/` en Phase 2;
- ne pas ajouter de logique data/scoring dans le rendu;
- garder le changement concentre sur navigation, structure de vues et stabilite du refresh;
- preparer le refactor progressif plus tard, quand les contrats agents seront valides.

Decision sur le live refresh:
- le dashboard utilise `/fragment` pour remplacer le contenu de `#dashboard-app`;
- le JavaScript de navigation des onglets ne doit pas vivre dans le fragment remplace;
- le JavaScript de navigation doit vivre dans le `live_script` ou dans une zone non remplacee;
- l'onglet actif doit etre stocke dans `localStorage`;
- apres chaque refresh, l'onglet actif doit etre reapplique.

Ordre obligatoire apres refresh:
1. remplacer `app.innerHTML` par le fragment;
2. lire l'onglet actif depuis `localStorage`;
3. reappliquer les classes actives;
4. reafficher la vue active.

Decision sur le bandeau global:
- un bandeau global doit rester visible dans tous les onglets;
- il doit etre dans le fragment pour recevoir les donnees live;
- il doit afficher prix, verdict, score, resume SL/TP, regime actif et alerte critique;
- il peut exposer `data-verdict`, `data-regime` et `data-alert`;
- le JavaScript peut lire ces attributs pour appliquer l'etat visuel;
- le bandeau ne doit pas masquer les donnees importantes dans un onglet secondaire.

Hors scope Phase 2:
- refactor backend massif;
- creation de `app.py` / `engine/` / `ui/` / `models/`;
- activation des agents;
- redesign final Stitch;
- suppression de fonctions mortes;
- changement du scoring global;
- ajout de nouvelles sources de donnees;
- modification de la logique interne de `render_weekend_gold_proxy()`;
- modification de la logique interne de `render_market_regime_panel()`.

## 5. Sources de donnees actuelles

### 5.1 Prix gold

Source actuelle:
- Investing.com XAU/USD: prix spot, variation, high/low.
- Investing.com historical XAU/USD: historique court pour niveaux.

Utilisation actuelle:
- prix principal;
- variation;
- range du jour;
- support/resistance;
- affichage dashboard.

Limite:
- le week-end, le spot classique peut ne pas refleter le marche week-end.

### 5.2 Technique

Source actuelle:
- Yahoo Finance Chart API.

Symboles actuels:
- `GC=F`: Gold Futures proxy COMEX.

Utilisation actuelle:
- bougies 5m;
- 15m;
- 1H;
- 4H agrege;
- 1D;
- volume;
- indicateurs techniques.

Limite:
- futures proxy, pas spot pur;
- l'alignement avec le spot est une approximation.

### 5.3 Dollar et taux

Sources actuelles:
- Yahoo `DX-Y.NYB`: US Dollar Index.
- Yahoo `^TNX`: US 10Y nominal.
- FRED `DFII10`: US 10Y real yield.

Utilisation actuelle:
- scoring fondamental;
- analyse cross-asset;
- correlation avec gold.

Limite:
- `^TNX` doit etre verifie contre une source officielle FRED.

### 5.4 News

Sources actuelles:
- Google News RSS search.
- Yahoo Finance RSS GC=F.
- Investing.com commodities RSS.
- Investing.com markets RSS.

Categories actuelles:
- gold;
- Fed;
- CPI;
- NFP;
- geopolitical;
- COT;
- open interest;
- ETF flows;
- economic calendar;
- FOMC;
- VIX;
- physical demand.

Limite:
- Google News est un aggregateur;
- les headlines peuvent etre bruitees;
- une headline n'est pas toujours une donnee confirmee.

### 5.5 Actifs correles

Symboles actuels:
- `GC=F`: gold futures;
- `DX-Y.NYB`: dollar index;
- `DFII10`: 10Y reel FRED;
- `JPY=X`: USD/JPY;
- `SI=F`: silver;
- `GDX`: gold miners;
- `GDXJ`: junior gold miners;
- `AUDUSD=X`: AUD/USD;
- `CHF=X`: USD/CHF;
- `TIP`: TIPS ETF;
- `^GSPC`: S&P 500;
- `^GVZ`: gold volatility;
- `^VIX`: VIX.

## 6. Sources a ajouter en v2.0

### 6.1 Prix week-end

Ajouter:
- IG Weekend Gold.

Utilisation:
- uniquement quand le marche classique est ferme ou le week-end;
- affichage separe: "Weekend proxy";
- ne pas remplacer aveuglement le spot officiel.

Regle:
- si samedi/dimanche, afficher les deux:
  - dernier spot classique;
  - prix week-end IG;
  - ecart entre les deux.

### 6.2 Petrole

Ajouter:
- `CL=F`: WTI crude futures;
- `BZ=F`: Brent crude futures.

Utilisation:
- detection Hormuz/Oil Shock;
- impact inflation;
- impact risque geopolitique;
- confirmation ou contradiction du signal gold.

### 6.3 Taux et inflation officiels FRED

Ajouter:
- FRED `DGS10`: US 10Y nominal officiel;
- FRED `DGS2`: US 2Y nominal;
- FRED `T10YIE`: 10Y breakeven inflation;
- conserver `DFII10`: 10Y real yield.

Utilisation:
- remplacer ou verifier Yahoo `^TNX`;
- detecter si le choc politique pousse les rendements;
- detecter si le marche price de l'inflation.

### 6.4 COT officiel

Ajouter:
- CFTC Commitments of Traders officiel;
- CFTC historical compressed data.

Utilisation:
- Managed Money net position;
- Producer/Merchant;
- Swap Dealers;
- Non-reportable;
- open interest officiel.

Regle:
- remplacer les headlines COT par une lecture officielle des donnees.

### 6.5 ETF flows officiels

Ajouter:
- World Gold Council ETF holdings and flows;
- SPDR GLD holdings;
- iShares IAU holdings.

Utilisation:
- flux institutionnels;
- demande papier;
- confirmation du biais moyen terme.

### 6.6 Trump / White House

Ajouter:
- White House News;
- Truth Social @realDonaldTrump si techniquement exploitable;
- AP/Reuters comme confirmation secondaire.

Utilisation:
- declarations directes sur Iran;
- declarations sur Fed;
- declarations sur dollar;
- declarations sur tarifs;
- declarations sur Chine;
- declarations sur sanctions;
- declarations sur petrole.

Regle:
- une declaration Trump a fort impact doit etre marquee comme:
  - officielle confirmee;
  - reprise AP/Reuters;
  - non confirmee;
  - ancienne;
  - contradictoire.

### 6.7 Calendrier economique

Ajouter:
- calendrier economique structure;
- priorite aux evenements high impact;
- si possible: Investing.com Economic Calendar ou alternative API.

Utilisation:
- CPI;
- NFP;
- FOMC;
- Fed speeches;
- PCE;
- Retail Sales;
- GDP;
- Jobless Claims.

### 6.8 CME FedWatch

Ajouter:
- CME FedWatch si accessible.

Utilisation:
- probabilites FOMC;
- changement de pricing des taux;
- impact sur gold via Fed expectations.

## 7. Regimes de marche a detecter

La v2.0 doit choisir un regime de marche actif. Le regime influence le scoring.

### 7.1 Safe-Haven Gold

Conditions possibles:
- tension geopolitique;
- gold monte;
- DXY baisse ou stable;
- taux reels baissent;
- oil ne domine pas;
- VIX/GVZ monte de facon coherente.

Impact:
- geopolitique favorable gold.

### 7.2 Hormuz / Oil Shock

Conditions possibles:
- headlines Hormuz, Iran, mines, blockade, shipping, navy, sanctions;
- WTI/Brent montent fortement;
- gold baisse ou ne confirme pas;
- DXY monte;
- 10Y nominal ou breakeven inflation monte;
- marche cherche de la liquidite.

Impact:
- geopolitique non automatiquement bullish gold;
- possible pression court terme sur gold;
- oil et dollar peuvent absorber les flux.

Message attendu:

> Regime Hormuz/Oil Shock detecte: la tension politique soutient d'abord oil et dollar. Gold peut etre vendu pour liquidite tant que Brent/WTI et DXY dominent.

### 7.3 Dollar Liquidity Squeeze

Conditions possibles:
- DXY monte fortement;
- USD/JPY ou USD/CHF confirment dollar fort;
- gold baisse;
- equities sous pression;
- VIX monte.

Impact:
- gold peut baisser malgre risk-off.

### 7.4 De-escalation

Conditions possibles:
- cessez-le-feu;
- talks confirmes;
- sanctions assouplies;
- oil baisse;
- VIX baisse;
- gold perd sa prime de risque.

Impact:
- gold souvent bearish court terme sauf si les taux/dollar baissent aussi.

### 7.5 Normal Macro

Conditions possibles:
- pas de choc geopolitique dominant;
- gold repond surtout a DXY, yields, Fed, inflation.

Impact:
- scoring classique fondamental/technique.

## 8. Moteur Event Facts

La v2.0 doit creer un moteur de faits.

Chaque fait important doit etre structure ainsi:

```json
{
  "event_id": "2026-04-25-ap-hormuz-mines",
  "title": "U.S. says it is clearing Iranian mines near Strait of Hormuz",
  "source_name": "AP News",
  "source_url": "...",
  "published_at": "2026-04-25T...",
  "actors": ["United States", "Iran"],
  "locations": ["Strait of Hormuz"],
  "themes": ["hormuz", "oil_shock", "military", "shipping"],
  "confirmation_level": "confirmed_secondary",
  "freshness": "fresh",
  "market_chain": [
    "Hormuz risk increases",
    "Oil shipping risk premium rises",
    "WTI/Brent can rise",
    "Inflation expectations and dollar demand can rise",
    "Gold can fall if liquidity moves to oil/dollar"
  ],
  "gold_impact": "mixed_bearish_short_term",
  "confidence": 82
}
```

## 9. Niveaux de validation des faits

### 9.1 Official confirmed

Source primaire:
- White House;
- Fed;
- Treasury;
- CFTC;
- FRED;
- WGC;
- CME;
- EIA.

Impact scoring:
- poids eleve.

### 9.2 Confirmed secondary

Sources:
- AP;
- Reuters;
- Bloomberg;
- CNBC;
- Financial Times;
- Wall Street Journal.

Impact scoring:
- poids moyen a eleve selon la fraicheur.

### 9.3 Market confirmed

Condition:
- news + reaction marche visible.

Exemple:
- headline Hormuz;
- oil monte;
- DXY monte;
- gold baisse.

Impact scoring:
- poids eleve, car le marche confirme.

### 9.4 Unconfirmed headline

Condition:
- source faible;
- screenshot;
- reseau social non verifie;
- aucune reaction marche.

Impact scoring:
- poids faible;
- afficher "a verifier".

## 10. Scoring cible v2.0

Le score global doit combiner:

- technique: 25%;
- macro/fondamental: 25%;
- geopolitique & sentiment: 20%;
- cross-assets: 15%;
- regime de marche: 10%;
- qualite/fraicheur des donnees: 5%.

Ces poids peuvent etre ajustes apres tests.

### 10.1 Score technique

Entrees:
- trend EMA;
- RSI7;
- MACD;
- volume;
- ATR;
- multi-timeframe.

Sortie:
- BUY;
- SELL;
- WAIT;
- score 0-100.

### 10.2 Score macro

Entrees:
- DXY;
- 10Y nominal;
- 2Y nominal;
- 10Y reel;
- breakeven inflation;
- Fed expectations;
- calendrier.

Sortie:
- macro bullish gold;
- macro bearish gold;
- neutral.

### 10.3 Score geopolitique & sentiment

Entrees:
- Event Facts;
- Trump/White House;
- Iran/Hormuz;
- oil;
- VIX/GVZ;
- COT;
- ETF flows;
- headlines confirmees.

Sortie:
- safe-haven bullish;
- oil-shock bearish/mixed;
- dollar-squeeze bearish;
- de-escalation bearish;
- neutral.

### 10.4 Score cross-assets

Entrees:
- oil;
- silver;
- miners;
- DXY;
- JPY;
- CHF;
- TIPS;
- SPX;
- VIX;
- GVZ.

Sortie:
- confirmation;
- contradiction;
- divergence.

### 10.5 Score qualite des donnees

Entrees:
- sources disponibles;
- fraicheur;
- coherence entre sources;
- nombre de confirmations;
- marche ouvert/ferme.

Sortie:
- data quality: low, medium, high.

## 11. Regles speciales Trump

La v2.0 doit traiter Trump comme une source politique speciale.

### 11.1 Categories Trump

- Iran/Hormuz;
- Fed/rates;
- dollar;
- tariffs;
- China;
- oil/energy;
- sanctions;
- ceasefire/talks;
- military action.

### 11.2 Impact type

Trump menace Iran/Hormuz:
- oil bullish;
- risk-off;
- gold mixed;
- gold bearish possible si dollar/oil dominent.

Trump annonce talks/cessez-le-feu:
- risk premium baisse;
- oil peut baisser;
- gold peut baisser court terme si prime de risque sort.

Trump attaque la Fed ou demande baisse des taux:
- dollar/yields peuvent baisser;
- gold bullish possible.

Trump parle dollar fort:
- gold bearish possible.

Trump parle tarifs/Chine:
- risk-off possible;
- gold bullish ou dollar bullish selon reaction marche.

### 11.3 Regle anti-hallucination

Le dashboard ne doit jamais inventer une declaration.

Si une declaration n'est pas verifiee:
- afficher "non confirmee";
- ne pas l'utiliser fortement dans le score;
- demander confirmation par source primaire/secondaire.

## 12. UX cible

### 12.1 Identite visuelle

Style cible:
- terminal institutionnel;
- sombre;
- gold accent;
- vert pour bullish;
- rouge/rose pour bearish;
- bleu/gris pour neutre;
- typographie lisible;
- cartes compactes;
- vrais onglets;
- pas de longue page unique.

### 12.2 Priorite visuelle

En haut du Dashboard:
1. prix;
2. verdict;
3. score;
4. SL/TP;
5. regime actif;
6. alerte principale.

Ensuite:
- preuves;
- details;
- sources.

### 12.3 Libelles humains

Eviter:
- phrases generiques;
- jargon sans explication;
- conclusions sans preuve.

Utiliser:
- "Fait detecte";
- "Pourquoi ca compte";
- "Chaine de marche";
- "Impact gold";
- "Confiance";
- "Source".

## 13. Architecture technique cible

La version actuelle est principalement dans `xauusd_agent.py`. La v2.0 doit progressivement separer les responsabilites.

### 13.1 Gouvernance des flux inspiree Fincept

A partir de la Phase 8, Aureum Flux doit s'enrichir progressivement de l'experience Fincept, mais sans copier son architecture lourde.

Principes a reprendre:
- un registre officiel des sources autorisees;
- un tier de fiabilite par source;
- une duree de fraicheur attendue par type de donnee;
- une detection des sources manquantes ou stale;
- une deduplication des news et faits;
- une separation entre donnees brutes, faits structures, sorties agents et decision finale;
- une capacite d'audit: savoir quelles sources et quels agents ont influence un signal.

Le terminal ne doit pas donner plus de poids a une information simplement parce qu'elle est repetee par plusieurs flux. Si Reuters, CNBC et BBC parlent du meme evenement, Aureum Flux doit creer un seul `EventFact` renforce par plusieurs sources, pas trois evenements independants.

Structure minimale cible:

```text
SourceRegistry
  source_id
  source_name
  category
  tier
  url_or_method
  refresh_policy
  agents_allowed

SourceSnapshot
  source_id
  fetched_at
  freshness_seconds
  status
  value_used
  error

DataQualitySnapshot
  data_quality_score
  missing_sources
  stale_sources
  source_conflicts
  last_refresh_age
```

Fraicheur recommandee:
- prix et actifs correles: 5 a 30 secondes selon source;
- news et declarations politiques: 1 a 5 minutes;
- macro officielle FRED/Fed/BLS/BEA: 1 heure ou plus selon serie;
- CFTC COT: hebdomadaire;
- ETF flows: quotidien;
- Event Facts critiques: refresh rapide tant que le regime est actif.

### 13.2 Trade Ledger / Signal Locking

Aureum Flux doit historiser les trades exploitables dans un registre append-only.

Le Trade Ledger ne remplace pas le signal live. Il fige une opportunite validee par le Quality Gate.

Modele cible:

```text
TradePlan
  trade_id
  created_at
  status
  direction
  entry_type
  reference_price
  entry_zone_low
  entry_zone_high
  stop_loss
  tp1
  tp2
  tp3
  risk_reward_tp1
  risk_reward_tp2
  risk_reward_tp3
  max_valid_until
  source_signal_id
  global_score_at_creation
  data_quality_score
  confidence_score
  market_regime
  agents_validating
  agents_contradicting
  evidence_sources
  event_facts_snapshot
  technical_snapshot
  macro_snapshot
  geopolitical_snapshot
  elliott_wave_snapshot
  invalidation_rules
  outcome
  outcome_reason
  closed_at
```

Statuts:
- `pending`;
- `active`;
- `tp1_hit`;
- `tp2_hit`;
- `tp3_hit`;
- `sl_hit`;
- `expired`;
- `invalidated`;
- `closed_manual`.

Regles:
- Aureum Flux ne cree pas un trade a chaque refresh;
- un trade est cree uniquement si le Quality Gate valide le signal;
- SL et TP doivent etre calculables;
- le risk/reward minimal doit etre acceptable;
- les sources critiques ne doivent pas etre stale;
- aucun trade identique recent ne doit deja etre actif;
- le cooldown initial recommande est de 60 a 120 minutes pour une meme direction et un meme regime;
- une exception est possible si un nouveau fait Tier 1 ou une cassure technique majeure change le contexte.

Utilisation Elliott Wave:
- le trade plan sauvegarde le comptage de vagues utilise;
- pour une vague 3 bullish, le SL de reference peut etre sous la fin de vague 2;
- les TP peuvent utiliser les extensions de vague 1: 1.0, 1.618, 2.618;
- pour une vague 3 bearish, la logique est inverse;
- le scenario alternatif et le niveau d'invalidation du comptage doivent etre conserves.

Structure cible possible:

```text
xauusd_agent.py
sources/
  investing.py
  yahoo.py
  fred.py
  ig_weekend.py
  cftc.py
  wgc.py
  news.py
  trump.py
  registry.py
analysis/
  technical.py
  macro.py
  geopolitical.py
  regimes.py
  scoring.py
  event_facts.py
  data_quality.py
  trade_ledger.py
dashboard/
  render.py
  templates.py
  assets.py
reports/
tests/
docs/
```

Important:
- ne pas tout refactorer d'un coup;
- commencer par ajouter les nouvelles sources et les tests;
- ensuite isoler les modules progressivement.

## 14. Etapes d'implementation detaillees

Cette roadmap remplace l'ordre precedent. Elle reprend le projet depuis le socle valide et reclasse les fonctionnalites deja codees.

Regle generale:
- aucune phase ne demarre sans validation utilisateur;
- avant chaque phase: verifier Git/GitHub;
- apres chaque phase finalisee: tests adaptes, commit et push GitHub;
- les agents passifs ne remplacent pas le moteur principal;
- l'orchestrateur ne devient principal qu'en Phase 14 et seulement apres validation.

### Phase 0 - Audit de reprise et cadrage officiel

Statut: fait.

Objectif:
- verifier l'etat reel du projet;
- verifier Git/GitHub;
- verifier les tests;
- verifier le dashboard local;
- clarifier ce qui est deja code, ce qui est partiel et ce qui reste a faire.

Livrable:
- rapport d'audit de reprise.

Critere de fin:
- etat du projet compris;
- aucune modification de code;
- prochaine phase officielle identifiee.

### Phase 1 - Stabilisation de la base actuelle

Statut: fait.

Objectif:
- conserver une base dashboard locale fonctionnelle;
- garder le scoring principal visible;
- garder prix, BUY/SELL, SL, TP et rapport accessibles.

Actions:
1. `git status`.
2. Lancer les tests existants.
3. Lancer le dashboard local.
4. Verifier que le systeme actuel reste exploitable.

Livrable:
- base stable.

Critere de fin:
- tests OK;
- dashboard accessible;
- aucune regression majeure.

### Phase 2 - Vrais onglets + departements officiels

Statut: fait.

Objectif:
- remplacer la longue page par des vues dediees;
- creer les departements officiels v2.0;
- securiser le live refresh pour conserver l'onglet actif;
- creer un bandeau global visible dans tous les onglets.

Actions:
1. Verifier Git/GitHub.
2. Identifier les sections existantes:
   - `#market`;
   - `#scores`;
   - `#technical`;
   - `#fundamental`;
   - `#sentiment`.
3. Creer une navigation principale.
4. Creer les vues:
   - Dashboard;
   - Market;
   - Decision;
   - Technical;
   - Macro;
   - Geopolitics & Flows;
   - Reports.
5. Transformer les liens de scroll en vrais boutons/vues.
6. Mettre le JavaScript des onglets dans le `live_script` ou une zone non remplacee par `/fragment`.
7. Stocker l'onglet actif dans `localStorage`.
8. Apres chaque refresh `/fragment`, reappliquer l'onglet actif.
9. Creer un bandeau global live visible partout:
   - prix;
   - verdict;
   - score;
   - resume SL/TP;
   - regime actif;
   - alerte IG Weekend Gold ou Hormuz/Oil Shock si applicable.
10. Splitter l'ancien `#market`:
   - Dashboard: prix, IG, verdict, score, SL/TP, regime actif;
   - Market: correlations, cross-assets, WTI/Brent.
11. Renommer et replacer:
   - `#scores` -> Decision;
   - `#fundamental` -> Macro;
   - `#sentiment` -> Geopolitics & Flows.
12. Ajouter Reports.
13. Preparer les emplacements futurs des agents par departement.
14. Ne pas modifier la logique interne IG Weekend Gold.
15. Ne pas modifier la logique interne Hormuz/Oil Shock.
16. Ne pas supprimer `render_dashboard_clarity` pendant Phase 2.
17. Ne pas activer les agents.
18. Tester chaque bouton.
19. Tester le live refresh avec un onglet autre que Dashboard actif.
20. Commit et push GitHub apres validation.

Livrable:
- dashboard multi-vues avec departements officiels;
- refresh live stable;
- bandeau global live.

Critere de fin:
- chaque bouton affiche une vue differente;
- pas de scroll monopage force;
- live refresh ne casse pas les onglets;
- l'onglet actif reste actif apres refresh `/fragment`;
- Dashboard affiche prix, verdict, SL/TP et regime;
- Market affiche correlations, cross-assets et WTI/Brent;
- IG Weekend Gold reste visible si disponible;
- Hormuz/Oil Shock reste visible si actif;
- Reports existe;
- les departements sont visibles et coherents;
- tests unitaires OK;
- verification navigateur OK;
- GitHub synchronise.

### Phase 3 - Revue IG Weekend Gold

Statut: fait.

Objectif:
- verifier que IG Weekend Gold est place au bon endroit apres creation des onglets.

Actions:
1. Verifier le parsing IG Weekend Gold existant.
2. Verifier l'affichage dans Dashboard et Market.
3. Verifier la distinction spot classique vs prix week-end.
4. Verifier le JSON et le rapport Markdown.
5. Ajouter ou ajuster tests si necessaire.

Livrable:
- integration IG Weekend Gold validee dans la structure multi-vues.

Critere de fin:
- le samedi/dimanche, le dashboard montre clairement le prix IG separe du spot classique;
- le prix IG n'est pas perdu dans une section secondaire.

### Phase 4 - Revue WTI/Brent et regime Hormuz/Oil Shock

Statut: fait.

Objectif:
- verifier que WTI/Brent et le regime Hormuz/Oil Shock sont places au bon endroit apres creation des onglets.

Actions:
1. Verifier `CL=F` et `BZ=F`.
2. Verifier variation jour/court terme.
3. Verifier detection headlines Hormuz/Iran/shipping/mines/blockade.
4. Verifier affichage dans Market, Decision et Geopolitics & Flows.
5. Verifier que la chaine oil -> dollar/taux -> gold reste claire.
6. Ajouter ou ajuster tests si necessaire.

Livrable:
- regime oil shock valide dans la structure multi-vues.

Critere de fin:
- le dashboard peut dire: tension geopolitique positive pour oil mais negative/mixte pour gold;
- le regime n'est pas cache trop bas dans la page.

### Phase 5 - Fondation multi-agents passive

Statut: fait.

Objectif:
- preparer Aureum Flux Terminal a une lecture multi-agents sans remplacer le moteur actuel.

Actions:
1. Creer une structure commune `AgentResult`.
2. Creer `AgentEvidence` si necessaire.
3. Creer `AgentRisk` si necessaire.
4. Ajouter les agents passifs:
   - `PriceAgent`;
   - `TechnicalAgent`;
   - `ElliottWaveAgent`;
   - `MacroAgent`;
   - `GeopoliticalOilShockAgent`;
   - `SentimentNewsAgent`;
   - `CorrelationAgent`;
   - `FlowPositioningAgent`;
   - `EventFactsAgent`;
   - `TrumpPoliticalStatementsAgent`;
   - `RiskManagerAgent`;
   - `OrchestratorAgent`.
5. Brancher les agents sur les donnees deja disponibles.
6. Afficher une lecture experimentale multi-agents dans les departements.
7. Afficher les contradictions entre agents.
8. Garder le verdict principal actuel comme decision officielle.
9. Ajouter des tests pour verifier que les agents ne cassent pas le payload existant.

Livrable:
- panneau multi-agents passif;
- chaque agent affiche bias, score, confiance, preuves et risques;
- aucune modification du verdict principal officiel.

Critere de fin:
- dashboard actuel toujours fonctionnel;
- tests OK;
- ancien scoring conserve;
- agents visibles uniquement comme lecture experimentale.

### Phase 6 - Ajout FRED macro officiel

Statut: fait.

Objectif:
- fiabiliser taux/inflation;
- alimenter progressivement `MacroAgent`.

Actions:
1. Ajouter FRED `DGS10`.
2. Ajouter FRED `DGS2`.
3. Ajouter FRED `T10YIE`.
4. Conserver `DFII10`.
5. Comparer Yahoo `^TNX` avec FRED `DGS10`.
6. Utiliser FRED comme source principale officielle.

Livrable:
- bloc macro officiel.

Critere de fin:
- les taux affiches ont une source officielle.

### Phase 7 - Event Facts

Statut: fait.

Objectif:
- remplacer les phrases vagues par des faits concrets;
- alimenter `GeopoliticalOilShockAgent` et `SentimentNewsAgent`.

Actions:
1. Creer une structure `EventFact`.
2. Convertir les headlines importantes en faits.
3. Ajouter actors, locations, themes.
4. Ajouter confirmation_level.
5. Ajouter market_chain.
6. Ajouter gold_impact.
7. Afficher les faits dans `Geopolitics & Flows`.

Livrable:
- cartes "Fait detecte".

Critere de fin:
- chaque conclusion geopolitique cite un fait et une source.

### Phase 8 - Trump / Political Statements

Statut: prochaine phase.

Objectif:
- suivre les declarations politiques a fort impact;
- alimenter `TrumpPoliticalStatementsAgent` et `GeopoliticalOilShockAgent`.

Actions:
1. Ajouter White House News.
2. Evaluer faisabilite Truth Social.
3. Ajouter requetes Google/AP pour Trump + Iran/Fed/dollar/oil.
4. Classer les declarations par theme.
5. Ajouter niveau de validation.
6. Ajouter scoring specifique.

Livrable:
- bloc Trump / White House.

Critere de fin:
- une declaration Trump n'est prise au serieux que si elle est confirmee ou sourcee.

### Phase 9 - CFTC COT officiel

Objectif:
- remplacer les headlines COT par des donnees officielles;
- alimenter `FlowPositioningAgent`.

Actions:
1. Identifier le fichier CFTC adapte a gold futures.
2. Parser les positions.
3. Extraire Managed Money, Producers, Swap Dealers, Non-reportable.
4. Calculer variation semaine.
5. Afficher le positionnement.
6. Integrer dans scoring sentiment/flows.

Livrable:
- bloc COT officiel.

Critere de fin:
- le dashboard n'utilise plus seulement des headlines pour COT.

### Phase 10 - ETF flows officiels

Objectif:
- mesurer les flux institutionnels gold;
- alimenter `FlowPositioningAgent` et `CorrelationAgent`.

Actions:
1. Ajouter WGC ETF flows si accessible.
2. Ajouter GLD holdings.
3. Ajouter IAU holdings.
4. Calculer flux jour/semaine.
5. Classer inflows/outflows/mixed.
6. Integrer dans Geopolitics & Flows.

Livrable:
- bloc ETF flows officiel.

Critere de fin:
- les flux ETF ont une source explicite.

### Phase 11 - Calendrier economique et Fed

Objectif:
- anticiper les catalyseurs macro;
- alimenter `MacroAgent` et `RiskManagerAgent`.

Actions:
1. Ajouter calendrier economique high impact.
2. Ajouter FOMC/Fed speeches.
3. Ajouter CME FedWatch si accessible.
4. Associer chaque evenement a un impact gold probable.
5. Afficher countdown ou date/heure.

Livrable:
- bloc Macro Catalysts.

Critere de fin:
- le dashboard sait dire quel evenement macro arrive et pourquoi il compte.

### Phase 12 - Data Feed Governance inspire Fincept

Objectif:
- enrichir Aureum Flux avec une gouvernance des flux d'information;
- eviter que les agents lisent un flux non filtre;
- mesurer la qualite, la fraicheur et la fiabilite des sources;
- preparer le Trade Ledger et l'orchestrateur final.

Actions:
1. Creer un `SourceRegistry` leger.
2. Classer les sources par categorie:
   - price;
   - macro;
   - rates;
   - oil;
   - geopolitics;
   - political_statements;
   - flows;
   - news;
   - technical.
3. Ajouter un tier de fiabilite:
   - Tier 1: source officielle, institution, regulateur, source primaire;
   - Tier 2: grand media financier/geopolitique fiable;
   - Tier 3: source specialisee ou blog utile mais a verifier;
   - Tier 4: agregateur, rumeur, source faible.
4. Ajouter une politique de fraicheur par source.
5. Ajouter `SourceSnapshot` pour historiser la valeur utilisee.
6. Ajouter `DataQualitySnapshot`.
7. Detecter sources manquantes, stale ou contradictoires.
8. Deduplicater les news et Event Facts.
9. Exposer data_quality_score aux agents passifs.
10. Ajouter tests de source stale, source manquante et deduplication.

Livrable:
- registre des sources officiel;
- score de qualite des donnees;
- snapshots des sources utilisees;
- deduplication minimale des faits.

Critere de fin:
- un signal ne peut pas etre considere fort si une source critique est stale ou absente;
- chaque agent sait quelles sources il a le droit d'utiliser;
- le dashboard peut afficher pourquoi une donnee est fiable ou faible.

### Phase 13 - Trade Ledger / Signal Locking / Suivi des recommandations

Objectif:
- separer le signal live du trade plan;
- historiser chaque recommandation exploitable;
- figer entry, SL, TP, score, sources et raisons au moment de creation;
- suivre le cycle de vie du trade jusqu'a TP, SL, expiration ou invalidation;
- mesurer la performance reelle des recommandations Aureum Flux.

Actions:
1. Creer le modele `TradePlan`.
2. Creer un stockage append-only des trades.
3. Ajouter un Trade Snapshot au moment ou le Quality Gate valide une opportunite.
4. Ajouter lifecycle:
   - pending;
   - active;
   - tp1_hit;
   - tp2_hit;
   - tp3_hit;
   - sl_hit;
   - expired;
   - invalidated;
   - closed_manual.
5. Ajouter regles de cooldown pour eviter trop de trades similaires.
6. Ajouter expiration automatique.
7. Ajouter evaluation outcome:
   - win;
   - loss;
   - partial;
   - expired;
   - invalidated.
8. Ajouter `outcome_reason`.
9. Ajouter integration Elliott Wave:
   - wave count;
   - invalidation;
   - TP extensions.
10. Ajouter snapshots des sources et agents au moment du trade.
11. Ajouter bloc dashboard Trade Tracker.
12. Ajouter section Reports pour historique des trades.
13. Ajouter tests.

Livrable:
- registre de trades historise;
- bloc dashboard Trade Tracker;
- evaluation win/loss/partial/expired/invalidated;
- aucun trade plan n'est ecrase par le refresh live.

Critere de fin:
- un trade cree a 10:00 garde toujours son entry, SL, TP et raisonnement meme si le dashboard live change a 10:15;
- le terminal peut expliquer pourquoi le trade a gagne, perdu, expire ou ete invalide;
- les statistiques de performance commencent a etre mesurables.

### Phase 14 - Refonte scoring global / orchestrateur

Objectif:
- consolider tout dans une decision plus robuste;
- decider si l'orchestrateur multi-agents devient le moteur principal;
- utiliser les sources gouvernees et l'historique des trades pour calibrer la decision.

Actions:
1. Comparer le scoring actuel avec les resultats des agents passifs.
2. Verifier les contradictions frequentes.
3. Comparer les anciens trades generes avec les signaux live correspondants.
4. Valider ou ajuster les ponderations agents.
5. Implementer scores separes:
   - technique;
   - Elliott;
   - macro;
   - geopolitique/oil;
   - cross-assets;
   - flows;
   - regime;
   - data quality.
6. Ajouter ponderation.
7. Ajouter WAIT si contradictions fortes.
8. Ajouter raisons top 3.
9. Ajouter raisons contre-signal top 3.
10. Ajouter Quality Gate final avant creation d'un trade.
11. Activer l'orchestrateur comme moteur principal uniquement apres validation utilisateur.

Livrable:
- score global v2.0;
- orchestrateur multi-agents actif seulement si valide;
- decision BUY/SELL/WAIT reliee au Trade Ledger.

Critere de fin:
- le verdict explique ses preuves et ses contradictions;
- l'ancien moteur peut encore servir de comparaison ou fallback;
- le terminal ne cree pas un trade si le Quality Gate refuse le signal.

### Phase 15 - Design Aureum Flux Terminal 2.0

Objectif:
- appliquer le design terminal institutionnel multi-vues;
- integrer visuellement le Trade Tracker, la qualite des sources et les statuts agents.

Actions:
1. Refaire layout global.
2. Ajouter top navigation.
3. Ajouter side rail.
4. Ajouter cartes compactes.
5. Ajouter indicateurs visuels de regime.
6. Ajouter tags de source/confiance.
7. Ajouter bloc Trade Tracker.
8. Ajouter etats visuels:
   - live signal;
   - trade locked;
   - source stale;
   - contradiction active;
   - WAIT force.
9. Verifier desktop/mobile.

Livrable:
- interface v2.0.

Critere de fin:
- design coherent avec les references Stitch;
- pas de texte qui deborde;
- onglets fonctionnels;
- les trades historises sont visibles sans confondre avec le signal live.

### Phase 16 - Monitoring / Audit / Inspector

Objectif:
- rendre le terminal auditable;
- verifier que les sources, agents et trades fonctionnent correctement.

Actions:
1. Tests unitaires existants.
2. Tests parsing sources.
3. Tests fallback source indisponible.
4. Tests scoring regimes.
5. Tests dashboard HTML.
6. Test navigateur local.
7. Ajouter vue ou bloc Inspector:
   - sources actives;
   - dernier refresh;
   - erreurs source;
   - sources stale;
   - agents actifs;
   - sorties agents recentes;
   - trades crees;
   - outcome des trades;
   - data_quality_score.
8. Ajouter logs exploitables pour les decisions et trades.

Livrable:
- verification complete;
- inspector de flux/sources/trades;
- monitoring minimal.

Critere de fin:
- tests OK;
- dashboard charge;
- chaque onglet fonctionne;
- pas d'erreur console critique;
- l'utilisateur peut auditer pourquoi une decision ou un trade existe.

### Phase 17 - Documentation utilisateur

Objectif:
- rendre le projet exploitable facilement.

Actions:
1. Mettre a jour README.
2. Documenter sources.
3. Documenter scoring.
4. Documenter Trade Ledger.
5. Documenter Signal Live vs Trade Plan.
6. Documenter launcher Mac.
7. Documenter limites.
8. Documenter avertissement financier.

Livrable:
- documentation propre.

Critere de fin:
- un utilisateur peut lancer et comprendre le dashboard;
- un utilisateur comprend qu'un trade historise n'est pas modifie retroactivement par le prix live.

## 15. Ordre recommande de livraison

Ordre prioritaire:

1. Finaliser Phase 0 - Audit de reprise.
2. Conserver Phase 1 - Base stable.
3. Lancer Phase 2 - Vrais onglets + departements officiels.
4. Revalider Phase 3 - IG Weekend Gold dans la structure multi-vues.
5. Revalider Phase 4 - WTI/Brent + Hormuz/Oil Shock dans la structure multi-vues.
6. Lancer Phase 5 - Fondation multi-agents passive.
7. Ajouter Phase 6 - FRED macro officiel.
8. Ajouter Phase 7 - Event Facts.
9. Ajouter Phase 8 - Trump / Political Statements.
10. Ajouter Phase 9 - CFTC COT officiel.
11. Ajouter Phase 10 - ETF flows officiels.
12. Ajouter Phase 11 - Calendrier economique et Fed.
13. Ajouter Phase 12 - Data Feed Governance inspire Fincept.
14. Ajouter Phase 13 - Trade Ledger / Signal Locking.
15. Lancer Phase 14 - Refonte scoring global / orchestrateur.
16. Finaliser Phase 15 - Design Aureum Flux Terminal 2.0.
17. Faire Phase 16 - Monitoring / Audit / Inspector.
18. Faire Phase 17 - Documentation utilisateur.

Point de reprise officiel:
- Phase 0: faite;
- Phase 1: faite;
- Phases 2 a 7: finalisees et synchronisees;
- prochaine phase a lancer uniquement apres validation utilisateur: Phase 8.

## 16. Regles de prudence

Le dashboard ne doit jamais:
- inventer une news;
- presenter une rumeur comme fait;
- dire qu'un trade est garanti;
- modifier retroactivement un trade plan deja cree;
- confondre le signal live avec un trade historise;
- confondre spot officiel et proxy week-end;
- dire automatiquement "geopolitique = gold bullish";
- ignorer le regime Hormuz/Oil Shock;
- masquer les sources.

Le dashboard doit toujours:
- afficher les sources;
- afficher le niveau de confiance;
- expliquer le pourquoi concret;
- montrer les contradictions;
- historiser les trades exploitables;
- figer entry, SL et TP dans le Trade Ledger;
- preferer WAIT quand les signaux sont incoherents;
- indiquer qu'il ne s'agit pas d'un conseil financier personnalise.

## 17. Definition de termine pour Aureum Flux Terminal 2.0

La v2.0 est terminee quand:

- le dashboard est multi-vues;
- Dashboard affiche decision rapide + prix + SL/TP;
- Market affiche prix, sources et correlations;
- Decision affiche verdict, SL/TP, contradictions et regime dominant;
- Technical affiche timing, indicateurs et Elliott Wave;
- Macro affiche macro officielle;
- Geopolitics & Flows affiche faits concrets, Trump, Hormuz, oil, COT, ETF;
- Reports exporte un resume propre;
- IG Weekend Gold est integre comme proxy week-end;
- WTI/Brent sont integres;
- FRED officiel est integre;
- Event Facts remplace les phrases vagues;
- Hormuz/Oil Shock change reellement le scoring;
- les agents passifs sont visibles avant activation de l'orchestrateur;
- les sources sont gouvernees par tier, fraicheur et qualite;
- les trades exploitables sont historises;
- les SL/TP des trades historises ne changent pas retroactivement;
- le terminal sait expliquer pourquoi une recommandation precedente a gagne, perdu, expire ou ete invalidee;
- un inspector permet d'auditer sources, agents et trades;
- les tests passent;
- les sources sont documentees.

## 18. Points a valider avant codage

Avant implementation, l'utilisateur doit valider:

- noms exacts des onglets;
- priorite des sources;
- poids du scoring;
- regles de creation d'un trade;
- duree de cooldown entre trades similaires;
- niveaux de risk/reward minimum;
- place de Trump/White House;
- affichage du prix week-end IG;
- formulation des alertes;
- niveau de detail dans les cartes;
- style visuel final.

## 19. Decision recommandee

Recommandation Codex:

Commencer par les fondations les plus utiles:

1. Phase 2 - vrais onglets + departements officiels;
2. Phase 3 - revue IG Weekend Gold;
3. Phase 4 - revue WTI/Brent + regime Hormuz/Oil Shock;
4. Phase 5 - fondation multi-agents passive;
5. Phase 6 a 11 - nouvelles sources officielles et Event Facts;
6. Phase 12 - gouvernance des flux inspiree Fincept;
7. Phase 13 - Trade Ledger / Signal Locking;
8. Phase 14 - orchestrateur et scoring global final.

Decision a partir de la Phase 8:
- continuer dans l'ordre officiel sans relancer les phases finalisees;
- enrichir les sources et les agents progressivement;
- introduire la gouvernance des flux avant le Trade Ledger;
- introduire le Trade Ledger avant l'orchestrateur final;
- ne pas activer l'orchestrateur comme moteur principal avant validation utilisateur.

Ces elements corrigent les plus gros problemes restants:
- politique et declarations Trump encore trop peu structurees;
- sources nombreuses mais pas encore gouvernees par qualite/fraicheur;
- recommandations live qui peuvent changer avec le prix;
- absence d'historique win/loss/expired/invalidated;
- besoin d'un audit clair des sources, agents et trades.

Une fois ces bases solides, le terminal peut passer a l'orchestrateur final et a la decision BUY/SELL/WAIT plus robuste.
