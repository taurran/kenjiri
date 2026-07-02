"""``python -m kenjiri`` — run the game, or ``--smoke`` for the headless
self-check used by CI and the packaged-exe verification (T7)."""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the game (or the smoke self-check).

    Args:
        argv: Argument list override for tests; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(
        prog="kenjiri", description="Kenjiri - a chibi-corgi block puzzle"
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="headless self-check: init everything, render one frame of "
        "every scene offscreen, exit 0",
    )
    args = parser.parse_args(argv)
    if args.smoke:
        from kenjiri.ui.app import run_smoke

        return run_smoke()
    from kenjiri.ui.app import App

    return App().run()


if __name__ == "__main__":
    sys.exit(main())
