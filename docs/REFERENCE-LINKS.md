# Translating preserved placement relationships

`dotnet/ReferenceLinks` is an optional postprocessing stage after PluginSpike. It
reads the generated plugin, its persistent `formids.json`, and version-2 cell
exports. It writes to a separate output directory; the input plugin is unchanged.
It refuses to overwrite an existing output plugin.

```powershell
$env:STARFIELD_DATA = '<Starfield Data directory>'
dotnet run --project dotnet/ReferenceLinks -- <input FO4Port.esm> <formids.json> <fresh output directory> <cell1.json> <cell2.json>
```

Supply every involved cell export together so cross-cell targets can resolve.
The tool reads Starfield's current vanilla static records to locate EnableMarker,
XMarker, XMarkerHeading and LightBox by EditorID. Needed source control markers are recreated
with stable IDs, source transforms, disabled state and persistent grouping. It
does not guess an equivalent record for arbitrary missing objects or actors.

LightBox helpers require a fresh export containing primitive bounds, RGBA color,
type and the primitive's unknown value. Bounds convert to metres; RGB colors and
the unknown value are retained. The JSON retains alpha, but the target primitive
binary color stores RGB, so alpha is not a supported target property.
Missing geometry or an unrecognized primitive
type produces an issue instead of creating an empty lighting volume. This has
binary round-trip coverage; equivalent lighting behavior still needs game testing.

Implemented translation:

- Persistent source object placements move into target cell persistent groups and
  retain the persistent flag.
- Enable parents resolve to actual placed target records, including recreated
  control markers. The opposite-state and pop-in flags retain their meanings.
- Linked references resolve placed targets. A null discriminator remains null; a
  discriminator that resolves to a placed object is translated as that reference.
- Default-open state applies to resolved, non-deleted DOOR bases.
- Locks (`lock_data`, FO4 REFR XLOC) are written on resolved, non-deleted DOOR bases only
  and counted as `Locks`. Levels are copied when Mutagen 0.55.0-alpha.67's Fallout4 and
  Starfield `LockLevel` enums give the value the same name: 0 None, 1 Novice1, 25 Novice25,
  50 Advanced, 75 Expert, 100 Master, 255 RequiresKey (only with a key). Flag bit 1
  (LeveledLock, same in both) is kept. A key must resolve through `KEYM:<source formkey>` in
  `formids.json` to an existing, non-deleted KEYM in the plugin (keys compare as parsed FormKeys, so
  case does not matter; two spellings of one key reserved at different IDs make the map invalid and stop the run before any change, even with `--allow-unresolved`); otherwise it is a warning and
  no lock is written (PluginSpike converts no keys, so keyed locks normally fail; a warning, so
  real runs are not blocked; no key is invented). Refused as warnings, nothing written: 251 Barred, 252 Chained, 253
  RequiresTerminal, 254 Inaccessible (what opens them in FO4 is not translated) and locks on
  non-door bases such as containers. RequiresKey without a key is a warning too.
  Issues: any other level, other flag bits. `--strict-activation-parents` blocks on every warning, lock warnings included.
  Synthetic and binary round-trip tests only; not verified in game.
- Absolute teleport destinations resolve placed doors and transition cells;
  positions convert from source units to metres and rotations remain radians.
  Both validated endpoints become persistent (group and flag), even when the
  exported flag is false or absent. This matches PluginSpike's native XTEL rule;
  a one-way link does not invent an unexported return link. Refused links do not
  force persistence; repeating a valid application does not duplicate endpoints.

Native bases are resolved from the actual `Starfield.esm` supplied by
`STARFIELD_DATA`, even with `--no-markers`. A local override takes precedence:
deleted DOORs, STAT overrides and unresolved bases cannot acquire open/teleport
semantics. The native DOOR is not cloned and endpoint IDs are not reallocated.
Without master records, library calls still resolve local doors and refuse unknown
external bases. Other masters are not implicitly read or guessed.

Eleven synthetic CLI cases cover native bases, missing/deleted/non-door records,
local override precedence, `--no-markers`, false/absent source persistence and
one-way endpoints. Library controls also check refusal before promotion and
idempotent application. Serialized readback checks both
persistent endpoint groups/flags, reciprocal XTEL and transition-cell identities,
source transforms, arrival units/rotation, open state and unchanged ID maps/inputs.
Set `FO4SF_NATIVE_DOOR_EVIDENCE` to a fresh private directory to retain the cases;
otherwise the test prints a new temporary evidence directory.

This fixes the optional ReferenceLinks post-pass's native-base rejection recorded
in PR174. PluginSpike remains the main load-door writer. This post-pass still scans
interior cells, not exterior worldspace groups, and cannot yet supply cross-plugin
placed endpoints. The worldspace merge-position problem, native travel and
save/reload acceptance remain separate requirements; binary roundtrips prove none
of those runtime behaviors.

Generic linked-reference keywords (`None` or an absent category, no flags or
attraction rule) now become source-scoped target KYWD records with stable
`KYWD:<source FormKey>` map entries. Color, resolved name and notes are retained.
EditorIDs include a source-identity digest rather than reusing unrelated vanilla
keywords with similar names. Specialized keyword categories/flags/attraction
semantics still need translators. A linked-reference target present in the supplied
source exports, with a valid source FormKey but no placed output record, produces
a counted `linked_references.reference` warning naming source, field and target.
The link is omitted without guessing a replacement; the source export is unchanged.
A reservation held by another record kind (such as STAT), an absent/null/malformed
target, and source/map conflicts remain blocking. Discriminator/keyword validation
still runs when the target produces only a warning, so a bad discriminator still
blocks output. This exception applies only to linked-reference targets: missing
enable parents and teleport destinations retain their blocking behavior.
Unsupported flag bits and relative-position teleports are also unresolved. Relative teleports need
additional handling for the converted door pivot. Ownership, container locks, actor behavior
and scripts remain separate work. No unsupported case is assigned a numeric-ID
guess.

The default refuses to write a plugin while blocking relationship issues remain. A
`relationships-report.json` lists `Issues`, `Warnings` and counts unplaced source references.
`--report-only` computes that report without emitting a plugin; incomplete state
is recorded in `build-state.json`. `--no-markers` disables marker recreation.
`--allow-unresolved` explicitly emits a partial plugin and records its unresolved
count and partial fidelity; this is for research, not proof of complete gameplay.
Every non-null `activate_parents` block in newly exported `refs` produces a counted,
listed warning, even an empty block or a reference with no placed target. These
warnings also print to stderr. The original flags, references and delays remain in
the source export; activation behavior is not implemented. Warnings alone permit
output by default with fidelity `partial_with_warnings`, never
`resolved_exported_relationships`. `build-state.json` counts all issues plus
warnings as `unresolved` and separately records `warnings` and `blocking`.
`--strict-activation-parents` makes every warning block output with exit 2,
including linked-reference and lock warnings despite the option's historical name.
`--allow-unresolved` explicitly overrides that gate (as well as other issues),
recording `partial_explicitly_allowed`. Report-only runs never emit a plugin or
mark the build complete. Other unresolved links retain their existing blocking behavior.

The output includes an updated `formids.json` reserving marker identities. Preserve
that map in subsequent writer/postprocessor runs, or newly added base records
could reuse IDs that were previously allocated to markers. Keep the output map
with the output plugin. The tool currently expects the standalone generated
plugin's only external master to be Starfield.esm; it does not guess master styles
for unrelated mod dependencies.

Synthetic tests run with:

```powershell
dotnet run --project dotnet/ReferenceLinks.Tests
```

They verify cross-cell parent/link/teleport identities, units, persistent grouping,
default-open state, stable control-marker IDs, idempotent links and binary output
round-tripping. They also compare Fallout 4 and Starfield flag names/values and
reject missing targets even if their IDs remain reserved in the map.

A local Vault 81 research run recreated six control markers and restored 109
enable-parent relationships, five linked references, 51 persistent placements and
two default-open door states. Binary read-back confirmed these counts. There were
65 unresolved issues and no resolved teleports in that one-cell run; missing
outside-cell destinations and keyword mapping remain open. This partial plugin
was written only to research scratch, never installed or tested in-game.

A refreshed export retained seven source linked-reference keywords, all generic.
The subsequent research pass created one keyword needed by currently placed
children; issues dropped to 35. Linked references stayed at five because missing
placed targets still block the remaining links. Binary read-back confirmed the
keyword record. Synthetic tests separately prove that a resolvable keyworded link
retains both target identities and survives serialization without duplicates.
Specialized categories are rejected rather than flattened to generic labels.
