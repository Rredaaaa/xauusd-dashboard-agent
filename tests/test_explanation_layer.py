"""Tests Phase 21 - ExplanationLayer."""
from __future__ import annotations

import unittest

from explanation_layer import (
    ExplanationContext,
    ExplanationLayer,
    FORBIDDEN_PATTERNS,
    render_experimental_agent,
    validate_phrase,
)


def _good_ctx() -> ExplanationContext:
    return ExplanationContext(
        fact="Plusieurs titres mentionnent Iran/Hormuz",
        evidence="WTI -2.45%, Brent -1.10%, DXY +0.13%",
        confirmation="seuil de declenchement: WTI > +1.0% sur 1h",
        impact="pas de bid refuge tant que oil baisse",
        action="WATCH_SELL si DXY > 105.20 et WTI < -1.0%",
    )


class ExplanationContextTests(unittest.TestCase):
    def test_all_fields_required_non_empty(self) -> None:
        with self.assertRaises(ValueError):
            ExplanationContext(fact="", evidence="x", confirmation="x", impact="x", action="x")
        with self.assertRaises(ValueError):
            ExplanationContext(fact="x", evidence="   ", confirmation="x", impact="x", action="x")

    def test_accepts_valid_context(self) -> None:
        ctx = _good_ctx()
        self.assertEqual(ctx.fact, "Plusieurs titres mentionnent Iran/Hormuz")


class ExplanationLayerTemplatesTests(unittest.TestCase):
    def test_each_template_includes_five_elements(self) -> None:
        ctx = _good_ctx()
        templates = [
            ExplanationLayer.price_alert,
            ExplanationLayer.news_alert,
            ExplanationLayer.geopolitical_regime,
            ExplanationLayer.agent_contradiction,
            ExplanationLayer.no_trade,
            ExplanationLayer.watch_setup,
            ExplanationLayer.trade_setup,
            ExplanationLayer.data_quality_degraded,
        ]
        for template in templates:
            text = template(ctx)
            self.assertIn(ctx.fact, text)
            self.assertIn(ctx.evidence, text)
            self.assertIn("Confirmation", text)
            self.assertIn("Impact XAU/USD", text)
            self.assertIn("Action", text)

    def test_templates_use_distinct_prefix(self) -> None:
        ctx = _good_ctx()
        self.assertTrue(ExplanationLayer.no_trade(ctx).startswith("NO_TRADE:"))
        self.assertTrue(ExplanationLayer.watch_setup(ctx).startswith("Setup surveille:"))
        self.assertTrue(ExplanationLayer.trade_setup(ctx).startswith("Trade exploitable:"))


class ForbiddenPatternsTests(unittest.TestCase):
    """Chaque pattern doit bloquer la formulation interdite issue de l'audit Phase 20."""

    def test_theme_existe_blocked(self) -> None:
        self.assertIn("theme_existe", validate_phrase("Le theme Iran/Hormuz existe."))

    def test_ne_confirme_pas_seul_blocked(self) -> None:
        self.assertIn(
            "ne_confirme_pas_seul",
            validate_phrase("Les correlations ne confirment pas le signal."),
        )

    def test_ne_confirme_pas_with_threshold_allowed(self) -> None:
        self.assertNotIn(
            "ne_confirme_pas_seul",
            validate_phrase(
                "DXY ne confirme pas tant que le seuil 105.20 n'est pas casse."
            ),
        )

    def test_flux_mitiges_blocked(self) -> None:
        self.assertIn("flux_mitiges", validate_phrase("Flux mitiges ce matin."))

    def test_contexte_qualifie_seul_blocked(self) -> None:
        self.assertIn(
            "contexte_qualifie_seul",
            validate_phrase("Le contexte favorable soutient l'or."),
        )

    def test_contexte_with_evidence_allowed(self) -> None:
        self.assertNotIn(
            "contexte_qualifie_seul",
            validate_phrase("Contexte favorable: DXY -0.40%, DGS10 -3 bps."),
        )

    def test_prudence_blocked_in_main_view(self) -> None:
        self.assertIn("prudence", validate_phrase("Prudence sur les entrees gold."))

    def test_prudence_allowed_in_inspector(self) -> None:
        self.assertNotIn(
            "prudence",
            validate_phrase("Prudence sur les entrees gold.", allow_in_inspector=True),
        )

    def test_risque_reste_actif_blocked(self) -> None:
        self.assertIn(
            "risque_reste_actif",
            validate_phrase("Le risque geopolitique reste actif et soutient l'or."),
        )

    def test_reste_favorable_blocked(self) -> None:
        self.assertIn(
            "reste_favorable",
            validate_phrase("Le fondamental reste favorable a l'or."),
        )

    def test_reste_partage_blocked(self) -> None:
        self.assertIn(
            "reste_partage",
            validate_phrase("Le message des banques centrales reste partage."),
        )

    def test_legerement_blocked_without_threshold(self) -> None:
        self.assertIn(
            "legerement_directionnel",
            validate_phrase("Biais court terme: legerement haussier."),
        )

    def test_legerement_with_threshold_allowed(self) -> None:
        self.assertNotIn(
            "legerement_directionnel",
            validate_phrase(
                "Biais legerement haussier si cassure M15 au-dessus de 2400."
            ),
        )

    def test_ressemble_davantage_blocked(self) -> None:
        self.assertIn(
            "ressemble_davantage",
            validate_phrase("La structure ressemble davantage a une correction."),
        )

    def test_en_general_blocked(self) -> None:
        self.assertIn(
            "en_general",
            validate_phrase(
                "Plus d'incertitude geopolitique soutient en general l'or."
            ),
        )

    def test_brouille_les_reperes_blocked(self) -> None:
        self.assertIn(
            "brouille_les_reperes",
            validate_phrase("Le conflit brouille les reperes habituels du marche."),
        )

    def test_controle_passif_blocked(self) -> None:
        self.assertIn("controle_passif", validate_phrase("Controle passif du risque."))

    def test_clean_phrase_passes(self) -> None:
        clean = (
            "WTI -2.45%, Brent -1.10%. Confirmation: cassure WTI > +1% sur 1h. "
            "Impact XAU/USD: pas de bid refuge. Action: WATCH_SELL si DXY > 105.20."
        )
        self.assertEqual(validate_phrase(clean), [])

    def test_all_documented_patterns_present(self) -> None:
        """Garde-fou: les 14 patterns documentes en Phase 20 doivent exister."""
        expected = {
            "theme_existe",
            "ne_confirme_pas_seul",
            "flux_mitiges",
            "contexte_qualifie_seul",
            "prudence",
            "risque_reste_actif",
            "reste_favorable",
            "reste_partage",
            "legerement_directionnel",
            "ressemble_davantage",
            "en_general",
            "besoin_confirmation_floue",
            "brouille_les_reperes",
            "controle_passif",
        }
        self.assertEqual(set(FORBIDDEN_PATTERNS.keys()), expected)


class TemplateRefusesForbiddenContextTests(unittest.TestCase):
    def test_template_raises_if_field_contains_forbidden(self) -> None:
        bad_ctx = ExplanationContext(
            fact="Le theme Iran/Hormuz existe",
            evidence="WTI -2.45%",
            confirmation="cassure WTI > +1%",
            impact="pas de bid refuge",
            action="WATCH_SELL",
        )
        with self.assertRaises(ValueError) as cm:
            ExplanationLayer.geopolitical_regime(bad_ctx)
        self.assertIn("theme_existe", str(cm.exception))


class ExperimentalAgentTests(unittest.TestCase):
    def test_includes_experimental_marker_and_blocking_reason(self) -> None:
        text = render_experimental_agent(
            agent_name="ElliottWaveAgent",
            hypothesis="impulsion haussiere",
            blocking_reason="Aucun Chart Store OHLC disponible",
        )
        self.assertIn("experimental", text)
        self.assertIn("non scorant", text)
        self.assertIn("ElliottWaveAgent", text)
        self.assertIn("Aucun Chart Store OHLC disponible", text)
        self.assertIn("n'influence pas la decision principale", text)

    def test_experimental_text_does_not_use_forbidden_patterns(self) -> None:
        text = render_experimental_agent(
            agent_name="ElliottWaveAgent",
            hypothesis="impulsion haussiere",
            blocking_reason="Historique insuffisant pour pivots multi-timeframe",
        )
        matches = validate_phrase(text, allow_in_inspector=True)
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
