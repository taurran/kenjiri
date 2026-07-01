"""7-bag piece randomizer for Kenjiri (D3).

Pure logic — no pygame. Every bag of 7 draws contains each of the 7 piece
kinds exactly once, order shuffled by the injected ``random.Random``.
"""
from __future__ import annotations

import itertools
import random
from collections import deque

from .pieces import PIECE_KINDS, PieceKind


class SevenBag:
    """7-bag randomizer: deals shuffled permutations of all 7 piece kinds.

    Each exhausted bag is refilled with a fresh permutation of the 7 kinds
    shuffled by the injected RNG, so every aligned window of 7 draws contains
    every kind exactly once (D3). Determinism is fully owned by the caller
    via the ``rng`` seed.
    """

    def __init__(self, rng: random.Random) -> None:
        """Create a bag driven by ``rng`` (inject a seeded ``random.Random``
        for reproducible sequences)."""
        self._rng = rng
        self._queue: deque[PieceKind] = deque()

    def _refill(self) -> None:
        """Append one freshly shuffled bag of all 7 kinds to the queue."""
        bag = list(PIECE_KINDS)
        self._rng.shuffle(bag)
        self._queue.extend(bag)

    def next(self) -> PieceKind:
        """Draw and consume the next piece kind."""
        if not self._queue:
            self._refill()
        return self._queue.popleft()

    def peek(self, n: int = 1) -> list[PieceKind]:
        """Return the next ``n`` piece kinds WITHOUT consuming them.

        Peeking past the current bag boundary pre-generates future bags in
        the same order ``next()`` would, so repeated peeks are identical and
        subsequent draws match exactly what was peeked.
        """
        if n < 0:
            raise ValueError(f"peek count must be non-negative, got {n}")
        while len(self._queue) < n:
            self._refill()
        return list(itertools.islice(self._queue, n))
