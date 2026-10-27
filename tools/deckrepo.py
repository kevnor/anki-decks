"""Shared plumbing: read decks.toml, find the decks, load their CrowdAnki exports.

Every tool in this repo goes through here, so there is one definition of what a
deck is and one place that knows where things live.

Needs Python 3.11 or later, or `pip install tomli` on 3.8 to 3.10.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        print(
            f"Reading decks.toml needs Python 3.11+ (you have {sys.version.split()[0]}) "
            "or the tomli package: pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(2) from None

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / "decks.toml"
TEMPLATES = Path(__file__).resolve().parent / "templates"

DECK_FILE = "deck.json"
MEDIA_DIR = "media"


class DeckRepoError(Exception):
    """Something is wrong with the repo itself, not with a card."""


@dataclass
class DeckSpec:
    """One entry from decks.toml, with defaults already merged in."""

    id: str
    title: str
    path: Path
    maintainer: str = ""
    reference: str = ""
    notes: str = ""
    required_tags: list[str] = field(default_factory=list)
    open_tags: list[str] = field(default_factory=list)
    tag_values: dict[str, list[str]] = field(default_factory=dict)
    min_front_chars: int = 15
    warn_back_chars: int = 260
    max_back_chars: int = 400
    max_cloze_deletions: int = 5
    scenario_types: list[str] = field(default_factory=list)
    min_scenario_share: float = 0.0
    max_notes: int = 0

    @property
    def deck_file(self) -> Path:
        return self.path / DECK_FILE

    @property
    def media_dir(self) -> Path:
        return self.path / MEDIA_DIR

    def load(self) -> dict:
        if not self.deck_file.exists():
            raise DeckRepoError(
                f"deck {self.id!r} is in decks.toml but {self.deck_file} does not exist"
            )
        try:
            data = json.loads(self.deck_file.read_text(encoding="utf8"))
        except json.JSONDecodeError as exc:
            raise DeckRepoError(f"{self.deck_file}: invalid JSON: {exc}") from exc
        if data.get("__type__") != "Deck":
            raise DeckRepoError(
                f"{self.deck_file}: not a CrowdAnki deck export "
                '(expected "__type__": "Deck"). Export from Anki with '
                "File > CrowdAnki: Export selected deck."
            )
        return data


SCALAR_DEFAULTS = (
    "min_front_chars",
    "warn_back_chars",
    "max_back_chars",
    "max_cloze_deletions",
    "min_scenario_share",
    "max_notes",
)
LIST_DEFAULTS = ("required_tags", "open_tags", "scenario_types")


def load_registry(registry: Path | None = None) -> list[DeckSpec]:
    """Read decks.toml and return every deck, defaults merged into each."""
    registry = registry or REGISTRY
    if not registry.exists():
        raise DeckRepoError(f"no deck registry at {registry}")

    raw = tomllib.loads(registry.read_text(encoding="utf8"))
    defaults = raw.get("defaults", {})
    default_tag_values = defaults.get("tag_values", {})

    entries = raw.get("decks", [])
    if not entries:
        raise DeckRepoError(f"{registry} lists no decks")

    specs: list[DeckSpec] = []
    seen: set[str] = set()
    for entry in entries:
        for required in ("id", "path"):
            if required not in entry:
                raise DeckRepoError(f"{registry}: a [[decks]] block is missing {required!r}")

        deck_id = entry["id"]
        if deck_id in seen:
            raise DeckRepoError(f"{registry}: duplicate deck id {deck_id!r}")
        seen.add(deck_id)

        tag_values = dict(default_tag_values)
        tag_values.update(entry.get("tag_values", {}))

        spec = DeckSpec(
            id=deck_id,
            title=entry.get("title", deck_id),
            path=(REPO_ROOT / entry["path"]).resolve(),
            maintainer=entry.get("maintainer", ""),
            reference=entry.get("reference", ""),
            notes=entry.get("notes", ""),
            tag_values=tag_values,
        )
        for key in SCALAR_DEFAULTS:
            value = entry.get(key, defaults.get(key))
            if value is not None:
                setattr(spec, key, value)
        for key in LIST_DEFAULTS:
            value = entry.get(key, defaults.get(key))
            if value is not None:
                setattr(spec, key, list(value))

        specs.append(spec)

    return specs


def select(specs: list[DeckSpec], wanted: list[str] | None) -> list[DeckSpec]:
    """Filter the registry by deck id. Matching is case-insensitive."""
    if not wanted:
        return specs
    by_id = {s.id.casefold(): s for s in specs}
    chosen: list[DeckSpec] = []
    for name in wanted:
        spec = by_id.get(name.casefold())
        if spec is None:
            known = ", ".join(s.id for s in specs)
            raise DeckRepoError(f"unknown deck {name!r}. Known decks: {known}")
        chosen.append(spec)
    return chosen


def canonical_note_models() -> list[dict]:
    """The repo-wide note types, with their stable uuids."""
    return json.loads((TEMPLATES / "note_models.json").read_text(encoding="utf8"))


def canonical_deck_config() -> dict:
    """The repo-wide deck options preset, with its stable uuid."""
    return json.loads((TEMPLATES / "deck_config.json").read_text(encoding="utf8"))


def collect_notes(deck: dict) -> list[dict]:
    """Every note in a deck and its subdecks."""
    found = list(deck.get("notes", []))
    for child in deck.get("children", []):
        found.extend(collect_notes(child))
    return found


def walk_decks(deck: dict, prefix: str = "") -> list[tuple[str, dict]]:
    """Flatten a deck tree into (full Anki deck name, node) pairs."""
    name = f"{prefix}::{deck['name']}" if prefix else deck["name"]
    out = [(name, deck)]
    for child in deck.get("children", []):
        out.extend(walk_decks(child, name))
    return out


def canonical_json(data: dict | list) -> str:
    """Exactly how CrowdAnki writes a deck file."""
    return json.dumps(data, sort_keys=True, indent=4, ensure_ascii=False) + "\n"


def add_deck_arguments(parser) -> None:
    """The --deck flag, shared by every tool."""
    parser.add_argument(
        "-d",
        "--deck",
        action="append",
        metavar="ID",
        help="limit to this deck id from decks.toml (repeatable; default: all decks)",
    )


def resolve(args) -> list[DeckSpec]:
    return select(load_registry(), getattr(args, "deck", None))
