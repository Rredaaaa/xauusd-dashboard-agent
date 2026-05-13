# Fourniwell Signals v4.0 - Roadmap officielle

Version: 1.0  
Date: 2026-05-13  
Ancien nom: Aureum Flux Terminal  
Nouveau nom produit: Fourniwell Signals  
Source de reference: rapport d'inspection technique `aureum_flux_v3_inspection_report_2026-05-12.md`

## 1. Objectif v4.0

Fourniwell Signals v4.0 doit transformer le terminal actuel en un systeme de signaux XAU/USD plus strict, plus lisible, plus fiable et preparable a un usage SaaS.

La v4.0 ne doit pas etre une simple mise a jour visuelle. Elle doit corriger:

- la qualite des sources;
- la logique des agents;
- le scoring;
- le news flow;
- le trade locking;
- le risk management;
- les niveaux SL/TP;
- les strategies de detection;
- l'interface utilisateur finale;
- la preparation utilisateurs / abonnement.

## 2. Principe directeur

Fourniwell Signals ne doit pas afficher du bruit.

Une information ne doit apparaitre sur la vue principale que si elle est:

- recente;
- sourcee;
- utile;
- directionnelle ou explicitement marquee comme non exploitable;
- comprehensible par un utilisateur final.

Tout le detail technique doit rester dans la page Inspector, reservee a l'admin.

## 3. Criteres de succes v4.0

La livraison v4.0 est validee seulement si:

- le systeme ne verrouille plus de trade avec R/R inferieur a 1.5;
- les trades sont bloques apres une serie de pertes;
- les news tier 4 et les vieilles analyses ne polluent plus la page News;
- les news recentes importantes sont visibles avec titre, source, heure, resume et impact XAU/USD;
- les agents faibles ne votent plus dans le scoring;
- le RiskManagerAgent calcule un vrai risque;
- le TradeQualityGate explique clairement pourquoi un trade est accepte ou refuse;
- les SL/TP sont bases sur des niveaux techniques et non sur un simple multiplicateur mecanique;
- le dashboard principal reste simple: prix, biais, signal, chart, trade locked;
- l'Inspector contient le bruit technique sans le montrer aux viewers;
- la version peut etre deployee sur VPS avec protection d'acces.

## 4. Phases officielles

### Phase 0 - Rebranding et base propre

Objectif: repartir sur une base controlee avant de modifier le moteur.

Actions:

- Renommer officiellement le produit en `Fourniwell Signals`.
- Documenter que `Aureum Flux Terminal` devient l'ancien nom.
- Verifier l'etat Git avant toute modification.
- Identifier les changements non commites existants.
- Supprimer ou ignorer les fichiers parasites comme `.DS_Store`.
- Creer la checklist exhaustive v4.0 depuis le rapport d'inspection.
- Geler les anciennes phases v3.
- Definir les objectifs mesurables de v4.0.

Livrables:

- `docs/FOURNIWELL_SIGNALS_V4_ROADMAP.md`
- `docs/V4_INSPECTION_ACTION_CHECKLIST.md`
- etat Git documente avant lancement Phase 1.

### Phase 1 - Stopper les mauvais trades

Objectif: empecher immediatement le systeme de verrouiller des trades faibles.

Actions:

- Passer `minimum_risk_reward` a `1.5`.
- Passer `trade_threshold` a `65`.
- Passer `minimum_agent_confidence` a `65`.
- Passer `scoring_mode` en `balanced` ou `conservative` par defaut.
- Ajouter cooldown apres loss: `240 min`.
- Ajouter cooldown apres win: `60 min`.
- Ajouter maximum trades / 24h.
- Ajouter circuit breaker apres serie de pertes.
- Bloquer les trades si data quality < 60.
- Bloquer les trades avant ou juste apres un evenement macro high impact.
- Plafonner la confidence du TechnicalAgent a `85/100`.
- Desactiver le scoring du SentimentNewsAgent si les sources sont faibles ou trop vieilles.
- Supprimer OrchestratorAgent legacy du scoring.

Livrable:

- moins de trades;
- trades mediocres filtres;
- systeme plus prudent avant la refonte complete.

Statut: livre le 2026-05-13 dans `docs/FOURNIWELL_SIGNALS_V4_PHASE_1.md`.

### Phase 2 - Quality Gate, cooldown et ledger

Statut: livre le 2026-05-13 dans `docs/FOURNIWELL_SIGNALS_V4_PHASE_2.md`.

Objectif: rendre la validation des trades stricte, auditable et dependante de l'historique recent.

Actions:

- Durcir `TradeQualityGate`.
- Exiger au moins 3 validations fiables.
- Supprimer le bypass agressif.
- Bloquer les directions contraires au regime fort.
- Ajouter cooldown differentiel par outcome.
- Ajouter cooldown global: pas plus de X trades / 24h.
- Ajouter blocage apres 2 ou 3 losses consecutives.
- Ajouter validite dynamique du trade selon timeframe.
- Journaliser pourquoi chaque trade est cree, refuse, expire, gagne ou perd.

Livrable:

- trade tracker plus utile;
- decision de lock explicable;
- moins de re-entries absurdes.

### Phase 3 - News Flow v4

Objectif: remplacer le flux news actuel, juge inutilisable.

Actions:

- Ajouter feeds officiels:
  - White House;
  - Federal Reserve;
  - BLS;
  - Treasury;
  - BEA;
  - CFTC;
  - WGC.
- Ajouter medias rapides fiables:
  - AP;
  - CNBC;
  - Reuters si le flux est accessible;
  - Bloomberg si le flux est accessible.
- Rejeter les sources faibles:
  - MSN;
  - FXEmpire;
  - LiteFinance;
  - Moomoo;
  - agregateurs peu fiables.
- Rejeter les titres de type:
  - forecast;
  - prediction;
  - outlook;
  - next week;
  - next month;
  - analysis today;
  - vieux articles;
  - opinions sans fait nouveau.
- Trier par heure reelle de publication.
- Renforcer la deduplication.
- Afficher uniquement les news recentes et impactantes.
- Ajouter resume concret de la news.
- Ajouter impact XAU/USD en langage humain.
- Masquer les news neutres par defaut.
- Si aucune news exploitable: afficher clairement qu'il n'y a pas de news exploitable.

Livrable:

- page News propre;
- plus de vieux bruit;
- news utiles classees par fraicheur et impact.

### Phase 4 - Rebuild des agents

Objectif: faire en sorte que chaque agent ait un role utile et mesurable.

Actions:

- Transformer PriceAgent en PriceActionAgent.
- Corriger TechnicalAgent:
  - confidence cap 85;
  - trigger reel requis;
  - contradictions intra-timeframe prises en compte.
- Conserver MacroAgent mais ajouter:
  - fraicheur FRED;
  - ponderation DXY/DGS10/DFII10/T10YIE;
  - veto avant macro high impact.
- Rendre GeopoliticalOilShockAgent directionnel.
- Desactiver SentimentNewsAgent si aucune news fiable recente.
- Ameliorer CorrelationAgent:
  - hierarchie confirmations/contradictions;
  - poids selon regime.
- Ameliorer FlowPositioningAgent:
  - percentiles CFTC;
  - divergence COT/ETF.
- Recrire EventFactsAgent:
  - qualite > quantite;
  - tier source;
  - recence;
  - confirmation marche.
- Rendre TrumpPoliticalStatementsAgent directionnel et pondere par recence.
- Recrire RiskManagerAgent:
  - R/R;
  - risque par trade;
  - drawdown recent;
  - exposition;
  - circuit breaker.
- Supprimer OrchestratorAgent legacy.

Livrable:

- agents plus fiables;
- votes moins bruyants;
- scoring plus robuste.

### Phase 5 - News Reaction Engine

Objectif: capter les vraies news qui bougent le marche.

Composants a creer:

- `FastNewsListener`
- `EventClassifier`
- `PriceReactionDetector`
- `NewsReactionTradePlan`
- boucle parallele de surveillance news.

Le moteur doit detecter:

- declarations Trump;
- declarations White House;
- declarations Netanyahu / Israel / Iran;
- sanctions;
- cessez-le-feu;
- attaque;
- blocage maritime;
- surprise Fed;
- surprise CPI/NFP.

Regle fondamentale:

- aucune news ne doit declencher un trade seule;
- il faut confirmer avec XAU/USD, oil, DXY et reaction prix.

Livrable:

- signaux news courts;
- validite 15-30 min;
- affichage clair: event exploitable ou non exploitable.

### Phase 6 - Refonte Trade Levels

Objectif: remplacer les SL/TP mecaniques par des niveaux de marche.

Actions:

- Calculer SL/TP selon:
  - swing high/low;
  - pivots;
  - range;
  - breakout;
  - ATR;
  - niveaux psychologiques;
  - structure H1/H4/M15.
- Verifier R/R apres calcul.
- Refuser tout trade avec R/R < 1.5.
- Ajouter validite dynamique:
  - M5: 2h;
  - M15: 4h;
  - H1: 12h;
  - H4: 24h;
  - D1: 72h.

Livrable:

- niveaux plus realistes;
- moins de SL/TP absurdes;
- trade plan mieux justifie.

### Phase 7 - Multi-Strategy Engine

Objectif: ne plus dependre d'une seule logique directionnelle.

Strategies a creer:

- Trend continuation;
- Range trading;
- Breakout du jour;
- Mean reversion;
- Pivot rejection;
- News reaction.

Chaque strategie doit avoir:

- conditions d'entree;
- SL propre;
- TP propre;
- R/R minimum;
- validite;
- cooldown;
- confidence.

Livrable:

- plusieurs types de setups;
- moins de trades forces en range;
- meilleur choix du setup dominant.

### Phase 8 - Interface Fourniwell Signals

Objectif: rendre le produit lisible pour un utilisateur final.

Structure cible:

#### Page 1 - Signal

- Prix XAU/USD.
- Chef de file.
- Biais.
- Confiance.
- TradingView live chart.
- Signal locked.
- Entry / SL / TP / validite.
- Raison courte du signal.

#### Page 2 - Agents

- Agents actifs.
- Boutons ON/OFF.
- Score.
- Confidence.
- Resume court.
- Contribution au signal.

#### Page 3 - News

- News recentes seulement.
- Source.
- Heure.
- Resume.
- Impact XAU/USD.
- Bullish / Bearish.
- Pas de bruit interne.

#### Page 4 - Trades

- Trades actifs.
- Historique.
- Win / loss / expired.
- R multiple.
- Pourquoi le trade a gagne ou perdu.

#### Page 5 - Inspector

- Sources.
- Debug agents.
- Logs.
- Contradictions.
- Data quality.
- Visible uniquement admin.

Livrable:

- dashboard propre;
- separation viewer/admin;
- interface vendable.

### Phase 9 - Preparation SaaS

Objectif: preparer les utilisateurs lecture seule et l'abonnement mensuel.

Actions:

- Authentification.
- Roles:
  - admin;
  - viewer.
- Dashboard lecture seule pour abonnes.
- Reglages visibles uniquement admin.
- Preparation Stripe.
- Protection du dashboard public.
- Sessions securisees.
- Nginx Basic Auth temporaire avant vrai login.

Livrable:

- Fourniwell Signals pret pour abonnement mensuel.

### Phase 10 - QA, replay et validation

Objectif: valider avant de croire le systeme.

Actions:

- Tests unitaires agents.
- Tests TradeQualityGate.
- Tests News Flow.
- Tests fixtures Trump / Iran / Fed / CPI / NFP.
- Replay du ledger.
- Comparaison v3 vs v4.
- Verification R/R.
- Verification cooldown.
- Verification circuit breaker.
- Verification UI mobile/desktop.
- Verification VPS.

Livrable:

- rapport de validation v4;
- decision Go/No-Go production.

### Phase 11 - Deploiement VPS

Objectif: mettre Fourniwell Signals en ligne proprement.

Actions:

- Deploiement sur VPS Hostinger.
- Service `systemd`.
- Nginx reverse proxy.
- Domaine `fourniwell.com`.
- HTTPS.
- Protection par mot de passe.
- Monitoring basique.
- Logs.
- Sauvegardes.
- Procedure rollback.

Livrable:

- Fourniwell Signals accessible H24 en ligne.

## 5. Ordre officiel

1. Phase 0 - Rebranding et base propre.
2. Phase 1 - Stopper les mauvais trades.
3. Phase 2 - Quality Gate, cooldown et ledger.
4. Phase 3 - News Flow v4.
5. Phase 4 - Rebuild des agents.
6. Phase 5 - News Reaction Engine.
7. Phase 6 - Refonte Trade Levels.
8. Phase 7 - Multi-Strategy Engine.
9. Phase 8 - Interface Fourniwell Signals.
10. Phase 9 - Preparation SaaS.
11. Phase 10 - QA, replay et validation.
12. Phase 11 - Deploiement VPS.

## 6. Regles de gouvernance

- Aucune phase ne commence sans etat Git documente.
- Toute phase doit avoir un commit dedie.
- Aucun deploiement VPS avant validation QA minimum.
- Toute source tier 4 doit etre exclue du scoring.
- Toute decision de trade doit pouvoir etre expliquee depuis le payload.
- Le dashboard viewer ne doit jamais afficher le bruit interne.
- L'Inspector peut contenir le detail technique, mais il doit etre reserve admin.

## 7. Decision actuelle

Cette roadmap devient la base de travail v4.0 apres validation utilisateur.

La prochaine phase officielle est:

`Phase 0 - Rebranding et base propre`
