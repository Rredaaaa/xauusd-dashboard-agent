# Fourniwell Signals v4 - Correctif pre-Phase 7

Statut: documentation prealable validee avant implementation code.

Objectif: livrer le `ReversalSetup Engine` complet et nettoyer le Desk avant de lancer la Phase 7.

Ce document est obligatoire parce que le terminal a rate un retournement visible par l'utilisateur, et parce que la page principale affiche encore trop de bruit interne.

## 1. Probleme a corriger

Le terminal sait produire un chef de file global, mais il ne sait pas encore isoler un retournement technique court ou moyen terme quand les agents globaux restent en retard.

Exemple de defaut actuel:

- le chef de file peut rester `NO_TRADE`, `WATCH_SELL` ou `SELL`;
- le prix peut deja construire un retournement BUY sur M5/M15;
- le dashboard n'affiche pas une position reversal exploitable;
- l'utilisateur voit a la place des phrases internes: `Orchestrateur v3`, `Quality Gate`, `SURVEILLER_SELL`, `Statut actuel`.

Ce comportement est refuse.

## 2. Principe produit

Le ReversalSetup Engine ne remplace pas le chef de file.

Il ajoute trois lectures de retournement visibles et separees:

- `Scalp Reversal`;
- `Intraday Reversal`;
- `Swing Reversal`.

Chaque horizon doit afficher soit une position reversal exploitable, soit l'absence de trade.

Statuts visibles autorises:

- `REVERSAL BUY`;
- `REVERSAL SELL`;
- `NO REVERSAL TRADE`.

Statuts interdits dans le Desk:

- `WATCH BUY`;
- `WATCH SELL`;
- `BLOCKED`;
- `SUSPENDED`;
- `Quality Gate`;
- `SURVEILLER_BUY`;
- `SURVEILLER_SELL`;
- `Orchestrateur v3`;
- `score pondere`;
- `reference initiale`.

Les statuts techniques peuvent rester dans le payload ou dans `Inspector`, mais pas sur la page principale.

## 3. Horizons obligatoires

### Scalp Reversal

- signal: M5;
- contexte: M15;
- validite: 30 minutes;
- usage: retournement rapide, entree courte, surveillance active.

### Intraday Reversal

- signal: M15;
- contexte: H1;
- validite: 90 minutes;
- usage: retournement de session, le plus important pour le Desk intraday.

### Swing Reversal

- signal: H1;
- contexte: H4/D1;
- validite: 12 heures;
- usage: retournement plus large, moins frequent mais plus structurant.

Les trois horizons doivent etre calcules et affiches a chaque refresh.
Il est interdit de livrer seulement `Intraday`.

## 4. Conditions de retournement

Chaque horizon calcule cinq familles de preuves:

1. RSI extreme:
   - BUY: RSI7 <= 18;
   - SELL: RSI7 >= 82.
2. Divergence RSI/prix:
   - BUY: prix lower low + RSI higher low;
   - SELL: prix higher high + RSI lower high.
3. Rejet de swing:
   - BUY: meche sous swing low puis cloture au-dessus;
   - SELL: meche au-dessus swing high puis cloture en dessous.
4. Volume spike:
   - volume_ratio > 1.5.
5. Position dans le range du jour:
   - BUY: prix dans les 20% inferieurs du range;
   - SELL: prix dans les 20% superieurs du range.

Un reversal visible exige:

- direction BUY ou SELL;
- au moins 4 conditions sur 5;
- ou 3 conditions sur 5 seulement si elles incluent divergence + rejet swing et que le R/R TP1 >= 1.80R;
- SL/TP ordonnes;
- R/R TP1 >= 1.50R;
- pas de contexte superieur qui invalide le retournement.

Sinon, le Desk affiche `NO REVERSAL TRADE`.

## 5. Niveaux

Chaque position reversal doit afficher:

- Entry;
- SL;
- TP1;
- TP2;
- TP3;
- R/R TP1;
- validite;
- raison principale.

Ordre obligatoire:

- BUY: `SL < entry < TP1 < TP2 < TP3`;
- SELL: `TP3 < TP2 < TP1 < entry < SL`.

Profils de niveaux:

- `reversal_scalp`: SL plus serre, TP rapides;
- `reversal_intraday`: SL intermediaire, TP de session;
- `reversal_swing`: SL plus large, TP plus etendus.

## 6. Affichage Desk cible

La page principale reste une page trader, pas une page debug.

Elle doit afficher:

- prix XAU/USD;
- chef de file;
- biais;
- signal locked;
- IG Weekend Gold si disponible;
- TradingView live chart;
- `Scalp Reversal`;
- `Intraday Reversal`;
- `Swing Reversal`.

Le bandeau prix / chef de file / biais / signal locked reste en colonnes.
Les trois rubriques reversal doivent rester lisibles, sans texte compresse.
Les niveaux Entry/SL/TP peuvent etre en mini-grille dans chaque rubrique.

## 7. Nettoyage Desk obligatoire

Le Desk ne doit plus afficher:

- resume complet de l'orchestrateur;
- `score pondere`;
- `reference initiale`;
- phrase `Pas de trade` issue du moteur interne;
- phrase `Le Desk affiche une surveillance`;
- `Quality Gate`;
- `SURVEILLER_*`;
- doublon `Signal live`.

Regle d'affichage:

- si un trade locked existe: afficher la position verrouillee et ses niveaux fixes;
- si aucun trade locked n'existe: afficher `AUCUNE POSITION ACTIVE`;
- si un scenario est surveille: l'afficher en une ligne courte, pas comme une position;
- si un reversal est exploitable: afficher `REVERSAL BUY` ou `REVERSAL SELL`;
- si aucun reversal n'est exploitable: afficher `NO REVERSAL TRADE` avec une raison courte.

## 8. Payload cible

Le payload doit contenir:

```text
reversal_engine.scalp
reversal_engine.intraday
reversal_engine.swing
```

Chaque objet contient:

- horizon;
- status interne;
- status visible;
- direction;
- tf_signal;
- tf_context;
- confluence_score;
- conditions_met;
- entry_zone_low;
- entry_zone_high;
- stop_loss;
- tp1;
- tp2;
- tp3;
- risk_reward_tp1;
- validity_minutes;
- reasons;
- blockers internes;
- detected_at.

## 9. Tests obligatoires

Tests minimum:

- divergence RSI bullish detectee;
- divergence RSI bearish detectee;
- aucune divergence quand prix et RSI sont alignes;
- no reversal si conditions insuffisantes;
- reversal BUY levels ordonnes;
- reversal SELL levels ordonnes;
- `scalp`, `intraday`, `swing` toujours presents;
- verdict orchestrator inchange;
- Desk ne contient plus `Orchestrateur v3`;
- Desk ne contient plus `Quality Gate`;
- Desk ne contient plus `SURVEILLER_`;
- Desk ne contient plus `WATCH BUY`, `WATCH SELL`, `BLOCKED`.

## 10. Definition de done

Le correctif est livre seulement si:

- cette documentation existe avant le code;
- la roadmap officielle reference ce correctif avant Phase 7;
- le code implemente les trois horizons;
- les trois horizons sont visibles dans le Desk;
- le Desk ne montre plus le bruit interne;
- les niveaux reversal sont coherents;
- tous les tests passent;
- le dashboard local se lance;
- le commit est pousse sur GitHub.
