# Next phase: voice, lip sync and companions (research, 2026-10-19)

Codsworth thread (Claude-cloud). Labels: **verified** (file, count or output cited), **supported hypothesis**,
**unresolved**. Nothing here was run in game except where it says so.

## Bottom line

1. **Every Fallout 4 voiced line can be built on the user's PC from their own files.** The steps are a split of each
   `.fuz` into lip data and xWMA, ffmpeg to WAV, an encoder to `.wem`, and lip sync to `.ffxanim`. The first four
   steps already work end to end for 20 Codsworth lines (PR #361, merged). What isn't proven is playback in game.
2. **Lip sync can likely be made with Starfield's own tools.** Starfield's Tools folder on the PC ships the FaceFX
   compiler (`ffxc.exe`) and face actors for it. What isn't known is whether it runs from the command line.
3. **The one hard dependency is the encoder.** Wwise can't be redistributed, so the launcher would need the user to
   install it. The cheapest next test is a `.wem` we write ourselves (PCM, then ADPCM). If the game plays that, Wwise
   drops out of the launcher completely.
4. **Companions:** Starfield has a native affinity record type (`AFFE`) that Fallout 4 lacks, plus a gated affinity
   model like Fallout 4's. To stay far from Starfield's content, we'd keep Fallout 4's data (thresholds, reactions,
   lines), write our own scripts, and use only the engine's follow AI and affinity plumbing. Codsworth is the natural
   first companion because his model and voice pipeline already exist.

## Scale (verified, repo measurements)

| | Fallout 4 | Starfield |
|---|---|---|
| Voice files | 122,857 `.fuz` (base game; DLC adds more) | 325,246 `.wem` |
| Lip files | inside each `.fuz` | 278k `.ffxanim` |
| DIAL / INFO | 35,443 / 78,089 | 68,154 / 126,347 |
| SCEN | 3,568 | 7,613 |
| VTYP (voice types) | 531 | 683 |
| AFFE (affinity events) | none | 1,360 |

Sources: `docs/FORMAT-GAP.md`, `docs/measurements/fo4_esm.json`, `sf_esm.json`, `esm_compare.json` (AFFE is in
`sf_only_record_types`). INFO shares only 38% of its subrecord types between the games. Starfield adds 20, including
`TSCE`, `PNAM` and `FLMV`, so INFOs are rebuilt rather than copied.

**Size estimate (supported hypothesis, to be measured):** about 3 s per line, as Vorbis at roughly 64 to 80 kbit/s,
gives about 30 KB per line. That's about 4 GB of `.wem` for the base game, plus small `.ffxanim` files. Uncompressed
PCM would be about 30 GB, and ADPCM about 8 GB. The real average comes from the PC count job below.

## Voice pipeline

**Verified (PC runs, 2026-10-18, PR #361):**
- A `.fuz` is `FUZE`, u32 version, u32 lip size, the lip data, then an xWMA RIFF (`codsworth_voice.py split_fuz`).
- ffmpeg (pip `imageio-ffmpeg`; winget's package failed its hash check) decodes xWMA to 44.1 kHz mono 16-bit WAV.
- Vanilla `RobotMiniBotA` voice `.wem` files are Wwise Vorbis (codec `0xffff`), mono, 44,100 Hz, fmt size 66. Each
  is named `<INFO id>.wem` under `sound\voice\starfield.esm\<voicetype>\`.
- Wwise 2026.1.3's WwiseConsole converted 20 WAVs to `.wem` with the same header fields. Starfield's project uses
  2021.1.10.7883, and the Xbox porting guide asks for 2021.1.14.8108, so 2021.1.x is the safe family.
- Codsworth's lines: 3,010 of his INFOs, 2,526 with voice (`codsworth_lines.py`). FO4 topics sit inside each quest's
  type-10 child group, not in a top-level DIAL group.

**Verified (PC Tools listing, 2026-10-18):** `<Starfield>\Tools` contains the full Wwise project
`wwise\Starfield\Starfield.wproj` (conversion settings, Dynamic Dialogue), `LipGenerator` (`LipGenerator.exe` plus
`FonixData.cdf`), `FaceFX` (`ffxc.exe` plus `StarfieldHumanMale`, `StarfieldHumanFemale` and `GenesisDefault`
`.facefx` actors), `RoboVoicer.exe` and Archive2. WwiseConsole isn't there, so Wwise itself is a separate install.

**Supported hypotheses:**
- **Exact conversion settings come free.** Converting with a *copy* of Starfield's own `Starfield.wproj` and its
  Voice conversion ShareSet should match vanilla exactly. It has to be a copy because opening it in a newer Wwise
  migrates the project in place.
- **File names can be a straight rename.** If the port keeps each FO4 INFO's id, the files are
  `sound\voice\<our master>.esm\<FO4 voice type>\<FO4 INFO id>.wem`. The path rule for a plugin that isn't
  Starfield.esm is still **unresolved** until Codsworth's greetings play.
- **The launcher can skip Wwise if a self-written `.wem` plays.** Starfield's Wwise runtime should decode PCM `.wem`
  (codec `0xfffe`) and Wwise ADPCM, and neither needs Wwise to encode. vgmstream documents both formats. PCM is about
  10 times the size of Vorbis and ADPCM about 4 times smaller than PCM. No open-source Wwise *Vorbis* encoder was
  found: ww2ogg and vgmstream only decode.
- **Licensing:** Wwise is free for non-commercial use but installs through Audiokinetic's launcher under the user's
  own account. The launcher can detect it and guide the user, but must never bundle it.

## Lip sync

- **Verified (UESP Starfield mod wiki):** the Creation Kit's *Audio > Run FaceFX Compiler* scans a plugin's dialogue,
  makes `.animset` files from each WAV and its response text, then compiles them to `.ffxanim` in the voice folder.
  Progress goes to `ffxc_00.log`. The page also says *"the Voice Type must match the character's body type for lip
  sync to work."*
- **Verified:** `.ffxanim` files are language-independent. `SFBGS003 - Main.ba2` holds 4,462 `.ffxanim`, the same as
  the 4,462 `.wem` in `SFBGS003 - Voices_en.ba2` (`docs/measurements/sf_ba2.json`).
- **Unresolved:** whether `ffxc.exe` runs from the command line, with what arguments, and how fast. This decides
  whether the launcher can make about 120k lip files unattended or needs the Creation Kit open. The plan is a small,
  read-only PC job (below).
- **Fallback (supported hypothesis):** FO4's own lip data sits in every `.fuz`, and Fallout 4's Creation Kit also
  made it with FaceFX. Converting those curves to Starfield's face rig is possible in principle but harder than
  regenerating from WAV plus text, which we already have (ILSTRINGS).
- **Robots:** Codsworth's mini bot body has no face, so he needs no lip files. Humans (Preston, Piper, Nick and the
  rest) on Starfield's human face use the `StarfieldHumanMale` and `StarfieldHumanFemale` actors.

## Player voice

Fallout 4's player is voiced (`PlayerVoiceMale01`, `PlayerVoiceFemale01`), but Starfield's player is silent, with a
list menu. Playing the player's lines would need the player to have a voice type and the menu to wait for the line.
That's **unresolved**. The suggested default is subtitles only for player lines, with an experiment later.

## Companions

**Fallout 4 side (to verify from Fallout4.esm on the PC; from community knowledge, unverified here):**
- The companions are Codsworth, Dogmeat, Preston, Piper, Nick, Cait, Curie, Danse, Deacon, Hancock, MacCready,
  Strong and X6-88. The DLC adds Ada, Old Longfellow and Gage.
- The framework is the `Followers` quest plus one `COM<Name>` quest per companion. Affinity is a per-companion value
  moved by reaction events (Like, Love, Dislike, Hate) with thresholds that unlock talks and perks. Bark and commentary
  topics sit inside those quests.
- Preston already carries `CompanionCrimeFaction_Preston`, the Current, HasBeen and Potential companion factions, and
  `Voices_CompanionsFaction` (verified, `docs/spikes/B4-mission-anatomy.md`).

**Starfield side (verified count, starfieldwiki for behaviour):** 1,360 `AFFE` records. Reactions are Loves +50,
Likes +25, Dislikes -15 and Hates -35. A "Wants to Talk" state, and story gates at 100, then 200 to 800 in steps of
100, each with a minimum real-time wait. That's the same shape as Fallout 4's system.

**Recommended design (supported hypothesis):**
- Build our own companion quests from FO4 data: thresholds, which actions each companion likes, and their lines. Keep
  our own scripts, because FO4 `.pex` won't run in Starfield and no FO4 sources ship.
- Use only engine-native pieces underneath: follower AI packages, and `AFFE`-style events if they turn out to work
  without Starfield's companion quests. Whether they do is **unresolved**.
- Order: Codsworth (model and voice done; follow, wait and talk), then Dogmeat (no dialogue), then Preston (ties to
  the mission), then the rest by line count.
- Cloud threads can't compile Papyrus, so companion scripts are a PC build step.

## Next experiments (small; first ones need no new installs)

1. **In game, after the v6 swap:** does Codsworth greet the user with the 20 Wwise-2026 lines? A subtitle with no
   sound points to Wwise version or path. Note: Starfield's `DialogueMiniBot` and `DialogueGenericRobotModelA` start
   with every game, so he may also speak vanilla mini-bot lines.
2. **No-Wwise test (cloud builds, PC plays):** write one PCM `.wem` and one Wwise ADPCM `.wem` for the same greeting.
   If either plays, the launcher needs only ffmpeg.
3. **Read-only PC job (tiny):** `ffxc.exe` with `-h` or `/?`, plus `LipGenerator.exe` and `RoboVoicer.exe` the same
   way. Capture the usage text only.
4. **Read-only PC job (tiny):** count `.fuz` files and bytes per voice-type folder in `Fallout4 - Voices.ba2` and the
   DLC voice archives. List `COM*` and `Followers` quests and the `CA_` globals and keywords in Fallout4.esm. This
   turns the estimates above into numbers.
5. **Later:** convert one batch with a copy of `Starfield.wproj` under Wwise 2021.1.x, and time
   Wwise and ffxc per 1,000 lines for the launcher's build-time budget.

Sources: [UESP Starfield mod wiki, audio conversion](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion);
[Xbox audio porting guide](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Porting_Custom_Audio_Files_to_Xbox);
[FaceFX forum, embedded in the Starfield CK](https://facefx.com/node/4600);
[Starfield affinity](https://starfieldwiki.net/wiki/Starfield:Affinity); repo `docs/measurements/*`, PR #361.
