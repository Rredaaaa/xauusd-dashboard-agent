# Phase 18 - Redesign structurel UI

Ce document sert de garde-fou avant de modifier le dashboard. La Phase 18 ne doit pas changer l'analyse, les agents, les sources, le Trade Ledger ou l'Orchestrateur.

## Probleme a corriger

La version actuelle contient les bonnes informations, mais l'interface recycle trop de blocs de l'ancien dashboard. Cela produit:

- cartes trop etroites;
- texte compresse ou vertical;
- zones vides importantes;
- tables longues mal integrees;
- navigation redondante;
- impression de monopage scrolle malgre les onglets.

## Objectif

Construire un vrai terminal multi-vues:

- lisible;
- compact;
- auditable;
- utilisable pendant le trading;
- stable au refresh live.

## Non-objectifs

Ne pas modifier:

- scoring;
- agents;
- sources;
- Orchestrateur v2;
- Trade Ledger;
- Inspector data model;
- payload JSON;
- logique BUY/SELL/WAIT.

## Sous-phases

### 18A - Audit visuel et specification

Livrer avant tout code:

- liste des problemes par onglet;
- composants a refaire;
- structure cible de chaque vue;
- decisions UI a valider.

### 18B - Shell global

Refaire:

- side rail;
- top status bar;
- grille principale;
- navigation;
- refresh live avec onglet actif conserve.

### 18C - Dashboard et Decision

Refaire les vues prioritaires:

- decision live;
- SL/TP;
- Quality Gate;
- Orchestrateur;
- Trade Tracker;
- separation Signal Live vs TradePlan.

### 18D - Market, Technical, Macro

Refaire les vues analytiques:

- prix et IG Weekend Gold;
- chandelles;
- correlations;
- technical matrix;
- Elliott Wave;
- FRED et calendrier macro.

### 18E - Geopolitics, Inspector, Reports

Refaire:

- Event Facts;
- Trump / White House;
- Oil Shock;
- Inspector sources/agents/trades;
- Reports simples.

### 18F - Verification et polish

Verifier:

- desktop;
- mobile;
- screenshots;
- pas de texte vertical;
- pas d'overflow incoherent;
- onglets apres refresh;
- tests unitaires;
- GitHub synchronise.

## Structure cible des vues

### Dashboard

But: savoir quoi faire ou pourquoi attendre.

Contenu:

- prix live;
- decision globale;
- regime;
- confiance;
- risk banner;
- Trade Tracker resume;
- alertes sources.

### Decision

But: comprendre la decision.

Contenu:

- Orchestrateur v2;
- raisons principales;
- contre-signaux;
- Decision Gate;
- Trade Gate;
- contradictions.

### Market

But: lire le marche.

Contenu:

- spot;
- IG Weekend Gold;
- chandelles;
- niveaux;
- correlations;
- WTI/Brent;
- COT;
- ETF flows.

### Technical

But: lire le timing.

Contenu:

- multi-timeframe;
- Elliott Wave;
- scenarios;
- invalidation.

### Macro

But: lire dollar/taux/Fed.

Contenu:

- DXY;
- FRED;
- real yield;
- calendrier;
- MacroAgent.

### Geopolitics & Flows

But: comprendre les faits externes.

Contenu:

- Event Facts;
- Trump / White House;
- Hormuz/Oil Shock;
- oil/dollar liquidity;
- headlines expliquees.

### Inspector

But: auditer le terminal.

Contenu:

- sources;
- erreurs;
- stale/missing/weak;
- agents;
- trades;
- outcomes;
- audit log.

### Reports

But: retrouver les exports.

Contenu:

- chemins fichiers;
- resume;
- avertissement.

## Critere de reussite

La Phase 18 est terminee seulement si:

- aucune carte n'est ecrasee;
- aucun texte n'est vertical;
- les tables sont lisibles;
- les grands vides inutiles sont supprimes;
- la navigation est claire;
- les onglets fonctionnent apres refresh;
- le dashboard reste lisible desktop et mobile;
- les tests passent;
- GitHub est synchronise.
