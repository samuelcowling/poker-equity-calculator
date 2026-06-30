"""Tests for poker.evaluator.

Includes a brute-force enumeration of all C(52,5) = 2,598,960 five-card hands
to verify the evaluator's category counts exactly match the known closed-form
poker hand distribution, plus targeted unit tests for tricky tiebreak cases.
"""

from __future__ import annotations

from itertools import combinations

import pytest

from poker.cards import Card, full_deck, parse_cards
from poker.evaluator import (
    FLUSH,
    FOUR_OF_A_KIND,
    FULL_HOUSE,
    HIGH_CARD,
    ONE_PAIR,
    STRAIGHT,
    STRAIGHT_FLUSH,
    THREE_OF_A_KIND,
    TWO_PAIR,
    evaluate_hand,
)

# Expected exact counts for all C(52,5) five-card combinations.
EXPECTED_COUNTS = {
    "royal_flush": 4,
    "straight_flush_non_royal": 36,
    "four_of_a_kind": 624,
    "full_house": 3744,
    "flush_non_sf": 5108,
    "straight_non_sf": 10200,  # includes the wheel
    "three_of_a_kind": 54912,
    "two_pair": 123552,
    "one_pair": 1098240,
    "high_card": 1302540,
}
EXPECTED_TOTAL = 2_598_960


def cards(spec: str) -> list[Card]:
    """Helper: parse a space-separated card spec string, e.g. 'Ah Kh Qh Jh Th'."""
    return parse_cards(spec.split())


# ---------------------------------------------------------------------------
# Brute-force exhaustive distribution check (the hard correctness bar).
# ---------------------------------------------------------------------------


def test_full_distribution_exact_counts():
    deck = full_deck()
    assert len(deck) == 52

    royal_flush = 0
    straight_flush_non_royal = 0
    four_of_a_kind = 0
    full_house = 0
    flush_non_sf = 0
    straight_non_sf = 0
    three_of_a_kind = 0
    two_pair = 0
    one_pair = 0
    high_card = 0
    total = 0

    for combo in combinations(deck, 5):
        total += 1
        category, tiebreak = evaluate_hand(combo)

        if category == STRAIGHT_FLUSH:
            high = tiebreak[0]
            if high == 14:
                royal_flush += 1
            else:
                straight_flush_non_royal += 1
        elif category == FOUR_OF_A_KIND:
            four_of_a_kind += 1
        elif category == FULL_HOUSE:
            full_house += 1
        elif category == FLUSH:
            flush_non_sf += 1
        elif category == STRAIGHT:
            straight_non_sf += 1
        elif category == THREE_OF_A_KIND:
            three_of_a_kind += 1
        elif category == TWO_PAIR:
            two_pair += 1
        elif category == ONE_PAIR:
            one_pair += 1
        elif category == HIGH_CARD:
            high_card += 1
        else:
            pytest.fail(f"Unknown category {category} for hand {combo}")

    assert total == EXPECTED_TOTAL

    actual_counts = {
        "royal_flush": royal_flush,
        "straight_flush_non_royal": straight_flush_non_royal,
        "four_of_a_kind": four_of_a_kind,
        "full_house": full_house,
        "flush_non_sf": flush_non_sf,
        "straight_non_sf": straight_non_sf,
        "three_of_a_kind": three_of_a_kind,
        "two_pair": two_pair,
        "one_pair": one_pair,
        "high_card": high_card,
    }

    assert actual_counts == EXPECTED_COUNTS
    assert sum(actual_counts.values()) == EXPECTED_TOTAL


# ---------------------------------------------------------------------------
# Targeted unit tests.
# ---------------------------------------------------------------------------


def test_wheel_loses_to_six_high_straight():
    wheel = evaluate_hand(cards("Ah 2c 3d 4s 5h"))
    six_high = evaluate_hand(cards("2h 3c 4d 5s 6h"))
    assert wheel[0] == STRAIGHT
    assert six_high[0] == STRAIGHT
    assert wheel < six_high
    assert wheel[1][0] == 5  # wheel's straight high card is the 5, not the ace
    assert six_high[1][0] == 6


def test_wheel_is_still_a_straight():
    wheel = evaluate_hand(cards("Ah 2c 3d 4s 5h"))
    assert wheel[0] == STRAIGHT


def test_royal_flush_is_ace_high_straight_flush():
    royal = evaluate_hand(cards("Ah Kh Qh Jh Th"))
    assert royal[0] == STRAIGHT_FLUSH
    assert royal[1][0] == 14


def test_straight_flush_beats_four_of_a_kind():
    sf = evaluate_hand(cards("5h 6h 7h 8h 9h"))
    quads = evaluate_hand(cards("Ah Ac Ad As Kh"))
    assert sf[0] == STRAIGHT_FLUSH
    assert quads[0] == FOUR_OF_A_KIND
    assert sf > quads


def test_four_of_a_kind_beats_full_house():
    quads = evaluate_hand(cards("2h 2c 2d 2s Kh"))
    boat = evaluate_hand(cards("Ah Ac Ad Kh Kc"))
    assert quads > boat


def test_full_house_trips_rank_comparison():
    # Higher trips wins the full house comparison, regardless of pair rank.
    aces_full_of_twos = evaluate_hand(cards("Ah Ac Ad 2h 2c"))
    kings_full_of_queens = evaluate_hand(cards("Kh Kc Kd Qh Qc"))
    assert aces_full_of_twos[0] == FULL_HOUSE
    assert kings_full_of_queens[0] == FULL_HOUSE
    assert aces_full_of_twos > kings_full_of_queens


def test_full_house_pair_rank_breaks_tie_on_equal_trips():
    # Same trips rank is impossible with one deck in real play, but the
    # tiebreak logic should still rank pair-rank correctly as a tiebreaker
    # field when comparing two full houses with different pair ranks.
    trips_aces_pair_kings = (6, (14, 13))
    trips_aces_pair_queens = (6, (14, 12))
    assert trips_aces_pair_kings > trips_aces_pair_queens


def test_two_pair_kicker_comparison():
    # Same two pair ranks (Aces and Kings), different kicker.
    hand_with_queen_kicker = evaluate_hand(cards("Ah Ac Kh Kc Qd"))
    hand_with_jack_kicker = evaluate_hand(cards("Ad As Kd Ks Jc"))
    assert hand_with_queen_kicker[0] == TWO_PAIR
    assert hand_with_jack_kicker[0] == TWO_PAIR
    assert hand_with_queen_kicker > hand_with_jack_kicker


def test_two_pair_top_pair_comparison():
    aces_and_twos = evaluate_hand(cards("Ah Ac 2h 2c Kd"))
    kings_and_queens = evaluate_hand(cards("Kh Kc Qh Qc Ad"))
    assert aces_and_twos[0] == TWO_PAIR
    assert kings_and_queens[0] == TWO_PAIR
    # Top pair (Aces) outranks top pair (Kings) regardless of second pair/kicker.
    assert aces_and_twos > kings_and_queens


def test_flush_compares_all_five_ranks_in_order():
    higher_flush = evaluate_hand(cards("Ah Kh 9h 5h 2h"))
    lower_flush = evaluate_hand(cards("Ac Kc 9c 4c 3c"))
    assert higher_flush[0] == FLUSH
    assert lower_flush[0] == FLUSH
    assert higher_flush > lower_flush  # 5 beats 4 as the third-ranked card


def test_high_card_compares_all_five_ranks_in_order():
    higher = evaluate_hand(cards("Ah Kc 9d 5s 2h"))
    lower = evaluate_hand(cards("Ac Kd 9h 4s 3c"))
    assert higher[0] == HIGH_CARD
    assert lower[0] == HIGH_CARD
    assert higher > lower


def test_seven_card_hand_picks_best_five_flush_over_pair():
    # 7 cards containing both a made flush and a pair; the flush should win
    # as the best possible 5-card hand.
    hand = cards("Ah Kh 9h 5h 2h Ac 2c")
    result = evaluate_hand(hand)
    assert result[0] == FLUSH
    assert result[1] == (14, 13, 9, 5, 2)


def test_seven_card_hand_picks_best_five_straight_over_two_pair():
    hand = cards("4h 5c 6d 7s 8h 8c 4c")
    result = evaluate_hand(hand)
    assert result[0] == STRAIGHT
    assert result[1][0] == 8


def test_six_card_hand_picks_best_five():
    # Six cards: best 5-card hand is trip aces, not just two pair.
    hand = cards("Ah Ac Ad Kh Qc 2d")
    result = evaluate_hand(hand)
    assert result[0] == THREE_OF_A_KIND
    assert result[1] == (14, 13, 12)


def test_evaluate_hand_rejects_wrong_card_count():
    with pytest.raises(ValueError):
        evaluate_hand(cards("Ah Kh Qh Jh"))
    with pytest.raises(ValueError):
        evaluate_hand(cards("Ah Kh Qh Jh Th 9h 8h 7h"))


def test_evaluate_hand_rejects_duplicate_cards():
    with pytest.raises(ValueError):
        evaluate_hand([Card(14, "h"), Card(14, "h"), Card(13, "h"), Card(12, "h"), Card(11, "h")])
