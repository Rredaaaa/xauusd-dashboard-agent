"""ExplanationLayer - couche centralisee de generation des phrases utilisateur.

Phase 21 du plan v3.0. Toute phrase trader doit suivre la structure:
  fait + preuve + confirmation + impact + action

Le module fournit:
  - ExplanationContext: porteur des 5 elements obligatoires;
  - ExplanationLayer: 8 templates de rendu (price, news, regime, contradiction,
    no_trade, watch_setup, trade_setup, data_quality_degraded);
  - render_experimental_agent: cas special pour les agents non scorants v3
    (Elliott avant Phase 27);
  - FORBIDDEN_PATTERNS: dictionnaire regex des formulations interdites;
  - validate_phrase(text): renvoie la liste des patterns matches (vide = ok).

Le module ne touche pas au scoring, aux agents ou aux sources. Il est
pur Python sans dependance reseau pour rester testable en isolation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExplanationContext:
    """5 elements obligatoires pour toute phrase exposee dans la decision principale.

    fact:         ce qui se passe, fait concret avec acteur/asset si possible.
    evidence:     preuve chiffree (variation %, niveau, headline + source).
    confirmation: ce qui confirmerait ou contredirait, idealement avec un seuil.
    impact:       impact direct sur XAU/USD.
    action:       BUY, SELL, WATCH_BUY, WATCH_SELL, NO_TRADE, WAIT, plus la condition.
    """

    fact: str
    evidence: str
    confirmation: str
    impact: str
    action: str

    def __post_init__(self) -> None:
        for field_name in ("fact", "evidence", "confirmation", "impact", "action"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"ExplanationContext: champ '{field_name}' obligatoire et non vide"
                )


FORBIDDEN_PATTERNS: dict[str, re.Pattern[str]] = {
    "theme_existe": re.compile(r"\ble theme\s+[^.]+?\s+existe\b", re.IGNORECASE),
    "ne_confirme_pas_seul": re.compile(
        r"\bne confirm(e|ent) pas\b(?!.{0,80}(seuil|si\b|>|<|au[- ]dessus|sous |cassure))",
        re.IGNORECASE,
    ),
    "flux_mitiges": re.compile(r"\bflux mitig(e|es|és?)\b", re.IGNORECASE),
    "contexte_qualifie_seul": re.compile(
        r"\bcontexte (favorable|defavorable|défavorable)\b(?!.{0,40}(\d|%|bps))",
        re.IGNORECASE,
    ),
    "prudence": re.compile(r"\bprudence\b", re.IGNORECASE),
    "risque_reste_actif": re.compile(r"\brisque[^.]{0,40}reste\s+actif\b", re.IGNORECASE),
    "reste_favorable": re.compile(r"\breste favorable\b", re.IGNORECASE),
    "reste_partage": re.compile(r"\breste partag(e|é)\b", re.IGNORECASE),
    "legerement_directionnel": re.compile(
        r"\bl(e|é)g(e|è)rement (haussier|baissier)\b(?!.{0,80}(seuil|si\b|>|<|cassure))",
        re.IGNORECASE,
    ),
    "ressemble_davantage": re.compile(r"\bressemble davantage\b", re.IGNORECASE),
    "en_general": re.compile(r"\ben g(e|é)n(e|é)ral\b", re.IGNORECASE),
    "besoin_confirmation_floue": re.compile(
        r"\bbesoin d['’]une confirmation\b(?!.{0,80}(par |via |de |seuil|si\b|>|<))",
        re.IGNORECASE,
    ),
    "brouille_les_reperes": re.compile(r"\bbrouille les rep(e|è)res\b", re.IGNORECASE),
    "controle_passif": re.compile(r"\bcontr(o|ô)le passif\b", re.IGNORECASE),
}


def validate_phrase(text: str, *, allow_in_inspector: bool = False) -> list[str]:
    """Retourne la liste des patterns interdits trouves dans `text`.

    Si la phrase doit etre rendue dans l'Inspector (audit technique), les
    formules de mise en garde 'prudence' et 'controle passif' restent
    autorisees parce que ce contexte demande la transparence sur l'etat
    interne du moteur.
    """
    matches: list[str] = []
    for name, pattern in FORBIDDEN_PATTERNS.items():
        if allow_in_inspector and name in {"prudence", "controle_passif"}:
            continue
        if pattern.search(text):
            matches.append(name)
    return matches


class ExplanationLayer:
    """Templates centralises. Chaque methode prend un ExplanationContext et
    retourne une phrase trader formatee. Le rendu evite les formulations
    interdites via validate_phrase().
    """

    @staticmethod
    def _join(ctx: ExplanationContext, prefix: str) -> str:
        line = (
            f"{prefix}: {ctx.fact}. "
            f"{ctx.evidence}. "
            f"Confirmation: {ctx.confirmation}. "
            f"Impact XAU/USD: {ctx.impact}. "
            f"Action: {ctx.action}."
        )
        return line

    @staticmethod
    def _validate_or_raise(text: str) -> str:
        matches = validate_phrase(text)
        if matches:
            raise ValueError(
                f"ExplanationLayer: phrase finale contient des patterns interdits {matches}: {text}"
            )
        return text

    @classmethod
    def price_alert(cls, ctx: ExplanationContext) -> str:
        return cls._validate_or_raise(cls._join(ctx, "Alerte prix"))

    @classmethod
    def news_alert(cls, ctx: ExplanationContext) -> str:
        return cls._validate_or_raise(cls._join(ctx, "News"))

    @classmethod
    def geopolitical_regime(cls, ctx: ExplanationContext) -> str:
        return cls._validate_or_raise(cls._join(ctx, "Regime geopolitique"))

    @classmethod
    def agent_contradiction(cls, ctx: ExplanationContext) -> str:
        return cls._validate_or_raise(cls._join(ctx, "Contradiction agents"))

    @classmethod
    def no_trade(cls, ctx: ExplanationContext) -> str:
        return cls._validate_or_raise(cls._join(ctx, "NO_TRADE"))

    @classmethod
    def watch_setup(cls, ctx: ExplanationContext) -> str:
        return cls._validate_or_raise(cls._join(ctx, "Setup surveille"))

    @classmethod
    def trade_setup(cls, ctx: ExplanationContext) -> str:
        return cls._validate_or_raise(cls._join(ctx, "Trade exploitable"))

    @classmethod
    def data_quality_degraded(cls, ctx: ExplanationContext) -> str:
        return cls._validate_or_raise(cls._join(ctx, "Qualite donnees degradee"))


def render_experimental_agent(
    *,
    agent_name: str,
    hypothesis: str,
    blocking_reason: str,
) -> str:
    """Format pour les agents marques experimentaux (non scorants v3).

    Utilise par Elliott avant la livraison de Phase 27 (Elliott Engine v3).
    Le texte est neutre, signale explicitement le statut experimental, et
    n'utilise jamais une formulation qui suggererait un comptage fiable.
    """
    return (
        f"{agent_name} (experimental, non scorant en v3): hypothese {hypothesis}. "
        f"{blocking_reason}. Ce signal n'influence pas la decision principale."
    )
