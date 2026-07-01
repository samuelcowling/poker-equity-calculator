"""Bet-sizing advice derived from equity.

Maps a hero's total equity (win % plus half of tie %) to a suggested bet
size as a percentage of the pot, following a simple exploitative heuristic
tuned for a shallow-stack home game:

    >= 75%   Strong value  -> bet big (75-100% pot)
    55-75%   Good value    -> bet for value (50-66% pot)
    40-55%   Marginal/draw -> semi-bluff sized bet (50-65% pot)
    < 40%    Weak / air    -> check

Never recommends a small "probe" bet (under ~50% pot) - at short stacks
those mostly just let opponents realize equity cheaply. Against loose,
calling-heavy opponents (the default assumption for a casual home game),
value tiers are bumped up further since bets get paid off more often.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_BASE_TIERS = (
    # (min_equity_pct, tier_name, action, low_pot_pct, high_pot_pct, rationale)
    (75.0, "Strong value", "bet", 75.0, 100.0,
     "Big made hand — bet for protection and maximum value."),
    (55.0, "Good value", "bet", 50.0, 66.0,
     "Solid hand — bet for value while keeping worse hands in."),
    (40.0, "Marginal / drawing", "bet", 50.0, 65.0,
     "Marginal equity or a drawing hand — a semi-bluff-sized bet builds the "
     "pot and can win outright if everyone folds."),
    (0.0, "Weak / air", "check", 0.0, 0.0,
     "Little equity — checking is usually best. Only bluff occasionally, "
     "and size it the same as your value bets when you do."),
)

# Loose/calling-opponent adjustment: (extra_low_pct, extra_high_pct, note) per bet tier.
_LOOSE_BUMP = {
    "Strong value": (15.0, 25.0, "Bumped up — calling-station opponents pay off bigger bets."),
    "Good value": (15.0, 19.0, "Bumped up — bet bigger for value against opponents who call too much."),
    "Marginal / drawing": (0.0, 0.0, "Sizing unchanged, but expect less fold equity from calling opponents."),
    "Weak / air": (0.0, 0.0, "Bluffing rarely works against calling-station opponents — check and give up."),
}

MAX_POT_PCT = 125.0


def _round_to_nearest(value: float, increment: float) -> float:
    """Round `value` to the nearest multiple of `increment` (half-up)."""
    if increment <= 0:
        return value
    return math.floor(value / increment + 0.5) * increment


@dataclass(frozen=True)
class BetAdvice:
    equity_pct: float
    tier: str
    action: str  # "bet" or "check"
    pot_pct_low: float
    pot_pct_high: float
    suggested_amount: float | None  # None when action == "check"
    rationale: str


def suggest_bet(
    equity_pct: float,
    pot_size: float,
    *,
    loose_opponents: bool = True,
    chip_increment: float = 0.5,
) -> BetAdvice:
    """Suggest a bet size given hero's total equity and the current pot size.

    `equity_pct` should be total equity on a 0-100 scale (win % + half of tie
    %, not raw win %) - ties return half the pot, so they count as partial
    equity for sizing purposes. `pot_size` is in dollars (or any consistent
    currency unit). `chip_increment` rounds the suggested dollar amount to
    the nearest playable chip denomination (default $0.50).
    """
    if pot_size < 0:
        raise ValueError(f"pot_size cannot be negative: {pot_size}")

    for min_equity, tier, action, low, high, rationale in _BASE_TIERS:
        if equity_pct >= min_equity:
            break
    else:  # pragma: no cover - _BASE_TIERS always has a 0.0 floor
        min_equity, tier, action, low, high, rationale = _BASE_TIERS[-1]

    note = None
    if loose_opponents:
        bump_low, bump_high, note = _LOOSE_BUMP[tier]
        low = min(low + bump_low, MAX_POT_PCT)
        high = min(high + bump_high, MAX_POT_PCT)

    rationale_text = rationale if note is None else f"{rationale} {note}"

    if action == "check":
        return BetAdvice(equity_pct, tier, action, 0.0, 0.0, None, rationale_text)

    mid_pct = (low + high) / 2
    suggested_amount = _round_to_nearest(pot_size * mid_pct / 100, chip_increment)
    return BetAdvice(equity_pct, tier, action, low, high, suggested_amount, rationale_text)
