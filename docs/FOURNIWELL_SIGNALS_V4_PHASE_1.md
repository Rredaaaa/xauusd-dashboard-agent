# Fourniwell Signals v4 - Phase 1

Date: 2026-05-13

Objet: stopper les mauvais trades avant toute refonte UI ou news.

## Changements appliques

- Settings par defaut durcis:
  - `scoring_mode=balanced`;
  - `trade_threshold=65`;
  - `minimum_agent_confidence=65`;
  - `minimum_risk_reward=1.5`;
  - `min_data_quality=60`.
- Cooldowns ajoutes:
  - apres loss meme direction: `240 min`;
  - apres win meme direction: `60 min`;
  - limite `max_trades_per_24h`;
  - circuit breaker apres pertes recentes.
- Trade Quality Gate:
  - trois agents decisionnels minimum pour valider une direction;
  - plus d'absorption automatique des contradictions par "majorite nette";
  - blocage des trades en regime geopolitique/petrole fort;
  - blocage autour d'un evenement macro HIGH proche;
  - RR TP1 minimum `1.50R`.
- Agents:
  - confidence du `TechnicalAgent` plafonnee a `85/100`;
  - `SentimentNewsAgent` neutralise si les sources sont faibles ou si l'age median du flux depasse `60 min`;
  - `OrchestratorAgent` legacy retire du scoring et des settings. `OrchestratorDecision` reste la synthese globale.

## Verification

- `python3 -m py_compile xauusd_agent.py`
- `python3 -m unittest discover tests`
- Resultat: `111 tests OK`.

## Effet attendu

Le terminal doit produire moins de trades verrouilles. Un `WAIT` ou `WATCH_*` est normal si le score, la qualite des donnees, le RR ou les confirmations ne sont pas suffisants.
