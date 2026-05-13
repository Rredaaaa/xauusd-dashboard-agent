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

- [ ] Passer `minimum_risk_reward` de `0.65` a `1.5`.
- [ ] Passer `trade_threshold` de `55` a `65`.
- [ ] Passer `minimum_agent_confidence` de `50` a `65`.
- [ ] Passer `scoring_mode` de `aggressive_controlled` a `balanced` ou `conservative`.
- [ ] Ajouter `cooldown_after_loss_minutes = 240`.
- [ ] Ajouter `cooldown_after_win_minutes = 60`.
- [ ] Ajouter `max_trades_per_24h`.
- [ ] Ajouter `circuit_breaker_after_n_losses`.
- [ ] Ajouter `circuit_breaker_window_hours`.
- [ ] Ajouter `circuit_breaker_pause_hours`.
- [ ] Ajouter `min_data_quality = 60`.
- [ ] Ajouter `no_trade_window_minutes_before_high_macro = 30`.
- [ ] Ajouter `no_trade_window_minutes_after_high_macro = 15`.
- [ ] Garder `live_refresh_seconds = 10`.
- [ ] Garder `full_refresh_seconds = 60`.

## 2. PriceAgent -> PriceActionAgent

- [ ] Renommer ou remplacer PriceAgent par PriceActionAgent.
- [ ] Calculer pivots Camarilla H1/H4/D1.
- [ ] Detecter swing high/low M15.
- [ ] Calculer position dans range journaliere.
- [ ] Calculer distance au niveau psychologique le plus proche.
- [ ] Classer etat prix: breakout / pullback / range / consolidation / reversal.
- [ ] Rendre le score dependant de ces niveaux.
- [ ] Rendre confidence dynamique selon disponibilite des donnees.
- [ ] Afficher 4-6 niveaux cles chiffres.
- [ ] Si refonte impossible temporairement: mettre poids a 0.

## 3. TechnicalAgent

- [ ] Plafonner confidence a `85/100`.
- [ ] Calibrer poids multi-timeframe sur backtest.
- [ ] Exiger trigger reel avant conversion WATCH -> TRADE.
- [ ] Verifier cloture M15 au-dessus/sous trigger.
- [ ] Adapter SL/TP selon structure: trend, range, breakout, reversal.
- [ ] Baisser confidence en cas de contradiction intra-timeframe.
- [ ] Documenter structure technique dans payload.
- [ ] Migrer vers vraies bougies XAU/USD spot quand Chart Store v3 est fiable.

## 4. MacroAgent

- [ ] Inclure fraicheur effective FRED dans confidence.
- [ ] Ponderer DGS10, DXY, DFII10, T10YIE.
- [ ] Ajouter macro surprise: reel - consensus.
- [ ] Ajouter veto HIGH-impact dans les 30 min.
- [ ] Exposer trajectoire sur 3 dernieres publications.
- [ ] Ajouter DGS3M.
- [ ] Ajouter 30Y.
- [ ] Conserver architecture actuelle, car agent globalement fonctionnel.

## 5. GeopoliticalOilShockAgent

- [ ] Rendre bias directionnel selon regime.
- [ ] Mapper `Hormuz / Oil Shock` vers SELL.
- [ ] Mapper `Safe-Haven Gold` vers BUY.
- [ ] Mapper `De-escalation / Oil Relief` vers SELL.
- [ ] Mapper `Dollar Liquidity Squeeze` vers SELL.
- [ ] Mapper `Normal Macro` vers NEUTRAL.
- [ ] Mesurer tendance regime: escalade / accalmie / stable.
- [ ] Documenter score brut par composant.
- [ ] Rendre confidence dynamique selon WTI/Brent/headlines.
- [ ] Ajouter cooldown de changement de regime sur 4h.
- [ ] Elever seuil Hormuz a 70.
- [ ] Ajouter regime Risk-On / Carry Trade.

## 6. SentimentNewsAgent

- [ ] Desactiver scoring si sources tier > 2.
- [ ] Desactiver scoring si age median news > 60 min.
- [ ] Mettre score a 50 et confidence a 0 si news faibles.
- [ ] Ponderer par tier source.
- [ ] Ponderer par fraicheur.
- [ ] Remplacer keyword scoring par tone analysis.
- [ ] Distinguer breaking news vs opinion.
- [ ] Opinion analyste -> score neutre.
- [ ] No fresh news -> bias NEUTRAL, confidence 0.
- [ ] Evidence: top 3 titres avec source, age, sentiment chiffre.

## 7. CorrelationAgent

- [ ] Hierarchiser confirmations et contradictions.
- [ ] Afficher verdict net: nombre BUY vs SELL.
- [ ] Calculer correlation glissante 30j.
- [ ] Abaisser poids si cassure de correlation.
- [ ] Adapter poids selon regime.
- [ ] Detecter correlation breakdown.
- [ ] Rendre confidence dynamique selon nombre actifs disponibles.
- [ ] Garder le reste de l'agent.

## 8. FlowPositioningAgent

- [ ] Ajouter percentile Managed Money 1 an.
- [ ] Ajouter percentile Managed Money 5 ans.
- [ ] Ajouter logique contrarienne si extremes.
- [ ] Detecter divergence COT vs ETF.
- [ ] Agreger GLD + IAU + SLV.
- [ ] Ponderer CFTC 0.6 et ETF 0.4.
- [ ] Ajouter Producers/Merchants.
- [ ] Garder architecture source tier 1.

## 9. EventFactsAgent

- [ ] Remplacer score quantitatif `45 + n_facts * 6`.
- [ ] Filtrer `qualified_facts`: tier <= 2 et confidence >= 60.
- [ ] Si aucun fait qualifie: score 45, bias NEUTRAL.
- [ ] Si faits qualifies: score moyen pondere par confidence.
- [ ] Choisir bias par vote directionnel.
- [ ] Choisir primary_fact par meilleur tier + confidence.
- [ ] Ponderer par market_confirmation.confirmation_score.
- [ ] Filtrer opinion et rumeur du score.
- [ ] Evidence: top 3 facts avec tier, confirmation_score, age.
- [ ] Confidence: moyenne ponderee des faits qualifies.

## 10. TrumpPoliticalStatementsAgent

- [ ] Rendre bias directionnel selon contenu.
- [ ] Iran/Hormuz menacant -> SELL.
- [ ] Fed pressure dovish -> BUY.
- [ ] Tariffs/trade war -> SELL.
- [ ] Ponderer par recence.
- [ ] Mesurer convergence de statements sur 24h.
- [ ] Distinguer action signee vs menace verbale.
- [ ] Garder validation source et evidence.

## 11. RiskManagerAgent

- [ ] Recrire completement le role.
- [ ] Calculer R/R potentiel actuel.
- [ ] Calculer risque par trade recommande.
- [ ] Calculer drawdown recent / attendu.
- [ ] Calculer exposition cumulee.
- [ ] Lire `reports/trade_ledger.jsonl`.
- [ ] Detecter circuit breaker actif.
- [ ] Score: 100 setup propre, 50 risque normal, 0 ne pas trader.
- [ ] Bias BLOCK si circuit breaker actif.
- [ ] Bias CAUTION si exposition trop forte.
- [ ] Bias OK sinon.
- [ ] Evidence: R/R, taille, drawdown, exposition, circuit breaker.
- [ ] Confidence selon disponibilite historique.

## 12. OrchestratorAgent legacy

- [ ] Supprimer OrchestratorAgent legacy.
- [ ] Conserver uniquement OrchestratorDecision v3.
- [ ] Nettoyer mentions "ancien moteur".
- [ ] Corriger duplication `RISK [high] Gate:`.
- [ ] Mettre a jour tests qui reference OrchestratorAgent.
- [ ] Verifier que les contradictions ne comptent plus cet agent legacy.

## 13. TradeQualityGate

- [ ] `min_rr` minimum a 1.5.
- [ ] Validating agents minimum a 3.
- [ ] Supprimer bypass aggressive majority.
- [ ] Hard block regime fort si score >= 70.
- [ ] Hard block direction contraire au regime.
- [ ] Hard block catalyseur high impact dans 30 min.
- [ ] Hard block apres >=3 losses dans 24h.
- [ ] Hard block data quality < 60.
- [ ] Ecrire raisons de blocage dans payload.

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

- [ ] Ajouter feed White House.
- [ ] Ajouter feed Fed press all.
- [ ] Ajouter feed Fed monetary.
- [ ] Ajouter feed BLS news release.
- [ ] Ajouter feed Treasury press releases.
- [ ] Ajouter feed BEA.
- [ ] Ajouter feed CFTC press releases.
- [ ] Ajouter feed WGC.
- [ ] Ajouter AP business si accessible.
- [ ] Ajouter AP top news si accessible.
- [ ] Ajouter CNBC RSS.
- [ ] Ajouter Reuters si flux accessible.
- [ ] Ajouter Bloomberg si flux accessible.
- [ ] Polling canal critique 20-30s.
- [ ] Rejeter sources tier 4 en amont.
- [ ] Rejeter forecasts/predictions/outlook.
- [ ] Rejeter vieux articles.
- [ ] Rejeter analysis today sans fait nouveau.
- [ ] Detecter breaking par hash de feed.
- [ ] Trier par heure reelle de publication.
- [ ] Masquer news neutres par defaut.
- [ ] Afficher "aucune news exploitable" si rien de fiable.

## 17. News Facts Engine

- [ ] Elever dedup Jaccard a 0.65.
- [ ] Ajouter dedup prefixe commun.
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

- [ ] Appliquer cooldown meme direction apres LOSS: 240 min.
- [ ] Appliquer cooldown meme direction apres WIN: 60 min.
- [ ] Appliquer cooldown apres EXPIRED: 60 min.
- [ ] Bloquer si trade ouvert meme direction/regime.
- [ ] Ajouter cooldown global: max trades / 24h.
- [ ] Ajouter pause 6h apres 2 losses consecutives.
- [ ] Documenter cooldown dans RiskManagerAgent.

## 19. Validity

- [ ] Remplacer validite fixe 6h.
- [ ] M5 -> 2h.
- [ ] M15 -> 4h.
- [ ] H1 -> 12h.
- [ ] H4 -> 24h.
- [ ] D1 -> 72h.
- [ ] Ajuster selon volatilite.
- [ ] Documenter validite dans payload.

## 20. Event Mode

- [ ] Adapter TP en mode event.
- [ ] TP1 event = 1.65 ATR.
- [ ] TP2 event = 3.15 ATR.
- [ ] Ajouter pre-event mode 30 min avant high impact.
- [ ] Bloquer nouveaux trades 15 min apres high impact.
- [ ] Stocker historique event modes.

## 21. Data Quality / SourceRegistry

- [ ] Ponderer par criticite.
- [ ] Gold spot, FRED DGS10, CFTC poids 3x.
- [ ] ETF/news poids 1x.
- [ ] Reclasser google_news_rss en tier 5.
- [ ] Reclasser IG Weekend Gold en tier 3.
- [ ] Ajouter delai depuis dernier refresh par source.
- [ ] Garder missing/stale/weak/preflight.

## 22. Market Regime Analysis

- [ ] Revoir seuils de regimes.
- [ ] Ajouter persistance de regime.
- [ ] Ajouter changement escalade/accalmie.
- [ ] Ajouter regime Risk-On / Carry Trade.
- [ ] Ajouter regime correlation breakdown si necessaire.
- [ ] Exposer composants de score.

## 23. Macro Catalysts

- [ ] Filtrer par impact HIGH/MEDIUM/LOW.
- [ ] Ajouter ECB.
- [ ] Ajouter BOJ.
- [ ] Ajouter consensus quand disponible.
- [ ] Calculer macro density 24h.
- [ ] Alerte 1h avant event HIGH.
- [ ] No-trade window 30 min avant / 15 min apres.

## 24. News Reaction Engine

- [ ] Creer `FastNewsListener`.
- [ ] Polling 5-15s sur feeds critiques.
- [ ] Stocker hashes de feeds.
- [ ] Creer `EventClassifier`.
- [ ] Dictionnaire high impact: Iran oil deal/escalation, Fed dovish/hawkish, macro surprise.
- [ ] Distinguer "rejects" vs "accepts".
- [ ] Creer `PriceReactionDetector`.
- [ ] Polling prix 1-3s pendant 60s apres event.
- [ ] Verifier XAU/USD.
- [ ] Verifier oil.
- [ ] Verifier DXY.
- [ ] Verifier volume/volatilite si disponible.
- [ ] Creer `NewsReactionTradePlan`.
- [ ] Validite 15-30 min.
- [ ] SL serre au prix pre-event +/- buffer.
- [ ] TP bases sur mouvement deja fait.
- [ ] Ajouter bypass controle du quality gate classique uniquement pour news event qualifie.
- [ ] Suspendre 10 min apres signal news.
- [ ] Ajouter tests fixtures Trump/Iran/Fed/CPI/NFP.

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
