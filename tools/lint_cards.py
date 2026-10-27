#!/usr/bin/env python3
"""Lint every deck in the registry against the card rules.

Usage:
    python tools/lint_cards.py                        # all decks
    python tools/lint_cards.py --deck SC-500          # one deck
    python tools/lint_cards.py --warnings-as-errors

Rules come from the six card rules plus each deck's tag vocabulary in
decks.toml. Errors fail the build. Warnings are judgement calls: a reviewer may
wave one through, but someone has to look.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser

try:
    from . import deckrepo  # type: ignore[attr-defined]
except ImportError:
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    import deckrepo

from deckrepo import DeckRepoError, DeckSpec, canonical_note_models, collect_notes

# Phrasings that almost always produce a card nobody passes cleanly.
ENUMERATION_PATTERNS = [
    re.compile(r"^\s*list\b", re.I),
    re.compile(r"\bname (all|the \w+|every)\b", re.I),
    re.compile(r"\bwhat are the\b", re.I),
    re.compile(r"\bwhich \w+ (are|can be)\b.*\?$", re.I),
    re.compile(r"\ball (of the )?(the )?\w+ that\b", re.I),
]

CLOZE_RE = re.compile(r"\{\{c(\d+)::")


# --- helpers -----------------------------------------------------------------


class _Stripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def strip_html(value: str) -> str:
    parser = _Stripper()
    parser.feed(value.replace("<br>", " ").replace("<br/>", " ").replace("<div>", " "))
    return re.sub(r"\s+", " ", parser.text()).strip()


def short_label(fields: list[str]) -> str:
    text = strip_html(fields[0]) if fields else "(no fields)"
    return text[:60] + ("..." if len(text) > 60 else "")


@dataclass
class Problem:
    level: str  # "error" or "warning"
    rule: str
    note: str
    message: str


@dataclass
class Report:
    deck_id: str
    problems: list[Problem] = field(default_factory=list)
    note_count: int = 0

    def error(self, rule: str, note: str, message: str) -> None:
        self.problems.append(Problem("error", rule, note, message))

    def warn(self, rule: str, note: str, message: str) -> None:
        self.problems.append(Problem("warning", rule, note, message))

    @property
    def errors(self) -> list[Problem]:
        return [p for p in self.problems if p.level == "error"]

    @property
    def warnings(self) -> list[Problem]:
        return [p for p in self.problems if p.level == "warning"]


# --- the checks --------------------------------------------------------------


def lint_deck(spec: DeckSpec, deck: dict) -> Report:
    report = Report(spec.id)
    models = {m["crowdanki_uuid"]: m for m in deck.get("note_models", [])}
    notes = collect_notes(deck)
    report.note_count = len(notes)

    check_note_models(report, deck)

    if not notes:
        # A freshly scaffolded deck is empty on purpose; that is not an error.
        report.warn("deck", "-", "the deck has no notes yet")
        return report

    if spec.max_notes and len(notes) > spec.max_notes:
        report.warn(
            "deck-size", "-",
            f"{len(notes)} notes, above the {spec.max_notes} target; "
            "the daily review load is outgrowing a working day",
        )

    seen_fronts: dict[str, str] = {}
    seen_guids: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()

    for note in notes:
        fields = note.get("fields", [])
        label = short_label(fields)
        seen_guids[note.get("guid", "")] += 1

        model = models.get(note.get("note_model_uuid"))
        if model is None:
            report.error(
                "model", label,
                f"note_model_uuid {note.get('note_model_uuid')!r} is not in this deck's note_models",
            )
            continue

        front_raw = fields[0] if fields else ""
        front = strip_html(front_raw)
        if not front:
            field_names = [f["name"] for f in model.get("flds", [])]
            first = field_names[0] if field_names else "?"
            report.error("empty", label, f"first field ({first}) is empty")
            continue

        if model.get("type") == 1:
            lint_cloze(report, spec, label, front_raw)
        else:
            lint_basic(report, spec, label, fields, front)

        lint_tags(report, spec, label, note.get("tags", []), type_counts)

        for pattern in ENUMERATION_PATTERNS:
            if pattern.search(front):
                report.warn(
                    "rule-4-enumeration", label,
                    "front reads as a list question; split it into one cloze per item "
                    "or turn it into a why-question",
                )
                break

        key = front.casefold()
        if key in seen_fronts:
            report.error("duplicate", label, f"duplicate front, already used by {seen_fronts[key]!r}")
        else:
            seen_fronts[key] = label

    for guid, count in seen_guids.items():
        if count > 1:
            report.error("guid", guid, f"guid appears {count} times; CrowdAnki identifies notes by guid")

    lint_mix(report, spec, type_counts, len(notes))
    return report


def check_note_models(report: Report, deck: dict) -> None:
    """Every deck should embed the repo's shared note types.

    If two decks ship near-identical note types under different uuids, anyone who
    imports both ends up with two of everything.
    """
    canonical = {m["crowdanki_uuid"]: m["name"] for m in canonical_note_models()}
    for model in deck.get("note_models", []):
        uuid = model.get("crowdanki_uuid")
        if uuid not in canonical:
            report.warn(
                "note-model", model.get("name", "?"),
                "note type is not one of the repo's shared types "
                f"({', '.join(sorted(canonical.values()))}). Importing several decks "
                "will then create duplicate note types.",
            )
        elif model.get("name") != canonical[uuid]:
            report.warn(
                "note-model", model.get("name", "?"),
                f"shared note type renamed locally; expected {canonical[uuid]!r}",
            )


def lint_basic(report: Report, spec: DeckSpec, label: str, fields: list[str], front: str) -> None:
    back_raw = fields[1] if len(fields) > 1 else ""
    back = strip_html(back_raw)

    if not back:
        report.error("empty", label, "back is empty")
        return

    if front.strip().casefold() == back.strip().casefold():
        report.error("rule-1", label, "front and back are identical")

    if len(front) < spec.min_front_chars:
        report.warn(
            "rule-3-orphan", label,
            f"front is only {len(front)} characters; a bare term gives retrieval nothing to grip",
        )

    if not front.rstrip().endswith(("?", ":")):
        report.warn(
            "rule-1-question", label,
            "front is not phrased as a question; a card that does not ask something is rereading",
        )

    if len(back) > spec.max_back_chars:
        report.error(
            "rule-1-multifact", label,
            f"back is {len(back)} characters (limit {spec.max_back_chars}); split it into separate cards",
        )
    elif len(back) > spec.warn_back_chars:
        report.warn(
            "rule-1-multifact", label,
            f"back is {len(back)} characters; check it is really one fact",
        )

    if re.search(r"(<li>|^\s*[-*•]\s|\b1\.\s.*\b2\.\s)", back_raw, re.M):
        report.warn(
            "rule-4-enumeration", label,
            "back contains a list; consider one cloze per item instead",
        )


def lint_cloze(report: Report, spec: DeckSpec, label: str, front_raw: str) -> None:
    ordinals = {int(m) for m in CLOZE_RE.findall(front_raw)}
    if not ordinals:
        report.error("cloze", label, "cloze note has no {{c1::...}} deletion")
        return
    if len(ordinals) > spec.max_cloze_deletions:
        report.warn(
            "rule-1-multifact", label,
            f"{len(ordinals)} cloze deletions on one note; above {spec.max_cloze_deletions} "
            "this is an enumeration",
        )
    missing = sorted(set(range(1, max(ordinals) + 1)) - ordinals)
    if missing:
        report.warn("cloze", label, f"cloze ordinals skip {missing}; Anki copes but it reads as a mistake")


def lint_tags(report: Report, spec: DeckSpec, label: str, tags: list[str], type_counts: Counter) -> None:
    for namespace in spec.required_tags:
        matching = [t for t in tags if t.startswith(f"{namespace}::")]
        if not matching:
            report.error("tags", label, f"missing a {namespace}:: tag")
            continue
        if len(matching) > 1 and namespace == "domain":
            report.warn("tags", label, f"more than one domain:: tag ({', '.join(matching)})")
        if namespace == "type":
            type_counts[matching[0].split("::", 1)[1]] += 1

    for tag in tags:
        if "::" not in tag:
            report.warn("tags", label, f"tag {tag!r} has no namespace")
            continue
        namespace, value = tag.split("::", 1)
        if namespace in spec.open_tags:
            continue
        allowed = spec.tag_values.get(namespace)
        if allowed is None:
            report.warn(
                "tags", label,
                f"tag namespace {namespace}:: is not declared for this deck in decks.toml",
            )
        elif value not in allowed:
            report.error(
                "tags", label,
                f"tag {tag!r} is not an allowed value for {namespace}:: "
                f"(allowed: {', '.join(sorted(allowed))})",
            )


def lint_mix(report: Report, spec: DeckSpec, type_counts: Counter, total: int) -> None:
    if total < 20 or not spec.min_scenario_share:
        return
    share = sum(type_counts.get(t, 0) for t in spec.scenario_types) / total
    if share < spec.min_scenario_share:
        kinds = " or ".join(spec.scenario_types)
        report.warn(
            "deck-mix", "-",
            f"only {share:.0%} of cards are {kinds} cards; "
            f"aim for at least {spec.min_scenario_share:.0%} on a scenario-based exam",
        )


# --- output ------------------------------------------------------------------


def print_report(report: Report, spec: DeckSpec) -> None:
    header = f"{spec.id} ({report.note_count} notes)"
    print(f"\n{header}\n{'=' * len(header)}")

    if not report.problems:
        print("  clean")
        return

    by_rule: dict[str, list[Problem]] = defaultdict(list)
    for problem in report.problems:
        by_rule[problem.rule].append(problem)

    for rule in sorted(by_rule):
        print(f"  [{rule}]")
        for problem in by_rule[rule]:
            marker = "ERROR  " if problem.level == "error" else "warning"
            print(f"    {marker} {problem.note}")
            print(f"             {problem.message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    deckrepo.add_deck_arguments(parser)
    parser.add_argument("--warnings-as-errors", action="store_true")
    args = parser.parse_args(argv)

    try:
        specs = deckrepo.resolve(args)
    except DeckRepoError as exc:
        print(f"lint: {exc}", file=sys.stderr)
        return 2

    reports: list[tuple[DeckSpec, Report]] = []
    for spec in specs:
        try:
            deck = spec.load()
        except DeckRepoError as exc:
            print(f"lint: {exc}", file=sys.stderr)
            return 2
        report = lint_deck(spec, deck)
        reports.append((spec, report))
        print_report(report, spec)

    total_notes = sum(r.note_count for _, r in reports)
    total_errors = sum(len(r.errors) for _, r in reports)
    total_warnings = sum(len(r.warnings) for _, r in reports)
    print(
        f"\n{len(reports)} deck(s), {total_notes} notes: "
        f"{total_errors} error(s), {total_warnings} warning(s)"
    )

    if total_errors:
        return 1
    if args.warnings_as_errors and total_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
