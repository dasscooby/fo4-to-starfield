# Contributing

Thanks for looking. This project is deliberately split into small, self-contained pieces so you can finish
one in a sitting.

## Pick something

1. Read [docs/PLAN.md](docs/PLAN.md) (10 minutes).
2. Open [docs/WORK-PACKAGES.md](docs/WORK-PACKAGES.md) or the GitHub issues. Take a package marked `ready`,
   or a **spike** (S1–S9 in [docs/RISKS.md](docs/RISKS.md)): spikes are the most valuable work right now.
3. Comment on the issue so nobody duplicates it.

## Do it

- Work from the package's **acceptance test**. A change isn't done until that passes.
- Add a **synthetic-fixture test** (build the input bytes in the test; never commit game files).
- Record what you tried in [docs/JOURNAL.md](docs/JOURNAL.md): date, game versions, command, result,
  oracle output (including negative results; they save the next person days).
- For a spike, write `docs/spikes/Sx-<name>.md`: question, method, result, **go / no-go / fallback**.

## Hard rules

- **No game data in commits.** Run `python scripts/guard.py`; CI runs it too.
- Don't commit your `config.toml` or any path from your machine.
- Offline / single-player only.
- Python tools that read game data run with `python -I` so they don't import from the data folder.

## Using an AI agent

Point it at `docs/PLAN.md`, `docs/WORK-PACKAGES.md` and `docs/JOURNAL.md`, and ask it to do the first
`ready` package, add tests, run the guard, and update the journal. Please note AI assistance in the PR.

## Style

Python: type hints, `unittest`, no hidden global state, deterministic output (sorted keys, no timestamps in
generated files). Mapping tables are JSON/TOML in `mappings/` with a one-line rationale per non-obvious entry.
