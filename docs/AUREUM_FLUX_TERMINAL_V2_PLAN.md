# Aureum Flux Terminal 2.0 - Plan de conception et d'implementation

Version du document: 1.0  
Date: 2026-04-25  
Statut: cadrage avant implementation  
Objectif: servir de base officielle pour toutes les evolutions v2.0 du dashboard XAU/USD.

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
- Que dit l'agent maintenant?
- Est-ce BUY, SELL ou WAIT?
- Ou sont le SL et les TP?
- Pourquoi cette decision en une phrase?
- Est-ce un marche normal ou un regime special?

### 4.2 Onglet Market Analysis

Role: expliquer le scenario global.

Contenu:
- scenario principal;
- scenario alternatif haussier;
- scenario alternatif baissier;
- scenario attente;
- niveaux importants;
- support/resistance;
- contexte intraday;
- synthese des facteurs dominants.

Questions auxquelles cet onglet repond:
- Pourquoi le marche penche d'un cote?
- Qu'est-ce qui invalide le scenario?
- Quel niveau change la lecture?
- Qu'est-ce qui est prioritaire maintenant?

### 4.3 Onglet Technical

Role: timing et structure de prix.

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
- verdict technique;
- raisons techniques concretes.

Questions auxquelles cet onglet repond:
- Le timing confirme-t-il le signal?
- Le prix est-il au-dessus ou sous les EMA?
- Les timeframes superieurs confirment-ils?
- Le volume soutient-il le mouvement?

### 4.4 Onglet Fundamental

Role: macro, taux, dollar, inflation.

Contenu:
- DXY;
- US 10Y nominal;
- US 10Y reel;
- breakeven inflation 10Y;
- Fed/FOMC;
- CPI/NFP si disponible;
- calendrier economique;
- impact des taux sur gold;
- impact du dollar sur gold;
- lecture macro finale.

Questions auxquelles cet onglet repond:
- Les taux soutiennent-ils ou freinent-ils l'or?
- Le dollar confirme-t-il le trade?
- Le marche price-t-il une Fed plus dovish ou hawkish?
- L'inflation pousse-t-elle gold ou les rendements?

### 4.5 Onglet Geopolitique & Sentiment

Role: faits politiques, guerre, Hormuz, Trump, sentiment, flows.

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
- Le sentiment soutient-il vraiment le signal global?

### 4.6 Onglet Reports

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
analysis/
  technical.py
  macro.py
  geopolitical.py
  regimes.py
  scoring.py
  event_facts.py
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

### Phase 0 - Validation du cahier des charges

Objectif:
- lire ce document;
- valider les onglets;
- valider les sources;
- valider la logique Hormuz/Oil Shock;
- valider le vocabulaire.

Livrable:
- document approuve par l'utilisateur.

Critere de fin:
- accord clair avant modification du code.

### Phase 1 - Stabilisation avant v2.0

Objectif:
- verifier l'etat actuel du projet;
- verifier les changements non commits;
- lancer les tests existants;
- s'assurer que le dashboard actuel fonctionne.

Actions:
1. `git status`.
2. Lire les fichiers modifies.
3. Lancer les tests.
4. Lancer le dashboard local.
5. Verifier visuellement.

Livrable:
- base stable.

Critere de fin:
- tests OK;
- dashboard accessible;
- aucune regression majeure.

### Phase 2 - Vrais onglets dashboard

Objectif:
- remplacer la longue page par des vues dediees.

Actions:
1. Creer une navigation principale.
2. Creer les vues:
   - Dashboard;
   - Market Analysis;
   - Technical;
   - Fundamental;
   - Geopolitique & Sentiment;
   - Reports.
3. Ajouter le JavaScript minimal pour afficher une seule vue a la fois.
4. Garder le live refresh compatible.
5. Tester chaque bouton.

Livrable:
- dashboard multi-vues.

Critere de fin:
- chaque bouton affiche une vue differente;
- pas de scroll monopage force;
- live refresh ne casse pas les onglets.

### Phase 3 - Ajout IG Weekend Gold

Objectif:
- rendre le dashboard utile le samedi/dimanche.

Actions:
1. Creer une fonction de recuperation IG Weekend Gold.
2. Parser sell/buy/mid si disponible.
3. Detecter si le marche classique est ferme.
4. Afficher `Weekend proxy`.
5. Comparer dernier spot classique vs IG week-end.

Livrable:
- bloc prix week-end.

Critere de fin:
- le samedi/dimanche, le dashboard montre clairement le prix IG separe du spot classique.

### Phase 4 - Ajout WTI/Brent et regime Hormuz/Oil Shock

Objectif:
- integrer le lien politique -> oil -> dollar/taux -> gold.

Actions:
1. Ajouter `CL=F`.
2. Ajouter `BZ=F`.
3. Ajouter variation jour/court terme.
4. Detecter headlines Hormuz/Iran/shipping/mines/blockade.
5. Construire le regime `Hormuz/Oil Shock`.
6. Modifier le scoring geopolitique.

Livrable:
- regime oil shock actif quand conditions remplies.

Critere de fin:
- le dashboard peut dire: tension geopolitique positive pour oil mais negative/mixte pour gold.

### Phase 5 - Ajout FRED macro officiel

Objectif:
- fiabiliser taux/inflation.

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

### Phase 6 - Event Facts

Objectif:
- remplacer les phrases vagues par des faits concrets.

Actions:
1. Creer une structure `EventFact`.
2. Convertir les headlines importantes en faits.
3. Ajouter actors, locations, themes.
4. Ajouter confirmation_level.
5. Ajouter market_chain.
6. Ajouter gold_impact.
7. Afficher les faits dans `Geopolitique & Sentiment`.

Livrable:
- cartes "Fait detecte".

Critere de fin:
- chaque conclusion geopolitique cite un fait et une source.

### Phase 7 - Trump / White House

Objectif:
- suivre les declarations politiques a fort impact.

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

### Phase 8 - CFTC COT officiel

Objectif:
- remplacer les headlines COT par des donnees officielles.

Actions:
1. Identifier le fichier CFTC adapte a gold futures.
2. Parser les positions.
3. Extraire Managed Money, Producers, Swap Dealers, Non-reportable.
4. Calculer variation semaine.
5. Afficher le positionnement.
6. Integrer dans scoring sentiment.

Livrable:
- bloc COT officiel.

Critere de fin:
- le dashboard n'utilise plus seulement des headlines pour COT.

### Phase 9 - ETF flows officiels

Objectif:
- mesurer les flux institutionnels gold.

Actions:
1. Ajouter WGC ETF flows si accessible.
2. Ajouter GLD holdings.
3. Ajouter IAU holdings.
4. Calculer flux jour/semaine.
5. Classer inflows/outflows/mixed.
6. Integrer dans sentiment.

Livrable:
- bloc ETF flows officiel.

Critere de fin:
- les flux ETF ont une source explicite.

### Phase 10 - Calendrier economique et Fed

Objectif:
- anticiper les catalyseurs macro.

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

### Phase 11 - Refonte scoring global

Objectif:
- consolider tout dans une decision plus robuste.

Actions:
1. Implementer scores separes:
   - technique;
   - macro;
   - geopolitique;
   - cross-assets;
   - regime;
   - data quality.
2. Ajouter pondération.
3. Ajouter WAIT si contradictions fortes.
4. Ajouter raisons top 3.
5. Ajouter raisons contre-signal top 3.

Livrable:
- score global v2.0.

Critere de fin:
- le verdict explique ses preuves et ses contradictions.

### Phase 12 - Design Aureum Flux Terminal 2.0

Objectif:
- appliquer le design terminal institutionnel multi-vues.

Actions:
1. Refaire layout global.
2. Ajouter top navigation.
3. Ajouter side rail.
4. Ajouter cartes compactes.
5. Ajouter indicateurs visuels de regime.
6. Ajouter tags de source/confiance.
7. Verifier desktop/mobile.

Livrable:
- interface v2.0.

Critere de fin:
- design coherent avec les references Stitch;
- pas de texte qui deborde;
- onglets fonctionnels.

### Phase 13 - Tests et verification

Objectif:
- eviter de casser le dashboard.

Actions:
1. Tests unitaires existants.
2. Tests parsing sources.
3. Tests fallback source indisponible.
4. Tests scoring regimes.
5. Tests dashboard HTML.
6. Test navigateur local.

Livrable:
- verification complete.

Critere de fin:
- tests OK;
- dashboard charge;
- chaque onglet fonctionne;
- pas d'erreur console critique.

### Phase 14 - Documentation utilisateur

Objectif:
- rendre le projet exploitable facilement.

Actions:
1. Mettre a jour README.
2. Documenter sources.
3. Documenter scoring.
4. Documenter launcher Mac.
5. Documenter limites.
6. Documenter avertissement financier.

Livrable:
- documentation propre.

Critere de fin:
- un utilisateur peut lancer et comprendre le dashboard.

## 15. Ordre recommande de livraison

Ordre prioritaire:

1. Valider ce document.
2. Stabiliser dashboard actuel.
3. Creer vrais onglets.
4. Ajouter IG Weekend Gold.
5. Ajouter WTI/Brent.
6. Ajouter regime Hormuz/Oil Shock.
7. Ajouter Event Facts.
8. Ajouter FRED DGS10/DGS2/T10YIE.
9. Ajouter Trump/White House.
10. Ajouter CFTC COT.
11. Ajouter WGC/GLD/IAU ETF flows.
12. Refaire scoring global v2.0.
13. Finaliser design.
14. Tester.
15. Documenter.

## 16. Regles de prudence

Le dashboard ne doit jamais:
- inventer une news;
- presenter une rumeur comme fait;
- dire qu'un trade est garanti;
- confondre spot officiel et proxy week-end;
- dire automatiquement "geopolitique = gold bullish";
- ignorer le regime Hormuz/Oil Shock;
- masquer les sources.

Le dashboard doit toujours:
- afficher les sources;
- afficher le niveau de confiance;
- expliquer le pourquoi concret;
- montrer les contradictions;
- preferer WAIT quand les signaux sont incoherents;
- indiquer qu'il ne s'agit pas d'un conseil financier personnalise.

## 17. Definition de termine pour Aureum Flux Terminal 2.0

La v2.0 est terminee quand:

- le dashboard est multi-vues;
- Dashboard affiche decision rapide + prix + SL/TP;
- Market Analysis explique le scenario;
- Technical affiche timing et indicateurs;
- Fundamental affiche macro officielle;
- Geopolitique & Sentiment affiche faits concrets, Trump, Hormuz, oil, COT, ETF;
- Reports exporte un resume propre;
- IG Weekend Gold est integre comme proxy week-end;
- WTI/Brent sont integres;
- FRED officiel est integre;
- Event Facts remplace les phrases vagues;
- Hormuz/Oil Shock change reellement le scoring;
- les tests passent;
- les sources sont documentees.

## 18. Points a valider avant codage

Avant implementation, l'utilisateur doit valider:

- noms exacts des onglets;
- priorite des sources;
- poids du scoring;
- place de Trump/White House;
- affichage du prix week-end IG;
- formulation des alertes;
- niveau de detail dans les cartes;
- style visuel final.

## 19. Decision recommandee

Recommandation Codex:

Commencer par les fondations les plus utiles:

1. vrais onglets;
2. IG Weekend Gold;
3. WTI/Brent;
4. regime Hormuz/Oil Shock;
5. Event Facts.

Ces cinq elements corrigent les plus gros problemes actuels:
- dashboard encore trop monopage;
- prix week-end absent;
- politique trop vague;
- geopolitique trop generalisee;
- manque de faits concrets.

Une fois ces bases solides, ajouter COT, ETF flows, FedWatch et refonte scoring globale.
