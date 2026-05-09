# Aureum Flux Terminal v3.0 QA Checklist

Date de validation: 2026-05-09

## Statut

v3.0 livree localement.

## Checklist

- [x] Compilation Python: `python3 -m py_compile xauusd_agent.py explanation_layer.py news_facts.py`
- [x] Tests unitaires: `python3 -m unittest discover -s tests`
- [x] Dashboard local charge sur `http://127.0.0.1:8787/`
- [x] Navigation active: `Desk`, `Agents`, `News Flow`, `Reports`, `Inspector`
- [x] Anciennes vues `Market`, `Technical`, `Macro` retirees du produit actif
- [x] Elliott retire du code actif, du payload public et du dashboard
- [x] TradingView present comme charte utilisateur principale
- [x] Trade Tracker v3: stats, outcomes, post-mortem et ledger append-only
- [x] Replay v3: commande `--replay`
- [x] Settings v3: commande `--init-settings`
- [x] Reports v3: exports dans `reports/v3/`
- [x] Docs mises a jour: README, SETUP, USER_GUIDE, ARCHITECTURE, SOURCES_AND_SCORING, PLAN v3

## Commandes utiles

```bash
python3 -m py_compile xauusd_agent.py explanation_layer.py news_facts.py
python3 -m unittest discover -s tests
python xauusd_agent.py --init-settings
python xauusd_agent.py --replay --replay-output reports/v3/replay_report.md
```

## Risques restants

- Les sources web gratuites peuvent etre absentes ou stale.
- Les exports `reports/` sont locaux et non versionnes.
- Le dashboard reste local-first; hebergement distant necessitera une phase de securisation.
- Les notifications de TradePlan exploitable restent une extension future.
