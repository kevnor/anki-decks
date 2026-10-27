#!/usr/bin/env python3
"""Rewrite each deck.json in CrowdAnki's canonical format (sort_keys, indent 4).

CrowdAnki already writes this format, so you only need this if an editor or a
merge has reflowed a file. CI runs it with --check.

Usage:
    python tools/format_deck.py                 # fix every deck
    python tools/format_deck.py --check         # report, change nothing
    python tools/format_deck.py --deck SC-500
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from . import deckrepo  # type: ignore[attr-defined]
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import deckrepo

from deckrepo import DeckRepoError, canonical_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    deckrepo.add_deck_arguments(parser)
    parser.add_argument("--check", action="store_true", help="exit non-zero instead of rewriting")
    args = parser.parse_args(argv)

    try:
        specs = deckrepo.resolve(args)
    except DeckRepoError as exc:
        print(f"format: {exc}", file=sys.stderr)
        return 2

    offenders = 0
    for spec in specs:
        if not spec.deck_file.exists():
            print(f"  {spec.id}: MISSING {spec.deck_file}", file=sys.stderr)
            return 2

        original = spec.deck_file.read_text(encoding="utf8")
        try:
            canonical = canonical_json(json.loads(original))
        except json.JSONDecodeError as exc:
            print(f"  {spec.id}: invalid JSON: {exc}", file=sys.stderr)
            return 2

        if original == canonical:
            print(f"  {spec.id}: canonical")
            continue

        offenders += 1
        if args.check:
            print(f"  {spec.id}: NOT canonical")
        else:
            spec.deck_file.write_text(canonical, encoding="utf8")
            print(f"  {spec.id}: reformatted")

    if args.check and offenders:
        print(
            f"\n{offenders} deck file(s) are not in CrowdAnki's format. "
            "Run: python tools/format_deck.py",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
