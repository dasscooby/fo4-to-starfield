# AGENTS.md: rules for every AI agent working on fo4-to-starfield

Applies to all agents: the local OpenCode team (Lead, Implementation, Research, QA) and the remote agents (Claude,
Codex, Grok, ChatGPT). It adds to [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/CODEX-HANDOFF.md](docs/CODEX-HANDOFF.md);
where they say more, they win. Owner: dasscooby.

## Communication: GitHub is the source of truth
- Issues are tasks; the owner's issues (#29, #30, #31, ...) are the inbox. #32 is the shared status thread.
  Read new issues/comments before choosing work and before declaring anything done.
- All agents share one GitHub account. **Start every comment with your role**, e.g. `Lead (local):`,
  `QA (local):`, `Claude:`, `Codex:`, `Grok:`, `ChatGPT:`. Never present agents as separate human contributors.
- Labels: `ready` (can start), `in-progress` (claimed; say who in a comment), `blocked` (say on what),
  `spike` (research with a go/no-go), `needs-qa` (PR or change waiting for review), `review` (external findings).
- Claim before you start (comment + `in-progress`), so nobody duplicates work. One owner per task.
- Keep posts short: what changed, the evidence, what's next. No duplicate issues; search first.

## Evidence and file formats
- No claim about a Fallout 4 or Starfield file format without evidence (file, offset, command, output).
  Label findings **verified**, **supported hypothesis** or **unresolved** (docs/ai/research-log.md).
- Research before implementing an uncertain format assumption. Offline checks are not in-game acceptance.
- Correct wrong claims publicly when found (see the journal's correction entries).

## Changes
- Substantial work happens on its own branch (`ai/<issue>-<slug>` for the local team) in its own worktree;
  never two agents writing in the same working directory.
- Only touch files your task needs and that you own (ownership: docs/CODEX-HANDOFF.md). No unrelated edits.
- Every behaviour change has a synthetic-fixture unittest (`python -m unittest discover -s tests`, run with the
  repo's Python env that has numpy) and passes `python scripts/guard.py`. QA reviews before merge.
- Architectural decisions go in docs/ai/decisions.md (date, decision, why, alternatives).
- Merging into `main` and pushing need the owner's approval for the local team. Never force-push, rewrite history,
  delete branches/tags you didn't create, or run destructive git/file commands.

## Safety
- No game assets in Git. No access to unrelated personal files, credentials, passwords, payments or outreach.
- Local inference goes through the Resource Guardian (tools/ai-team): check `guardian.py status` first; never
  bypass it by calling LM Studio on :1234 directly. While Starfield runs, the GPU is reserved for game tests.
- Live game control (deploy, cycle, input automation) belongs to Claude (handoff). Others don't send game input.

## Where things are
- Plan and history: docs/PLAN.md, docs/JOURNAL.md, docs/spikes/. Team status: docs/CODEX-HANDOFF.md, #32.
- Local AI team: docs/ai/ (architecture, decisions, research log, known unknowns, agent status), tools/ai-team/README.md.
