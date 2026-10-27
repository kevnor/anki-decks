#!/usr/bin/env python3
"""Scaffold a new deck: registry entry plus an empty CrowdAnki export.

Usage:
    python tools/new_deck.py AZ-104 \
        --title "Microsoft Azure Administrator" \
        --domain identity --domain storage --domain compute --domain networking \
        --maintainer "Kevin Nordnes" \
        --reference https://learn.microsoft.com/.../az-104

Then, in Anki:
    File > CrowdAnki: Import from disk  ->  deck/AZ-104

The deck arrives empty, with the repo's shared note types already attached, so
your first card is written against the same templates as every other deck.

Domains are the deck's own `domain::` tag values. For an exam, use its skill
areas. For a topic deck, use whatever divisions you would filter on later.
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from pathlib import Path

try:
    from . import deckrepo  # type: ignore[attr-defined]
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import deckrepo

from deckrepo import (
    REGISTRY,
    REPO_ROOT,
    DeckRepoError,
    canonical_deck_config,
    canonical_json,
    canonical_note_models,
    load_registry,
)

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def build_empty_deck(deck_id: str, description: str) -> dict:
    """A CrowdAnki export with the shared note types and no notes."""
    config = canonical_deck_config()
    return {
        "__type__": "Deck",
        "children": [],
        "crowdanki_uuid": str(uuid.uuid4()),
        "deck_config_uuid": config["crowdanki_uuid"],
        "deck_configurations": [config],
        "desc": description,
        "desiredRetention": None,
        "dyn": 0,
        "extendNew": 0,
        "extendRev": 0,
        "media_files": [],
        "name": deck_id,
        "newLimit": None,
        "newLimitToday": None,
        "note_models": canonical_note_models(),
        "notes": [],
        "reviewLimit": None,
        "reviewLimitToday": None,
    }


def registry_block(args, path: str) -> str:
    lines = [
        "",
        "",
        "[[decks]]",
        f'id = "{args.deck_id}"',
        f'title = "{escape(args.title)}"',
        f'path = "{path}"',
    ]
    if args.maintainer:
        lines.append(f'maintainer = "{escape(args.maintainer)}"')
    if args.reference:
        lines.append(f'reference = "{escape(args.reference)}"')
    if args.notes:
        lines.append(f'notes = "{escape(args.notes)}"')
    lines.append("")
    lines.append("[decks.tag_values]")
    domains = ", ".join(f'"{escape(d)}"' for d in args.domain)
    lines.append(f"domain = [{domains}]")
    return "\n".join(lines) + "\n"


def escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("deck_id", help="short id, used as the Anki deck name and the .apkg name (e.g. AZ-104)")
    parser.add_argument("--title", default="", help="full name of the exam or topic")
    parser.add_argument(
        "--domain",
        action="append",
        default=[],
        required=True,
        metavar="VALUE",
        help="an allowed domain:: tag value (repeat for each)",
    )
    parser.add_argument("--maintainer", default="")
    parser.add_argument("--reference", default="", help="link to the study guide or syllabus")
    parser.add_argument("--notes", default="", help="one line of context for the registry")
    parser.add_argument("--path", default="", help="defaults to deck/<id>")
    args = parser.parse_args(argv)

    if not ID_RE.match(args.deck_id):
        print(
            f"new_deck: {args.deck_id!r} is not a usable id "
            "(letters, digits, dot, dash and underscore only)",
            file=sys.stderr,
        )
        return 2

    args.title = args.title or args.deck_id

    try:
        existing = load_registry()
    except DeckRepoError as exc:
        print(f"new_deck: {exc}", file=sys.stderr)
        return 2

    if any(spec.id.casefold() == args.deck_id.casefold() for spec in existing):
        print(f"new_deck: deck {args.deck_id!r} is already in decks.toml", file=sys.stderr)
        return 1

    rel_path = args.path or f"deck/{args.deck_id}"
    deck_dir = (REPO_ROOT / rel_path).resolve()
    if deck_dir.exists() and any(deck_dir.iterdir()):
        print(f"new_deck: {deck_dir} already exists and is not empty", file=sys.stderr)
        return 1

    description = (
        f"{args.title}. Shared deck for mnemonic trainees. "
        "Import with CrowdAnki; read the repo README before adding cards."
    )

    (deck_dir / "media").mkdir(parents=True, exist_ok=True)
    (deck_dir / "media" / ".gitkeep").touch()
    (deck_dir / "deck.json").write_text(
        canonical_json(build_empty_deck(args.deck_id, description)), encoding="utf8"
    )

    with REGISTRY.open("a", encoding="utf8") as handle:
        handle.write(registry_block(args, rel_path))

    print(f"created {deck_dir.relative_to(REPO_ROOT)}/deck.json")
    print(f"added  [[decks]] {args.deck_id} to decks.toml")
    print()
    print("Next:")
    print(f"  1. In Anki: File > CrowdAnki: Import from disk  ->  {rel_path}")
    print(f"  2. Write cards in the {args.deck_id} deck, tagged domain:: and type::")
    print(f"  3. File > CrowdAnki: Export selected deck  ->  the repo's deck/ directory")
    print(f"  4. python tools/lint_cards.py --deck {args.deck_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
