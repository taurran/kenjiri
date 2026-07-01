"""Tests for kenjiri.game.bag — 7-bag randomizer per D3.

Every bag of 7 draws contains each of the 7 piece kinds exactly once;
``peek`` never consumes.
"""
from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kenjiri.game.bag import SevenBag
from kenjiri.game.pieces import PIECE_KINDS

ALL_KINDS = set(PIECE_KINDS)


def test_thousand_draws_every_aligned_window_is_a_full_bag() -> None:
    """1000 draws from SevenBag(Random(42)): every consecutive 7-window
    aligned to bag boundaries contains all 7 kinds exactly once."""
    bag = SevenBag(random.Random(42))
    draws = [bag.next() for _ in range(1000)]
    for start in range(0, 994, 7):  # 142 complete bags
        window = draws[start : start + 7]
        assert set(window) == ALL_KINDS, f"bag at {start} broken: {window}"
        assert len(window) == len(set(window))


def test_exact_distribution_per_bag() -> None:
    """Distribution is exact per bag: over 142 complete bags each kind
    appears exactly 142 times."""
    bag = SevenBag(random.Random(42))
    counts = Counter(bag.next() for _ in range(994))
    assert counts == {kind: 142 for kind in PIECE_KINDS}


def test_bags_are_shuffled_not_constant_order() -> None:
    """The injected rng shuffles each bag: 142 bags are not all identical."""
    bag = SevenBag(random.Random(42))
    bags = [tuple(bag.next() for _ in range(7)) for _ in range(142)]
    assert len(set(bags)) > 1


def test_same_seed_reproduces_sequence() -> None:
    a = SevenBag(random.Random(7))
    b = SevenBag(random.Random(7))
    assert [a.next() for _ in range(70)] == [b.next() for _ in range(70)]


def test_peek_default_returns_one() -> None:
    bag = SevenBag(random.Random(1))
    peeked = bag.peek()
    assert isinstance(peeked, list)
    assert len(peeked) == 1


def test_peek_twice_identical_no_consumption() -> None:
    """Negative: peek twice in a row returns identical sequences."""
    bag = SevenBag(random.Random(42))
    first = bag.peek(10)
    second = bag.peek(10)
    assert first == second
    assert len(first) == 10


def test_peek_matches_subsequent_next() -> None:
    """What peek shows is exactly what next() then delivers."""
    bag = SevenBag(random.Random(42))
    peeked = bag.peek(15)
    assert [bag.next() for _ in range(15)] == peeked


def test_peek_across_bag_boundary_preserves_distribution() -> None:
    """Peeking past a bag boundary pre-fills without corrupting bags."""
    bag = SevenBag(random.Random(3))
    bag.peek(20)
    draws = [bag.next() for _ in range(21)]
    for start in (0, 7, 14):
        assert set(draws[start : start + 7]) == ALL_KINDS
