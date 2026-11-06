# Background-game audio: the original games play their own voices and music while we play in Starfield

The owner, 1 November 2026: "a mod for fallout 4, nv, 3, 2, 1 to have the games run in a state where our starfield
can call to it to have the game run voice lines when they should and music (they will run in the background while we
play i just need the audio so lets think about the idea)".

Status: **a design on paper.** Nothing here is built or tested, and nothing here changes a standing decision. Written
by Claude-cloud-2; review on #32 before any code. Labels as in [docs/ai/research-log.md](../../ai/research-log.md):
**verified**, **supported hypothesis**, **unresolved**; each with its source. IDs: BGA.

## 1. The standing record

This idea was researched before, on 19 October 2026, and decided. This note builds on that record; it does not reopen
it.
- [findings/original-engine-audio.md](findings/original-engine-audio.md) studied "run each Fallout's own engine beside
  Starfield to play its voice lines and music". Its conclusions: technically possible for Fallout 4, New Vegas and
  Fallout 3, not 76; legally it most likely changes nothing for voice lines, because the Capital Wasteland objection was
  to the actors' performances being used in another game, not to the conversion, so Fallout 3 and New Vegas voice stay
  no; radio is the one case that plausibly differs (the player's own game playing its own licensed stations, unchanged).
  It labels the legal reading **inferred**, not legal advice.
- [REL-61](release-community-legal.md) records that finding. Standing recommendation: **do not build it now**. Its
  groundwork is PS-38 (each voice line and music track has a swappable source) and PS-39 (each silent voice file is cut
  to the original line's length), in [people-and-story.md](people-and-story.md).
- **A1** in [engine-mechanics-notes/quests-dialogue-voice.md](engine-mechanics-notes/quests-dialogue-voice.md),
  section 10: decided by the owner on 19 October 2026 (page RE-1), no voice reuse for now, subtitles only.

The precedents behind that record, from the same quests-dialogue-voice.md ("Precedents and lessons" and its sources):
- Capital Wasteland (Fallout 3 in Fallout 4) stopped after talking with Bethesda; letting players extract from their
  own copies of Fallout 3 was also judged unworkable, because the voice acting is licensed, not owned. **verified**
  ([PCGamesN](https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod))
- Fallout 4: New Vegas recast every voice for the same reason.
  **verified** ([Kotaku](https://kotaku.com/fallout-4-modders-cant-use-new-vegas-voice-acting-so-t-1829149325))

What the precedent establishes: the objection is to using the performances in another game, and the player owning the
original does not cure it. What it does not establish: whether Bethesda would treat "the original game plays its own
file on another game's cue" differently. No precedent tests that, so this note makes no claim that the route is
legally different. For voice it is the same use under the record's reading; only Bethesda's word could change that.
For radio it may differ, which is why the stages below lead with radio and music.

## 2. What it looks like

```
 Starfield (the player plays here)                 Fallout 4 (running in the background, unfocused, small window)
 ---------------------------------                 ------------------------------------------------------------------
 radio on, station N       --cue-->  pipe  --->     audio host plugin (F4SE) -> the original radio station plays
 player enters a location  --cue-->        --->     pushes the original music type for it (exploration, combat, ...)
 combat starts / ends      --cue-->        --->     combat music on / off
 our dialogue line starts  --cue-->        --->     plays INFO 0x00012345 as voice type X   [only if A1 is reopened]
                           <--duration, done, amplitude envelope (for mouths)---
```

- **The host:** one source game at a time, the one whose world the player is in (Fallout 4 for the Commonwealth, New
  Vegas for the Mojave once build 2 exists).
  - Our host plugin keeps it in an empty interior, the "audio room".
  - It runs in a small window at the lowest settings with a frame cap, and gets no input (section 4).
- **The Starfield side:** our SFSE plugin (the FOCC sidecar), or for now the Papyrus-to-plugin log bridge
  (`sfse/FO4SFBorder`). It sends a cue when the radio is switched, the music context changes, or (only if A1 is
  reopened) a converted dialogue line starts.
- **The transport:** a local named pipe (Windows) with the line protocol in section 5. The launcher starts the host
  game before Starfield and closes it after.
- **Where it fits:** the host is one more audio source behind PS-38, beside silent, converted and runtime-decoded. It
  needs nothing from the core that PS-38 and PS-39 do not already reserve.

## 3. What each part needs, and how sure we are

| Need | How | Label and source |
|---|---|---|
| The host keeps running and playing sound while Starfield has focus | `[General] bAlwaysActive=1` in `Fallout4Custom.ini` | **unresolved**: Steam threads report it working, original-engine-audio.md found conflicting reports and none on audio; S0 settles it |
| Two games at once | Steam runs several different games at once on one PC | **supported hypothesis** (Steam community posts; no Valve statement read) |
| Radio | The host turns an original radio station on and off | **unresolved**: no function or approach checked |
| Music | Papyrus `MusicType.Add()` / `Remove()` push and pop the original music types; Starfield's own music is silenced in our worlds | **unresolved**: function names from memory; the Creation Kit wiki page (falloutck.uesp.net, MusicType Script) returned 403 on 6 November and was not read |
| The host plays one specific voice line (only if A1 is reopened) | (a) Papyrus `ObjectReference.Say(Topic, akActorToSpeakAs, ...)` makes a hidden speaker say a topic "as if it were the specified actor"; the engine picks the response, so the line's conditions must pass in the audio room. (b) An engine call that plays a given file: the Skyrim library has `BSAudioManager::BuildSoundDataFromFile` (used by AudioUtil); the Fallout 4 library has `BSAudioManager`, this call unchecked | (a) **verified** that the function exists (Creation Kit wiki); that it plays a chosen line out of its quest is **unresolved**. (b) **unresolved** |
| Spatial sound | Either mirror the speaker's offset and heading inside the host, or play flat and set volume and balance ourselves (original-engine-audio.md's simpler option) | **supported hypothesis** for the idea; neither tried |
| Timing | The host reports duration and end; Starfield holds the subtitle until then, as Starfield Silent Voice does for unvoiced lines. PS-39's length-cut silent files give the same pacing without a round trip | **supported hypothesis** (Silent Voice: quests-dialogue-voice.md, "Starfield Silent Voice") |
| Moving mouths (voice only) | The host streams the line's loudness (about 100 samples a second) and our SFSE plugin opens and closes the speaker's mouth by it, as Skyrim's AudioUtil does from a wav's amplitude envelope; no lip file leaves the host | **supported hypothesis** for the idea (AudioUtil repository, read 1 November); on Starfield's faces **unresolved** |
| Latency | a pipe message plus one frame in the host: tens of milliseconds | **supported hypothesis** (original-engine-audio.md, inferred, not measured); S1 measures it |

## 4. Risks we already know

- **Input leaks into the background game.** A Fallout 4 multiplayer project reports that with `bAlwaysActive` on,
  Fallout 4 keeps polling raw input when unfocused, so clicks meant for another window reach it, and fixed it by
  turning polling off whenever the window is not in front (F4Multiplayer PR 124, reading Fallout4.exe 1.11.240).
  **supported hypothesis**: that project's reading, not reproduced here; S0 checks it. If it holds, the host plugin
  must do the same, or the player's clicks in Starfield fire guns in Fallout 4.
- **Cost.** Two Creation Engine games at once: a second game's memory (likely a few GB for Fallout 4, less for the
  32-bit New Vegas and Fallout 3) and some GPU time. **supported hypothesis** (original-engine-audio.md, inferred,
  needs a measurement). The host must run in an empty cell, at minimum settings, in a tiny window, with a low frame cap.
  S0 measures it.
- **Alt-tab behaviour.** Bethesda games are known to misbehave when they lose focus (Steam threads). The host never
  takes focus: the launcher starts it minimised or off-screen and never brings it forward. **unresolved** how well
  that holds.
- **Versions.** The host plugin is a second script-extender plugin per game and must match the runtime the player
  has installed, not the one we read data from. F4SE's home page lists 1.11.240 (F4SE 0.7.9), 1.10.984 (0.7.2) and
  1.10.163 (0.6.23) **verified** ([launcher-sources/fo4source.md](launcher-sources/fo4source.md)); the project reads
  1.10.163 data now and adds 1.11.240 after a record diff (VM-01, [versions-and-maintenance.md](versions-and-maintenance.md)).
  One host build per supported runtime, or one CommonLibF4 build covering several: **unresolved**.
- **Each player must own and install each game** the host runs, which the build already requires to convert it. The
  launcher refuses without it.

## 5. The cue protocol (draft)

One line per message, UTF-8, fields separated by a single tab, over a named pipe
(`\\.\pipe\fo4sf-audio-<game>`):

| From Starfield | Meaning |
|---|---|
| `hello 1 <game>` | protocol version, the source game expected (`fo4`, `fnv`, `fo3`) |
| `radio <station>` / `radio off` | the radio |
| `music <plugin>:<MUSC form id>` / `music off` | the music context |
| `combat on` / `combat off` | combat music |
| `volume <music 0..1> <voice 0..1>` | follows Starfield's own sliders |
| `say <cue id> <speaker id> <plugin>:<INFO form id> <voice type editor id> <dx> <dy> <dz> <heading>` | voice only, if A1 is reopened: play this response as this voice type, at this offset from the listener (metres, Starfield axes) |
| `move <speaker id> <dx> <dy> <dz> <heading>` / `stop <speaker id>` | voice only: the speaker moved; cut the line |

| From the host | Meaning |
|---|---|
| `ready 1 <game> <runtime>` | the host is in its audio room |
| `started <cue id> <duration ms>` / `done <cue id>` / `failed <cue id> <reason>` | a cue's life |
| `env <cue id> <0..255 per 10 ms, hex>` | voice only: the loudness envelope for mouths, streamed in chunks |

Ids are the source game's form ids, which the converter already keeps (the identity work), matching PS-39's stable
line id map.

## 6. Per game

| Game | Engine and extender | Host | Notes and labels |
|---|---|---|---|
| Fallout 4 | Creation Engine, F4SE, CommonLibF4 | first: F4SE plugin, a tiny `FO4SF_AudioHost.esp` (the audio room, a hidden speaker, one quest) | voice `.fuz`, music and radio `.xwm` **verified** (original-engine-audio.md section 3). Everything above is written for it |
| Fallout: New Vegas | Gamebryo, xNVSE | second | voice `.ogg` with `.lip` **verified** (original-engine-audio.md section 3, from findings/asset-conversion.md); music `.ogg` per the same note, which the earlier draft gave as `.mp3`: **unresolved** until checked in an install. 32-bit: **supported hypothesis** (original-engine-audio.md). Sound functions in JIP LN NVSE: **unresolved**, not checked |
| Fallout 3 | Gamebryo, FOSE | own FOSE host; or through New Vegas when the player has Tale of Two Wastelands, which builds a merged Fallout 3 and New Vegas game from the player's own files ([multi-game-future.md](multi-game-future.md)) | same formats as New Vegas (original-engine-audio.md). One host serving both through TTW: **supported hypothesis** |
| Fallout 1 and 2 | Interplay's 2D engine | last, maybe never | little speech (the talking heads) and no Creation Engine dialogue to map to. Their audio formats, sfall, and engine reimplementations (fallout1-ce / fallout2-ce) as a host: **unresolved**, no source read for this note |
| Fallout 76 | | none | closed: online only, ban risk, Terms of Service (original-engine-audio.md, REL-60) |

## 7. Stages, each with a go/no-go

The record says do not build it now (REL-61). These stages run only if the owner reopens REL-61. Radio and music
lead, because they are the case the record says might differ; voice stages need A1 reopened as well.

- **S0, PC, no code, about an hour of the owner's time:**
  - set `bAlwaysActive=1` in Fallout 4, start it windowed at the lowest settings, load a save in a quiet interior with
    a radio station on, then start Starfield;
  - go if: both run; Fallout 4's radio and music can be heard while Starfield has focus; memory leaves the PC usable;
  - record whether Starfield clicks reach Fallout 4 (section 4).
- **S1, offline then PC: the Fallout 4 host for radio and music:**
  - an F4SE plugin (CommonLibF4) serving the pipe and the audio room plugin; `radio`, `music`, `combat`, `volume`;
    input polling off while unfocused;
  - a test client sends the cues: no Starfield needed;
  - go if: each cue takes effect within 100 ms, `started` comes back, no input leak, an hour without a crash.
- **S2, from Starfield:** our SFSE plugin (or the log bridge) sends `radio` and `music` cues from one location. Go if
  station and music follow the player in time.
- **S3, voice (only if A1 is reopened):** `say` for five fixed lines by Papyrus `Say(..., akActorToSpeakAs)`, then one
  converted conversation with the subtitle held for the host's duration, the speaker placed for 3D sound, and the
  envelope driving one Starfield face.
- **S4, New Vegas (xNVSE), then Fallout 3** through Tale of Two Wastelands or FOSE: radio and music; voice only on
  the same terms as S3.

Offline work possible now, all of it already covered by PS-38 and PS-39: the protocol as code with its tests, the
converter's record of each line's source INFO and voice type, and a launcher setting (off by default) that starts and
stops the host.

## 8. What the owner would need to decide

- **BGA-1. To reopen REL-61** (build any of this): the owner would choose REL-61 option (b), prototype the radio case,
  and decide whether a radio question goes to Bethesda first, as original-engine-audio.md section 5 suggests (the owner
  approves any text; nothing is sent by a thread).
- **BGA-2. To reopen A1 for voice through a host:** the owner would need to reverse the RE-1 decision, and under the
  record's reading would need Bethesda's written word that "played by the original game" differs from conversion.
  Without that, Fallout 3 and New Vegas voice stay no and Fallout 4 voice stays subtitles only.
- **BGA-3.** Fallout 1 and 2: in scope at all, given how little voice they have?
- **BGA-4.** Is a second running game acceptable on the minimum spec we tell players about, or only as an option?

## Sources (read 1 November 2026 unless noted)

- Fallout 4 running unfocused with `bAlwaysActive=1`:
  https://steamcommunity.com/app/377160/discussions/0/3211505894126608236/ and
  https://steamcommunity.com/app/377160/discussions/0/1291817208497230051/ ; conflicting reports in
  https://steamcommunity.com/app/377160/discussions/0/4778901811094055005 (via original-engine-audio.md)
- The input leak under `bAlwaysActive`, and its fix: https://github.com/Jolley71717/F4Multiplayer/pull/124
- `ObjectReference.Say(Topic, akActorToSpeakAs, abSpeakInPlayersHead, akTarget)`:
  https://falloutck.uesp.net/wiki/ObjectReference_Script
- Playing audio files directly through `BSAudioManager::BuildSoundDataFromFile`, and an amplitude envelope driving the
  mouth (Skyrim): https://github.com/crajjjj/AudioUtil
- `BSAudioManager` member functions in CommonLibF4: https://github.com/Dear-Modding-FO4/commonlibf4/pull/28
- Several Steam games at once on one PC: https://steamcommunity.com/discussions/forum/0/1735465524697733891/
- Capital Wasteland: https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod ; Fallout 4: New Vegas
  recast: https://kotaku.com/fallout-4-modders-cant-use-new-vegas-voice-acting-so-t-1829149325
- Project record: findings/original-engine-audio.md; release-community-legal.md (REL-26, REL-60, REL-61);
  people-and-story.md (PS-38, PS-39); engine-mechanics-notes/quests-dialogue-voice.md (A1, Silent Voice);
  versions-and-maintenance.md (VM-01); launcher-sources/fo4source.md (F4SE runtimes); multi-game-future.md (TTW).
