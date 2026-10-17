# Agent Log Protocol

This directory is the durable record of what changed in the project and why.
Git shows diffs; this log shows intent, commands, validation, and follow-ups.

## Files

- `AGENT_LOG.md` — append-only chronological log. Each entry has a stable
  `LOG-XXXX` ID.
- `INDEX.md` — one-row-per-entry index for quick scanning.
- `_template.md` — copy this for a new entry.
- `README.md` — this file.

## Read order

Before making changes:

1. `README.md`
2. `AGENTS.md`
3. `docs/decisions.md`
4. `docs/logs/INDEX.md`
5. The last 5–10 entries in `docs/logs/AGENT_LOG.md`

## When to write

Write an entry for every **material action**:

- code/doc/test/notebook file changes;
- data-generation runs;
- dependency changes;
- git setup, commits, pushes;
- failures that change the plan or require a retry;
- decisions that are not already in `docs/decisions.md`.

Read-only exploration can be one "Inspection" entry per phase; do not log every
`ls`.

## Entry rules

- Append; never rewrite a committed entry.
- Corrections or reversals go into a new entry that references the old ID.
- Include exact commands and validation results (counts, tests passed, etc.).
- Reference decision IDs (`D-001`) when relevant.
- Write the entry before committing; stage it with the change.
- Commit message must include: `Log: docs/logs/AGENT_LOG.md#LOG-XXXX`.
- Commit hashes are added to `INDEX.md` in a later docs commit; the log ID is
  the stable cross-reference.
