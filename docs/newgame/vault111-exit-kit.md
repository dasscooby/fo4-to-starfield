# Vault 111 exit kit (FAL-461, first piece)

Plan: the document `vault111-exit-sequence` on FAL-461. This kit is steps 1 to 3 of it (Pip-Boy pickup, door terminal, cog
door) with quest stages for the order. Gate, walkway box and lift are not in it. Offline only: nothing here ran in game and
the Papyrus was not compiled (no compiler on the Linux box).

Tool: `dotnet/Vault111Exit` (`fixture`, `build`, `check`, `scan`). Plugin `FO4SFVault111Exit.esm` (master flag, so the installers take it), masters Starfield.esm and
FO4Port.esm, holds: quest `FO4SF_V111Exit` (stages 5, 10, 20, 30; script, no properties), MISC `FO4SF_V111PipBoyToken`, ACTI
`FO4SF_V111PipBoyPickup` and `FO4SF_V111DoorTerminal` (scripts on the base; the terminal has `CogDoorId` and `DoorPlugin`),
and an override of the port's `FO4Port_Vault111Cryo` with two temporary references, one per activator.

Params: `scripts/vault111_exit/params.json`, built from the owner-PC `scan` of the installed port (FAL-461 comment, 11 Nov):
pickup = ref 001616 (base FO4Port_NpcPipboyGroundTake01), terminal = ref 00138B (base FO4Port_V111GearDoorConsole02),
cog door = ref 00126D. A spot names its mesh by `base_edid`: the tool reads that base's model from FO4Port.esm at build time.
`scan <FO4Port.esm> FO4Port_Vault111Cryo` lists such references again after a port rebuild.

Stage and install (PC, same shape as the other kits):

    python scripts\vault111_exit\make_vault111_exit.py precheck
    python scripts\vault111_exit\make_vault111_exit.py stage --out <new dir>
    python scripts\vault111_exit\vault111_exit_install.py install --dir <stage> --starfield <game dir>     (owner's word, game closed)
    python scripts\vault111_exit\vault111_exit_install.py uninstall --starfield <game dir>
    python scripts\vault111_exit\make_vault111_exit.py log        (user log FO4SFV111.0.log)

`stage` builds and re-reads the plugin against the installed Starfield.esm and FO4Port.esm, compiles the three scripts with
the PC's PapyrusCompiler, and writes plan.json (hashes of every file and both inputs). `install` refuses a stage that no
longer matches its plan or either input, never overwrites a game file, packs the .pex into a ba2, appends the plugin line and
keeps its own record (uninstall removes exactly that).

Sequence the scripts enforce: Pip-Boy taken (token, stage 10), terminal without the token (message, stage 5), terminal with
it (plug in, stage 20), terminal again (`SetOpen(True)` on the cog door, stage 30). The log shows `pickup: taken, stage 10`,
`terminal: plugged in, stage 20`, `terminal: cog door open_state before=.. after=..`; `log` gives yes/NO per step.

The new-game quest's own opening of the cog door: it runs only inside the new-game start (its stage 20, player within 2.5 m of
the console). So test the kit from a save already past the start, not a fresh new game; there nothing else opens the door.
For a fresh new game the way to switch it off is a NewGame build option that writes `CogDoorId` 0 (the script then skips the
branch); that is an edit of Claude's NewGame tool and its contract tests and is NOT in this PR: say so if wanted.

NEEDS-PC (unproven guesses): an activator over the prop gives a prompt; the duplicate mesh at the same spot looks right; a
temporary reference in a cell override is loaded with the cell; `Game.GetFormFromFile` finds the port's cog door by
`CogDoorId`; the scripts compile (never compiled offline).
