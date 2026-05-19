# Fourniwell Signals v4 - Phase 7F QA Readiness

Statut: livree le 2026-05-19.

Objectif: valider toute la Phase 7 avant Phase 7.5, sans activer le moteur multi-strategies dans le chef de file ni dans le trade lock.

## Perimetre verifie

- Phase 7A: foundation `SetupCandidate`;
- Phase 7B: candidates Pivot, Mean Reversion, Range, Trend, Breakout, News Reaction;
- Phase 7C: `StrategyCoordinator`;
- Phase 7D: Inspector multi-strategy;
- Phase 7E: shadow integration;
- correctif audit A-D: `NO_SETUP_TRADE`, `partial_conditions`, weekend, range 3 touches, breakout range asiatique, historique JSONL.

## Correction trouvee pendant 7F

Le cycle reel a detecte un bug de serialization JSON quand aucune strategie n'etait eligible.

Cause:

- `StrategyCoordinator.select()` retournait les `rejected_candidates` bruts dans le cas `not ranked`;
- ces objets contenaient encore la cle interne `candidate` avec un `SetupCandidate`;
- `json.dumps(bundle.payload)` echouait avec `TypeError: Object of type SetupCandidate is not JSON serializable`.

Correctif applique:

- les `rejected_candidates` sont maintenant convertis via `public_rank()` meme quand aucune strategie n'est eligible;
- le test `test_phase7c_no_setup_when_all_candidates_are_noise` verifie que la cle interne `candidate` n'est plus exposee;
- le meme test verifie que `json.dumps(asdict(selection))` passe.

## Runtime reel verifie

Commande executee:

```bash
.venv/bin/python xauusd_agent.py --quiet --top-news 12 --save reports/xauusd_report.md --dashboard reports/xauusd_dashboard.html --data-json reports/xauusd_data.json
```

Resultat:

- `reports/xauusd_dashboard.html` genere;
- `reports/xauusd_data.json` genere;
- `reports/audit_log.jsonl` append-only mis a jour;
- `reports/multi_strategy_history.jsonl` cree et alimente;
- `strategy_candidates` present dans le JSON;
- `strategy_selection` present dans le JSON;
- `strategy_shadow_integration` present dans le JSON;
- `monitoring_inspector.strategy_shadow` present dans le JSON;
- dashboard contient `Phase 7E · Integration controlee`;
- dashboard contient `Phase 7D · Multi-Strategy Inspector`.

Snapshot QA runtime:

- `reports/multi_strategy_history.jsonl`: 2 lignes au moment du controle;
- `reports/audit_log.jsonl`: 3733 lignes au moment du controle;
- dernier shadow status observe: `SHADOW_NO_SETUP`;
- `allowed_to_lock_trade`: `False`.

## Tests executes

```bash
python3 -m unittest discover tests
.venv/bin/python -m unittest discover tests
.venv/bin/python -m py_compile xauusd_agent.py tests/test_xauusd_agent.py
git diff --check
```

Resultats:

- Python systeme 3.9: 188 tests OK;
- Python venv 3.12: 188 tests OK;
- compilation Python: OK;
- whitespace/check diff: OK.

## Garde-fous confirmes

- Phase 7 ne change pas le chef de file;
- Phase 7 ne cree pas de trade lock;
- `allowed_to_affect_lead=False`;
- `allowed_to_lock_trade=False`;
- les conflits multi-strategy vs chef de file sont journalises uniquement;
- le multi-strategy reste en observation jusqu'a calibration Phase 7.5.

## Readiness Phase 7.5

Phase 7F autorise la suite vers Phase 7.5.

Preconditions satisfaites:

- historique multi-strategy disponible;
- audit log enrichi avec `strategy` et `strategy_shadow`;
- payload JSON serialisable;
- dashboard HTML rendu;
- tests systeme et venv OK;
- documentation Phase 7 et roadmap synchronisees.

Phase 7.5 doit maintenant calibrer les poids et seuils du coordinateur sur historique avant toute activation dans le chef de file ou le trade lock.
