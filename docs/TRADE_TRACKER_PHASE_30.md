# Phase 30 - Trade Tracker v3 / Shadow Terminal

Statut: implementation lancee.

Objectif:
Apprendre des signaux passes sans modifier retroactivement les trades.

Ce qui est ajoute:
- enrichissement `TradePlan` avec type v3:
  - `setup_surveille`;
  - `trade_exploitable`;
  - `trade_expire`;
  - `trade_invalide`;
- post-mortem automatique par trade ferme;
- calcul `R multiple`;
- duree du trade en minutes;
- agents utiles;
- agents trompeurs;
- condition manquee;
- statistiques globales du ledger:
  - win rate;
  - expectancy R;
  - average R;
  - duree moyenne;
  - taux setup -> trade;
  - taux trade -> win;
- affichage dans `Reports` via le panneau Trade Tracker.

Regle importante:
Phase 30 n'optimise pas encore les entrees. Elle mesure et explique. La calibration des trades sera traitee apres la livraison des phases prevues.

Append-only:
- les anciens `TradePlan` ne sont pas reecrits;
- chaque mise a jour d'outcome ajoute un snapshot JSONL;
- les champs v3 sont reconstruits a la lecture si un ancien snapshot ne les contient pas.

Definition de termine:
- un signal passe peut etre relu;
- son outcome est visible;
- le post-mortem explique pourquoi il est win/loss/partial/expired/invalidated;
- les stats du ledger sont disponibles dans le dashboard, le payload et l'Inspector.
