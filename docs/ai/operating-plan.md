## Operating Plan

### Roles and Chain of Command
- **Owner (dasscooby)**: Sets goals, merges to main, handles installations and security settings.
- **Lead (local)**: Coordinates between owner and Claude, reviews project state, prioritizes tasks, reports to owner via issue #32 and this document.
- **Claude (remote)**: Primary engineering lead for coding, file-format research, builds, and in-game tests. Operates autonomously except for merges/installs/security changes.

### Claude's Week Plan
- **Work Cadence**: Daily progress updates on issue #32; self-directed tasks with owner approval only for merges or installations.
- **Autonomous Work**: Focuses on PRs #41 (movable items), #38, #39, and research into `.af` formats and collision systems.
- **Owner Interaction Needed For**: Merging to main, launching the game, installs, spending money, security settings changes.
- **Reporting**: Daily status updates on issue #32; this document tracks long-term planning.

### Next Tasks
1. **Test movable items in-game (PR #41)**: Acceptance = successful in-game verification without owner presence.
2. **Fix cycle.ps1 to prevent achievements from swallowing cell jumps**: Acceptance = script runs without interruption during testing.
3. **Resolve Vault 114 door blocked by skeleton**: Acceptance = door opens fully on both sides with ragdoll physics.
4. **Re-run Vault 81 and library tests**: Acceptance = all doors pass through with correct animations.
5. **Finish Prydwen routes and small falls**: Acceptance = all 7 falls are correctly implemented with no collisions.

### Agent Tasks
- **Codex/Grok**: QA review of PR #41 for acceptance testing.