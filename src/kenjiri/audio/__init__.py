"""Kenjiri audio layer: event-driven SFX + music engine (D11/D12/D24/D26).

All audio calls no-op cleanly when the mixer is unavailable — the game runs
silent rather than crashing (D24).
"""
from __future__ import annotations
