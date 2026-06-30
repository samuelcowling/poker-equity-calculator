"""From-scratch Texas Hold'em hand evaluator.

Given 5, 6, or 7 Card objects, finds the BEST 5-card poker hand achievable and
returns a HandRank: a tuple of (category_rank, tiebreakers...) that is directly
comparable with the standard operators (<, >, ==, ...). Higher HandRank wins.

No external poker library is used - hand categorization and tiebreaking are
implemented directly from rank/suit counting.

Category ranks (higher is better):
    0 = high card
    1 = one pair
    2 = two pair
    3 = three of a kind
    4 = straight
    5 = flush
    6 = full house
    7 = four of a kind
    8 = straight flush (royal flush is just the A-high straight flush)
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Sequence

from poker.cards import Card

HIGH_CARD = 0
ONE_PAIR = 1
TWO_PAIR = 2
THREE_OF_A_KIND = 3
STRAIGHT = 4
FLUSH = 5
FULL_HOUSE = 6
FOUR_OF_A_KIND = 7
STRAIGHT_FLUSH = 8

CATEGORY_NAMES: dict[int, str] = {
    HIGH_CARD: "high card",
    ONE_PAIR: "one pair",
    TWO_PAIR: "two pair",
    THREE_OF_A_KIND: "three of a kind",
    STRAIGHT: "straight",
    FLUSH: "flush",
    FULL_HOUSE: "full house",
    FOUR_OF_A_KIND: "four of a kind",
    STRAIGHT_FLUSH: "straight flush",
}

# HandRank: (category, tiebreaker_tuple). Tuples compare lexicographically,
# which gives correct tiebreaking automatically as long as tiebreaker_tuple
# ranks are listed in order of significance (most significant first).
HandRank = tuple[int, tuple[int, ...]]


def category_name(hand_rank: HandRank) -> str:
    return CATEGORY_NAMES[hand_rank[0]]


def _straight_high(distinct_ranks_desc: list[int]) -> int | None:
    """Given distinct rank values sorted descending, return the high card of
    the best straight present, or None if no straight exists. Handles the
    wheel (A-2-3-4-5), whose high card is treated as 5 (ranks below a 6-high
    straight) per standard poker rules.
    """
    ranks = set(distinct_ranks_desc)
    # Treat an Ace (14) as also playing low (1) for wheel detection.
    if 14 in ranks:
        ranks.add(1)

    # Check every possible 5-in-a-row window, from highest to lowest, so the
    # first match found is the best straight.
    for high in range(14, 4, -1):  # 14 down to 5
        window = {high, high - 1, high - 2, high - 3, high - 4}
        if window.issubset(ranks):
            return high
    return None


def evaluate_hand(cards: Sequence[Card]) -> HandRank:
    """Evaluate the best 5-card hand from 5, 6, or 7 cards.

    Returns a HandRank tuple comparable with standard operators; higher wins.
    """
    n = len(cards)
    if n < 5 or n > 7:
        raise ValueError(f"evaluate_hand requires 5-7 cards, got {n}")
    if len(set(cards)) != n:
        raise ValueError(f"Duplicate cards passed to evaluate_hand: {cards}")

    if n == 5:
        return _evaluate_five(cards)

    best: HandRank | None = None
    for combo in combinations(cards, 5):
        rank = _evaluate_five(combo)
        if best is None or rank > best:
            best = rank
    assert best is not None
    return best


def _evaluate_five(cards: Sequence[Card]) -> HandRank:
    """Evaluate exactly 5 cards into a HandRank."""
    ranks = [c.rank for c in cards]
    suits = [c.suit for c in cards]

    is_flush = len(set(suits)) == 1

    distinct_ranks_desc = sorted(set(ranks), reverse=True)
    straight_high = _straight_high(distinct_ranks_desc)
    is_straight = straight_high is not None and len(distinct_ranks_desc) == 5

    if is_straight and is_flush:
        return (STRAIGHT_FLUSH, (straight_high,))

    rank_counts = Counter(ranks)
    # Sort by (count desc, rank desc) so e.g. trips before pair before kickers,
    # and within equal counts, higher rank first.
    groups = sorted(rank_counts.items(), key=lambda item: (-item[1], -item[0]))
    counts = [count for _, count in groups]
    group_ranks = [rank for rank, _ in groups]

    if counts == [4, 1]:
        return (FOUR_OF_A_KIND, tuple(group_ranks))
    if counts == [3, 2]:
        return (FULL_HOUSE, tuple(group_ranks))
    if is_flush:
        return (FLUSH, tuple(sorted(ranks, reverse=True)))
    if is_straight:
        return (STRAIGHT, (straight_high,))
    if counts == [3, 1, 1]:
        return (THREE_OF_A_KIND, tuple(group_ranks))
    if counts == [2, 2, 1]:
        return (TWO_PAIR, tuple(group_ranks))
    if counts == [2, 1, 1, 1]:
        return (ONE_PAIR, tuple(group_ranks))
    return (HIGH_CARD, tuple(sorted(ranks, reverse=True)))
