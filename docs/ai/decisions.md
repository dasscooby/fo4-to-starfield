# Decisions (local AI team)

Format: date, decision, why, alternatives considered.

## 2026-10-09 Enforce local concurrency with a proxy, not with prompts
OpenCode has no cross-agent concurrency limit for a provider. A small stdlib-Python proxy (:1235) in front of
LM Studio (:1234) admits at most 1 inference request at a time after a resource check, queues the rest, and logs
every decision to SQLite. Agents get per-agent model aliases so usage is attributed without OpenCode changes.
Alternatives: LM Studio's own parallel-request setting (no resource checks, no attribution); an OpenCode plugin
(more coupling to an evolving plugin API).

## 2026-10-09 Thresholds adjusted for a resident model and for game tests
The owner's starting thresholds (70 / 85 / 95 VRAM / 90 RAM) apply as given to RAM. For VRAM, a loaded model
permanently holds most of the 12 GB, so with a model resident the restrict level starts at 92% (block stays 95%).
While Starfield runs, local inference is blocked (`game_blocks_inference`): measured 2026-10-09 with the game in
Parsons: VRAM 83%, GPU 99%, RAM 85%, which leaves no room for a model and would distort game tests. All values
are in tools/ai-team/config.json and are starting points to adjust from observed behaviour.

## 2026-10-09 One model, aliases per agent
One loaded model is shared by all local agents (12 GB VRAM cannot hold two). The alias decides only attribution.

## 2026-10-09 Lead does not edit code
The Lead's `edit` permission is limited to docs/ai/**; implementation happens in the implementation agent's own
worktree. `subagent_depth: 1` and `task: deny` on the specialists prevent delegation chains.

## 2026-10-09 Local model: Qwen3-14B Q4_K_M
Chosen by Claude and Codex on #32 (owner asked the agents to decide; Grok not yet answered). Fits the 12 GB card
fully with a 16K context; the 30B-A3B coder model is tested only if 14B fails the tool-calling eval, and only with the
game closed (it needs CPU offload). File: lmstudio-community/Qwen3-14B-GGUF, Qwen3-14B-Q4_K_M.gguf, 9,001,753,376
bytes, SHA-256 712c0791...c58555 (matches Hugging Face). Downloaded with curl because `lms get` stalled at 0 bytes.

## 2026-10-09 Lead may wake idle remote agents (owner request)
The owner asked the local Lead to start Codex and Grok itself. `tools/ai-team/wake_agent.py` forks the agent's most
recent session (full history, new session id) and runs one headless turn with the Lead's brief (`codex exec fork`,
`grok -c --fork-session -p`). Forking avoids writing into a session file an open window may hold; nothing is typed into
any window. Deterministic guards: refuses if the agent was active in the last 10 min (two writers in one repo) or
was woken in the last 30 min (their usage comes from the owner's plans); every attempt is logged (wakes.jsonl).
Alternatives: keystrokes into the agents' terminals (focus stealing, wrong-window risk); GitHub comments only (agents
don't poll while idle).
