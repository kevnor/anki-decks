#!/usr/bin/env python3
"""Show every deck in the registry and its current state.

Usage:
    python tools/list_decks.py
    python tools/list_decks.py --deck SC-500
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from . import deckrepo  # type: ignore[attr-defined]
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import deckrepo

from deckrepo import REPO_ROOT, DeckRepoError, collect_notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    deckrepo.add_deck_arguments(parser)
    args = parser.parse_args(argv)

    try:
        specs = deckrepo.resolve(args)
    except DeckRepoError as exc:
        print(f"list: {exc}", file=sys.stderr)
        return 2

    rows = []
    for spec in specs:
        try:
            deck = spec.load()
            count = str(len(collect_notes(deck)))
        except DeckRepoError as exc:
            count = f"! {exc}"
        rows.append((spec.id, count, str(spec.path.relative_to(REPO_ROOT)), spec.title))

    width_id = max(len("DECK"), *(len(r[0]) for r in rows))
    width_n = max(len("NOTES"), *(len(r[1]) for r in rows))
    width_p = max(len("PATH"), *(len(r[2]) for r in rows))

    print(f"{'DECK':<{width_id}}  {'NOTES':>{width_n}}  {'PATH':<{width_p}}  TITLE")
    for deck_id, count, path, title in rows:
        print(f"{deck_id:<{width_id}}  {count:>{width_n}}  {path:<{width_p}}  {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
