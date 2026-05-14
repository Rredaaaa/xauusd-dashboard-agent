# Fourniwell Signals v4.0 - Checklist d'application du rapport d'inspection

Version: 1.0
Date: 2026-05-13
Source: `aureum_flux_v3_inspection_report_2026-05-12.md`

Objectif: transformer toutes les recommandations du rapport en taches suivables.

Statuts autorises:

- `[ ]` a faire
- `[~]` en cours
- `[x]` fait
- `[!]` bloque / decision requise

## 0. Hygiene projet

- [x] Verifier `git status` avant chaque phase.
- [x] Identifier les modifications non commitees existantes dans `xauusd_agent.py`.
- [x] Decider quoi faire du fichier `.DS_Store`.
- [ ] Ne pas melanger corrections moteur et changements UI dans le meme commit.
- [x] Creer un commit dedie par phase.
- [x] Mettre a jour la documentation apres chaque phase.

## 1. Settings critiques

- [x] Passer `minimum_risk_reward` de `0.65` a `1.5`.
- [x] Passer `trade_threshold` de `55` a `65`.
- [x] Passer `minimum_agent_confidence` de `50` a `65`.
- [x] Passer `scoring_mode` de `aggressive_controlled` a `balanced` ou `conservative`.
- [x] Ajouter `cooldown_after_loss_minutes = 240`.
- [x] Ajouter `cooldown_after_win_minutes = 60`.
- [x] Ajouter `max_trades_per_24h`.
- [x] Ajouter `circuit_breaker_after_n_losses`.
- [x] Ajouter `circuit_breaker_window_hours`.
- [x] Ajouter `circuit_breaker_pause_hours`.
- [x] Ajouter `min_data_quality = 60`.
- [x] Ajouter `no_trade_window_minutes_before_high_macro = 30`.
- [x] Ajouter `no_trade_window_minutes_after_high_macro = 15`.
- [ ] Garder `live_refresh_seconds = 10`.
- [ ] Garder `full_refresh_seconds = 60`.

## 2. PriceAgent -> PriceActionAgent

- [x] Renommer ou remplacer PriceAgent par PriceActionAgent.
- [x] Calculer pivots Camarilla H1/H4/D1.
- [x] Detecter swing high/low M15.
- [x] Calculer position dans range journaliere.
- [x] Calculer distance au niveau psychologique le plus proche.
- [x] Classer etat prix: breakout / pullback / range / consolidation / reversal.
- [x] Rendre le score dependant de ces niveaux.
- [x] Rendre confidence dynamique selon disponibilite des donnees.
- [x] Afficher 4-6 niveaux cles chiffres.
- [ ] Si refonte impossible temporairement: mettre poids a 0.

## 3. TechnicalAgent

- [x] Plafonner confidence a `85/100`.
- [ ] Calibrer poids multi-timeframe sur backtest.
- [x] Exiger trigger reel avant conversion WATCH -> TRADE.
- [x] Verifier cloture M15 au-dessus/sous trigger.
- [ ] Adapter SL/TP selon structure: trend, range, breakout, reversal.
- [x] Baisser confidence en cas de contradiction intra-timeframe.
- [x] Documenter structure technique dans payload.
- [ ] Migrer vers vraies bougies XAU/USD spot quand Chart Store v3 est fiable.

## 4. MacroAgent

- [x] Inclure fraicheur effective FRED dans confidence.
- [x] Ponderer DGS10, DXY, DFII10, T10YIE.
- [ ] Ajouter macro surprise: reel - consensus.
- [x] Ajouter veto HIGH-impact dans les 30 min.
- [ ] Exposer trajectoire sur 3 dernieres publications.
- [x] Ajouter DGS3M.
- [x] Ajouter 30Y.
- [ ] Conserver architecture actuelle, car agent globalement fonctionnel.

## 5. GeopoliticalOilShockAgent

- [x] Rendre bias directionnel selon regime.
- [x] Mapper `Hormuz / Oil Shock` vers SELL.
- [x] Mapper `Safe-Haven Gold` vers BUY.
- [x] Mapper `De-escalation / Oil Relief` vers SELL.
- [x] Mapper `Dollar Liquidity Squeeze` vers SELL.
- [x] Mapper `Normal Macro` vers NEUTRAL.
- [x] Mesurer tendance regime: escalade / accalmie / stable.
- [x] Documenter score brut par composant.
- [x] Rendre confidence dynamique selon WTI/Brent/headlines.
- [ ] Ajouter cooldown de changement de regime sur 4h.
- [x] Elever seuil Hormuz a 70.
- [x] Ajouter regime Risk-On / Carry Trade.

## 6. SentimentNewsAgent

- [x] Desactiver scoring si sources tier > 2.
- [x] Desactiver scoring si age median news > 60 min.
- [x] Mettre score a 50 et confidence a 0 si news faibles.
- [x] Ponderer par tier source.
- [x] Ponderer par fraicheur.
- [ ] Remplacer keyword scoring par tone analysis.
- [ ] Distinguer breaking news vs opinion.
- [x] Opinion analyste -> score neutre.
- [x] No fresh news -> bias NEUTRAL, confidence 0.
- [x] Evidence: top 3 titres avec source, age, sentiment chiffre.

## 7. CorrelationAgent

- [x] Hierarchiser confirmations et contradictions.
- [x] Afficher verdict net: nombre BUY vs SELL.
- [ ] Calculer correlation glissante 30j.
- [ ] Abaisser poids si cassure de correlation.
- [ ] Adapter poids selon regime.
- [ ] Detecter correlation breakdown.
- [x] Rendre confidence dynamique selon nombre actifs disponibles.
- [ ] Garder le reste de l'agent.

## 8. FlowPositioningAgent

- [x] Ajouter percentile Managed Money 1 an.
- [x] Ajouter percentile Managed Money 5 ans.
- [x] Ajouter logique contrarienne si extremes.
- [x] Detecter divergence COT vs ETF.
- [ ] Agreger GLD + IAU + SLV.
- [ ] Ponderer CFTC 0.6 et ETF 0.4.
- [x] Ajouter Producers/Merchants.
- [ ] Garder architecture source tier 1.

## 9. EventFactsAgent

- [x] Remplacer score quantitatif `45 + n_facts * 6`.
- [x] Filtrer `qualified_facts`: tier <= 2 et confidence >= 60.
- [x] Si aucun fait qualifie: score 45, bias NEUTRAL.
- [x] Si faits qualifies: score moyen pondere par confidence.
- [x] Choisir bias par vote directionnel.
- [x] Choisir primary_fact par meilleur tier + confidence.
- [x] Ponderer par market_confirmation.confirmation_score.
- [x] Filtrer opinion et rumeur du score.
- [x] Evidence: top 3 facts avec tier, confirmation_score, age.
- [x] Confidence: moyenne ponderee des faits qualifies.

## 10. TrumpPoliticalStatementsAgent

- [x] Rendre bias directionnel selon contenu.
- [x] Iran/Hormuz menacant -> SELL.
- [x] Fed pressure dovish -> BUY.
- [x] Tariffs/trade war -> SELL.
- [x] Ponderer par recence.
- [ ] Mesurer convergence de statements sur 24h.
- [x] Distinguer action signee vs menace verbale.
- [ ] Garder validation source et evidence.

## 11. RiskManagerAgent

- [x] Recrire completement le role.
- [x] Calculer R/R potentiel actuel.
- [x] Calculer risque par trade recommande.
- [x] Calculer drawdown recent / attendu.
- [x] Calculer exposition cumulee.
- [x] Lire `reports/trade_ledger.jsonl`.
- [x] Detecter circuit breaker actif.
- [x] Score: 100 setup propre, 50 risque normal, 0 ne pas trader.
- [x] Bias BLOCK si circuit breaker actif.
- [x] Bias CAUTION si exposition trop forte.
- [x] Bias OK sinon.
- [x] Evidence: R/R, taille, drawdown, exposition, circuit breaker.
- [x] Confidence selon disponibilite historique.

## 12. OrchestratorAgent legacy

- [x] Supprimer OrchestratorAgent legacy.
- [x] Conserver uniquement OrchestratorDecision v3.
- [x] Nettoyer mentions "ancien moteur".
- [x] Corriger duplication `RISK [high] Gate:`.
- [x] Mettre a jour tests qui reference OrchestratorAgent.
- [x] Verifier que les contradictions ne comptent plus cet agent legacy.

## 13. TradeQualityGate

- [x] `min_rr` minimum a 1.5.
- [x] Validating agents minimum a 3.
- [x] Supprimer bypass aggressive majority.
- [x] Hard block regime fort si score >= 70.
- [x] Hard block direction contraire au regime.
- [x] Hard block catalyseur high impact dans 30 min.
- [x] Hard block apres >=3 losses dans 24h.
- [x] Hard block data quality < 60.
- [x] Ecrire raisons de blocage dans payload.

## 14. TradeLevels

- [ ] Remplacer niveaux purement mecaniques ATR.
- [ ] Utiliser swing high/low.
- [ ] Utiliser pivots.
- [ ] Utiliser range.
- [ ] Utiliser breakout/retest.
- [ ] Utiliser niveaux psychologiques.
- [ ] Adapter SL/TP a la strategie.
- [ ] Verifier R/R final.
- [ ] Refuser si R/R < 1.5.
- [ ] Ajouter tests BUY/SELL: SL et TP doivent etre dans le bon sens.

## 15. OrchestratorDecision v3

- [ ] Permettre poids 0 pour agents defaillants.
- [ ] Recalibrer poids contextuels.
- [ ] Ajouter backtest des poids.
- [ ] Hard block si agents fiables en desaccord critique.
- [ ] Cap aucun agent > 0.30.
- [ ] Cap aucun agent < 0.05 sauf desactivation totale.
- [ ] Logger contributions par agent.
- [ ] Rendre decision auditable dans Reports/Inspector.

## 16. News Flow v4

- [x] Ajouter feed White House.
- [x] Ajouter feed Fed press all.
- [x] Ajouter feed Fed monetary.
- [x] Ajouter feed BLS news release.
- [x] Ajouter feed Treasury press releases.
- [x] Ajouter feed BEA.
- [x] Ajouter feed CFTC press releases.
- [x] Ajouter feed WGC.
- [x] Ajouter AP business si accessible.
- [x] Ajouter AP top news si accessible.
- [x] Ajouter CNBC RSS.
- [x] Ajouter Reuters si flux accessible.
- [x] Ajouter Bloomberg si flux accessible.
- [ ] Polling canal critique 20-30s.
- [x] Rejeter sources tier 4 en amont.
- [x] Rejeter forecasts/predictions/outlook.
- [x] Rejeter vieux articles.
- [x] Rejeter analysis today sans fait nouveau.
- [x] Detecter breaking par hash de feed.
- [x] Trier par heure reelle de publication.
- [x] Masquer news neutres par defaut.
- [x] Afficher "aucune news exploitable" si rien de fiable.

## 17. News Facts Engine

- [x] Elever dedup Jaccard a 0.65.
- [x] Ajouter dedup prefixe commun.
- [ ] Ameliorer `build_why_it_matters`.
- [ ] Utiliser actors et locations detectes.
- [ ] Recalibrer `build_trader_action`.
- [ ] Score 4/4 + tier <=2 -> WATCH/TRADE direct selon confirmation.
- [ ] Score 2-3/4 + tier <=2 -> WATCH avec trigger.
- [ ] Score 0-1/4 ou tier >2 -> WAIT.
- [ ] Etendre keywords au francais.
- [ ] Stocker historique NewsFacts.
- [ ] Completer SOURCE_TIER_MAP avec 30-50 sources.

## 18. Cooldown

- [x] Appliquer cooldown meme direction apres LOSS: 240 min.
- [x] Appliquer cooldown meme direction apres WIN: 60 min.
- [x] Appliquer cooldown apres EXPIRED: 60 min.
- [x] Bloquer si trade ouvert meme direction/regime.
- [x] Ajouter cooldown global: max trades / 24h.
- [x] Ajouter pause 6h apres 3 losses dans la fenetre configuree.
- [x] Documenter cooldown dans Settings/Risk Gate.

## 19. Validity

- [x] Remplacer validite fixe 6h.
- [x] M5 -> 2h.
- [x] M15 -> 4h.
- [x] H1 -> 12h.
- [x] H4 -> 24h.
- [x] D1 -> 72h.
- [x] Ajuster selon volatilite.
- [x] Documenter validite dans payload.

## 20. Event Mode

- [x] Adapter TP en mode event.
- [x] TP1 event = 1.65 ATR.
- [x] TP2 event = 3.15 ATR.
- [x] Ajouter pre-event mode 30 min avant high impact.
- [x] Bloquer nouveaux trades 15 min apres high impact.
- [ ] Stocker historique event modes.

## 21. Data Quality / SourceRegistry

- [x] Ponderer par criticite.
- [x] Gold spot, FRED DGS10, CFTC poids 3x.
- [x] ETF/news poids 1x.
- [x] Reclasser google_news_rss en tier 5.
- [x] Reclasser IG Weekend Gold en tier 3.
- [x] Ajouter delai depuis dernier refresh par source.
- [x] Garder missing/stale/weak/preflight.

## 22. Market Regime Analysis

- [x] Revoir seuils de regimes.
- [x] Ajouter persistance de regime.
- [x] Ajouter changement escalade/accalmie.
- [x] Ajouter regime Risk-On / Carry Trade.
- [ ] Ajouter regime correlation breakdown si necessaire.
- [x] Exposer composants de score.

## 23. Macro Catalysts

- [x] Filtrer par impact HIGH/MEDIUM/LOW.
- [x] Ajouter ECB.
- [x] Ajouter BOJ.
- [ ] Ajouter consensus quand disponible.
- [x] Calculer macro density 24h.
- [x] Alerte 1h avant event HIGH.
- [x] No-trade window 30 min avant / 15 min apres.

## 24. News Reaction Engine

- [x] Creer `FastNewsListener`.
- [x] Polling 5-15s sur feeds critiques via refresh dashboard; boucle daemon VPS a activer au deploiement H24.
- [x] Stocker hashes de feeds.
- [x] Creer `EventClassifier`.
- [x] Dictionnaire high impact: Iran oil deal/escalation, Fed dovish/hawkish, macro surprise.
- [x] Distinguer "rejects" vs "accepts".
- [x] Creer `PriceReactionDetector`.
- [x] Polling prix 1-3s pendant 60s apres event prepare cote detecteur; boucle daemon VPS a activer au deploiement H24.
- [x] Verifier XAU/USD.
- [x] Verifier oil.
- [x] Verifier DXY.
- [x] Verifier volume/volatilite si disponible par event mode/market snapshots quand disponible.
- [x] Creer `NewsReactionTradePlan`.
- [x] Validite 15-30 min.
- [x] SL serre au prix pre-event +/- buffer.
- [x] TP bases sur mouvement deja fait.
- [x] Ajouter bypass controle du quality gate classique uniquement pour news event qualifie.
- [x] Suspendre 10 min apres signal news.
- [x] Ajouter tests fixtures Trump/Iran/Fed/CPI/NFP.

## 25. Multi-Strategy Engine

- [ ] Creer modele `SetupCandidate`.
- [ ] Creer `TrendContinuationSetup`.
- [ ] Creer `RangeTradingSetup`.
- [ ] Creer `BreakoutDuJourSetup`.
- [ ] Creer `MeanReversionSetup`.
- [ ] Creer `PivotRejectionSetup`.
- [ ] Integrer `NewsReactionSetup`.
- [ ] Creer `MultiStrategyCoordinator`.
- [ ] Chaque setup doit avoir SL/TP/RR/validite/cooldown/confidence.
- [ ] Prioriser NewsReaction puis Trend puis Breakout puis Range puis MeanReversion puis Pivot.
- [ ] Ajouter tests croises.

## 26. Interface Fourniwell Signals

- [ ] Remplacer le branding Aureum Flux visible par Fourniwell Signals.
- [ ] Page Signal: prix, chef de file, biais, TradingView, signal locked.
- [ ] Page Agents: ON/OFF, score, confidence, contribution.
- [ ] Page News: news recentes, resume, impact, source, heure.
- [ ] Page Trades: actifs, historique, R multiple, outcome reason.
- [ ] Page Inspector: details techniques admin uniquement.
- [ ] Retirer bruit interne des pages viewer.
- [ ] Garder les details techniques dans Inspector.
- [ ] Verifier desktop/mobile.

## 27. SaaS / utilisateurs

- [ ] Ajouter authentication.
- [ ] Ajouter role admin.
- [ ] Ajouter role viewer.
- [ ] Mettre reglages accessibles admin seulement.
- [ ] Mettre dashboard viewer en lecture seule.
- [ ] Preparer Stripe Checkout.
- [ ] Preparer Stripe Customer Portal.
- [ ] Proteger dashboard public.
- [ ] Ajouter Basic Auth Nginx temporaire au deploiement initial.

## 28. QA et replay

- [ ] Tests unitaires settings.
- [ ] Tests agents.
- [ ] Tests TradeQualityGate.
- [ ] Tests TradeLevels.
- [ ] Tests cooldown.
- [ ] Tests News Flow.
- [ ] Tests News Reaction Engine.
- [ ] Fixtures Trump/Iran.
- [ ] Fixtures Fed.
- [ ] Fixtures CPI.
- [ ] Fixtures NFP.
- [ ] Replay `reports/trade_ledger.jsonl`.
- [ ] Comparaison v3 vs v4.
- [ ] Rapport de validation v4.
- [ ] Decision Go/No-Go.

## 29. Deploiement VPS

- [ ] Deployer depuis GitHub sur VPS.
- [ ] Installer dependances Python.
- [ ] Creer venv serveur.
- [ ] Creer service systemd.
- [ ] Configurer Nginx reverse proxy.
- [ ] Pointer `fourniwell.com`.
- [ ] Activer HTTPS.
- [ ] Ajouter Basic Auth temporaire.
- [ ] Configurer logs.
- [ ] Configurer sauvegardes.
- [ ] Definir procedure rollback.

## 30. Definition de done v4.0

- [ ] Aucun trade lock avec R/R < 1.5.
- [ ] Aucun trade lock si data quality < 60.
- [ ] Aucun trade lock si circuit breaker actif.
- [ ] Aucun scoring news depuis source tier 4.
- [ ] Aucune vieille news affichee comme signal actuel.
- [ ] Les SL/TP sont dans le bon sens.
- [ ] Le RiskManagerAgent a une evidence chiffree.
- [ ] Le dashboard viewer est comprehensible sans connaitre le code.
- [ ] L'Inspector contient le detail technique.
- [ ] Le VPS peut servir Fourniwell Signals H24.
