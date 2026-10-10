# Admin node review: should a Mac be the always-on coding admin? (2026-10-10)

Written by Claude (agent:claude) from a 7-agent review: 4 researchers (Mac facts, repo portability audit, local models, alternatives), a plan writer, an adversarial critic and a revision. Prices are from press reports unless Apple's page is cited; confirm at checkout. Owner's framing: the Mac never runs the game; it coordinates the agents and writes and tests code 24/7, handing builds and in-game tests to the Windows PC.

## Verdict

Not yet. A Mac mini would make a good always-on admin, but it adds no Claude, Codex or Grok quota, because limits are per account. What it really buys is a 24/7 local model that works at junior level (Qwen3.6-35B-A3B scores 18 against Claude Opus 5.5's 58 on Artificial Analysis's general index), plus a separate machine that keeps the agents away from your Windows account, browser and passwords. For the next two weeks, do the free steps a Mac would need anyway: write down a buy threshold, log every hour by what stopped the agents (PC off, game running, quota used up, no ready local-model work), trial the 35B model on your 4070 Ti (with 32 GB of RAM that trial may come out inconclusive rather than a no), and set up a GitHub machine account, a protected main branch and a game-test queue you start by hand. If the log meets your threshold around the end of October, buy a Mac mini M5 Pro with 48 GB / 512 GB on the base chip (15-core CPU, 16-core GPU), about $2,299 according to press reports (Apple's configurator couldn't be read, so confirm at checkout). Choose 48 GB because the memory can never be upgraded and it leaves about 20 GB next to a 20-26 GB model for macOS, three CLI agents and tests (my estimate); 64K context is a bonus, not the reason, and 64 GB (+$400) only adds room for bigger models nothing shows you need. If your cap is about $1,500, the cheapest new option is the M6 with 32 GB / 512 GB (about $1,499, confirm at checkout), though even 32K context fitting under its default GPU memory limit is unconfirmed; if you won't run a local model at all, skip the Mac and use the cloud admin or a $90-270 Linux mini box.

## Options (ranked)

| # | Option | Cost | Gives | Doesn't |
|---|---|---|---|---|
| 1 | Free first: cloud admin + 35B trial on the 4070 Ti + safety groundwork (machine account, protected main, macOS CI, hand-started game-test queue) | $0. Uses your existing subscriptions plus a roughly 20 GB model download that you approve | Real numbers for the decision: an hourly log of what blocks the agents, and whether Qwen3.6-35B-A3B or KAT-Coder-V2.5-Dev does better than Qwen3-14B on real Lead and unit-test work. Comparable 4070 Ti setups measured about 800 tok/s prompt reading and 40-60 tok/s writing, but those machines had 48-64 GB of RAM. A free macOS check of the test suite on GitHub's Apple Silicon (M1) runners. Jules's free tier (15 tasks per 24 h, 3 at once), the only genuinely extra quota. A cloud coordinator if Claude Code Projects is enabled on your account. The machine account, ruleset, trusted-author filter and game-test queue all carry over unchanged to a Mac or any other admin box. | Add any Claude or Codex quota: cloud sessions and routines use the same Claude plan, and Codex cloud uses the same ChatGPT allowance. The local model still pauses during games and stops when the PC is off. On 32 GB the trial will probably push RAM to about 87-100% (my arithmetic from today's measured 71.4%, not measured), above the guardian's 85/90% limits, so the result may be inconclusive. Cloud VMs can't reach LM Studio, the game files or the game. Projects (public beta, rolling out gradually) and routines (research preview) may not be on your account yet. |
| 2 | Mac mini M5 Pro, 48 GB / 512 GB, base 15-core CPU / 16-core GPU (the recommended Mac) | About $2,299 ($1,699 plus a $600 memory upgrade, per press; a third source, a refurb.me search snippet, agrees; Apple's configurator couldn't be read, so confirm at checkout). The 20-core GPU chip is about $2,499. The base M5 Pro is $1,599 with education pricing, if you qualify. Power is 6 W idle / 145 W max, roughly $20-45 a year (my estimate). AppleCare+ is optional, about $44.99/yr (press). | An always-on admin that doesn't depend on the gaming PC, with a separate standard user, so agents never sit next to your passwords. It runs the Lead loop, Claude Code, Codex and Grok CLIs, gh, the unittest suite and .NET. On this exact chip (16-core GPU, 48 GB), a community oMLX run of Qwen3.6-35B-A3B (UD-Q4_K_XL, oMLX 0.3.8) measured 1,911 / 1,802 tok/s prompt reading at 8K / 16K and 66 / 62 tok/s writing, and it completed 64K at 1,156 / 44. Peak memory at 64K was 26.3 GB, measured on a 20-core GPU, 64 GB machine. That leaves about 20 GB for macOS, three CLIs and tests (my estimate). It never pauses for a game, it is near-silent (5 dBA idle), and it has room to try a dense 27B model. | Add any Claude, Codex or Grok quota. Make the local model a senior engineer: it is a junior (18 vs 58 on the general index). Run texconv builds, Archive2 deploys or the game. Guarantee those speeds: one base-chip run at 8-bit read only 948 / 911 tok/s, and the plan uses LM Studio's MLX engine, not oMLX. If prompt reading turns out to be the bottleneck, the 20-core GPU (+$200) can't be added later. Memory can't be upgraded, and press teardowns report the SSD is soldered. |
| 3 | Mac mini M6, 32 GB / 512 GB (cheapest new Mac that can run the model) | About $1,499 built to order (worked out from press upgrade prices; confirm at checkout). 32 GB / 256 GB is about $1,299. One source lists 32 GB / 1 TB at $1,299 and two others list $1,799. A price aggregator on 10 Oct showed no 32 GB M6 price at all. Power is 4 W idle / 70 W max. | The same admin role and separate agent user, about $800 below the M5 Pro 48 GB. Community oMLX runs of the 4-bit 35B model show about 64-67 tok/s writing at 8K and about 50 at 32K; a second-hand LM Studio report says 64 tok/s. | Give certain numbers. One research pass read 1,566-2,083 tok/s prompt reading on omlx.ai, but another pass and a later spot-check found no M6 rows, so treat those as disputed. Whether even 32K context fits under macOS's default GPU memory limit (about 21 GB of 32 GB) is unconfirmed; it may need the sudo iogpu.wired_limit_mb change, which needs your approval. It leaves little room for macOS, three CLIs and tests at once, and none to grow. 170 GB/s makes dense models slow, and 32 GB is the M6's maximum. |
| 4 | Refurbished or used Mac mini M4 Pro, 48 GB (watch for one; don't plan on it) | Unconfirmed. One search snippet (page returned 404) listed $2,199 new and $1,869 refurbished. M4 Pro clearance units start around $1,649, probably with 24 GB. Apple's US refurbished store lists no Mac mini today. | 48 GB of headroom, a removable SSD module (unlike the 2026 models, per press), and the macOS 26.5 automatic power-on (it supports Mac mini 2024 or newer). Apple refurbished units come with a one-year warranty and can get AppleCare. | Come with any benchmarks for the 35B model in this research. It has lower bandwidth than the M5 Pro (about 273 GB/s, not re-checked here, vs 307) and an older chip. Price and availability are unconfirmed; unless one is clearly cheaper than the M5 Pro 48 GB, buy the M5 Pro. |
| 5 | Linux mini box with no local model: used ThinkCentre M720q/M920q Tiny, or a new N100/N150 mini PC | ThinkCentre $90-170 used (March 2026 prices, probably higher now; buy one that already has 16 GB), 12-27 W (12-16 W in one guide; ServeTheHome measured 27 W idle), about $1.30-3 a month. N100/N150 about $240-270 new (January 2026 price), about 10-12 W (an N150 measured 11.8 W), about $1.10-1.30 a month. | A 24/7 box for gh, the Claude, Codex and Grok CLIs, unittest and .NET, and the job queue, on a separate machine and user away from your Windows account. It gives most of the admin value if the local model doesn't prove itself. | Run a useful local model (no GPU). The OpenCode Lead loop would need a model elsewhere: the PC's guardian over the LAN or Tailscale (a security change, and only while the PC is on), or the cloud. |
| 6 | Mac mini M5 Pro 64 GB | About $2,699 on the base chip, about $2,899 with the 20-core GPU (press; confirm at checkout) | Everything the 48 GB model gives, plus room for Qwen3-Coder-Next 4-bit (48.4 GB, a tight fit that needs the GPU memory limit raised), two models at once, the 8-bit 35B model, or longer context. | Justify the extra $400 today. There is no measured Qwen3-Coder-Next data on the M5 Pro, and nothing shows the bigger models do better on this repo. |
| 7 | Used RTX 3090 24 GB added to the gaming PC | About $1,200-1,460 (Sep-Oct 2026), and possibly a ~1,000 W PSU (not checked). Adds about 350 W under load. | The fastest local model per dollar: about 3,150-3,500 tok/s prompt reading (512-token prompt) and about 148 tok/s writing on the 35B model. With a GPU-aware guardian, the model could keep running during game tests. | Act as an admin: everything still stops when the PC is off, and the agents still share your Windows account. Whether it fits your PSU and case is unknown. |
| 8 | Leave the gaming PC on 24/7 | $0 upfront. About $6.50-13 a month at idle (estimate; idle draw not measured), and about $22 a month with heavy local inference. | All current tooling unchanged. | Fix the clash with game tests (the local model pauses while Starfield runs). The agents stay next to your browser profiles, your own gh login and your passwords, and Windows updates reboot the PC. |
| 9 | Mac Studio M5 Max | $2,499 (36 GB only) or $3,099 (40-core GPU, 48 GB), both from Apple's store. 64 GB at about $3,499 is unconfirmed. Power is 7 W idle / 200 W max. | More memory bandwidth (460-614 GB/s), so dense models run faster. | Do anything for the admin job that the $2,299 mini can't. The $2,499 base has only 36 GB, and 48 GB costs about $800 more than the mini with 48 GB. |
| 10 | Mac mini M6 16 GB or 24 GB | $899 for 16/256 at Apple ($779.99 at Amazon on 10 Oct), or about $1,299 for 24/512 (press, and Amazon per an aggregator) | A silent, low-power box for the CLIs and gh. | Run the 35B model properly, and the memory is permanent. If you won't run a local model, a Linux mini box or the cloud admin does the same job for less. |

## Do now, free (before buying anything)

- Write the buy threshold first (suggested: 20+ hours a week blocked only by the PC while ready local-model work existed, and at least half of local-model PRs accepted; your numbers). Then log every hour by cause: PC off / game running / quota exhausted / no ready local-model task. Without those numbers, $1,500-2,300 is a guess.
- An agent adds a macos-latest job to `ci/github-actions-ci.yml`; you paste it into `.github/workflows/ci.yml` on GitHub's web page. That tests Mac compatibility on GitHub's free Apple Silicon (M1) runners without giving the agents' shared token the `workflow` scope.
- Create the free GitHub machine account, a ruleset on main (PR plus your approval, approvals dismissed on new pushes, no bypass) and CODEOWNERS for `.github/`, `tools/ai-team/` and `scripts/game/`. Log the autonomous agents' gh in as the machine account. Until this exists, 'only you merge' is a rule agents are asked to follow, not one GitHub enforces.
- Add the trusted-author filter in code, so the Lead and woken agents only read issues, PRs and comments written by you or the machine account. A sentence in a prompt is not a control.
- Swap Qwen3-14B for Qwen3.6-35B-A3B or KAT-Coder-V2.5-Dev on the 4070 Ti (IQ4_XS, 20-24 MoE layers on the CPU, q8 KV, 32K, memory mapping off, preserve_thinking, higher output limit, other apps closed). You approve the roughly 20 GB download. Expect RAM near the guardian's 85/90% limits; if it can't run within them, the result is 'inconclusive', not 'weak'. Log RAM % and the largest context used.
- Use the 35B model and Jules's free tier (15 tasks per 24 h, 3 at once) for the trial workload, for example the Mac-port tasks or other small ready issues. That keeps scarce Claude and Codex quota off work that only matters if you buy a Mac.
- Build the game-test queue in hand-started mode: you run `poll-game-tests.ps1 -Issue <n>` for each job. It checks the issue author through the API (never labels), the schema, the allowlist, and that the commit came from a PR you approved. It works with a cloud admin today and with a Mac later.
- From Oct 13, if Claude Code Projects is on your account: one Project plus schedule-only routines, with a budget (same weekly limit; daily caps unconfirmed). Never trigger them on 'PR opened', because anyone can open a PR on a public repo.
- Use `@codex review` only after checking whether outside accounts can trigger it (undocumented); until then, watch Codex usage.
- Don't expose the guardian proxy on the LAN, install a self-hosted GitHub runner on the gaming PC, add repository secrets, or add the `workflow` scope to the shared token.

## The Mac's role

### What the Mac admin is
A headless Mac mini that **never runs the game**. It coordinates the agents and writes and tests code around the clock. It hands builds, deploys and in-game tests to the PC through GitHub.
- The agents get their own **standard (non-admin) macOS user** and full use of it. Your admin account keeps the Apple ID, payment details and passwords. Don't sign the agent user into an Apple ID that has a payment method.
- You do every login. The agent user's `gh` is logged in as the **GitHub machine account**, never as you. That way agents on this machine can't merge without your approval or change workflow files.

### Must exist before it wakes any agent
1. **Machine account and ruleset.** The machine account has Write access. A ruleset on `main` requires a PR with your approval, dismisses approvals when new commits are pushed, and has no bypass list (you can edit the ruleset yourself if you ever need to). `.github/CODEOWNERS` covers `.github/`, `tools/ai-team/` and `scripts/game/`.
2. **Trusted-author filter, in code.** The Lead, woken agents and the local model only ever see issues, PRs and comments written by you or the machine account. Everything else is dropped before any model reads it.
3. **Usage accounting covers both machines**, or a fixed share of each weekly limit is set aside for your own sessions.
4. **The day-one login test below has passed.**

### Runs on the Mac, 24/7
| Job | How |
|---|---|
| **Lead loop** | A Python port of `run-lead.ps1`, started by launchd (a persistent service, so you approve it). It reads the board, #32 and the handoff through the trusted-author filter, writes briefs, sends work to the OpenCode Implement/Research/QA agents, wakes Claude/Codex/Grok within the shared usage budget, and files game-test jobs. It never pauses, because there's no game on this machine. |
| **Local model** | LM Studio (MLX engine) serving Qwen3.6-35B-A3B or KAT-Coder-V2.5-Dev at 4-bit, behind the guardian proxy on `127.0.0.1:1235` as today. Set the context from what the PC trial shows the Lead needs: 32K today, and a community run on this chip completed 64K. Turn on `preserve_thinking` and raise OpenCode's output limit (4,096 today in `opencode.json`), or tool calls break. oMLX is the alternative for its SSD prompt cache, but switching would likely need code changes. |
| **Cloud CLIs** | Claude Code, Codex CLI and Grok CLI (whether Grok CLI has a macOS build wasn't checked). The Mac becomes the **only** machine where `wake_agent.py` wakes agents automatically. |
| **GitHub** | `gh` as the machine account handles triage, the board, PR text, `gh pr review --comment`, #32 status text and `game-test` jobs. You approve and merge in your browser; the ruleset enforces this once it exists. |
| **Code + checks** | `src/fo4sf` converters (NIF, mesh, BA2, Havok, collision, materials, door planning), `scripts/oracles`, the offline route planner and judge, deployment logic (mocked tests), the `dotnet/` plugin writer and its tests, `scripts/guard.py`, and `python -m unittest discover tests` before every PR. |
| **Optional research data** | Your own copies of Fallout4.esm (0.33 GB) and Starfield.esm (1.46 GB) for recon and Fo4Export work. Copy them rather than mounting a share (build checkpoints record paths and timestamps). They never go into Git. |

### Stays on the Windows PC
- **Starfield and every in-game test:** `scripts/game/*.ps1`, `C:\Modding\research\s1\cycle.ps1`, OCR, probes and the #32 screenshots. The focus guard stays, and agents ask first when you're at the PC.
- **Production builds:** `convert_batch.py` needs texconv.exe, which is Windows-only. Build checkpoints don't carry between machines, so the PC stays the only machine that builds what you deploy.
- **Deployment and Windows-only tools:** `deploy_starfield.py` (Archive2.exe, `Plugins.txt`), the CALUMI door export (a Windows DLL), Creation Kit and xEdit.
- **The game-test poller** and any Claude or Codex session you start yourself. Nothing on the PC is woken automatically any more.
- **The PC's local model becomes optional.** Turning it off gives the game the whole GPU and all 32 GB of RAM.

### Handing game tests to the PC
**Phase A: you start each job (begin here)**
1. A Mac agent branches and opens a PR. CI (Ubuntu and macOS) must pass, QA reviews it, and you approve and merge.
2. The Mac Lead opens an issue from the `game-test` form containing exactly one fenced JSON block, for example `{"commit": "<sha on main>", "build": "<staging name>", "routes": ["<id from the allowlist>"], "timeout_min": 45}`. It then adds the `game-test` label itself. The form doesn't add the label, because anyone can fill in a form on a public repo.
3. You run `scripts/game/poll-game-tests.ps1 -Issue <n>` yourself. It shows the job and the PR that put the commit on main, and waits for your yes.

**Phase B: automatic in test mode, only once all three of these exist**
- **(1)** The machine account and the ruleset above.
- **(2) A fixed checkout.** The poller, the game scripts and the deploy step run from a separate checkout that you update by hand to a commit you reviewed. Only the conversion runs at the job's commit.
- **(3) A separate standard Windows user for conversion.** It can read the FO4/Starfield Data folders, write one staging folder, and can't touch your profile. Only the final copy into the game runs as you, done by the fixed-checkout deploy script.

The poller is a scheduled task that starts at logon, so it runs in your desktop session (SSH sessions can't see the game window). It takes jobs only while your test-mode flag is on.

**Checks on every job, in both phases:**
- The issue's author, and the last editor of the job block, are you or the machine account (checked through the API, including edit history). Labels count for nothing, and a body edited by anyone else is rejected.
- The JSON matches the schema, the routes are on the allowlist, and the timeout is capped.
- The commit reached `main` through a merged PR that your account approved (checked through the API).
- A daily job cap, set in config.
- The focus guard stays on, and the poller asks first when you're at the PC.
- Logs, the staging hash and screenshots are posted to the issue and to #32 using a fine-grained token you create (this repo only; Issues read/write, Contents read).

The Mac Lead reads the result on its next pass and files the follow-up work.

**Rules:**
- No inbound ports and no SSH into the PC.
- No self-hosted GitHub runner (GitHub warns against them on public repos).
- The guardian proxy stays on localhost.
- No repository secrets, and only you change workflow files.
- Claude routines run on a schedule only, never on 'PR opened'.
- Text from anyone other than you or the machine account is dropped in code before a model reads it. Even trusted text is never run as commands.

### Power cuts, reboots and logins
- **Energy settings:** "Start up when power is connected: After power failure" (needs macOS 26.5 or later) and "Prevent automatic sleeping".
- **FileVault:** I suggest keeping it on. After a power cut the Mac waits at the unlock screen, and you unlock it over SSH from the PC on your home network. This works on macOS 26 or later, according to Jeff Geerling's blog, not an Apple document.
- **The login catch:**
  - A LaunchAgent runs only while the agent user has a GUI login session, and FileVault turns off automatic login.
  - Claude Code keeps its login in the Keychain. Its docs say it falls back to `~/.claude/.credentials.json` when the Keychain rejects a write, for example when it's locked over SSH.
  - One unverified report says `claude -p` started from launchd reports "Not logged in" even though valid Keychain credentials exist.
  - How Codex and Grok store their logins on macOS wasn't checked.
- **Day-one test:** cold boot, unlock over SSH, then confirm that the Lead loop and one `claude -p` wake both start from launchd.
- **If the test fails, you choose one fix:**
  - (a) a LaunchDaemon with `UserName` set to the agent user
  - (b) `claude setup-token`, putting `CLAUDE_CODE_OAUTH_TOKEN` and the machine account's gh token in files only the agent user can read (0600). These are secrets in plain files, and that token can't use connectors or Remote Control.
  - (c) you log the agent user in through Screen Sharing after every unlock
  - (d) FileVault off with automatic login (weaker security)
- **Remote access:**
  - Allow Remote Login and Screen Sharing for your admin account only.
  - Use SSH keys for routine logins (the FileVault unlock still asks for your password).
  - Keep both reachable only on the home network, or over Tailscale once you're logged in.
- **Not checked:** how to stop macOS updates from rebooting the Mac unattended, and whether a headless mini needs an HDMI dummy plug for usable Screen Sharing.

### Storage budget for 512 GB
| Item | Size |
|---|---|
| macOS, Xcode command-line tools, .NET 9, Node, Python | tens of GB (my estimate) |
| Local models | about 20-50 GB each; two or three is roughly 50-100 GB (estimate) |
| oMLX SSD prompt cache (only if used) | not measured |
| Repo, venv, `.opencode` node_modules | small (not measured) |
| Fallout4.esm + Starfield.esm copies (optional) | 1.8 GB |
| Staging builds (about 6 GB each) | stay on the PC |
| FO4 BA2 copies | not planned; their size was never measured, so measure before copying |

512 GB should fit this with room to spare. If it fills, add an external SSD (price not researched) rather than paying +$300 for 1 TB up front.

## Setup steps

1. **owner+agent:** Write the buy threshold into docs/ai/admin-node-log.md before any logging starts (Suggested starting point (the numbers are yours to set): buy only if, over two weeks, at least 20 hours a week were blocked only by the PC (off or Starfield running) while ready local-model work existed, and at least half the local-model PRs were accepted by QA or you. Paid usage or a higher plan is the other way to spend the money, but those prices weren't researched.)
2. **agent:** Start the hourly blocker log (one cause per hour, plus local-model tasks accepted vs abandoned, RAM %, and the largest context the Lead used) (PC-off hours are inferred from gaps, because nothing runs while the PC is off. Claude is out of quota until Oct 13, so those hours count as quota-exhausted, not as hours a Mac would recover.)
3. **owner+agent:** An agent adds a macos-latest job to ci/github-actions-ci.yml; you create .github/workflows/ci.yml from it on GitHub's web page (Keeps the `workflow` scope off the agents' shared token. GitHub's Apple Silicon (M1) runners are free for public repos, and this shows whether the 254 tests pass on macOS before you spend anything.)
4. **owner:** Create the GitHub machine account (Write access) and a ruleset on main: PR plus your approval, approvals dismissed on new pushes, no bypass list. Then log the autonomous agents' gh in as the machine account (Free; GitHub's terms allow one machine account. An agent can write the CODEOWNERS file. This is required before any automatic game test and before the Mac. You keep approving and merging in your browser as yourself.)
5. **agent:** PR: the trusted-author filter for the Lead, wake_agent and OpenCode agents (Small and useful on the PC today. You review and merge.)
6. **owner+agent:** Trial Qwen3.6-35B-A3B or KAT-Coder-V2.5-Dev on the 4070 Ti (IQ4_XS, about 20-24 MoE layers on the CPU, q8 KV cache, 32K context, preserve_thinking on, higher OpenCode output limit, other apps closed) and log before/after against Qwen3-14B in docs/ai/optimization.md (You approve the roughly 20 GB download. Memory mapping stays off (load_model.py already does this). Expect RAM around 87-100% by arithmetic from today's measured 71.4%. Any temporary change to the guardian's 85/90% limits needs your approval and goes in optimization.md. If the model can't run within the limits, record 'inconclusive', not 'weak'.)
7. **agent:** Give the Mac-port tasks (resources.py macOS backend, wake_agent shutil.which, Python Lead loop) to the 35B model and Jules as the trial workload, checked by the macOS CI job (Measures quality on real repo work without spending Claude or Codex quota on Mac-only code. If you'd rather not spend anything on Mac work before deciding, use other ready issues. Only you merge.)
8. **owner+agent:** Build the hand-started game-test queue (form without auto-label, schema, allowlist, poll-game-tests.ps1 -Issue <n>) and create the fine-grained token it posts results with (An agent writes it; Claude can help after Oct 13. You create the token (this repo only; Issues read/write, Contents read) and run every job yourself until the Phase B protections exist.)
9. **owner:** After Oct 13: if Claude Code Projects is enabled on your account, try one Project plus schedule-only routines (for example nightly triage) as the cloud admin (Projects is a public beta rolling out gradually, and routines are a research preview. Both use the same weekly limit; daily routine caps (5 on Pro, 15 on Max) are unconfirmed. Remove connectors the routines don't need. If Projects isn't available, keep the Lead loop on the PC.)
10. **owner:** Before relying on @codex review, check from an account that isn't a collaborator whether its @codex comment starts a task (Who can trigger @codex on a public repo is undocumented. Until you've checked, watch Codex usage for unexpected tasks.)
11. **owner:** Decide around the end of October against the written threshold. If buying: Mac mini M5 Pro 48 GB / 512 GB on the base chip; the M6 32 GB / 512 GB if your cap is about $1,500; a refurbished M4 Pro 48 GB only if one appears clearly cheaper (Spending money is your decision. Confirm every price at checkout: the 48 GB, 64 GB and M6 32 GB prices come from press reports, not Apple. The memory, and reportedly the SSD, can't be upgraded later.)
12. **owner:** First boot: create your admin account, decide on FileVault, create a standard (non-admin) user for the agents, set Energy to start after a power failure and to prevent sleep, and turn on Remote Login and Screen Sharing for your admin account only, using SSH keys, home network only (These are security settings and passwords, so you do them. Automatic power-on needs macOS 26.5 or later.)
13. **owner+agent:** Install the toolchain: Xcode command-line tools, Python 3, git, gh, Node, .NET 9 SDK, LM Studio, and pwsh only if you keep the PowerShell scripts (An agent lists the exact commands; you approve them and type the admin password)
14. **owner:** Sign in as the agent user: gh as the machine account (never your own account), Claude Code, Codex (`codex login --device-auth`) and Grok (Agents never see passwords. Check that Grok CLI exists for macOS (not verified).)
15. **agent:** Clone the repo, create a venv, `pip install numpy pillow`, run `npm install` in .opencode, then run `python -m unittest discover tests`, guard.py and the dotnet build/tests, and post the results to an issue
16. **owner+agent:** Download the model in LM Studio's MLX engine, load it with load_model.py at the context the trial showed is needed, and time one Lead step against the PC's current 40-135 s (You approve the large download. On an M6 32 GB, even 32K may need the GPU memory limit raised with sudo (iogpu.wired_limit_mb), which needs your approval.)
17. **owner+agent:** Day-one login test: cold boot, unlock over SSH, then check that the Lead loop and one `claude -p` wake both start from launchd. Pick the fix if they don't, and install the service (The options are your decisions: a LaunchDaemon with UserName=agent; setup-token plus gh token in 0600 files (secrets in plain files, and no connectors or Remote Control); logging the agent user in via Screen Sharing after each unlock; or FileVault off. The service is persistent, so you approve it.)
18. **agent:** Put usage accounting in place (a reserved share for you, or combined logs), then switch automatic agent waking to the Mac only: turn off wake_agent and the Lead loop on the PC and update AGENTS.md (Without this, two machines wake the same account and burn its weekly limit twice)
19. **owner+agent:** Power-cut test: pull the Mac's plug, confirm it powers back on, unlock it over SSH from the PC, and check that the Lead loop comes back. Also check what a macOS update reboot does (Whether the SSH unlock also starts the agent user's session is unconfirmed)
20. **owner+agent:** Phase B, only when you want automatic game tests: create a separate standard Windows user for conversion (read-only on the FO4/Starfield Data folders, one staging folder, no access to your profile), set up the fixed reviewed checkout for the poller, game scripts and deploy step, then turn on the logon-started poller in test mode (Creating the Windows user needs admin rights and the scheduled task is persistent, so you do or approve both. Until then, every job stays hand-started.)

## Repo changes it would need

- CI without widening the agents' token: an agent adds a `macos-latest` job next to `ubuntu-latest` in the staged `ci/github-actions-ci.yml`. The job runs `pip install numpy pillow`, `python scripts/guard.py` and `python -m unittest discover tests -v`, plus an optional `dotnet test` step on .NET 9. You then create `.github/workflows/ci.yml` with that content using 'Add file' on GitHub's web page. The shared `gh` token never gets the `workflow` scope, so agents can't create or change workflows later. Don't add repository secrets.
- `.github/CODEOWNERS` (new): your account owns `.github/`, `tools/ai-team/` and `scripts/game/`. It takes effect once the `main` ruleset requires code-owner review, after the machine account exists.
- Trusted-author filter (new, for example `tools/ai-team/trusted_gh.py` plus a `trusted_authors` list in `tools/ai-team/config.json`). The Lead loop, `wake_agent.py` briefs and the OpenCode agents read issues, PRs, comments and #32 only through it. It drops anything whose API author isn't you or the machine account before a model sees it. Point the OpenCode agents at it in `opencode.json` instead of raw `gh issue/pr view`. Add a unit test with mocked `gh` output. It is useful on the PC today.
- Usage accounting, required before the Mac wakes agents: `tools/ai-team/remote_usage.py` and `wake_agent.py`'s idle check see only the machine they run on. Simplest fix: set aside a fixed share of each weekly limit for your interactive sessions in `config.json`, and let the Lead budget only the rest. Alternatives: combine logs from both machines, or have the Lead read each provider's own usage readout.
- Blocker log (new, for example `tools/ai-team/blocker_log.py` writing to the state folder, summarised in `docs/ai/admin-node-log.md`). One row per hour with the cause: working / PC off (inferred from gaps) / game running / quota exhausted / no ready local-model task. Also log local-model tasks accepted vs abandoned, RAM %, and the largest context the Lead used. Write the buy threshold at the top before logging starts.
- `tools/ai-team/guardian/resources.py`: add a platform switch with a macOS backend. ram(): `sysctl hw.memsize` plus `vm_stat`. cpu(): `top -l 1` (psutil would be a new dependency, so ask first). processes(): `ps -axo pid,rss,comm` instead of tasklist (lines 107-121). Keep gpu() working without nvidia-smi (lines 28-32). Add a unit test with mocked command output. Do this after a purchase, or use it as a trial task for the local model or Jules.
- `tools/ai-team/config.json`: a Mac profile with RAM limits retuned for unified memory (the model's weights count as RAM) and the new model names. The setting that pauses the model during games does nothing on the Mac.
- `tools/ai-team/wake_agent.py:32-33`: find codex and grok with `shutil.which()`, falling back to the current Windows .exe paths.
- New `tools/ai-team/lead_loop.py`: a Python port of `run-lead.ps1` and `start-team.ps1`, used on both machines. It is a good Jules or local-model trial task, or do it after a purchase. The minimum alternative is pwsh fixes: LOCALAPPDATA (run-lead.ps1:10, start-team.ps1:8; use FO4_AI_TEAM_STATE or store.py's ~/fo4-ai-team/state fallback), the backslash path (run-lead:29), the opencode.exe path (run-lead:31), `powershell` to `pwsh` (run-lead:47), and dropping `-WindowStyle Hidden` (run-lead:55, start-team:13).
- `tools/ai-team/load_model.py`, `opencode.json` (repo root; lines 13-16 set 32,768 context and 4,096 output today) and `.opencode/agents/*.md` if they name the model: switch to the MLX 4-bit model (Qwen3.6-35B-A3B or KAT-Coder-V2.5-Dev), take the context from the trial log, raise the output limit and turn on preserve_thinking. Skip the GGUF-only settings (KV quantization, flashAttention, gpu.ratio) when the engine is MLX.
- New `tools/ai-team/macos/`: launchd templates for both a LaunchAgent and a LaunchDaemon with `UserName` (the day-one login test picks one), plus a Mac setup section in `tools/ai-team/README.md`. Document the fresh `npm install` in `.opencode`, because the local node_modules contains a Windows-only module. Installing either template is a persistent service, so you approve it.
- `src/fo4sf/textures.py:117-122` and `src/fo4sf/pipeline.py:110-138`: when texconv.exe is missing, raise a clear 'texconv is Windows-only; real conversions run on the PC' error instead of a raw subprocess failure. Don't add a Compressonator backend: its output bytes would differ from the PC's builds.
- Game-test hand-off files:
- `.github/ISSUE_TEMPLATE/game-test.yml` with no `labels` key (the Lead adds the label).
- `scripts/game/game_test_job.schema.json` (commit SHA, build name, route ids, timeout cap).
- A route allowlist file.
- `scripts/game/poll-game-tests.ps1`. It starts in hand-run mode (`-Issue <n>`, waits for your yes). It checks the author and edit history through the API, ignores labels, checks the commit came from a merged PR you approved, and enforces the schema, allowlist and a daily job cap. It calls only `scripts/game/*.ps1` and `cycle.ps1`, and posts results with your fine-grained token.
- Document the Phase B design (fixed reviewed checkout, separate standard Windows user for conversion) before turning on automatic mode.
- `AGENTS.md` and `docs/ai/handoff.md` (new) document:
- Machine roles: the Mac is the admin; the PC is the test rig and the only machine that builds and deploys.
- Automatically woken CLI agents run only on the Mac.
- The trusted-author rule.
- 'Only the owner merges', marked as enforced once the machine account and ruleset exist.
- Routines are schedule-only.
- Labels: game-test, game-passed, game-failed.
- Issue text is never run.
- Write repo-relative paths in docs, because `scripts/guard.py:19` rejects machine-specific home-folder paths.

## Risks

- The Mac adds no frontier-model capacity. Claude, Codex and Grok limits are per account, and an agent running 24/7 can use up the same weekly limit faster. Only a local model, Jules's free tier, or paid usage or a higher plan add capacity. Paid usage is your money decision, and its prices weren't researched, so the $2,299 couldn't be compared with buying more quota.
- The local model is a junior: 18 vs 58 for Opus 5.5 on Artificial Analysis's general index. Users report reasoning loops and malformed tool calls in long OpenCode sessions, and one bad turn can end a run. Converter design, format reverse-engineering and in-game debugging stay with Claude and Codex.
- Prompt injection from public input. Anyone can open issues, PRs and comments, and the agents reading them hold gh and CLI login tokens. Claude routines run without permission prompts, their connectors can write without asking, and their commits go out under your GitHub user. Mitigations: the trusted-author filter in code, schedule-only routines, removing unneeded connectors, and a machine account without the workflow scope. Whether outside commenters can trigger @codex on a public repo is undocumented; test it before relying on it.
- The game-test queue is the most dangerous piece:
- Today, a commit being on main doesn't mean you merged it. Remote agents push as your account, and wake_agent starts Codex with --approve-for-me and network access.
- Agents can edit the very scripts the poller runs.
- Labels from an issue form are applied to anyone's issue.
So jobs stay hand-started until the machine account, the ruleset, a fixed reviewed checkout and a separate Windows user for conversion all exist.
- On the PC, agents run under your Windows account next to your browser sessions, so the ruleset there mainly stops honest mistakes. A separate machine with its own standard user (the Mac or a Linux box) makes the separation real.
- Adding the `workflow` scope to the shared gh token would let any agent create workflows that could read secrets added later. Add CI on GitHub's web page instead, and keep any future subscription token in an environment secret limited to main.
- Unattended logins on macOS:
- A LaunchAgent needs the agent user's GUI session, and FileVault turns off automatic login.
- Claude Code stores its login in the Keychain. One unverified report says `claude -p` from launchd reports 'Not logged in'.
- How Codex and Grok store their logins on macOS wasn't checked.
The agents may sit idle after every reboot until the day-one test settles which fix you accept.
- With FileVault on, every power cut stops the agents until you unlock the Mac over SSH from the home network. That method comes from a blog, not Apple. Turning FileVault off is weaker security, and that choice is yours.
- Memory can't be upgraded (Apple states this), and press teardowns report the 2026 mini's SSD is soldered. A wrong memory size can't be fixed later; extra storage would have to be an external drive.
- Prices aren't fully confirmed:
- The 48 GB and 64 GB upgrade prices come from press reports.
- Sources disagree on the M6 32 GB / 1 TB ($1,299 vs $1,799), and an aggregator on 10 Oct listed no 32 GB M6 or 48 GB M5 Pro price.
- Base-mini prices have climbed from $599 to $799 to $899, blamed on RAM costs, and Apple's refurbished store has no minis today, so waiting for a deal is not a safe bet.
- M6 32 GB numbers are shaky. Its prompt-reading figures are disputed between the two research passes, and whether even 32K context fits under its default GPU memory limit (about 21 GB) is unconfirmed. Raising the limit needs sudo and your approval.
- M5 Pro base-chip speed is less certain than the headline figures:
- One base-chip 8-bit run read only 948 / 911 tok/s.
- The 1,911 / 1,802 run used UD-Q4_K_XL on oMLX 0.3.8, not LM Studio's MLX engine.
- The 26.3 GB peak at 64K was measured on a 20-core, 64 GB machine.
- The 20-core GPU can't be added later.
- The 4070 Ti trial will probably push the PC's 32 GB of RAM to about 87-100% (my arithmetic from the measured 71.4% baseline), above the guardian's limits. The comparison machines had 48-64 GB of RAM, and the earlier '~45 tok/s at 64K' claim could not be confirmed. An inconclusive trial leaves the buy decision without quality data.
- Two machines can double-spend a limit. wake_agent's idle check and remote_usage.py see only the machine they run on, so usage accounting (or a reserved share for your sessions) is required before the Mac wakes agents.
- The Mac can't produce what gets deployed. texconv.exe is Windows-only, a Compressonator substitute would produce different bytes, and build checkpoints don't carry between machines. Every in-game result must name the PC build's commit and staging hash.
- Cloud-admin features may not be available. Claude Code Projects is a public beta rolling out gradually, and routines are a research preview. The daily routine caps and the one-time $100/$250 cloud credit are unconfirmed.
- Untested on macOS: the 254 tests, the .NET 9 / Mutagen build, and a Grok CLI macOS build. The CI job answers the first two before you buy. The benchmarks are community oMLX submissions, mostly from MacBook Pros, and no noise measurement under sustained load was found.
- A refurbished or used M4 Pro 48 GB has no confirmed price or availability, and there are no 35B benchmarks for it in this research.
- Not yet checked: how to keep macOS updates from rebooting the Mac unattended, and whether a headless mini needs an HDMI dummy plug for usable Screen Sharing.
- Resale through Apple is weak: Trade In caps any Mac mini at $620. Private resale of high-memory Macs looks stronger, but that is unconfirmed.
