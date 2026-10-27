# Contributing cards

You write cards in Anki, because that is where you can see them render and where you are already studying. Git is only how they get reviewed and shared.

If you have never used Git, read this once and then follow the checklist at the bottom. You need four commands.

Everything below uses `SC-500` as the example deck. Substitute whichever deck you are working on; `python tools/list_decks.py` shows them all.

## Before you write anything

Read the [six rules](README.md#the-six-card-rules). Most rejected cards break rule 1 (one fact per card) or rule 4 (enumerations).

Only make cards from material you can already explain. A card built on something you have not understood will fail forever and poison your schedule.

## The loop

### 1. Pull first

```bash
git checkout main
git pull
```

Re-import in Anki (**File → CrowdAnki: Import from disk** → the `deck/SC-500` folder) so you are adding to the current deck and not to a stale copy.

### 2. Make a branch

```bash
git checkout -b cards/jit-vm-access
```

Name it after what you are adding.

### 3. Write your cards in Anki

Add them to the **SC-500** deck. Tag each one with at least a `domain::` and a `type::` tag; the allowed `domain::` values for each deck are in `decks.toml`. Use existing cards as a model for phrasing.

Use the shared **Mnemonic Basic** and **Mnemonic Cloze** note types. If you need a different one, raise it first: a new note type affects everyone who imports the deck.

### 4. Export over the top of the repo

In Anki: **File → CrowdAnki: Export selected deck**, pick **SC-500**, and choose the repo's `deck/` directory as the destination.

CrowdAnki writes into `deck/SC-500/`, overwriting `deck.json`. That is expected: Git works out what actually changed.

### 5. Check your own work

```bash
python tools/lint_cards.py --deck SC-500
git diff
```

Read the diff. You should see only your new notes and nothing else. If the whole file appears changed, see [Troubleshooting](#troubleshooting).

### 6. Push and open a PR

```bash
git add deck/SC-500
git commit -m "Add 6 cards on JIT VM access"
git push -u origin cards/jit-vm-access
```

Then open a pull request on GitHub. CI runs the linter and builds an `.apkg`.

### 7. After it merges

```bash
git checkout main
git pull
```

Re-import in Anki. Your scheduling on existing cards is preserved: CrowdAnki matches notes by `guid`.

## Reviewing someone else's PR

You are reviewing the wording, not the Git. For each new card ask:

- Is this **one** fact? Would failing half of it be fair?
- Is the front a **question**? A bare term is not a card.
- Could I answer it **without** having seen this exact card? (If not, it may be testing phrasing rather than knowledge.)
- For two confusable products, does the card actually **separate** them?
- Is it still true? Microsoft renames things.

Approve, or leave a comment naming the rule. "Rule 1, split this" is a complete review comment.

## Troubleshooting

**The diff shows the entire file changed.**
Your editor or Anki version reflowed the JSON. Run `python tools/format_deck.py` and commit again.

**The diff shows note types changed.**
You edited a shared note type, or Anki renamed one on import. Revert those hunks: note types are repo-wide, and changing one here changes it for every deck. Bring it up in the team channel instead.

**The diff shows deck config or note type changes I did not make.**
Your local deck options differ from the repo's. Revert those hunks before committing:

```bash
git checkout -p deck/SC-500/deck.json
```

Answer `y` only for the hunks you want to discard. Deck options are personal; keep them out of the shared deck unless you are deliberately changing the default for everyone.

**Merge conflict in `deck.json`.**
Do not hand-edit the JSON. Take `main`'s version, re-import it in Anki, re-add your cards, and re-export:

```bash
git checkout --theirs deck/SC-500/deck.json   # or: git checkout main -- deck/SC-500/deck.json
```

Then repeat steps 3 to 5. This is why small, frequent PRs beat one large one.

**The linter complains about a card I am sure is fine.**
Warnings are judgement calls, and the linter has no taste. Say so in the PR and the reviewer decides. Errors are not negotiable: duplicate fronts, missing tags, empty fields and identical front/back are always bugs.

## Adding a whole new deck

See [Add a new deck](README.md#add-a-new-deck) in the README. In short: `python tools/new_deck.py <ID> --domain ... --domain ...`, import the scaffolded folder in Anki, write cards, export back, open a PR. The PR should include both the new `deck/<ID>/` folder and the `decks.toml` entry.

## Checklist

- [ ] Pulled `main` and re-imported before writing
- [ ] Every new card is one fact, phrased as a question
- [ ] Every new card has a `domain::` and a `type::` tag
- [ ] At least some cards are `type::scenario` or `type::discriminator`
- [ ] `python tools/lint_cards.py` passes
- [ ] `git diff` shows only my cards
