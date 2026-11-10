# Optimization log

Ongoing (AGENTS.md "Keep optimizing"). Every entry: date, agent, what, **measured before / after** (same command,
same input), and the commit. Use the `optimization` label on the issue or PR.

## Baselines (measured 2026-10-09 on the owner's PC; Ryzen 9 7950X3D, RTX 4070 Ti 12 GB, 32 GB)

| What | Command | Measured | Source |
|---|---|---|---|
| Full conversion build, 15 cells / 4,014 models | `scripts/convert_batch.py --cell-json merged.json` (no `--resume`) | 311–373 s | Claude, journal 2026-10-09 |
| Plugin write, 15 cells | `dotnet/PluginSpike` | ~10 s (not timed precisely) | Claude |
| Unit tests (241) | `python -m unittest discover -s tests` | 2.4 s | Claude |
| Deploy + launch + load cell | `research/s1/cycle.ps1` | ~3 min | Claude |
| Parsons route run, 45 routes | `scripts/game/route_run.ps1` | ~2 min per door route (prompt search + console checks) | Claude, in progress |
| Guardian status (one sample) | `guardian.py status` | 1.1 s | Claude |
| Remote usage report, 24 h | `remote_usage.py` | 2.7 s | Claude |
| Local model tokens per task | `guardian.py report` | no data yet (no model) | n/a |
| Papyrus tick over 50 globals (combined-core P5), 10 ticks | `cgf "FOCC_Probe.P5Tick" 10` (docs/spikes/combined-core-probes.md) | median 121.0 ms (119.0 to 123.0), 2.42 ms per place | Install thread, 2026-10-28 |

## Candidates (not done; each needs a before/after)
- Build: `--resume` checkpoints (Codex) instead of full rebuilds when only a few models change. The last six
  Claude rebuilds were full (~6 min each) for changes touching 2–118 models.
- Route runs: the prompt search takes up to 9 screenshot+OCR rounds per door; start the tilt from the last
  successful pitch per cell.
- Remote usage: Codex 102 M input tokens in 24 h, 96% cached; Claude 160 M cache reads; Grok 73 M input.
  Long single sessions dominate. Shorter sessions with handoff notes may cut cached-context cost; measure first.

## Entries

### 2026-10-09 Codex: hash archive contents for resume identity (`c74a952`)
Same deterministic synthetic 64 MiB archive, seven warm-cache runs on the owner's PC. Before: metadata-only
`archive_identity()` median **0.000170 s**. After: content-hashed `archive_identity()` median **0.049534 s**;
about 291× the fingerprint time, or +0.0494 s per 64 MiB (~1.29 GiB/s observed). The one-time scan per input
archive closes stale-resume reuse when size and timestamp are preserved. Large archive sets pay this scan on
each resume invocation; correctness was prioritized over this added startup I/O.

### 2026-10-09 Claude: model load without memory mapping (local team)
Before: `lms load qwen3-14b --gpu max` -> LM Studio held 10.5 GB of system RAM for a model fully in VRAM; RAM 88.2%,
the guardian held every request (restrict/block). After: `tools/ai-team/load_model.py` (tryMmap=false,
keepModelInMemory=false) -> LM Studio 5.4 GB, RAM 71.4%, VRAM unchanged (10,890 -> 10,930 MiB). Requests admitted.

### 2026-10-09 Claude: 32K context at the cost of 16K (local team)
OpenCode's own system prompt + tools is ~12K tokens; at 16K context it compacted and re-continued in a loop.
Before: 16K, f16 KV cache, VRAM 10,952 MiB. After: 32K, q8_0 K/V cache + flash attention, VRAM 11,061 MiB (90.1%,
below the 92% restrict level with a resident model). Twice the context for +109 MiB.

### 2026-10-09 Claude: wake remote agents with a fresh session, not a fork
Before: `wake_agent.py` forked Codex's last session; one headless turn reported **5,677,999 tokens used** (the
whole long session history replayed) and, in the default read-only sandbox, could not fix or post anything.
After: default is a fresh session with a short brief pointing at #32 / handoff / AGENTS.md, with workspace-write +
network. `--fork` stays available when the old context is really needed. After (measured): the next fresh-session wake fixed the bug it was briefed on, ran the tests and the guard, and
opened PR #34 using **54,793 tokens** (99% less than the fork's 5,677,999).

### 2026-10-10 Claude: cycle.ps1 waits on the screen instead of timers (in progress)
Before (measured today, `cycle.ps1` from close to verified arrival): 195 s (Vault 114 swap, 20:3x) and 210 s (Vault 81,
18:5x). Fixed timers inside: 30 s after launch, 45 s after Continue, 37 s after a blind `coc` (112 s), plus coc.ps1's
30 s. Change: poll a screenshot every 3 s for the main menu text, then for the HUD, and go on as soon as it shows (the
timers stay as the upper bound). After (first run, 2026-10-11 01:3x, library cell, verified arrival): **168 s**, from 195-210 s (-15 to -20%). The per-phase times were swallowed by a pipe on that run; the script now prints them with Write-Host.

### 2026-10-22 Claude-cloud: `convert_batch.py --retry-failures` reruns only the failed models (#333, Grok)
Synthetic, not yet measured on the PC. `scripts/testing/bench_retry_failures.py` stubs the FO4 archives and the
converter; each `convert_nif` call sleeps 0.085 s (the PC's 2026-10-09 rate, 4,014 models in 311-373 s). Same staged
input every round: 200 models, 20 of them failed in the first run. Before: the rerun without the flag, 200 convert
calls, median **17.13 s** (3 rounds). After: the same command with `--retry-failures`, 20 convert calls, median
**1.72 s** (-90%). Merging into the prior manifest costs nothing measurable: at zero conversion cost with 4,014 models
and 40 failures, 0.446 s before and 0.078 s after (`--cost 0 --models 4014 --failures 40 --rounds 5`). Cloud
container, 4 CPUs, Python 3.13. The saving scales with the failure share (a retry costs about failures x per-model
time). Pending: the same before/after on the owner's PC with a real failure-summary.json.

### 2026-10-22 Claude: snapshot.ps1 writes Plugins.txt as plain strings
Before: `state.json` kept every Plugins.txt line as a Get-Content object, with PSPath, PSDrive and Provider. Install saw
3 MB on the owner's PC. Change: `plugins_txt` turns each line into a plain string (PR #484). Measured by Codex desktop on
Windows with the real script, real Get-Content/ConvertTo-Json, the same synthetic ten-line Plugins.txt and a stubbed
capture: **4,551,695 bytes before, 794 bytes after** (parent vs 1da8aba3). The list keeps the same strings in the same
order.

### 2026-11-10 Codex: reuse verified experiment packages (FAL-161)

Ubuntu OptiPlex, Ubuntu 26.04.1 x86_64, Python 3.14. Same deterministic staged set: four 16 MiB synthetic
terrain members and one synthetic plugin, three alternating install/uninstall rounds per path. Command:
`.venv/bin/python .paperclip-evidence/fal161/bench.py` (script and raw output preserved in FAL-161's
`optimization-evidence` document). Both paths call the real installer, verification, copies and rollback;
Archive2 alone is replaced by the repository's `ba2_fixture.archive_from_tree`, with no artificial delay.

Before (`install --pack`): median **1.269059 s** (1.289017, 1.211789, 1.269059), **3 archive builds**.
After (`install --pack --package <dir>`): median **1.070381 s** (1.070381, 1.042383, 1.074718),
**0 archive builds**, a 15.7% reduction here. One package build cost **0.736135 s** outside install timing.
The package archive is renamed into its reserved directory on the same filesystem, without another archive copy.
All staged inputs and stored archive members remain content-verified on reuse. This is a synthetic Linux
measurement, not an Archive2 or 4 GB PC prediction. Windows/real Archive2 timing remains NOT_RUN; the PC recipe
requests one package build and one timed scratch install without a game launch. No existing baseline was rerun.
