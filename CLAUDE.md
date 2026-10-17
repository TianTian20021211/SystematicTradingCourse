# CLAUDE.md

Read `AGENTS.md` first. It contains the project invariants, repository
conventions, and the mandatory logging protocol.

Claude Code-specific notes:

- Run notebooks from the repo root:
  `jupyter nbconvert --execute --to notebook --inplace notebooks/00_data_audit.ipynb`
- Run tests with `python -m pytest -q`.
- Never commit raw data, PDFs, `calendar-spread-brief.html`, processed
  parquet, or secrets. Check `git status` before staging.
- Every material change needs a new entry in `docs/logs/AGENT_LOG.md` and a
  matching row in `docs/logs/INDEX.md`, committed together with the change.
- Keep notebook code cells short and narrative; put reusable logic in `src/`.
- Do not change the locked D=10 / no-delivery-month / dollar-primary
  conventions without a new `docs/decisions.md` entry approved by the user.
