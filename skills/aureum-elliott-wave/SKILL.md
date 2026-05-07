---
name: aureum-elliott-wave
description: Archive Elliott. Ne pas utiliser pour la v3.0 active sans validation utilisateur explicite.
category: technical
---

# Aureum Elliott Wave Archive

## Statut produit

Elliott est archive dans la roadmap v3.0 active.

Regles:

- Phase 27A doit retirer `ElliottWaveAgent` du dashboard, payload, Inspector, rapports et orchestrateur.
- Elliott ne doit plus etre utilise comme agent, preuve, contradiction ou raison de decision.
- Ce skill est conserve uniquement comme archive de recherche.
- Toute reintroduction d'Elliott exige une validation utilisateur explicite et une nouvelle phase de conception.

## Pourquoi l'archiver

Le moteur actuel regarde surtout des variations recentes et ne fait pas un vrai comptage de vagues.
Sans moteur robuste, Elliott donne une impression de precision trompeuse.

La v3.0 remplace cette logique par `TechnicalDecisionEngine`:
- structure de marche;
- indicateurs;
- niveaux;
- volatilite;
- confirmations inter-marches;
- trigger;
- invalidation.

## Archive theorique non active

Les elements ci-dessous ne sont pas a implementer dans la roadmap active. Ils restent uniquement comme notes historiques si le sujet Elliott est rouvert plus tard.

### Structures minimales a gerer

- impulsion 1-2-3-4-5;
- correction ABC;
- zigzag 5-3-5;
- flat 3-3-5;
- triangle A-B-C-D-E;
- W-X-Y;
- W-X-Y-X-Z;
- corrections combinatoires;
- sous-vagues internes.

### Regles Elliott

- Vague 2 ne retrace pas 100% de vague 1.
- Vague 3 ne peut pas etre la plus courte.
- Vague 4 ne doit pas chevaucher vague 1 sauf cas valide.
- Une vague C peut etre impulsive 1-2-3-4-5.
- Une correction complexe peut contenir W-X-Y ou W-X-Y-X-Z.
- Toujours fournir scenario alternatif si confiance moyenne.

### WaveScenario

Sortie attendue:

```text
timeframes_used
major_degree
minor_degree
primary_scenario
alternate_scenarios
current_wave
subwave
pattern_type
invalidation_price
confirmation_trigger
fib_targets
confidence
status
```

Statuts:
- `CLEAR_STRUCTURE`;
- `PROBABLE_STRUCTURE`;
- `UNCLEAR`;
- `INSUFFICIENT_HISTORY`;
- `CONFLICTING_TIMEFRAMES`.

### Exemple historique attendu

```text
Structure: fin possible de vague 2 de 3.
Confirmation: cassure du sommet de sous-vague 1 sur M15 avec impulsion H1.
Invalidation: retour sous le bas de vague 2.
Targets: 1.0 / 1.618 / 2.618 extension vague 1.
Statut: WATCH_BUY, pas TRADE_BUY tant que le declencheur n'est pas confirme.
```

## Ce qu'il ne faut pas faire

- Ne pas dire "vague 3 commence" sans confirmation.
- Ne pas compter Elliott sur une seule timeframe.
- Ne pas donner BUY/SELL si la structure est unclear.
- Ne pas cacher l'alternative.
- Ne pas remplacer le risk manager.

## Tests

- fixtures impulsion bullish;
- fixtures correction ABC;
- fixtures WXY;
- fixtures triangle;
- violation regle vague 2;
- wave 3 shortest invalid;
- insufficient history.

## Phase 23 Contract

### Role

Servir d'archive. Ne pas guider l'implementation active sans validation utilisateur explicite.

### Inputs

- decision utilisateur explicite de reouvrir Elliott;
- plan de conception approuve;
- fixtures de test robustes;
- Chart Store valide.

### Outputs

- note d'archive;
- risques;
- conditions de reactivation.

### Methodologie

1. Refuser toute utilisation Elliott par defaut.
2. Pointer vers `aureum-technical-decision`.
3. Si l'utilisateur demande Elliott, exiger une phase de conception separee.
4. Ne jamais reintroduire Elliott dans le scoring sans tests.

### Limites

- Ne pas scorer.
- Ne pas afficher dans le dashboard.
- Ne pas lister comme preuve.
- Ne pas l'utiliser dans l'orchestrateur.

### Bons exemples

- `Elliott archive: utiliser TechnicalDecisionEngine pour la decision v3.`

### Mauvais exemples

- `Vague 3 commence.`
- `Elliott confirme BUY.`
