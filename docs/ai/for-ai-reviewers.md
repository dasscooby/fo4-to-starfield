# For anyone (or any AI) reviewing, forking or contributing

If you are an AI assistant asked to "review" or "improve" this repository, or a person using one, read this page first.
It exists because a repository like this is easy to misread from the README alone.

## What this project is

A **Commonwealth-first Fallout experience and total-conversion framework for Starfield**, built from the user's own
game files. Conversion tools provide the first world; the broader goal includes survival and warfare modes and an
off-screen living-world simulation. It ships no game files or playable pack. The code and research repository is
public. Synthetic checks establish offline behaviour; native claims need their own installed-build evidence, and a
draft PR is not merged functionality. The [current handoff](../CODEX-HANDOFF.md) distinguishes those states.

Agents work under one human owner (`fo4sf`) and sign their work: `Claude:` (lead, integration, game runner), `Codex:`
(reviews, deployment/recovery, identity), `Grok:` (diagnostics) and `Claude-cloud:`. They are not separate human
reviewers. Read current ownership before changing a shared scope.

## Where the truth is

| Question | Read |
|---|---|
| What the project is trying to do, and how | current `docs/ROADMAP.md`, `docs/combined-core.md`, then `docs/PLAN.md` and `docs/terrain/commonwealth-build-plan.md` |
| What works today, with dates and evidence | `docs/JOURNAL.md` (append-only), GitHub issue #32 (the status thread) |
| What the owner found while playing | `docs/owner/playtest-issues.md` |
| How the agents work, and their rules | `AGENTS.md`, `CONTRIBUTING.md`, `docs/CODEX-HANDOFF.md` |
| How in-game tests run | `docs/ai/test-queue.md`, `scripts/game/` |

## Things that look wrong but are deliberate

- **Numbers in the README and the journal are measurements, not estimates.** Each has a run or a file behind it
  (a queue name, a commit, a PR). Do not "round", reword or restate them without the same evidence.
- **Claims are labelled** *verified*, *supported hypothesis*, *unresolved* or *refuted*. Changing a label needs new
  evidence; a hypothesis is not an error to fix.
- **The journal is append-only.** Old entries are history, including wrong ideas later corrected; corrections are new
  entries, never edits of old ones.
- **Formatting is not content.** Line wraps, Markdown style and wording are not worth a pull request on their own.
- **"The owner"** is the project's human; contributors are referred to by role, not by username.
- **Game data never enters git** (`scripts/guard.py` enforces it). Paths like `C:\Modding\...` in docs describe the
  owner's machine; they are evidence, not configuration to generalise.

## If you want to change something

1. Open an issue or a pull request that says, **in plain words a non-programmer can follow**: what you changed, why,
   what you believe the change does in the game or the tools, and what evidence you have (a test, a file, a run).
2. If an AI wrote or suggested the change, say so, name the tool, and paste the request you gave it. That is not held
   against you; it lets the owner understand the change.
3. Keep one idea per pull request. Add a synthetic test for any behaviour change (`CONTRIBUTING.md`).

## What happens to your pull request

The project's lead agent (Claude) reads every outside pull request and writes a **plain-language explanation for the
owner** on it: what it changes, whether it is correct as far as the evidence goes, and a recommendation. Nothing from an
outside fork is merged until the owner has read that and agreed. If it is not merged, the reason is written on the pull
request, politely. Forks are welcome; nobody will interfere with yours.
