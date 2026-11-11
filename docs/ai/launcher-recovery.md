# Interrupted installation: one player recovery action

FAL-247 item 5, Codex / The Lone Wanderer. This part covers recovery, before the
separate save compatibility, uninstall/cache and guided-report changes. No new game
format assumptions. The tests construct their own plugin bytes and temporary folders.

When an installer journal says an install or cleanup is incomplete, **Play refuses**
before changing the plugin order, logging settings or starting a process. The window
names the reason and offers **Recover install**. This rolls back the interrupted work;
the player then runs the install again. It does not resume conversion or reinstall
from potentially changed source inputs.

The equivalent CLI is:

```text
python -I scripts/launcher.py recover-install --settings <launcher-settings.json>
python -I scripts/launcher.py recover-install --settings <launcher-settings.json> --apply
```

The first command is a read-only preview. The second applies rollback. Both use the
saved FO4SF instance when configured, including its own LOCALAPPDATA. With no instance,
the saved Starfield location or explicit `--starfield <folder>` is used.

If Plugins.txt has partial or external edits, explicit recovery first keeps every
current byte in an exclusive `Plugins.txt.recovery-*.bak` beside it, flushes the copy
and reads it back. Only then can it restore the same profile's recorded pre-install
bytes. This may deactivate later plugin-list edits; their bytes remain in the backup.
If the list changed after reading it, the guarded restore refuses. The installer
then handles its own files and retires its journal after successful rollback. Saves,
cache and unowned game files are outside this action.

Failures preserve journals and backups. Unreadable or malformed receipts require
inspection; recovery never invents missing receipt data. A healthy installed rider
that needs an interrupted base is refused before any rollback; remove it through its
own installer first. Each installer retains its existing ownership, profile and hash
checks. Multiple interrupted components are attempted in existing uninstall order;
an installer may refuse if another incomplete dependency prevents safe recovery.

## Bounded Windows PC check (no game launch or live installation)

At the independently reviewed remote PR head, use the repository's Python environment
with numpy and Pillow installed:

```text
python -m unittest discover -s tests -p test_launcher_recovery.py -v
python scripts/guard.py
```

Expected: 17 recovery tests pass and guard reports `ok`. Tests run the real installer
on temporary synthetic files, restore BOM/CRLF plugin bytes after an interruption,
preserve a partial list in a verified backup, keep unowned files, refuse corrupt or
foreign-profile receipts, block Play/dry-run before mutations, and stop when the
game/process state is running or unknown. No Starfield, SFSE, Steam, ProcDump, live
profile or game data is needed. Actual Windows file-sharing/Controlled Folder Access
and a real window/game session remain **NOT_RUN** until separately authorized and
recorded. Passing these fixtures establishes offline recovery behavior only.
