# Aureum Flux Skills - Index assistant

Ce dossier sert de base de reprise pour tout assistant qui doit continuer Aureum Flux Terminal sans reconstituer plusieurs jours de contexte.

Ordre de lecture recommande:

1. `aureum-project-context/SKILL.md`
2. `aureum-editorial-style/SKILL.md`
3. `aureum-news-engine/SKILL.md`
4. `aureum-chart-store/SKILL.md`
5. `aureum-technical-decision/SKILL.md`
6. `aureum-data-preflight/SKILL.md`
7. `aureum-gold-macro/SKILL.md`
8. `aureum-geopolitical-oil/SKILL.md`
9. `aureum-risk-manager/SKILL.md`
10. `aureum-scenario-orchestrator/SKILL.md`
11. `aureum-trade-quality-gate/SKILL.md`
12. `aureum-replay-shadow-terminal/SKILL.md`

Documents de reference a lire avant implementation:

- `docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md`
- `docs/SOURCES_AND_SCORING.md`
- `docs/ARCHITECTURE.md`
- `docs/USER_GUIDE.md`
- `docs/V3_QA_CHECKLIST.md`

Regle de reprise:

> Aureum Flux v3.0 est livree localement jusqu'a la Phase 34. Toute reprise doit commencer par verifier Git, relire la checklist QA et comprendre les 5 pages actives.

Decision v3.0 active:

- ne pas commencer par Elliott;
- Phase 27A a retire Elliott du dashboard, payload public, Inspector et orchestrateur;
- Phase 27A a remplace la charte interne principale par TradingView;
- Phase 27B a cree `TechnicalDecisionEngine` v1;
- Phases 30-34 ont livre Trade Tracker, Replay, Settings, Reports v3 et QA finale;
- le skill Elliott archive a ete supprime du repo: il ne doit plus guider l'implementation.
