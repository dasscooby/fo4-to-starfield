# Vault 111 exit kit (FAL-461, first piece)

Plan: the document `vault111-exit-sequence` on FAL-461. This kit is steps 1 to 3 of it (Pip-Boy pickup, door terminal, cog
door) with quest stages for the order. Gate, walkway box and lift are not in it. Offline only: nothing here ran in game and
the Papyrus was not compiled (no compiler on the Linux box).

Tool: `dotnet/Vault111Exit` (`fixture`, `build`, `check`, `scan`). Plugin `FO4SFVault111Exit.esp`, masters Starfield.esm and
FO4Port.esm, holds: quest `FO4SF_V111Exit` (stages 5, 10, 20, 30; script, no properties), MISC `FO4SF_V111PipBoyToken`, ACTI
`FO4SF_V111PipBoyPickup` and `FO4SF_V111DoorTerminal` (scripts on the base; the terminal has `CogDoorId` and `DoorPlugin`),
and an override of the port's `FO4Port_Vault111Cryo` with two temporary references, one per activator.

Params (`build <params.json> <Starfield.esm> <FO4Port.esm> <out dir>`): plugin, cell, `pickup` and `terminal` (`pos`, `rot`,
`model`, `name`), `cog_door` (`plugin`, `id`). On the PC `scan <FO4Port.esm> FO4Port_Vault111Cryo` lists the references
whose base editor id mentions PipBoy, Console, Terminal or GearDoor, with model and position: those are the params.

Sequence the scripts enforce: Pip-Boy taken (token, stage 10), terminal without the token (message, stage 5), terminal with
it (plug in, stage 20), terminal again (`SetOpen(True)` on the cog door, stage 30).

NEEDS-PC (unproven guesses): an activator over the prop gives a prompt; the duplicate mesh at the same spot looks right; a
temporary reference in a cell override is loaded with the cell; `Game.GetFormFromFile` finds the port's cog door by
`CogDoorId`; the NewGame quest's own proximity opening at the console (its stage 20) must be off in the same run, or the
door opens without the Pip-Boy.
