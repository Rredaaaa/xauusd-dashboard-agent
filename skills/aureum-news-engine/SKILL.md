---
name: aureum-news-engine
description: Methodologie News Facts v3 pour transformer les headlines en faits, confirmations marche et actions trader.
category: analysis
---

# Aureum News Engine

## Probleme actuel

Le dashboard affiche parfois:
- titre brut;
- phrase generique;
- chaine marche repetee;
- impact gold vague.

La v3 doit produire des `NewsFact` structures.

## Objet cible: NewsFact

Champs minimum:

```text
source_name
source_tier
published_at
headline
detected_fact
actors
location_or_theme
event_type
confirmation_level
market_chain
oil_confirmation
dxy_confirmation
rates_confirmation
gold_confirmation
xauusd_impact
trader_action
confidence
```

## Niveaux de confirmation

- `official_confirmed`: source officielle ou primaire.
- `confirmed_secondary`: Reuters/AP/Bloomberg/major finance confirme.
- `market_confirmed`: headline confirmee par prix oil/DXY/taux/gold.
- `unconfirmed_headline`: titre non confirme.
- `opinion`: opinion/commentaire.
- `weak_source`: source faible.

## Transformation attendue

Input:

```text
Gold Price Falls as US-Iran War Drives Inflation Fears
```

Output:

```text
Fait detecte: le titre relie la baisse de l'or a la crainte d'inflation liee au conflit US-Iran.
Pourquoi: si le petrole monte, le marche peut anticiper inflation plus haute et Fed plus restrictive.
Confirmation marche: verifier WTI/Brent, DXY, 10Y reel.
Impact XAU/USD: mixte a baissier si dollar/taux montent; refuge seulement si risk-off domine.
Action: ne pas valider BUY refuge sans confirmation oil/DXY favorable.
```

## Regles specifiques gold

Geopolitique ne veut pas automatiquement dire gold bullish.

Cas Iran/Hormuz/oil:
- si WTI/Brent montent fortement + DXY monte: gold peut baisser par liquidite/dollar/taux;
- si WTI/Brent montent mais DXY baisse et risk-off domine: gold peut monter;
- si headlines geopol mais oil baisse: pas de choc confirme.

## Deduplication

Plusieurs titres sur le meme evenement = un seul `NewsFact` renforce.

Ne jamais compter 5 headlines similaires comme 5 faits independants.

## Sortie UI

Chaque carte news doit afficher:
- source + tier;
- fait detecte en une phrase;
- confirmation marche;
- impact XAU/USD;
- action.

Le titre brut peut rester secondaire.

## Tests

Creer fixtures:
- headline Hormuz non confirmee par oil;
- headline oil shock confirmee par WTI/Brent;
- declaration politique non confirmee;
- source officielle;
- doublons semantiques.
