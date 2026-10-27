# Anki decks

Shared, version-controlled Anki decks for mnemonic cloud trainees. One repo, as many decks as we need: certification decks, topic decks, whatever the next cohort is studying.

| Deck | Notes | What it covers |
| --- | --- | --- |
| `SC-500` | 221 | Implementing End-to-End Security Controls for Cloud and AI Workloads (Cloud and AI Security Engineer Associate) |

`python tools/list_decks.py` prints the current list straight from the registry.

Maintainer: Kevin Nordnes.

## Why a Git repo and not `.apkg` files in SharePoint

An `.apkg` is a binary. You cannot see what changed between two versions, you cannot review a card before it reaches the whole team, and re-importing one can duplicate notes or clobber your scheduling.

[CrowdAnki](https://github.com/Stvad/CrowdAnki) exports a deck to JSON instead. That gives us:

- **Readable diffs.** A pull request shows the exact wording that changed.
- **Review before merge.** A badly written card gets caught by a person, not by the whole cohort failing it for a month.
- **Scheduling survives updates.** CrowdAnki matches notes by `guid`, so pulling new cards does not reset your progress on the old ones.
- **A history.** When Microsoft renames a product, you can see when the card was fixed and why.

## Get started (trainees)

### 1. Install CrowdAnki

In Anki: **Tools → Add-ons → Get Add-ons**, paste code `1788670778`, restart Anki.

### 2. Clone the repo

```bash
git clone git@github.com:<org>/anki-decks.git
cd anki-decks
```

### 3. Import the decks you need

In Anki: **File → CrowdAnki: Import from disk**, then select a deck **folder** such as `deck/SC-500` (not the JSON file inside it). Repeat per deck.

Do this again whenever you pull. Your review history stays intact.

Every deck ships the same two note types (`Mnemonic Basic`, `Mnemonic Cloze`) and the same options preset (`Mnemonic trainee`), so importing five decks does not give you five of everything, and your own stock `Basic` and `Cloze` are left alone.

### 4. Check your deck options

The preset arrives with the import, but confirm it:

| Setting | Value |
| --- | --- |
| FSRS | On |
| Desired retention | 0.90 |
| New cards/day | 10 for your first two weeks, then raise |
| Maximum reviews/day | 100 |

Press **Again** when you failed to recall a card, never **Hard**. Hard tells the scheduler you got it.

## Repository layout

```
decks.toml             the registry: every deck, its tags and its lint thresholds
deck/
  SC-500/
    deck.json          the deck: note types, options preset, and every note
    media/             images and audio
tools/
  deckrepo.py          shared plumbing: reads the registry, loads decks
  list_decks.py        what is in the repo right now
  lint_cards.py        checks cards against the rules and each deck's tags
  build_apkg.py        CrowdAnki JSON -> .apkg, for people without the add-on
  format_deck.py       keeps deck.json in CrowdAnki's canonical JSON format
  new_deck.py          scaffolds a new deck
  templates/           the shared note types and options preset
.github/workflows/
  deck.yml             lints and builds every deck, one CI job per deck
```

## Add a new deck

```bash
python tools/new_deck.py AZ-104 \
  --title "Microsoft Azure Administrator" \
  --domain identity-governance --domain storage --domain compute \
  --domain networking --domain monitor-backup \
  --maintainer "Your Name" \
  --reference https://learn.microsoft.com/.../study-guides/az-104
```

That appends a `[[decks]]` block to `decks.toml` and writes an empty CrowdAnki export at `deck/AZ-104/` with the shared note types already attached. Then import it in Anki, write cards, export back over the folder, and open a PR.

`--domain` values are that deck's `domain::` tag vocabulary. For an exam, use its skill areas. For a topic deck, use whatever divisions you would want to filter on later.

### Deck settings

Anything in `[defaults]` can be overridden per deck in its `[[decks]]` block:

| Key | Default | What it does |
| --- | --- | --- |
| `required_tags` | `["domain", "type"]` | Namespaces every note must carry |
| `open_tags` | `["service"]` | Namespaces with no fixed vocabulary |
| `min_front_chars` | 15 | Below this, a front is a bare term, not a question |
| `warn_back_chars` / `max_back_chars` | 260 / 400 | Where "one fact per card" stops being plausible |
| `max_cloze_deletions` | 5 | Above this a cloze is an enumeration |
| `scenario_types` | `["scenario", "discriminator"]` | Which card types count as transfer-ready |
| `min_scenario_share` | 0.25 | Set to `0.0` for a deck that is not exam-shaped |
| `max_notes` | 500 | Warn once the daily load outgrows a working day |

## The six card rules

Every card in every deck has to pass these. CI checks what a machine can check; the rest is on the reviewer.

1. **One fact per card.** If the answer has three parts, it is three cards.
2. **Understand before you memorise.** Never make a card from material you cannot explain.
3. **No orphan facts.** Put the service name in the question so retrieval has a handle.
4. **Avoid enumerations.** Turn "list the five things X does" into one cloze per item, or a why-question.
5. **Ask for the discriminator.** For confusable products, write the card that separates them.
6. **Write it in your own words.** Pasting a Microsoft Learn sentence reproduces the docs, not your understanding.

## Tags

Two namespaces are required on every note; the rest are optional but encouraged.

| Namespace | Required | Values |
| --- | --- | --- |
| `domain::` | yes | Per deck, declared in `decks.toml` |
| `type::` | yes | `fact`, `discriminator`, `scenario`, `why` |
| `service::` | no | Open-ended: `entra`, `keyvault`, `defender-cloud`, `sentinel`, `purview`, ... |
| `source::` | no | `ms-learn`, `lab`, `exam-topic`, `docs` |
| `status::` | no | `review-needed` when you are unsure a card is still correct |

**One deck per exam, not one per domain.** Interleaving confusable material is most of the point; `domain::` tags exist so you can build a filtered deck when you are weak in one area, not so you can study the areas separately.

## Run the checks locally

```bash
pip install -r requirements.txt     # genanki, plus tomli on Python < 3.11

python tools/list_decks.py
python tools/lint_cards.py                    # all decks
python tools/lint_cards.py --deck SC-500      # one deck
python tools/build_apkg.py -o dist
python tools/format_deck.py --check
```

Needs Python 3.11+, or `pip install tomli` on 3.8 to 3.10.

## A note on the built `.apkg`

CI attaches one `.apkg` per deck to every run, for anyone who has not installed CrowdAnki yet. It carries the cards, tags and note types, but **not** the options preset: set FSRS and your daily limits by hand if you import that way. Importing the CrowdAnki folder brings the preset with it. The JSON is the source of truth either way.

## Keeping the decks honest

Microsoft renames products often, and a deck full of dead names actively teaches the wrong thing.

If you meet a renamed service, tag the card `status::review-needed`, post in the team channel, and open a PR if you know the fix. The maintainer does a correctness pass monthly and after any rename.

Target size is **300 to 500 cards per deck**. Past that the daily review load outgrows a working day, and people quit. The linter warns when a deck crosses the line.
