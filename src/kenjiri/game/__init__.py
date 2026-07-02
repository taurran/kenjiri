"""Kenjiri core game logic — pure, headless, no pygame imports.

Matrix convention (D25): columns 1-10 left-to-right, rows 1-22 bottom-up.
Rows 1-20 are visible; rows 21-22 are the hidden Buffer. A cell is
``(col, row)``.
"""
