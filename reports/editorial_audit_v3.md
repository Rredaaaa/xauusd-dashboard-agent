# Audit editorial Phase 20 - Aureum Flux Terminal v3.0

Date: 2026-05-02
Phase: 20 - Audit editorial phrase par phrase
Statut: livrable Phase 20

## 1. Methode

1. Generation du dashboard HTML local: `python3 xauusd_agent.py --dashboard reports/xauusd_dashboard.html`.
2. Extraction de toutes les phrases visibles via `scripts/extract_dashboard_text.py` (TSV: occurrence, vue, parent HTML, texte).
3. 975 phrases uniques extraites. Filtre sur les phrases >= 30 caracteres + recherche des patterns interdits listes dans `docs/AUREUM_FLUX_TERMINAL_V3_PLAN.md`.
4. Recoupement avec `xauusd_agent.py` pour identifier les fonctions sources et la liste des composants a modifier en Phase 21.
5. Aucune modification moteur. Phase 20 produit uniquement des constats et des propositions.

Sortie d'extraction non commitee (volumineuse):  
`/.claude/work/dashboard_phrases.tsv` (975 lignes).

## 2. Conventions de notation

Priorite:
- P0: phrase interdite explicite, danger d'incomprehension trader.
- P1: phrase vague repetee plusieurs fois, perd la valeur du signal.
- P2: phrase technique correcte mais qui devrait basculer dans Inspector.
- P3: phrase repetitive sans valeur, peut etre supprimee.

Vue: la vue d'origine n'est pas systematiquement exposee par le HTML (les blocs de synthese sont rendus a plat). Les vues citees ci-dessous sont identifiees par recoupement avec la fonction Python source.

## 3. Phrases interdites (P0)

Phrases qui correspondent au dictionnaire interdit de Phase 21.

| # | Texte actuel | Probleme | Texte propose | Vue | Source | Priorite |
|---|---|---|---|---|---|---|
| I1 | "Le theme Iran/Hormuz existe, mais le petrole ne confirme pas un choc. La prime de risque peut sortir de gold si oil et volatilite se detendent." | "le theme existe" + "ne confirme pas un choc" sans nommer ce qui confirmerait | "Plusieurs titres mentionnent Iran/Hormuz, mais WTI {wti_var:+.2f}% et Brent {brent_var:+.2f}% reculent. Le marche ne price pas encore un choc petrole. Impact XAU/USD: pas de confirmation refuge. Action: attendre un repricing oil/DXY avant de valider un trade." | Dashboard / Geopolitics | xauusd_agent.py:4099 build_market_regime_analysis | P0 |
| I2 | "Les correlations ne confirment pas assez le BUY gold: prudence ou attente d'une meilleure confluence." | "prudence" + "ne confirment pas" sans expliquer ce qui confirmerait, ni quels actifs vs quels actifs | "Cross-assets contradictoires: DXY {dxy_var:+.2f}% (devrait baisser), GDX {gdx_var:+.2f}% (devrait monter). Confluence BUY incomplete. Action: attendre soit DXY < {dxy_threshold} soit GDX > {gdx_threshold} pour valider la direction." | Decision | xauusd_agent.py:3938 build_cross_asset_analysis | P0 |
| I3 | "Le fondamental reste favorable a l'or [...] Le risque geopolitique reste actif, donc la demande de couverture sur l'or ne disparait pas. Le message des banques centrales reste partage [...]" | "reste favorable", "risque geopolitique reste actif", "reste partage" - 3 phrases interdites concentrees | Reformuler en triplet fait+source+chaine: "Taux reels {dfii10:+.2f}% et DXY {dxy:.2f} (-X%): contexte taux/dollar negatif pour le dollar, positif pour l'or. Hormuz: {n_titles} titres relayes par {sources}. Fed: {fed_event} prevu {fed_date}. Action: {watch_or_trade}." | Dashboard / Decision | xauusd_agent.py:3412, 3425 build_executive_summary | P0 |
| I4 | "Le risque geopolitique reste actif. Cela soutient la demande de couverture sur l'or [...]" | meme formulation interdite repetee dans un autre composant | meme reformulation que I3 mais cible la zone "What happens now" | Dashboard | xauusd_agent.py:8414 build_what_happens_now_lines | P0 |
| I5 | "Plus d'incertitude geopolitique soutient en general la demande de couverture sur l'or." | "en general" - generalite sans fait, sans source, sans chaine marche | "Headline {source}: {fact}. Chaine marche: aversion -> bid sur dollar et or refuge. Confirmation requise: VIX > {vix_th} ou TIP > {tip_th}." | Geopolitics | xauusd_agent.py:5455 explain_headline_gold_impact | P0 |
| I6 | "Le conflit brouille les reperes habituels de marche et augmente l'aversion au risque." | "brouille les reperes" - formule generique non actionnable | "Conflit {acteurs}: aversion mesurable via VIX {vix:.1f} ({vix_var:+.1f}%) et flight-to-quality TIP {tip:+.2f}%. Si confirme, biais refuge gold; sinon prudence sur correlation." | Geopolitics | xauusd_agent.py:5415 explain_headline_reason | P0 |
| I7 | "Mode event actif: prudence renforcee sur les entrees gold." | "prudence" sans definir l'event ni le seuil | "Mode event actif (score {score}/100): {event_name}. Seuil de declenchement {threshold}. Reduction de l'exposition recommandee tant que VIX > {vix_high}." | Dashboard | xauusd_agent.py:4076 build_market_regime_analysis | P0 |
| I8 | "Le choc petrole soutient le theme refuge et inflation pour l'or, mais il peut aussi repousser les baisses de taux de la Fed." | "le theme" - formule interdite. Ambiguite: refuge ET inflation ET taux | "Choc petrole: WTI {wti:+.2f}%, Brent {brent:+.2f}%. Effet inflation possible -> Fed plus longue -> taux reels en hausse -> negatif court terme pour l'or. Effet refuge possible -> bid gold. Ces deux effets se neutralisent. Action: regarder DFII10 pour trancher." | Geopolitics | recherche `Le choc petrole soutient` | P0 |

## 4. Phrases vagues (P1)

Phrases techniquement correctes mais qui n'ajoutent rien au signal.

| # | Texte actuel | Probleme | Texte propose | Vue | Source | Priorite |
|---|---|---|---|---|---|---|
| V1 | "Lecture fondamentale intraday positive: dollar et taux se detendent, avec un flux d'actualites qui ne contredit pas la hausse." | "qui ne contredit pas la hausse" - double negatif vague | "Fundamentaux intraday positifs gold: DXY {dxy_var:+.2f}%, DGS10 {dgs10_var:+.2f} bps, DFII10 {dfii10_var:+.2f} bps. News flow {news_score}/100 sans contradiction majeure." | Dashboard | xauusd_agent.py:3187 build_fundamental_recommendation | P1 |
| V2 | "Structure technique intraday fragile: le poids des timeframes superieurs garde un risque vendeur dominant. Attention: regime volatil, ne pas chasser le mouvement." | "fragile" + "risque vendeur dominant" sans niveau, sans EMA, sans pivot | "Structure SELL: prix sous EMA50 {ema50:.2f} et EMA200 {ema200:.2f} sur H1+H4. Resistance majeure {res:.2f}. Pivot bear si cassure {pivot:.2f}. Volatilite ATR M15 {atr_m15:.2f} ({atr_var:+.0f}%)." | Technical / Dashboard | xauusd_agent.py:3260 build_technical_recommendation | P1 |
| V3 | "Biais court terme: legerement haussier, avec besoin d'une confirmation par les news macro et le comportement du DXY." | "legerement haussier" + "besoin de confirmation" sans seuil | "Biais court terme: BUY conditionnel. Declencheur: cassure {trigger:.2f} M15 + DXY < {dxy_th}. Invalidation: retour sous {invalid:.2f}. WATCH_BUY tant que ces conditions ne sont pas remplies." | Dashboard / Decision | xauusd_agent.py:5951 heuristic_decision_sentence (5 variantes lignes 5951-5958) | P1 |
| V4 | "Controle passif du risque: verifie regime, contradictions, SL/TP et prudence execution." | resume vide qui ne dit rien sur l'etat actuel | "RiskManager: regime {regime}, {n_contradictions} contradictions agents, R/R potentiel {rr:.1f}, qualite source {dq_label}. Bloquant: {blockers_or_none}." | Inspector / Dashboard | xauusd_agent.py:4588 build_risk_manager_agent | P1 |
| V5 | "haussier possible si le marche cherche du cash dollar." / "haussier si sanctions, menaces ou risque maritime augmentent." / "mixte: soutien refuge possible, mais pression possible si oil/USD captent la liquidite." | conditionnels generiques sans seuil ni horizon | Reecrire chacun en {fact} {chaine_marche} {seuil_confirmation} {horizon}. Exemple: "Sanctions Iran -> WTI > {wti_th}/baril -> CPI breakeven > {tipie_th}% -> bid refuge gold sur 1-3 jours." | Geopolitics | xauusd_agent.py:5699-5701, 5729 political_impacts | P1 |

## 5. Elliott - phrases qui doivent etre desactivees du discours principal (P0)

L'Orchestrateur v2 garde Elliott dans le scoring sans Chart Store OHLC. Phase 26 sortira Elliott du scoring; Phase 21 doit deja eviter de produire ces phrases dans les blocs principaux et les rerouter vers Inspector avec un badge "experimental".

| # | Texte actuel | Probleme | Texte propose | Source | Priorite |
|---|---|---|---|---|---|
| E1 | "Lecture Elliott passive: le prix garde une sequence motive haussiere tant que le dernier repli reste contenu." | parle d'une "sequence motive" sans Chart Store | Inspector uniquement: "Elliott (experimental, non scorant): hypothese impulsion haussiere. Aucun Chart Store OHLC disponible. Conclusion non fiable." | xauusd_agent.py:4203 build_elliott_wave_agent | P0 |
| E2 | "Lecture Elliott passive: le prix garde une sequence motive baissiere tant que le rebond court reste limite." | idem | Inspector uniquement, hypothese baissiere | xauusd_agent.py:4208 | P0 |
| E3 | "Lecture Elliott passive: la structure ressemble davantage a une correction qu'a une impulsion propre." | "ressemble davantage" sans methode | Inspector: "Elliott (experimental): hypothese corrective. Aucune confirmation pivot/Fibo possible sans OHLC v3." | xauusd_agent.py:4213 | P0 |
| E4 | "Lecture Elliott passive indisponible: pas assez de points pour compter les swings." | OK sur le fond mais doit aller dans Inspector avec badge | Inspector: "Elliott (experimental): historique insuffisant. Statut: non scorant." | xauusd_agent.py:4181 | P1 |

Note: la mise en quarantaine reelle du scoring est Phase 26. Phase 21 doit reformuler le texte affichable principal et router le reste vers Inspector.

## 6. Phrases repetees inutilement (P3)

Phrases courtes, sans valeur ajoutee, qui occupent de l'espace UI.

| # | Texte actuel | Probleme | Action | Source |
|---|---|---|---|---|
| R1 | "Themes:" (6 occurrences en `<strong>`) | label sans contenu attache | supprimer le label si pas de fait associe | template HTML |
| R2 | "Decision & prudence" (titre) | "prudence" en titre est interdit | renommer "Decision & validation" | template HTML |
| R3 | "Mode event et prudence SL" (h2) | "prudence" en titre | renommer "Mode event et risque execution" | template HTML |
| R4 | "Cross-assets: SELL 41/100 - Les correlations ne confirment pas assez..." | doublon de I2 | supprimer la duplication, garder une seule source de verite | template HTML + xauusd_agent.py:3938 |

## 7. Liste des composants Python a modifier en Phase 21

Liste indicative. La Phase 21 (Explanation Layer) devra centraliser les regles, donc certaines de ces fonctions deviendront fines: elles construiront des `ExplanationContext` et delegueront le rendu textuel.

| Fonction | Fichier:ligne | Phrases concernees |
|---|---|---|
| `build_fundamental_recommendation` | xauusd_agent.py:3081 | I3 (partiel), V1 |
| `build_technical_recommendation` | xauusd_agent.py:3205 | V2 |
| `build_executive_summary` | xauusd_agent.py:3400 | I3 (principal) |
| `build_cross_asset_analysis` | xauusd_agent.py:3842 | I2 |
| `build_market_regime_analysis` | xauusd_agent.py:4031 | I1, I7 |
| `build_elliott_wave_agent` | xauusd_agent.py:4171 | E1, E2, E3, E4 |
| `build_risk_manager_agent` | xauusd_agent.py:4540 | V4 |
| `explain_headline_reason` | xauusd_agent.py:5407 | I6 |
| `explain_headline_gold_impact` | xauusd_agent.py:5441 | I5 |
| `political_impacts` | xauusd_agent.py:5688 | V5 (lignes 5699-5701, 5729) |
| `heuristic_decision_sentence` | xauusd_agent.py:5949 | V3 (5 variantes 5951-5958) |
| `build_what_happens_now_lines` | xauusd_agent.py:8380 | I4 |
| Templates HTML (rendu dashboard) | xauusd_agent.py rendu HTML | R1, R2, R3, R4 |

## 8. Dictionnaire des phrases interdites (Phase 21)

A integrer dans `ExplanationLayer` comme verifications automatiques. Si une phrase finale matche un de ces patterns, l'engine doit refuser de la rendre et reclamer un fait + source + chaine + impact + action.

Patterns interdits:
- `le theme [^.]+ existe`
- `ne confirme pas` sans suite "ce qui confirmerait serait"
- `flux mitiges?`
- `contexte (favorable|defavorable)` sans preuve chiffree
- `prudence` (sauf dans Inspector ou en label de mode)
- `risque .* reste actif`
- `reste favorable`
- `reste partage`
- `legerement (haussier|baissier)` sans seuil de declenchement
- `ressemble davantage`
- `en general` (formules generiques)
- `besoin d.une confirmation` sans nommer la confirmation
- `brouille les reperes`
- `controle passif`

Verbes a privilegier: nommer le fait, citer le chiffre, dire la chaine marche, donner le seuil, donner l'action.

## 9. Structure cible d'une phrase (rappel V3 PLAN)

Toute phrase principale doit repondre a:
1. Qu'est-ce qui se passe ? (fait + chiffre + source)
2. Pourquoi c'est important ? (chaine de transmission)
3. Qu'est-ce qui confirme ou contredit ? (seuils explicites)
4. Impact XAU/USD ?
5. Action: BUY, SELL, WATCH_BUY, WATCH_SELL, NO_TRADE, WAIT.

Cette structure est portee par la couche `ExplanationLayer` a livrer en Phase 21.

## 10. Conclusion

Phase 20 livre:
- 975 phrases extraites du dashboard rendu;
- 8 phrases interdites P0 identifiees avec source code precise;
- 5 patterns vagues P1 a reformuler;
- 4 phrases Elliott P0 a router vers Inspector avec badge experimental;
- 4 phrases repetitives P3 a supprimer ou renommer;
- 13 fonctions Python listees comme cibles de Phase 21;
- 14 patterns interdits a integrer dans le dictionnaire de l'ExplanationLayer.

Aucun changement moteur. Aucune modification de scoring, agent, source ou Trade Ledger. Phase 20 reste un audit.
