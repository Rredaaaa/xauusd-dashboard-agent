---
name: aureum-replay-shadow-terminal
description: Replay, post-mortem et Shadow Terminal pour apprendre des signaux Aureum.
category: evaluation
---

# Aureum Replay / Shadow Terminal

## But

Mesurer si Aureum s'ameliore.

Le terminal doit pouvoir repondre:
- quel signal a ete donne?
- pourquoi?
- quel etait le prix apres?
- quels agents avaient raison?
- quelles sources ont trompe?
- quelle regle doit etre ajustee?

## Objets

- `SignalSnapshot`;
- `SetupSnapshot`;
- `TradePlan`;
- `TradeOutcome`;
- `PostMortem`.

## Replay

Rejouer:
- une heure;
- une journee;
- une semaine;
- un signal precis.

Comparer:
- decision au moment T;
- prix apres 1h/2h/4h/24h;
- TP/SL atteint;
- setup devenu trade ou pas;
- trigger confirme ou invalide.

## Shadow Terminal

Inspire Vibe-Trading Shadow Account, mais adapte Aureum:

- ce que le terminal aurait recommande;
- ce qui s'est passe ensuite;
- delta entre setup surveille et trade exploitable;
- raisons de win/loss/expired;
- agent contribution.

## Rapports

Generer:
- rapport du signal;
- rapport journalier;
- post-mortem trade;
- audit agents;
- audit news.

## Metriques

- win rate;
- expectancy;
- average R;
- taux setup -> trade;
- taux trade -> win;
- agent accuracy;
- false positives news;
- false positives Elliott.

## Tests

- replay sur fixture;
- post-mortem win;
- post-mortem loss;
- expired;
- invalidated;
- agent attribution.

## Phase 23 Contract

### Role

Mesurer apres coup la qualite des signaux, setups et trades Aureum.

### Inputs

- SignalSnapshot;
- SetupSnapshot;
- TradePlan;
- prix apres 1h/2h/4h/24h;
- agent contributions;
- NewsFacts et source quality au moment T.

### Outputs

- outcome;
- post-mortem;
- agent attribution;
- metrics;
- recommandations de reglage.

### Methodologie

1. Charger snapshot append-only.
2. Rejouer le prix apres le signal.
3. Comparer trigger, TP, SL, expiration.
4. Identifier agents utiles ou trompeurs.
5. Sauvegarder post-mortem.

### Limites

- Ne pas reecrire un ancien TradePlan.
- Ne pas juger avec des donnees inconnues au moment T.
- Ne pas transformer replay en optimisation abusive.

### Bons exemples

- `WATCH_SELL invalide apres 2h: DXY a casse le seuil inverse, pas de trade cree.`

### Mauvais exemples

- Modifier retroactivement l'entry pour rendre un trade gagnant.
