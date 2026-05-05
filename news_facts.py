"""News Facts Engine v3 - Phase 22.

Remplace la lecture news generique par des faits structures.

Chaque NewsFact repond a:
  1. Qu'est-ce qui se passe? (title + fact_type + actors)
  2. Pourquoi c'est important? (why_it_matters)
  3. Qu'est-ce que le marche confirme ou contredit? (MarketConfirmation)
  4. Impact XAU/USD? (gold_impact + impact_bias)
  5. Action trader? (trader_action + trader_action_detail)

Pas de dependance reseau. Les snapshots marche sont passes en parametre.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

FACT_TYPES = {
    "confirmed_fact": "Fait confirme",
    "unconfirmed_headline": "Headline non confirmee",
    "opinion": "Opinion / analyse",
    "rumor": "Rumeur / non sourcee",
    "market_analysis": "Analyse marche",
}

SOURCE_TIER_LABELS = {
    1: "Source officielle",
    2: "Agence majeure",
    3: "Media finance",
    4: "Agregateur",
    5: "Source faible",
}

# Sources connues et leur tier
SOURCE_TIER_MAP: dict[str, int] = {
    # Tier 1 - officielles
    "white house": 1, "federal reserve": 1, "fed": 1, "ecb": 1,
    "cftc": 1, "bls": 1, "bea": 1, "treasury": 1, "imf": 1,
    "world gold council": 1, "wgc": 1,
    # Tier 2 - agences majeures
    "reuters": 2, "ap": 2, "associated press": 2, "bloomberg": 2,
    "financial times": 2, "ft": 2, "wall street journal": 2, "wsj": 2,
    "new york times": 2, "nyt": 2, "bbc": 2,
    # Tier 3 - media finance
    "cnbc": 3, "marketwatch": 3, "barrons": 3, "seeking alpha": 3,
    "kitco": 3, "gold price": 3, "investing.com": 3, "forexlive": 3,
    "fx street": 3, "fxstreet": 3, "daily sabah": 3,
    # Tier 4 - agregateurs
    "google news": 4, "yahoo finance": 4, "yahoo": 4, "msn": 4,
    "benzinga": 4, "zerohedge": 4,
}

# Mots-cles pour detecter le type de fait
CONFIRMED_SIGNALS = (
    "confirms", "confirmed", "announces", "announced", "reports", "reported",
    "signed", "agreed", "passed", "approved", "annonce", "confirme",
    "publie", "official", "officiel",
)
OPINION_SIGNALS = (
    "says", "believes", "thinks", "warns", "predicts", "expects", "selon",
    "estime", "pense", "prevoit", "analysts say", "analysts expect",
    "could", "may", "might", "would",
)
RUMOR_SIGNALS = (
    "rumor", "rumour", "sources say", "sources close", "reportedly",
    "unconfirmed", "allegation", "alleged", "according to sources",
    "selon des sources",
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MarketConfirmation:
    """Est-ce que le marche confirme la these du fait?

    Un fait geopolitique Iran/Hormuz n'a d'impact reel que si oil monte.
    Un fait Fed dovish n'a d'impact que si DXY baisse et taux reculent.
    """
    # Oil
    oil_change_pct: float | None = None
    oil_trend: str = "indisponible"       # "hausse", "baisse", "stable", "indisponible"
    oil_confirms: bool = False

    # Dollar
    dxy_change_pct: float | None = None
    dxy_trend: str = "stable"
    dxy_confirms: bool = False

    # Taux reels (DFII10, bps)
    rates_change_bps: float | None = None
    rates_trend: str = "stable"
    rates_confirm: bool = False

    # Or lui-meme
    gold_change_pct: float | None = None
    gold_trend: str = "stable"
    gold_confirms: bool = False

    # Synthese
    confirmation_score: int = 0   # 0-4, nombre d'actifs qui confirment
    summary: str = ""


@dataclass
class NewsFact:
    """Fait d'actualite structure pour le dashboard v3.

    Remplace et etend EventFact avec les champs manquants pour Phase 22.
    Compatibilite ascendante maintenue: tous les champs EventFact sont presentes.
    """
    # --- champs EventFact (compatibilite) ---
    title: str
    source: str
    source_url: str
    published_at: str
    category: str
    actors: list[str]
    locations: list[str]
    themes: list[str]
    confirmation_level: str
    market_chain: str
    gold_impact: str
    impact_bias: str
    confidence: int

    # --- champs v3 ---
    fact_type: str                              # cle de FACT_TYPES
    source_tier: int                            # 1-5
    source_tier_label: str                      # label lisible
    why_it_matters: str                         # pourquoi important pour trader
    market_confirmation: MarketConfirmation = field(default_factory=MarketConfirmation)
    trader_action: str = "WAIT"                 # WATCH_BUY / WATCH_SELL / NO_TRADE / WAIT
    trader_action_detail: str = ""              # detail de l'action avec seuils

    @property
    def fact_type_label(self) -> str:
        return FACT_TYPES.get(self.fact_type, self.fact_type)

    @property
    def market_confirmed(self) -> bool:
        return self.market_confirmation.confirmation_score >= 2


# ---------------------------------------------------------------------------
# Fonctions de classification
# ---------------------------------------------------------------------------

def classify_source_tier(source_name: str) -> tuple[int, str]:
    """Retourne (tier, label) pour un nom de source."""
    lower = source_name.lower()
    for key, tier in SOURCE_TIER_MAP.items():
        if key in lower:
            return tier, SOURCE_TIER_LABELS[tier]
    return 4, SOURCE_TIER_LABELS[4]


def classify_fact_type(title: str, source: str, source_tier: int) -> str:
    """Determine le type de fait a partir du titre et de la source."""
    text = title.lower()

    if any(w in text for w in RUMOR_SIGNALS):
        return "rumor"

    if any(w in text for w in OPINION_SIGNALS):
        if source_tier <= 2:
            return "market_analysis"
        return "opinion"

    if any(w in text for w in CONFIRMED_SIGNALS) and source_tier <= 2:
        return "confirmed_fact"

    if "%" in text or any(c.isdigit() for c in text[:50]):
        return "market_analysis"

    return "unconfirmed_headline"


def build_why_it_matters(category: str, themes: list[str], fact_type: str) -> str:
    """Explique pourquoi ce fait est important pour un trader XAU/USD."""
    t = " ".join(themes).lower()
    cat = category.lower()

    if "iran" in t or "hormuz" in t or "oil" in t or "petrole" in t:
        return (
            "Un choc oil alimente l'inflation et le risque de marche. "
            "Si WTI monte, les rendements peuvent suivre et limiter le soutien or."
        )
    if "fed" in t or "fomc" in t or cat in ("macro_fed", "events_fomc"):
        return (
            "Le calendrier Fed influence directement DXY et taux reels. "
            "Un pivot dovish aide l'or; un message hawkish le penalise."
        )
    if "cpi" in t or "inflation" in t or cat == "macro_cpi":
        return (
            "L'inflation determine si la Fed peut couper les taux. "
            "Inflation haute = Fed plus dure = headwind pour l'or."
        )
    if "nfp" in t or "emploi" in t or "jobs" in t or cat == "macro_nfp":
        return (
            "Le marche de l'emploi US est un proxy de la sante economique et "
            "influence les attentes de taux via le dollar."
        )
    if "cot" in t or "speculative" in t or cat == "sentiment_cot":
        return (
            "Le positionnement COT revele si les specs sont surcharges en long ou en short. "
            "Un long sature augmente le risque de retournement."
        )
    if "etf" in t or "gld" in t or "iau" in t or cat == "sentiment_etf":
        return (
            "Les flux ETF or mesurent la demande institutionnelle. "
            "Des sorties persistantes signalent une perte de confiance."
        )
    if "vix" in t or "volatility" in t or cat == "risk_vix":
        return (
            "Le VIX mesure le stress de marche. "
            "Un VIX > 20 signale une aversion au risque qui peut orienter les capitaux vers l'or."
        )
    if "central bank" in t or "banque centrale" in t or "reserve" in t:
        return (
            "Les achats banques centrales sont un soutien structurel pour l'or. "
            "Un ralentissement des achats peut peser sur le sentiment long terme."
        )
    return (
        "Cette information met a jour le contexte de marche. "
        "Verifier l'impact sur DXY, taux reels et oil avant d'agir."
    )


def build_market_confirmation(
    category: str,
    themes: list[str],
    impact_bias: str,
    *,
    wti_change: float | None = None,
    brent_change: float | None = None,
    dxy_change: float | None = None,
    rates_change_bps: float | None = None,
    gold_change: float | None = None,
) -> MarketConfirmation:
    """Determine si le marche confirme la these du fait.

    Chaque categorie de fait a ses propres actifs de confirmation:
    - Geopolitique/oil: WTI/Brent principaux, DXY secondaire
    - Fed/macro: taux reels + DXY principaux
    - COT/ETF: or lui-meme
    - Geopolitique neutre: VIX proxy (absent ici, on utilise gold)
    """
    t = " ".join(themes).lower()
    cat = category.lower()
    conf = MarketConfirmation()

    # --- Oil ---
    oil_raw = None
    if wti_change is not None and brent_change is not None:
        oil_raw = (wti_change + brent_change) / 2
    elif wti_change is not None:
        oil_raw = wti_change
    elif brent_change is not None:
        oil_raw = brent_change

    if oil_raw is not None:
        conf.oil_change_pct = round(oil_raw, 2)
        conf.oil_trend = "hausse" if oil_raw >= 0.20 else "baisse" if oil_raw <= -0.20 else "stable"
    else:
        conf.oil_trend = "indisponible"

    # --- DXY ---
    if dxy_change is not None:
        conf.dxy_change_pct = round(dxy_change, 2)
        conf.dxy_trend = "hausse" if dxy_change >= 0.10 else "baisse" if dxy_change <= -0.10 else "stable"

    # --- Taux ---
    if rates_change_bps is not None:
        conf.rates_change_bps = round(rates_change_bps, 1)
        conf.rates_trend = "hausse" if rates_change_bps >= 1.0 else "baisse" if rates_change_bps <= -1.0 else "stable"

    # --- Or ---
    if gold_change is not None:
        conf.gold_change_pct = round(gold_change, 2)
        conf.gold_trend = "hausse" if gold_change >= 0.10 else "baisse" if gold_change <= -0.10 else "stable"

    # --- Logique de confirmation selon la categorie ---
    is_geo_oil = any(k in t for k in ("iran", "hormuz", "oil", "petrole", "conflict", "geopolitique"))
    is_macro_fed = cat in ("macro_fed", "events_fomc") or any(k in t for k in ("fed", "fomc", "taux"))
    is_macro_rates = cat in ("macro_cpi", "macro_nfp") or any(k in t for k in ("cpi", "inflation", "nfp", "emploi"))

    score = 0

    if is_geo_oil:
        # Pour un fait geopolitique/oil bullish or: oil DOIT monter
        if impact_bias == "bullish":
            conf.oil_confirms = conf.oil_trend == "hausse"
            conf.dxy_confirms = conf.dxy_trend == "baisse"
            conf.gold_confirms = conf.gold_trend == "hausse"
        else:
            # bearish/mixte: oil qui baisse confirme la de-escalation
            conf.oil_confirms = conf.oil_trend == "baisse"
            conf.dxy_confirms = conf.dxy_trend == "hausse"
            conf.gold_confirms = conf.gold_trend == "baisse"

    elif is_macro_fed or is_macro_rates:
        # Dovish Fed → taux baissent + DXY baisse → bullish or
        if impact_bias == "bullish":
            conf.rates_confirm = conf.rates_trend == "baisse"
            conf.dxy_confirms = conf.dxy_trend == "baisse"
            conf.gold_confirms = conf.gold_trend == "hausse"
        else:
            conf.rates_confirm = conf.rates_trend == "hausse"
            conf.dxy_confirms = conf.dxy_trend == "hausse"
            conf.gold_confirms = conf.gold_trend == "baisse"

    else:
        # Categorie generique: on regarde juste si or va dans le bon sens
        if impact_bias == "bullish":
            conf.gold_confirms = conf.gold_trend == "hausse"
            conf.dxy_confirms = conf.dxy_trend == "baisse"
        elif impact_bias in ("bearish", "mixte"):
            conf.gold_confirms = conf.gold_trend == "baisse"
            conf.dxy_confirms = conf.dxy_trend == "hausse"

    score = sum([
        conf.oil_confirms,
        conf.dxy_confirms,
        conf.rates_confirm,
        conf.gold_confirms,
    ])
    conf.confirmation_score = score
    conf.summary = _build_confirmation_summary(conf, is_geo_oil)

    return conf


def _build_confirmation_summary(conf: MarketConfirmation, is_geo_oil: bool) -> str:
    parts: list[str] = []

    if conf.oil_trend != "indisponible":
        sign = "+" if (conf.oil_change_pct or 0) >= 0 else ""
        status = "confirme" if conf.oil_confirms else "diverge"
        parts.append(f"Oil {sign}{conf.oil_change_pct:.1f}% ({status})")

    if conf.dxy_change_pct is not None:
        sign = "+" if conf.dxy_change_pct >= 0 else ""
        status = "confirme" if conf.dxy_confirms else "diverge"
        parts.append(f"DXY {sign}{conf.dxy_change_pct:.2f}% ({status})")

    if conf.rates_change_bps is not None:
        sign = "+" if conf.rates_change_bps >= 0 else ""
        status = "confirme" if conf.rates_confirm else "diverge"
        parts.append(f"Taux {sign}{conf.rates_change_bps:.1f} bps ({status})")

    if conf.gold_change_pct is not None:
        sign = "+" if conf.gold_change_pct >= 0 else ""
        status = "confirme" if conf.gold_confirms else "diverge"
        parts.append(f"Or {sign}{conf.gold_change_pct:.2f}% ({status})")

    if not parts:
        return "Donnees marche insuffisantes pour confirmer."

    score = conf.confirmation_score
    if score >= 3:
        verdict = "Marche confirme fortement."
    elif score == 2:
        verdict = "Marche confirme partiellement."
    elif score == 1:
        verdict = "Confirmation faible."
    else:
        verdict = "Validation marche absente."

    return f"{verdict} {' | '.join(parts)}."


def build_trader_action(
    impact_bias: str,
    market_confirmation: MarketConfirmation,
    fact_type: str,
    confidence: int,
) -> tuple[str, str]:
    """Retourne (trader_action, detail).

    trader_action: WATCH_BUY / WATCH_SELL / NO_TRADE / WAIT
    """
    score = market_confirmation.confirmation_score

    if fact_type == "rumor":
        return "NO_TRADE", "Rumeur non sourcee: aucun trade avant confirmation officielle."

    if fact_type == "opinion":
        return "WAIT", "Opinion d'analyste: surveiller si le marche reagit dans le sens prevu."

    if confidence < 50:
        return "WAIT", "Confiance source insuffisante: attendre une confirmation par agence majeure ou officielle."

    if impact_bias == "bullish":
        if score >= 2:
            return (
                "WATCH_BUY",
                (
                    "Fait bullish confirme par le marche. "
                    "Trigger: cassure resistance intraday. "
                    "Invalide si DXY reprend > +0.50% ou or recasse sous support."
                ),
            )
        return (
            "WAIT",
            (
                "Fait bullish sans validation marche. "
                "Attendre oil/DXY/taux dans le bon sens avant d'entrer."
            ),
        )

    if impact_bias == "bearish":
        if score >= 2:
            return (
                "WATCH_SELL",
                (
                    "Fait bearish confirme par le marche. "
                    "Trigger: rejet sous resistance intraday. "
                    "Invalide si DXY recasse ou or tient le support."
                ),
            )
        return (
            "WAIT",
            (
                "Fait bearish sans validation marche. "
                "Attendre DXY/taux/oil dans le bon sens."
            ),
        )

    # mixte ou info
    if score >= 3:
        return (
            "NO_TRADE",
            "Fait mixte avec signaux opposes: pas d'avantage directionnel clair. Re-evaluer dans 1h.",
        )
    return (
        "WAIT",
        "Fait mixte et confirmation insuffisante. Surveiller sans entrer.",
    )


# ---------------------------------------------------------------------------
# Deduplication semantique
# ---------------------------------------------------------------------------

def _normalize_for_dedup(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    stop = {"the", "a", "an", "of", "in", "on", "at", "to", "and", "or", "is",
            "are", "as", "by", "for", "with", "that", "this", "it", "its",
            "le", "la", "les", "de", "du", "des", "en", "et", "un", "une"}
    words = [w for w in text.split() if w not in stop and len(w) > 2]
    return " ".join(sorted(words[:8]))


def _jaccard_similarity(a: str, b: str) -> float:
    set_a = set(a.split())
    set_b = set(b.split())
    if not set_a and not set_b:
        return 1.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def deduplicate_news_facts(facts: list[NewsFact], threshold: float = 0.55) -> list[NewsFact]:
    """Garde le meilleur fait parmi les doublons semantiques.

    Le "meilleur" est celui avec le tier de source le plus bas (= plus fiable)
    et la confiance la plus haute.
    """
    if not facts:
        return []

    normalized = [_normalize_for_dedup(f.title) for f in facts]
    kept: list[NewsFact] = []
    used: set[int] = set()

    for i, fact in enumerate(facts):
        if i in used:
            continue
        group = [i]
        for j in range(i + 1, len(facts)):
            if j in used:
                continue
            sim = _jaccard_similarity(normalized[i], normalized[j])
            if sim >= threshold:
                group.append(j)
                used.add(j)
        # Garder le meilleur du groupe: tier le plus bas, puis confiance la plus haute
        best = min(group, key=lambda k: (facts[k].source_tier, -facts[k].confidence))
        kept.append(facts[best])

    return kept


# ---------------------------------------------------------------------------
# Constructeur principal
# ---------------------------------------------------------------------------

def build_news_fact(
    title: str,
    source: str,
    source_url: str,
    published_at: str,
    category: str,
    actors: list[str],
    locations: list[str],
    themes: list[str],
    confirmation_level: str,
    market_chain: str,
    gold_impact: str,
    impact_bias: str,
    confidence: int,
    *,
    wti_change: float | None = None,
    brent_change: float | None = None,
    dxy_change: float | None = None,
    rates_change_bps: float | None = None,
    gold_change: float | None = None,
) -> NewsFact:
    """Construit un NewsFact complet a partir des donnees disponibles."""
    source_tier, source_tier_label = classify_source_tier(source)
    fact_type = classify_fact_type(title, source, source_tier)
    why_it_matters = build_why_it_matters(category, themes, fact_type)
    market_conf = build_market_confirmation(
        category, themes, impact_bias,
        wti_change=wti_change,
        brent_change=brent_change,
        dxy_change=dxy_change,
        rates_change_bps=rates_change_bps,
        gold_change=gold_change,
    )
    trader_action, trader_action_detail = build_trader_action(
        impact_bias, market_conf, fact_type, confidence
    )

    return NewsFact(
        title=title,
        source=source,
        source_url=source_url,
        published_at=published_at,
        category=category,
        actors=actors,
        locations=locations,
        themes=themes,
        confirmation_level=confirmation_level,
        market_chain=market_chain,
        gold_impact=gold_impact,
        impact_bias=impact_bias,
        confidence=confidence,
        fact_type=fact_type,
        source_tier=source_tier,
        source_tier_label=source_tier_label,
        why_it_matters=why_it_matters,
        market_confirmation=market_conf,
        trader_action=trader_action,
        trader_action_detail=trader_action_detail,
    )
