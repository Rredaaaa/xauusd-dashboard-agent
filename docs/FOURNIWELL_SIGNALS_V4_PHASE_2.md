# Fourniwell Signals v4 - Phase 2

Date: 2026-05-13

## Objectif

Rendre le Trade Tracker plus strict, plus auditable et moins sensible aux re-entrees absurdes. La Phase 2 ne change pas le design: elle renforce le comportement du Quality Gate et du ledger.

## Livrables

- Cooldown differentiel apres outcome:
  - loss: 240 minutes;
  - win: 60 minutes;
  - expired: 60 minutes;
  - doublon actif ou recent: blocage de la meme direction/regime.
- Validite dynamique des TradePlans:
  - M5: 2h;
  - M15: 4h;
  - H1: 12h;
  - H4: 24h;
  - D1: 72h.
- Reduction de validite de 25% en mode event actif.
- Journal d'audit append-only dans `reports/trade_gate_audit.jsonl`.
- Traces auditees pour:
  - `trade_created`;
  - `trade_refused_gate`;
  - `trade_refused_ledger_guard`;
  - `trade_refused_cooldown`;
  - `trade_won`;
  - `trade_lost`;
  - `trade_partial`;
  - `trade_expired`;
  - `trade_invalidated`.

## Impact utilisateur

Le signal live peut encore changer avec le prix, mais un TradePlan verrouille sa validite, son entry, son SL, ses TP et ses raisons au moment de creation. Si un signal expire, le terminal ne reprend pas automatiquement la meme direction pendant 60 minutes.

## Fichiers touches

- `xauusd_agent.py`
- `config/aureum_settings.example.json`
- `docs/FOURNIWELL_SIGNALS_V4_ROADMAP.md`
- `docs/V4_INSPECTION_ACTION_CHECKLIST.md`
- `docs/SOURCES_AND_SCORING.md`
- `docs/SETUP.md`
- `docs/USER_GUIDE.md`
- `tests/test_xauusd_agent.py`

## Verification

- `python3 -m py_compile xauusd_agent.py`
- `python3 -m unittest discover tests`

