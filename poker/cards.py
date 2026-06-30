"""Core card model: Card parsing, hand-spec parsing, and the Deck abstraction.

Card notation:
    ranks: 2 3 4 5 6 7 8 9 T J Q K A   (case-insensitive on input, normalized internally)
    suits: s h d c                     (spades, hearts, diamonds, clubs; case-insensitive)

Examples: "Ah" = Ace of hearts, "Td" = Ten of diamonds, "2c" = Two of clubs.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Sequence

# Ranks ordered low -> high. Index into this tuple is used as the integer rank value.
RANKS: tuple[str, ...] = ("2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A")
RANK_VALUES: dict[str, int] = {rank: i for i, rank in enumerate(RANKS, start=2)}  # '2' -> 2 ... 'A' -> 14

SUITS: tuple[str, ...] = ("s", "h", "d", "c")
SUIT_NAMES: dict[str, str] = {"s": "spades", "h": "hearts", "d": "diamonds", "c": "clubs"}


class CardParseError(ValueError):
    """Raised when a card string or hand spec cannot be parsed."""


@dataclass(frozen=True, order=False)
class Card:
    """A single playing card.

    `rank` is an int from 2-14 (2..10, J=11, Q=12, K=13, A=14).
    `suit` is one of 's', 'h', 'd', 'c'.
    """

    rank: int
    suit: str

    def __post_init__(self) -> None:
        if self.rank not in range(2, 15):
            raise CardParseError(f"Invalid card rank value: {self.rank!r}")
        if self.suit not in SUITS:
            raise CardParseError(f"Invalid card suit: {self.suit!r}")

    @property
    def rank_char(self) -> str:
        return RANKS[self.rank - 2]

    def __str__(self) -> str:
        return f"{self.rank_char}{self.suit}"

    def __repr__(self) -> str:
        return f"Card({self.rank_char}{self.suit})"

    def __lt__(self, other: "Card") -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return (self.rank, self.suit) < (other.rank, other.suit)


def parse_card(text: str) -> Card:
    """Parse a single card string like 'Ah', 'td', '2C' into a Card.

    Raises CardParseError on malformed input.
    """
    if not isinstance(text, str):
        raise CardParseError(f"Card must be a string, got {type(text).__name__}")

    cleaned = text.strip()
    if len(cleaned) != 2:
        raise CardParseError(
            f"Invalid card notation {text!r}: expected exactly 2 characters (rank+suit)"
        )

    rank_char, suit_char = cleaned[0].upper(), cleaned[1].lower()

    if rank_char not in RANK_VALUES:
        raise CardParseError(
            f"Invalid card notation {text!r}: unknown rank {cleaned[0]!r} "
            f"(expected one of {', '.join(RANKS)})"
        )
    if suit_char not in SUITS:
        raise CardParseError(
            f"Invalid card notation {text!r}: unknown suit {cleaned[1]!r} "
            f"(expected one of {', '.join(SUITS)})"
        )

    return Card(rank=RANK_VALUES[rank_char], suit=suit_char)


def parse_cards(card_strings: Sequence[str], *, context: str = "hand") -> list[Card]:
    """Parse a list of card strings into Card objects.

    Raises CardParseError on any invalid notation or on duplicate cards within
    this list (e.g. ["Ah", "Ah"]). `context` is included in error messages to
    help identify which input group (hero hole cards, board, dead cards, ...)
    failed validation.
    """
    cards: list[Card] = []
    seen: set[Card] = set()
    for raw in card_strings:
        card = parse_card(raw)
        if card in seen:
            raise CardParseError(f"Duplicate card {card} in {context}: {list(card_strings)}")
        seen.add(card)
        cards.append(card)
    return cards


def full_deck() -> list[Card]:
    """Return all 52 cards of a standard deck, in a fixed (rank, then suit) order."""
    return [Card(rank=r, suit=s) for r in range(2, 15) for s in SUITS]


class Deck:
    """Represents the unseen portion of a standard 52-card deck.

    Given a collection of "known" cards (hero hole cards, board cards, and
    dead/burned cards the user has marked as no longer in play), the Deck
    exposes only the remaining unseen cards, and can deal/sample from them
    without replacement. Known cards (including dead cards) are excluded from
    the unseen pool exactly the same way - the deck has no notion of "dead"
    cards once they're removed, it simply never sees them again.
    """

    def __init__(self, known_cards: Iterable[Card] = ()):
        known_list = list(known_cards)
        known_set = set(known_list)
        if len(known_set) != len(known_list):
            # Find the offending duplicate for a clear error message.
            seen: set[Card] = set()
            for card in known_list:
                if card in seen:
                    raise CardParseError(f"Duplicate known card {card} passed to Deck")
                seen.add(card)

        self._known: set[Card] = known_set
        self._unseen: list[Card] = [c for c in full_deck() if c not in known_set]

    @property
    def known_cards(self) -> frozenset[Card]:
        return frozenset(self._known)

    @property
    def unseen_cards(self) -> list[Card]:
        """All remaining unseen cards, in fixed deck order (rank, then suit)."""
        return list(self._unseen)

    def __len__(self) -> int:
        return len(self._unseen)

    def deal(self, n: int, rng: random.Random | None = None) -> list[Card]:
        """Sample `n` distinct cards at random from the unseen pool, without
        replacement and without mutating the Deck's remaining pool.

        Uses `rng` (a random.Random instance) if provided, else the module-level
        `random` functions. Raises ValueError if `n` exceeds the number of
        unseen cards.
        """
        if n < 0:
            raise ValueError(f"Cannot deal a negative number of cards: {n}")
        if n > len(self._unseen):
            raise ValueError(
                f"Cannot deal {n} cards: only {len(self._unseen)} unseen cards remain"
            )
        sampler = rng if rng is not None else random
        return sampler.sample(self._unseen, n)

    def remove(self, cards: Iterable[Card]) -> None:
        """Permanently remove the given cards from the unseen pool (e.g. after
        dealing them out for real, as opposed to a hypothetical sample)."""
        cards = list(cards)
        missing = [c for c in cards if c not in set(self._unseen)]
        if missing:
            raise ValueError(f"Cannot remove cards not in unseen pool: {missing}")
        remove_set = set(cards)
        self._unseen = [c for c in self._unseen if c not in remove_set]
        self._known |= remove_set

    def __contains__(self, card: Card) -> bool:
        return card in self._unseen

    def __repr__(self) -> str:
        return f"Deck(unseen={len(self._unseen)}, known={len(self._known)})"
