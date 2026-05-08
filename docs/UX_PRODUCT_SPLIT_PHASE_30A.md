# Phase 30A - UX Product Split + Noise Gate

Statut: a valider avant implementation.

Skill UX installe:
- `ui-ux-pro-max`
- source: `https://github.com/nextlevelbuilder/ui-ux-pro-max-skill`
- installation locale Codex: `/Users/reda/.codex/skills/ui-ux-pro-max`

Important:
- redemarrer Codex pour que le nouveau skill soit automatiquement disponible dans les prochaines sessions;
- Claude/Codex doivent appliquer ce skill comme garde-fou UX avant de modifier l'interface.

## Objectif

Transformer Aureum Flux Terminal en outil trader clair, sans exposer la plomberie interne du moteur.

Le moteur peut garder les details complexes pour calculer, auditer et debugger. L'utilisateur final ne doit voir que ce qui aide a prendre une decision.

## Nouvelle structure produit

### Page 1 - Desk

Role: decision immediate.

Afficher uniquement:
- prix XAU/USD live;
- position du chef de file;
- biais global;
- charte TradingView;
- signal locked;
- statut du trade: aucun trade, setup surveille ou trade exploitable;
- SL/TP seulement si le trade est valide et coherent;
- alerte courte si une information recente change la lecture.

Interdit:
- chaines marche;
- details de source;
- phrases d'audit agent;
- termes internes de regime;
- news neutres;
- news anciennes;
- tableaux lourds.

### Page 2 - Agents

Role: controle du scoring.

Afficher:
- score global;
- decision de l'orchestrateur;
- position de chaque agent;
- poids de chaque agent;
- agents bullish, bearish, neutral;
- contradictions utiles;
- raison courte du statut final.

Interdit:
- longues explications narratives;
- titres news complets non relies au scoring;
- details de scraping.

### Page 3 - News Flow

Role: flux d'information exploitable.

Afficher:
- flash infos recentes;
- politique;
- macro;
- geopolitique;
- petrole/dollar;
- source;
- heure de publication;
- impact `BULLISH`, `BEARISH` ou `NEUTRAL`;
- une phrase d'impact maximum si l'information est importante.

Regles:
- trier d'abord par date/heure de publication;
- masquer les news `NEUTRAL` par defaut;
- masquer les news anciennes sans impact immediat;
- de-dupliquer les titres similaires;
- separer flash info, analyse longue et contexte archive;
- ne pas afficher les chaines marche dans la vue principale.

### Page 4 - Reports

Role: memoire et suivi.

Afficher:
- trades locked;
- trades actifs;
- trades expires;
- trades invalides;
- historique de decisions;
- rapports Markdown/JSON;
- performance et post-mortem quand disponible.

### Page 5 - Inspector

Role: moteur, debug et audit.

Afficher ici seulement:
- Source Registry;
- Data Quality;
- Preflight;
- routes internes;
- chaines marche;
- validations internes;
- payload agents;
- logs;
- audit;
- donnees stale ou faibles;
- details qui ne servent pas directement a l'utilisateur final.

Si le moteur peut travailler avec une information sans l'afficher, ne pas l'afficher hors Inspector.

## Noise Gate global

Toutes les surfaces hors Inspector doivent bloquer:
- termes internes du type `Hormuz/Oil Shock`;
- phrases abstraites du type `change la transmission`;
- `chaine marche`;
- `anti-rumeur`;
- `validation interne`;
- `fait structure detecte`;
- paragraphes longs;
- informations anciennes sans impact actuel;
- sources faibles non confirmees;
- news neutres dans le flux principal.

Les noms internes peuvent rester dans le code et le payload technique, mais doivent etre traduits dans l'UI utilisateur.

Exemple:
- interne: `political_oil_dollar_stress`;
- UI: `Stress politique petrole/dollar`.

## News Gate

Une information visible dans News Flow doit avoir:
- titre;
- source;
- timestamp;
- impact directionnel;
- score de fraicheur;
- statut de confirmation;
- lien si disponible.

Elle est cachee par defaut si:
- impact `NEUTRAL`;
- timestamp absent;
- source trop ancienne;
- source faible sans confirmation;
- contenu redondant;
- analyse longue sans impact immediat.

## SL/TP Gate

Ne jamais afficher un plan de trade comme exploitable si les niveaux sont incoherents.

Pour `BUY`:
- `SL < entry <= TP1 < TP2 < TP3`.

Pour `SELL`:
- `SL > entry >= TP1 > TP2 > TP3`.

Si le signal est `WATCH_BUY`, `WATCH_SELL`, `WAIT` ou `NO_TRADE`:
- afficher une zone surveillee ou un trigger;
- ne pas presenter SL/TP comme une position conseillee;
- afficher `trade non verrouille` si necessaire.

Si les niveaux echouent au gate:
- bloquer l'affichage trade;
- envoyer le detail dans Inspector;
- afficher une phrase courte: `Niveaux invalides, trade bloque`.

## Definition de termine

Phase 30A est terminee quand:
- les 5 pages existent;
- Desk ne montre que le prix, le chef de file, le biais, TradingView et le signal locked;
- Agents montre le scoring sans bruit news;
- News Flow montre uniquement les infos recentes utiles;
- Reports contient historique et exports;
- Inspector contient toute la plomberie;
- aucun terme interne interdit n'apparait hors Inspector;
- les niveaux SL/TP incoherents ne peuvent plus apparaitre comme trade exploitable;
- screenshots desktop et mobile valident la lisibilite.

