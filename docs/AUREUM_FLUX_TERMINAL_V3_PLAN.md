# Aureum Flux Terminal 3.0 - Plan d'implementation detaille

Version du document: 1.1
Date: 2026-05-07
Statut: document de passation pour implementation v3.0
Responsable execution prevu: Claude
Base de depart: Aureum Flux Terminal 2.0 apres Phase 18 terminee

## 0. Objectif de la v3.0

La v3.0 n'est pas une phase design.  
La v3.0 est une phase intelligence, lisibilite decisionnelle et robustesse des signaux.

Problemes observes apres v2.0:
- le dashboard affiche encore des phrases difficiles a comprendre;
- la partie news repete parfois des phrases generiques au lieu de resumer le fait detecte;
- certaines alertes ne repondent pas clairement a "quoi, pourquoi, impact, action";
- `WAIT` bloque souvent toute exploitation sans fournir de setup surveille;
- `ElliottWaveAgent` actuel est trop faible et doit etre retire de l'analyse visible;
- la charte interne actuelle n'est pas acceptable pour un trader: le dashboard doit afficher une vraie charte TradingView;
- il manque un moteur technique clair base sur structure, indicateurs, niveaux et confirmations;
- il manque une couche d'explication centralisee;
- il manque une memoire d'apprentissage des signaux et erreurs.

Objectif v3.0:
- transformer Aureum Flux en terminal qui explique clairement le marche;
- produire des faits news structurés, pas seulement des headlines;
- afficher des signaux en trois niveaux: biais, setup surveille, trade exploitable;
- supprimer Elliott du parcours utilisateur tant qu'un vrai moteur robuste n'existe pas;
- remplacer Elliott par un `TechnicalDecisionEngine` auditable;
- afficher une vraie charte TradingView dans le dashboard principal;
- ajouter une architecture inspiree de Vibe-Trading: skills, data routing, preflight, replay, shadow account;
- conserver une interface trader simple: resultat utile d'abord, details dans Inspector.

## 1. Regles non negociables

1. Aucune phase ne commence sans validation explicite utilisateur.
2. Avant chaque phase: verifier `git status`, branche locale, remote GitHub.
3. Apres chaque phase: tests adaptes, commit, push GitHub.
4. Ne pas lancer de trading automatique.
5. Ne pas mentionner de broker specifique dans l'interface utilisateur.
6. Ne pas afficher de phrase vague sans fait concret.
7. Ne plus inclure Elliott dans le raisonnement utilisateur tant qu'il n'est pas robuste.
8. Ne pas forcer un trade pour reduire le nombre de `WAIT`.
9. Conserver `WAIT`, mais ajouter `WATCH_BUY` / `WATCH_SELL`.
10. Les details techniques de sources restent dans Inspector, pas dans la decision principale.

## 2. Inspiration Vibe-Trading retenue

Le repo HKUDS/Vibe-Trading sert de reference d'architecture, pas de code a copier massivement.

Elements a reprendre:
- Skill Registry: methodes documentees dans des dossiers separes;
- Swarm Presets: equipes d'agents par mission;
- Data Routing: selection de source + fallback + statut;
- Preflight Checks: verification des sources avant analyse;
- Backtest / Replay: rejouer des signaux et mesurer leur resultat;
- Shadow Account: comparer ce que le terminal aurait fait vs resultat reel;
- Settings: activer/desactiver agents et seuils;
- Report Generator: rapport signal, rapport jour, post-mortem.

Elements a ne pas reprendre:
- UI React/FastAPI complete;
- couverture multi-marches generaliste;
- Elliott Wave tel quel, car trop simple et trompeur;
- strategy generator universel;
- perimetre actions/crypto/futures complet.

Adaptation Aureum:
- tout reste centre sur XAU/USD;
- les skills sont orientees gold, macro, geopolitique, news, technique, risque;
- les agents produisent des sorties structurees;
- l'orchestrateur transforme les sorties en decision exploitable.

## 3. Architecture cible v3.0

### 3.1 Nouveaux objets de donnees

Creer des modeles explicites:

- `MarketSnapshot`
  - prix live;
  - variation;
  - regime;
  - source quality;
  - timestamp.

- `NewsFact`
  - source;
  - titre;
  - fait detecte;
  - acteurs;
  - categorie;
  - niveau de confirmation;
  - chaine marche;
  - impact XAU/USD;
  - confirmation marche;
  - action trader.

- `AgentOpinion`
  - agent;
  - departement;
  - biais;
  - score;
  - confiance;
  - preuves;
  - risques;
  - invalidation.

- `TechnicalDecision`
  - timeframes utilises;
  - direction technique;
  - structure: trend, breakout, range, pullback ou reversal;
  - trigger;
  - invalidation;
  - entry zone;
  - SL logique;
  - TP1/TP2/TP3;
  - indicateurs confirmants;
  - contradictions;
  - confiance.

- `TradeSetup`
  - statut: `NO_TRADE`, `WATCH_BUY`, `WATCH_SELL`, `TRADE_BUY`, `TRADE_SELL`;
  - direction;
  - zone d'entree;
  - SL;
  - TP1/TP2/TP3;
  - declencheur;
  - invalidation;
  - expiration;
  - raison principale;
  - risques.

- `SourceQuality`
  - source;
  - tier;
  - last_update;
  - stale;
  - missing;
  - confidence;
  - notes.

### 3.2 Couche d'explication

Ajouter une couche unique responsable de la langue utilisateur.

Les agents ne doivent plus chacun ecrire librement leur phrase finale.

La couche `ExplanationLayer` transforme:
- faits;
- scores;
- contradictions;
- structure technique;
- source quality;
- risk gate;

en texte trader clair.

Chaque bloc doit repondre a:
1. Qu'est-ce qui se passe?
2. Pourquoi c'est important?
3. Qu'est-ce qui confirme ou contredit?
4. Impact XAU/USD?
5. Action: acheter, vendre, attendre, surveiller, invalider?

### 3.3 Niveaux de signal

La v3.0 doit separer:

1. `MARKET_BIAS`
   - direction probable du marche;
   - peut exister meme si aucun trade n'est validé.

2. `WATCH_SETUP`
   - setup en surveillance;
   - indique ce qui manque pour devenir exploitable.

3. `TRADE_SETUP`
   - trade exploitable avec entry, SL, TP, invalidation et expiration.

4. `NO_TRADE`
   - aucun setup propre;
   - le dashboard doit expliquer pourquoi.

Cette separation corrige le probleme "aucun signal exploitable" sans forcer des trades.

## 4. Roadmap officielle v3.0

### Phase 19 - Audit documentation et verrouillage v3.0

Objectif:
Verifier la documentation existante et figer la roadmap v3.0 avant codage.

Actions:
1. Verifier `README.md`, `docs/ARCHITECTURE.md`, `docs/SOURCES_AND_SCORING.md`, `docs/USER_GUIDE.md`, `docs/SETUP.md`, `docs/UI_REDESIGN_PHASE_18.md`.
2. Corriger les statuts obsoletes: Phase 18 doit etre marquee terminee.
3. Ajouter ce document v3.0 comme reference officielle.
4. Ajouter un lien depuis `README.md` vers le plan v3.0.
5. Verifier qu'aucune doc ne presente Elliott comme agent fiable.
6. Verifier qu'aucune doc ne promet un trade garanti.
7. Verifier que la notion `WAIT` est expliquee avec futurs statuts `WATCH`.

Livrables:
- documentation coherente;
- point de reprise v3.0 clair;
- pas de contradiction v2/v3.

Tests:
- `rg` sur les termes critiques;
- verification markdown manuelle.

Definition de termine:
- Claude peut reprendre sans devoir redemander ou reconstituer l'historique.

### Phase 20 - Audit editorial phrase par phrase

Objectif:
Auditer toutes les phrases affichees dans le dashboard et identifier ce qui doit etre reecrit.

Actions:
1. Generer un dashboard HTML actuel.
2. Extraire tous les textes visibles.
3. Classer chaque phrase:
   - claire;
   - vague;
   - repetitive;
   - trop technique;
   - incomplete;
   - dangereuse;
   - inutile.
4. Identifier les phrases interdites:
   - "le theme existe";
   - "le risque reste actif";
   - "flux mitigés";
   - "contexte favorable";
   - "prudence";
   - "ne confirme pas" sans expliquer quoi confirme.
5. Produire une table:
   - texte actuel;
   - probleme;
   - texte propose;
   - vue concernee;
   - priorite.

Livrables:
- `reports/editorial_audit_v3.md`;
- liste des composants a modifier;
- dictionnaire des phrases interdites.

Tests:
- pas de changement moteur;
- dashboard continue de se lancer.

Definition de termine:
- chaque texte critique a une version cible claire.

### Phase 21 - Editorial Engine / Explanation Layer

Objectif:
Centraliser la generation des phrases utilisateur.

Actions:
1. Creer un module ou bloc logique `ExplanationLayer`.
2. Ajouter templates:
   - alerte prix;
   - alerte news;
   - regime geopolitique;
   - contradiction agents;
   - no trade;
   - setup surveille;
   - trade exploitable;
   - data quality degradee.
3. Chaque template doit suivre:
   - fait;
   - preuve;
   - confirmation;
   - impact;
   - action.
4. Remplacer progressivement les phrases hardcodees les plus visibles.
5. Ajouter tests unitaires sur les formulations.

Exemple attendu:

Avant:
> Le theme Iran/Hormuz existe, mais le petrole ne confirme pas un choc.

Apres:
> Plusieurs titres mentionnent Iran/Hormuz, mais WTI et Brent reculent. Le marche ne price donc pas encore un choc petrole. Impact XAU/USD: prudence, pas de confirmation refuge. Action: attendre une confirmation oil/DXY avant de valider un trade.

Livrables:
- moteur de phrases;
- tests;
- dashboard plus clair.

Definition de termine:
- aucune alerte principale ne contient une phrase vague non expliquee.

### Phase 22 - News Facts Engine v3

Objectif:
Remplacer la lecture news generique par des faits structures.

Actions:
1. Creer `NewsFact`.
2. Parser chaque headline en:
   - acteur;
   - evenement;
   - actif impacte;
   - type de risque;
   - source;
   - confirmation level.
3. Distinguer:
   - fait confirme;
   - headline non confirmee;
   - opinion;
   - rumeur;
   - analyse marche.
4. Ajouter deduplication semantique.
5. Ajouter scoring source:
   - officielle;
   - agence majeure;
   - media finance;
   - aggregator;
   - faible.
6. Ajouter "confirmation marche":
   - oil confirme ou non;
   - DXY confirme ou non;
   - taux confirment ou non;
   - gold confirme ou non.
7. Afficher dans la vue Geopolitics:
   - resume fait;
   - pourquoi important;
   - impact XAU/USD;
   - action trader.

Livrables:
- `NewsFact` structure;
- remplacement des cartes news;
- tests avec headlines fixtures.

Definition de termine:
- aucune carte news ne repete seulement un titre ou une phrase generique.

### Phase 23 - Skill Registry Aureum

Objectif:
Structurer les methodes agents comme Vibe-Trading, mais en version Aureum.

Actions:
1. Creer dossier `skills/`.
2. Ajouter au minimum:
   - `skills/aureum-editorial-style/SKILL.md`;
   - `skills/aureum-news-engine/SKILL.md`;
   - `skills/aureum-elliott-wave/SKILL.md`;
   - `skills/aureum-chart-store/SKILL.md`;
   - `skills/aureum-data-preflight/SKILL.md`;
   - `skills/aureum-gold-macro/SKILL.md`;
   - `skills/aureum-geopolitical-oil/SKILL.md`;
   - `skills/aureum-risk-manager/SKILL.md`;
   - `skills/aureum-scenario-orchestrator/SKILL.md`;
   - `skills/aureum-trade-quality-gate/SKILL.md`;
   - `skills/aureum-replay-shadow-terminal/SKILL.md`.
3. Chaque skill doit definir:
   - role;
   - inputs;
   - outputs;
   - methodologie;
   - limites;
   - exemples bons/mauvais.
4. Ne pas encore brancher tout au moteur si cela augmente le risque.

Livrables:
- skills documentees;
- base methodologique stable.

Definition de termine:
- chaque agent important a une methode documentee.

### Phase 24 - Data Routing et Preflight v3

Objectif:
Ajouter une logique de verification avant analyse.

Actions:
1. Creer un `DataRouter` pour les sources existantes.
2. Creer un `PreflightCheck`.
3. Verifier:
   - prix XAU/USD disponible;
   - IG Weekend si necessaire;
   - FRED;
   - news;
   - WTI/Brent;
   - CFTC;
   - ETF;
   - OHLC terminal quand disponible.
4. Afficher mode:
   - `READY`;
   - `DEGRADED`;
   - `SOURCE_STALE`;
   - `NO_TRADE_DATA`;
   - `OFFLINE`.
5. Ne pas bloquer tout le dashboard si une source non critique est absente.
6. Separer blockers et warnings:
   - blocker: prix XAU/USD principal absent/stale, data quality tres faible, source bloquante indisponible;
   - warning: source secondaire stale, news weak, data quality degradee mais exploitable.

Livrables:
- preflight visible dans Inspector;
- status global plus fiable.

Definition de termine:
- le dashboard sait expliquer pourquoi une source degrade le signal;
- une source secondaire stale ne force plus `WAIT` seule si le prix principal reste exploitable.

### Phase 25 - Chart Store OHLC multi-timeframe

Objectif:
Donner une base OHLC propre aux agents techniques et au futur `TechnicalDecisionEngine`.

Actions:
1. Creer un `ChartStore`.
2. Stocker OHLC:
   - M5;
   - M15;
   - H1;
   - H4;
   - D1.
3. Format interne:
   - timestamp;
   - open;
   - high;
   - low;
   - close;
   - volume si disponible;
   - source;
   - freshness.
4. Ajouter cache local.
5. Ajouter detection gaps.
6. Ajouter resampling si la source fournit M1.
7. Afficher dans Inspector:
   - timeframes disponibles;
   - nombre de bougies;
   - dernier timestamp;
   - qualite.
8. Dans l'interface principale, ne pas afficher de details inutiles de source.

Livrables:
- stockage OHLC;
- fetch/cache;
- tests de resampling;
- inspector chart quality.

Definition de termine:
- le terminal connait la qualite OHLC par timeframe et peut refuser une lecture technique si l'historique est insuffisant.

### Phase 26 - Elliott Quarantine

Objectif:
Retirer Elliott du scoring tant que le moteur n'est pas fiable.  
Cette phase est une securisation intermediaire; la Phase 27A retire ensuite Elliott du produit visible.

Actions:
1. Mettre poids Elliott a 0 dans l'orchestrateur.
2. Afficher statut:
   - `Elliott experimental`;
   - `non scorant`;
   - `historique insuffisant` si applicable.
3. Modifier docs:
   - Elliott actuel n'est pas un vrai moteur de vague.
4. Tests:
   - Elliott ne peut pas changer BUY/SELL/WAIT.

Livrables:
- scoring securise;
- dashboard honnete.

Definition de termine:
- un faux comptage Elliott ne peut plus influencer un trade.

### Phase 27A - Elliott Removal + TradingView Chart

Statut 2026-05-07: LIVREE.

Objectif:
Retirer Elliott du terminal utilisateur et remplacer la charte interne principale par une vraie charte TradingView.

Decision produit:
Elliott est retire de la v3.0 tant qu'il n'existe pas de moteur robuste.  
Il ne doit plus etre affiche comme agent, preuve, contradiction, scenario ou raison de decision.

Actions:
1. Supprimer `ElliottWaveAgent` des agents affiches.
2. Supprimer Elliott du payload JSON, rapports, Inspector et dashboard.
3. Supprimer le composant Elliott de l'orchestrateur, pas seulement son poids.
4. Garder une note de documentation:
   - Elliott archive;
   - non utilise;
   - ne participe a aucune decision.
5. Remplacer la charte interne principale par un widget TradingView:
   - theme sombre;
   - symbole configurable;
   - `OANDA:XAUUSD` par defaut ou autre symbole public disponible;
   - timeframes TradingView;
   - plein panneau dans Market/Technical.
6. Conserver le Chart Store OHLC en Inspector uniquement:
   - qualite data;
   - timeframes disponibles;
   - cache;
   - gaps.
7. Tests:
   - `ElliottWaveAgent` absent du dashboard;
   - Elliott absent du payload;
   - Elliott absent de l'orchestrateur;
   - TradingView present dans le HTML;
   - dashboard charge sans erreur.

Livrables:
- terminal sans Elliott visible;
- vraie charte TradingView;
- fallback Chart Store conserve en diagnostic;
- tests anti-regression.

Definition de termine:
- aucun utilisateur ne voit Elliott;
- aucune decision ne depend d'Elliott;
- le dashboard affiche une vraie charte TradingView au lieu de la charte interne principale.

### Phase 27B - Technical Decision Engine

Statut 2026-05-07: LIVREE v1.
La v1 remplace Elliott dans les surfaces actives par `TechnicalDecisionEngine`, affiche `TradingView` dans Market/Technical et expose direction, structure, trigger, invalidation, entry zone, SL, TP1/TP2/TP3, raisons et contradictions. Les indicateurs avances listés ci-dessous restent la cible d'enrichissement progressif des phases suivantes.

Objectif:
Remplacer Elliott par un moteur technique auditable base sur structure, indicateurs, niveaux, volatilite et confirmations inter-marches.

Sorties attendues:
- direction technique:
  - `BUY`;
  - `SELL`;
  - `WAIT`;
  - `WATCH_BUY`;
  - `WATCH_SELL`;
- structure:
  - `trend`;
  - `breakout`;
  - `range`;
  - `pullback`;
  - `reversal`;
- trigger;
- invalidation;
- zone d'entree;
- SL logique;
- TP1/TP2/TP3;
- raisons concretes;
- contradictions.

Indicateurs a ajouter ou renforcer:
1. Market Structure:
   - swing highs / swing lows;
   - higher high / higher low;
   - lower high / lower low;
   - Break of Structure `BOS`;
   - Change of Character `CHoCH`;
   - retest apres cassure;
   - range high / range low;
   - premium / discount zone.
2. Trend:
   - EMA 20;
   - EMA 50;
   - EMA 100;
   - EMA 200;
   - pente des EMA;
   - alignement M15/H1/H4/D1;
   - prix au-dessus/sous EMA 50/200.
3. Momentum:
   - RSI 14;
   - RSI 7;
   - MACD ligne/signal/histogramme;
   - divergence RSI/prix;
   - acceleration/deceleration du momentum.
4. Volatility:
   - ATR 14;
   - ATR percentile;
   - range du jour vs ATR;
   - compression / expansion;
   - distance prix au SL logique;
   - volume spike proxy futures.
5. Levels:
   - support/resistance intraday;
   - high/low du jour;
   - high/low veille;
   - open price;
   - Asia high/low;
   - London high/low;
   - New York high/low;
   - VWAP si disponible;
   - pivots classiques `P`, `R1`, `R2`, `S1`, `S2`.
6. Liquidity / Execution:
   - sweep de high/low recent;
   - stop hunt probable;
   - retour dans range apres sweep;
   - vraie cassure vs fausse cassure;
   - distance au prochain niveau de liquidite.
7. Cross Confirmation:
   - DXY;
   - US10Y;
   - 10Y real yield;
   - WTI / Brent;
   - Silver;
   - GDX / GDXJ;
   - VIX / GVZ.

Regles de statut:
- `WATCH_BUY`: tendance/support/momentum preparent un achat, mais trigger non valide.
- `BUY`: `WATCH_BUY` + trigger confirme + invalidation claire + risk/reward acceptable + Preflight non bloquant.
- `WATCH_SELL`: tendance/resistance/momentum preparent une vente, mais trigger non valide.
- `SELL`: `WATCH_SELL` + trigger confirme + invalidation claire + risk/reward acceptable + Preflight non bloquant.
- `WAIT`: range sale, contradiction forte, volatilite anormale, source bloquante ou prix trop loin du niveau d'entree.

Livrables:
- `TechnicalDecisionEngine`;
- structure technique affichee clairement;
- indicateurs calcules et testes;
- integration dans Decision et Technical;
- tests de `BUY`, `SELL`, `WAIT`, `WATCH_BUY`, `WATCH_SELL`.

Definition de termine:
- chaque mot technique affiche dans le dashboard vient d'une regle testee;
- le terminal peut expliquer pourquoi un setup est surveille mais pas encore exploitable.

### Phase 28 - Scenario Engine

Objectif:
Passer de "score unique" a scenarios trader.

Actions:
1. Creer `ScenarioEngine`.
2. Produire:
   - scenario principal;
   - scenario alternatif;
   - invalidation;
   - declencheur;
   - confirmation requise.
3. Integrer `TechnicalDecisionEngine` comme structure technique principale.
4. Integrer news comme declencheur ou contradiction.
5. Integrer macro/correlation comme validation.

Exemple:
- Scenario principal: pullback haussier surveille pres d'un support valide.
- Confirmation: cloture M15 au-dessus de la resistance de reprise + DXY faible + momentum qui repasse positif.
- Invalidation: cloture sous le support/retest ou perte du dernier swing low.
- Statut: `WATCH_BUY`.

Livrables:
- scenarios visibles dans Decision;
- tests de combinaisons contradictoires.

Definition de termine:
- le dashboard ne dit plus seulement WAIT; il explique le prochain trigger.

### Phase 29 - Orchestrator v3 et poids dynamiques

Objectif:
Remplacer le scoring fixe par une decision contextuelle.

Actions:
1. Ajouter poids dynamiques:
   - regime normal: macro + technical plus forts;
   - regime geopolitique: oil/geopolitics plus forts;
   - source degradee: poids reduits;
   - structure technique confirmee: poids technique augmente;
   - structure technique contradictoire: poids technique reduit.
2. Ajouter decision:
   - `NO_TRADE`;
   - `WATCH_BUY`;
   - `WATCH_SELL`;
   - `TRADE_BUY`;
   - `TRADE_SELL`;
   - `WAIT`.
3. Ajouter Quality Gate:
   - minimum source quality;
   - minimum confirmation;
   - contradiction max;
   - risk/reward minimum.
4. Ne jamais creer `TRADE_*` si:
   - prix XAU/USD principal stale ou absent;
   - data quality trop faible;
   - setup sans invalidation;
   - contradiction directionnelle majeure entre composants decisionnels;
   - news non confirmee seule.
5. Ne pas forcer `WAIT` seulement pour:
   - source secondaire stale;
   - data quality degradee mais non bloquante;
   - mode event modere;
   - agent archive ou agent d'audit contradictoire.

Livrables:
- `OrchestratorV3`;
- affichage Decision refondu;
- tests.

Definition de termine:
- le terminal peut donner un setup surveille sans verrouiller un trade.

### Phase 30 - Trade Tracker v3 / Shadow Terminal

Objectif:
Apprendre des signaux precedents.

Actions:
1. Etendre Trade Ledger.
2. Ajouter types:
   - setup surveille;
   - trade exploitable;
   - trade expire;
   - trade invalide.
3. Pour chaque entree:
   - signal;
   - scenario;
   - agents;
   - news fact;
   - structure technique;
   - source quality;
   - resultat.
4. Ajouter post-mortem:
   - pourquoi win;
   - pourquoi loss;
   - agent utile;
   - agent trompeur;
   - condition manquee.
5. Ajouter statistiques:
   - win rate;
   - expectancy;
   - R multiple;
   - duree moyenne;
   - taux setups -> trades.

Livrables:
- ledger v3;
- panneau Reports;
- JSONL ou SQLite selon risque.

Definition de termine:
- un signal passe peut etre relu et explique.

### Phase 31 - Backtest / Replay v3

Objectif:
Verifier les regles sur historique.

Actions:
1. Rejouer une journee avec snapshots.
2. Rejouer plusieurs signaux.
3. Comparer:
   - signal au moment T;
   - prix apres 1h/2h/4h/24h;
   - TP/SL atteint;
   - raison outcome.
4. Ajouter rapport replay.

Inspiration Vibe-Trading:
- backtest;
- validation;
- shadow account.

Livrables:
- commande replay;
- rapport post-mortem;
- tests.

Definition de termine:
- on peut mesurer si Aureum s'ameliore.

### Phase 32 - Settings et controle utilisateur

Objectif:
Permettre de regler le terminal sans modifier le code.

Actions:
1. Ajouter settings fichier local.
2. Parametres:
   - agents actifs;
   - poids minimum;
   - mode prudent/agressif;
   - seuil `WATCH`;
   - seuil `TRADE`;
   - cooldown;
   - risk/reward minimum;
   - notifications plus tard.
3. Ajouter vue Inspector/Settings simple.
4. Ne pas exposer de complexite inutile au dashboard principal.

Livrables:
- settings local;
- validation settings;
- docs.

Definition de termine:
- l'utilisateur peut ajuster le comportement sans casser le projet.

### Phase 33 - Reports v3

Objectif:
Produire des rapports utiles.

Rapports:
- rapport du jour;
- rapport du signal;
- rapport d'un trade verrouille;
- rapport post-mortem;
- audit news;
- audit source quality.

Actions:
1. Ajouter templates de rapport.
2. Ajouter export markdown.
3. Ajouter export HTML simple.
4. Ajouter liens depuis Reports.

Livrables:
- rapports propres;
- tests de generation.

Definition de termine:
- un utilisateur peut comprendre apres coup pourquoi le terminal disait ce qu'il disait.

### Phase 34 - QA finale v3.0

Objectif:
Stabiliser la version.

Actions:
1. Tests unitaires.
2. Tests dashboard local.
3. Tests responsive.
4. Tests source stale.
5. Tests no news.
6. Tests no OHLC.
7. Tests weekend.
8. Tests contradictory agents.
9. Tests trade ledger.
10. Tests replay.
11. Verification documentation.

Livrables:
- checklist QA;
- documentation finale;
- commit/push final.

Definition de termine:
- v3.0 livrable et documentee.

## 5. Ordre recommande

Ne pas commencer par Elliott.
Decision mise a jour v1.1: Elliott n'est plus une phase prioritaire de v3.0. La prochaine etape est de le retirer du produit visible, puis de construire un moteur technique plus fiable.

Ordre recommande:
1. Phase 19 - documentation;
2. Phase 20 - audit editorial;
3. Phase 21 - explanation layer;
4. Phase 22 - news facts;
5. Phase 24 - preflight/data routing;
6. Phase 25 - chart store;
7. Phase 26 - Elliott quarantine;
8. Phase 27A - Elliott removal + TradingView chart;
9. Phase 27B - Technical Decision Engine;
10. Phase 28 - scenario engine;
11. Phase 29 - orchestrator v3;
12. Phase 30 - trade tracker v3;
13. Phase 31 - replay;
14. Phase 32 - settings;
15. Phase 33 - reports;
16. Phase 34 - QA finale.

Raison:
- le langage utilisateur doit etre corrige avant d'ajouter plus d'intelligence;
- Elliott n'est plus fiable pour la v3.0 et doit etre retire du raisonnement utilisateur;
- le Technical Decision Engine a besoin du Chart Store et de TradingView pour l'experience utilisateur;
- l'orchestrateur v3 a besoin de News Facts + Scenario Engine;
- Trade Tracker v3 a besoin des statuts `WATCH` et `TRADE`.

## 6. Definition de succes v3.0

La v3.0 est reussie si:
- un utilisateur comprend la premiere page sans explication externe;
- les news sont resumees en faits et impacts concrets;
- le dashboard ne repete pas des phrases generiques;
- Elliott n'apparait plus dans le dashboard, le payload, l'Inspector ou les rapports tant qu'il n'est pas refonde;
- une vraie charte TradingView remplace la charte interne principale;
- le Technical Decision Engine explique structure, trigger, invalidation, niveaux et confirmations;
- le terminal affiche `WATCH_BUY` / `WATCH_SELL` quand un trade n'est pas encore exploitable;
- `NO_TRADE` explique ce qui manque;
- les trades exploitables restent rares mais justifies;
- les signaux sont historises et evaluables;
- les sources faibles degradent le signal de maniere explicite;
- l'Inspector permet d'auditer chaque decision.

## 7. Passation pour Claude

Claude doit commencer par:
1. lire ce document;
2. lire `docs/AUREUM_FLUX_TERMINAL_V2_PLAN.md`;
3. lire `docs/UI_REDESIGN_PHASE_18.md`;
4. verifier `git status`;
5. confirmer avec l'utilisateur avant Phase 19.

Claude ne doit pas:
- reintroduire Elliott dans le raisonnement utilisateur sans validation explicite;
- ajouter une source OHLC sans Chart Store;
- remplacer TradingView par une charte interne principale;
- changer toute l'UI avant l'audit editorial;
- supprimer les protections `WAIT`;
- creer de trade automatique;
- mentionner un broker personnel dans l'interface.

Phrase de reprise:

> Le projet v2.0 est stabilise apres Phase 18. La v3.0 commence par Phase 19: audit documentation et verrouillage de la roadmap, puis Phase 20: audit editorial phrase par phrase.
