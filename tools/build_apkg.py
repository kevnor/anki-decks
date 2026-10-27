#!/usr/bin/env python3
"""Build an .apkg for each deck in the registry.

Usage:
    python tools/build_apkg.py                      # every deck -> dist/<id>.apkg
    python tools/build_apkg.py --deck SC-500
    python tools/build_apkg.py --out-dir build

The .apkg is a convenience for people who have not installed CrowdAnki. The
CrowdAnki JSON remains the source of truth: importing the JSON is what keeps
your scheduling when the deck is updated.

Note guids and the shared note-type uuids are carried over, so Anki matches
existing notes and existing note types rather than adding copies.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

try:
    import genanki
except ImportError:  # pragma: no cover
    print("build: genanki is not installed (pip install -r requirements.txt)", file=sys.stderr)
    raise SystemExit(2)

try:
    from . import deckrepo  # type: ignore[attr-defined]
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import deckrepo

from deckrepo import DeckRepoError, DeckSpec, walk_decks


def stable_id(uuid: str) -> int:
    """A deterministic Anki id derived from a CrowdAnki uuid.

    Deriving it means the same deck always builds to the same ids, so a rebuilt
    .apkg updates an existing import instead of landing beside it.
    """
    digest = hashlib.sha256(uuid.encode("utf8")).digest()
    return (1 << 30) + (int.from_bytes(digest[:4], "big") % (1 << 30))


def build_model(model_json: dict) -> genanki.Model:
    is_cloze = model_json.get("type") == 1
    return genanki.Model(
        model_id=stable_id(model_json["crowdanki_uuid"]),
        name=model_json["name"],
        fields=[{"name": f["name"]} for f in model_json["flds"]],
        templates=[
            {"name": t["name"], "qfmt": t["qfmt"], "afmt": t["afmt"]}
            for t in model_json["tmpls"]
        ],
        css=model_json.get("css", ""),
        model_type=genanki.Model.CLOZE if is_cloze else genanki.Model.FRONT_BACK,
        sort_field_index=model_json.get("sortf", 0),
    )


class GuidNote(genanki.Note):
    """A note whose guid comes from the JSON instead of being derived."""

    def __init__(self, *args, guid: str, **kwargs):
        super().__init__(*args, **kwargs)
        self._explicit_guid = guid

    @property
    def guid(self):  # type: ignore[override]
        return self._explicit_guid

    @guid.setter
    def guid(self, value):  # genanki's __init__ assigns to this
        self._explicit_guid = value


def build_one(spec: DeckSpec, out_dir: Path) -> tuple[Path, int]:
    root = spec.load()
    models = {m["crowdanki_uuid"]: build_model(m) for m in root.get("note_models", [])}

    decks: list[genanki.Deck] = []
    note_count = 0
    for full_name, node in walk_decks(root):
        anki_deck = genanki.Deck(stable_id(node["crowdanki_uuid"]), full_name)
        anki_deck.description = node.get("desc", "")
        for note in node.get("notes", []):
            model = models.get(note["note_model_uuid"])
            if model is None:
                raise DeckRepoError(
                    f"{spec.id}: note {note.get('guid')} references unknown note type "
                    f"{note['note_model_uuid']}"
                )
            anki_deck.add_note(
                GuidNote(
                    model=model,
                    fields=list(note["fields"]),
                    tags=list(note.get("tags", [])),
                    guid=note["guid"],
                )
            )
            note_count += 1
        decks.append(anki_deck)

    media_files: list[str] = []
    if spec.media_dir.is_dir():
        media_files = [
            str(p)
            for p in sorted(spec.media_dir.iterdir())
            if p.is_file() and not p.name.startswith(".")
        ]

    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{spec.id}.apkg"
    package = genanki.Package(decks)
    package.media_files = media_files
    package.write_to_file(str(output))

    print(
        f"  {spec.id}: {note_count} notes, {len(decks)} deck(s), "
        f"{len(media_files)} media file(s) -> {output} "
        f"({output.stat().st_size / 1024:.0f} KB)"
    )
    return output, note_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    deckrepo.add_deck_arguments(parser)
    parser.add_argument("-o", "--out-dir", type=Path, default=Path("dist"))
    args = parser.parse_args(argv)

    try:
        specs = deckrepo.resolve(args)
    except DeckRepoError as exc:
        print(f"build: {exc}", file=sys.stderr)
        return 2

    print(f"building {len(specs)} deck(s) into {args.out_dir}/")
    total = 0
    for spec in specs:
        try:
            _, count = build_one(spec, args.out_dir)
        except DeckRepoError as exc:
            print(f"build: {exc}", file=sys.stderr)
            return 1
        total += count

    print(f"done: {total} notes across {len(specs)} deck(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
