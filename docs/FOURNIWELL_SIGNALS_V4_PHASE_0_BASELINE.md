# Fourniwell Signals v4.0 - Phase 0 baseline

Date: 2026-05-13  
Phase: 0 - Rebranding et base propre  
Statut: terminee cote documentation / prete pour validation utilisateur

## Objectif

Lancer officiellement la v4.0 sous le nom Fourniwell Signals, nettoyer l'etat de travail et documenter la base avant toute correction moteur.

## Actions realisees

- Creation de la roadmap officielle v4.0:
  - `docs/FOURNIWELL_SIGNALS_V4_ROADMAP.md`
- Creation de la checklist exhaustive d'application du rapport:
  - `docs/V4_INSPECTION_ACTION_CHECKLIST.md`
- Creation du present baseline Phase 0.
- Rebranding documentaire principal:
  - `README.md`
  - `docs/SETUP.md`
  - `docs/USER_GUIDE.md`
  - `docs/SOURCES_AND_SCORING.md`
- Ajout de `.DS_Store` dans `.gitignore`.
- Suppression des fichiers `.DS_Store` locaux generes par macOS.
- Isolation du patch code non valide qui etait reste en attente dans `xauusd_agent.py`.

## Etat Git observe au lancement

Avant nettoyage Phase 0:

```text
 M xauusd_agent.py
?? .DS_Store
?? docs/FOURNIWELL_SIGNALS_V4_ROADMAP.md
?? docs/V4_INSPECTION_ACTION_CHECKLIST.md
```

Le changement `xauusd_agent.py` etait un patch news non valide issu d'une tentative precedente. Il n'appartient pas a Phase 0 et ne doit pas etre melange au rebranding.

## Decision Phase 0

- Ne pas integrer le patch code news dans cette phase.
- Conserver Phase 0 comme phase documentation / hygiene.
- Reporter toute correction moteur a Phase 1 ou suivantes.

## Documents v3

Les documents v3 restent dans le depot comme historique de conception. Ils ne sont plus la roadmap active.

Roadmap active:

```text
docs/FOURNIWELL_SIGNALS_V4_ROADMAP.md
```

Checklist active:

```text
docs/V4_INSPECTION_ACTION_CHECKLIST.md
```

## Prochaine phase officielle

Phase 1 - Stopper les mauvais trades.

Objectif Phase 1:

- durcir les settings;
- bloquer les trades faibles;
- retirer les agents qui polluent;
- empecher les trade locks a R/R insuffisant;
- installer les premiers garde-fous du rapport.
