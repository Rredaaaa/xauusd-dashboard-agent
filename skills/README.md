# Aureum Flux Skills - Index Claude

Ce dossier sert de base de reprise pour Claude et tout autre assistant qui doit continuer Aureum Flux Terminal sans reconstituer plusieurs jours de contexte.

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
13. `aureum-elliott-wave/SKILL.md` archive, a ne pas utiliser sans validation explicite.

Documents de reference a lire avant implementation:

- `docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md`
- `docs/AUREUM_FLUX_TERMINAL_V2_PLAN.md`
- `docs/UI_REDESIGN_PHASE_18.md`
- `docs/SOURCES_AND_SCORING.md`
- `docs/ARCHITECTURE.md`
- `docs/USER_GUIDE.md`

Regle de reprise:

> Aureum Flux v2.0 est stabilise apres Phase 18. La v3.0 commence par Phase 19: audit documentation, puis Phase 20: audit editorial phrase par phrase.

Decision v3.0 active:

- ne pas commencer par Elliott;
- Phase 27A retire Elliott du dashboard, payload, Inspector, rapports et orchestrateur;
- Phase 27A remplace la charte interne principale par TradingView;
- Phase 27B cree `TechnicalDecisionEngine`;
- `aureum-elliott-wave` est archive et ne doit pas guider l'implementation sans validation utilisateur explicite.
