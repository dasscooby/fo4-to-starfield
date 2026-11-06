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
- Fallout 4: New Vegas recast every voice. Its own stated reasons differ: ripping needs decompiling, which the EULA
  forbids, and the voice contracts would need renegotiating. **verified**
  ([Kotaku](https://kotaku.com/fallout-4-modders-cant-use-new-vegas-voice-acting-so-t-1829149325), as quoted in
  quests-dialogue-voice.md)

What the precedent shows (**verified**, PCGamesN): the voice acting is licensed, not owned, and extracting it from
the player's own copies was judged untenable. What it suggests, as the record reads it: the objection is to using the
performances in another game, not to the conversion method (**unresolved**; REL-61 and original-engine-audio.md
label this reading inferred). What it does not test: whether Bethesda would treat "the original game plays its own
file on another game's cue" differently. So this note makes no claim that the route is legally different. Under the
record's reading, voice and Bethesda's own score are the same use whichever program plays them (the score "sits with
the voice question", original-engine-audio.md section 4); only the licensed radio songs plausibly differ. That is
why the stages below lead with radio alone.

## 2. What it looks like

```
 Starfield (the player plays here)                 Fallout 4 (background, small window off-screen, never focused)
 ---------------------------------                 ------------------------------------------------------------------
 radio on, station N       --cue-->  pipe  --->     audio host plugin (F4SE) -> the original radio station plays
 player enters a location  --cue-->        --->     the original score for it          [only with voice, BGA-2]
 combat starts / ends      --cue-->        --->     combat music on / off              [only with voice, BGA-2]
 our dialogue line starts  --cue-->        --->     plays INFO 0x00012345 as voice type X   [only if A1 is reopened]
                           <--started, done; amplitude envelope for mouths [voice only]---
```

- **The host:** one source game at a time, the one whose world the player is in (Fallout 4 for the Commonwealth, New
  Vegas for the Mojave once build 2 exists).
  - Our host plugin keeps it in an empty interior, the "audio room".
  - It runs in a small window kept off-screen, at the lowest settings with a frame cap, never focused, and gets no
    input (section 4).
- **The Starfield side:** our SFSE plugin (the FOCC sidecar), or for now the Papyrus-to-plugin log bridge
  (`sfse/FO4SFBorder`). It sends a cue when the radio is switched, or (only with voice, BGA-2) the music context changes
  or a converted dialogue line starts.
- **The transport:** a local named pipe (Windows) with the line protocol in section 5. The launcher starts the host
  game before Starfield and closes it after.
- **Where it fits:** the host is one more audio source behind PS-38, beside silent, converted and runtime-decoded. It
  needs nothing from the core that PS-38 and PS-39 do not already reserve.

## 3. What each part needs, and how sure we are

| Need | How | Label and source |
|---|---|---|
| The host keeps running and playing sound while Starfield has focus | `[General] bAlwaysActive=1` in `Fallout4Custom.ini` | **unresolved**: two Steam threads (in Sources) report it working, original-engine-audio.md found conflicting reports and none on audio; S0 settles it |
| Two games at once | Steam runs several different games at once on one PC | **supported hypothesis** (Steam community posts, listed in Sources; no Valve statement read) |
| Radio | The host turns an original radio station on and off | **unresolved**: no function or approach checked |
| Score music (only with voice, BGA-2) | Papyrus `MusicType.Add()` / `Remove()` push and pop the original music types; Starfield's own music is silenced in our worlds | **unresolved**: function names from memory; the Creation Kit wiki page (falloutck.uesp.net, MusicType Script) returned 403 on 6 November and was not read |
| The host plays one specific voice line (only if A1 is reopened) | (a) Papyrus `ObjectReference.Say(Topic, akActorToSpeakAs, ...)` makes a hidden speaker say a topic "as if it were the specified actor"; the engine picks the response, so the line's conditions must pass in the audio room. (b) An engine call that plays a given file: the Skyrim library has `BSAudioManager::BuildSoundDataFromFile` (used by AudioUtil); the Fallout 4 library has `BSAudioManager`, this call unchecked | (a) **verified** that the function exists: Fallout 4's Papyrus source `ObjectReference.psc` declares `Function Say(Topic akTopicToSay, Actor akActorToSpeakAs = None, bool abSpeakInPlayersHead = false, ObjectReference akTarget = None) native` (read 6 November; the quoted description is the Creation Kit wiki's, read 1 November); that it plays a chosen line out of its quest is **unresolved**. (b) **unresolved** |
| Spatial sound | Either mirror the speaker's offset and heading inside the host, or play flat and set volume and balance ourselves (original-engine-audio.md's simpler option) | **unresolved**: unmeasured reasoning (original-engine-audio.md, section 2); neither tried |
| Timing | The host reports duration and end; Starfield holds the subtitle until then, as Starfield Silent Voice does for unvoiced lines. PS-39's length-cut silent files give the same pacing without a round trip | **supported hypothesis** (Silent Voice: quests-dialogue-voice.md, "Starfield Silent Voice") |
| Moving mouths (voice only) | The host streams the line's loudness (about 100 samples a second) and our SFSE plugin opens and closes the speaker's mouth by it, as Skyrim's AudioUtil does from a wav's amplitude envelope | technique: **supported hypothesis** (AudioUtil repository, read 1 November); on Starfield's faces **unresolved**. Rights: the envelope is data derived from the voice line; original-engine-audio.md (section 2) reads lip data made from the original audio as a converted derivative and raises the same question for line length, so the same reading may cover the envelope: **unresolved**, part of A1 |
| Latency | a pipe message plus one frame in the host: tens of milliseconds | **unresolved**: unmeasured reasoning (original-engine-audio.md, section 2); S1 measures it |

## 4. Risks we already know

- **Input leaks into the background game.** A Fallout 4 multiplayer project reports that with `bAlwaysActive` on,
  Fallout 4 keeps polling raw input when unfocused, so clicks meant for another window reach it, and fixed it by
  turning polling off whenever the window is not in front (F4Multiplayer PR 124, reading Fallout4.exe 1.11.240).
  **supported hypothesis**: that project's reading, not reproduced here; S0 checks it. If it holds, the host plugin
  must do the same, or the player's clicks in Starfield fire guns in Fallout 4.
- **Cost.** Two Creation Engine games at once: a second game's memory (likely a few GB for Fallout 4, less for the
  32-bit New Vegas and Fallout 3) and some GPU time. **unresolved**: unmeasured reasoning (original-engine-audio.md,
  section 2). The host must run in an empty cell, at minimum settings, in a tiny window, with a low frame cap.
  S0 measures it.
- **Alt-tab behaviour.** Bethesda games may misbehave when they lose focus: **unresolved**, no thread read for it.
  The host never takes focus: the launcher starts its small window off-screen and never brings it forward.
  **unresolved** how well that holds.
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
| `hello 1 <game>` | protocol version, the source game expected (`fo4`, `fnv`, `fo3`; Fallout 3 content through Tale of Two Wastelands runs in New Vegas, so it uses `fnv`) |
| `radio <station>` / `radio off` | the radio |
| `music <plugin>:<MUSC form id>` / `music off` | score only with voice (BGA-2): the music context |
| `combat on` / `combat off` | score only with voice (BGA-2): combat music |
| `volume <music 0..1> <voice 0..1>` | follows Starfield's own sliders (whether our SFSE plugin can read them: **unresolved**) |
| `say <cue id> <speaker id> <plugin>:<INFO form id> <voice type editor id> <dx> <dy> <dz> <heading>` | voice only, if A1 is reopened: play this response as this voice type, at this offset from the listener (metres, Starfield axes) |
| `move <speaker id> <dx> <dy> <dz> <heading>` / `stop <speaker id>` | voice only: the speaker moved; cut the line |

| From the host | Meaning |
|---|---|
| `ready 1 <game> <runtime>` | the host is in its audio room |
| `started <cue id> <duration ms>` / `done <cue id>` / `failed <cue id> <reason>` | a cue's life |
| `env <cue id> <0..255 per 10 ms, hex>` | voice only: the loudness envelope for mouths, streamed in chunks |

Ids are the source game's form ids. A stable map from each source line to ours is proposed groundwork in
original-engine-audio.md (section 6); it is not part of PS-38 or PS-39 and is not built.

## 6. Per game

| Game | Engine and extender | Host | Notes and labels |
|---|---|---|---|
| Fallout 4 | Creation Engine; F4SE **verified** (F4SE runtime list, launcher-sources/fo4source.md); CommonLibF4 **supported hypothesis** (its BSAudioManager PR, in Sources; library not otherwise read) | first: F4SE plugin, a tiny `FO4SF_AudioHost.esp` (the audio room, a hidden speaker, one quest) | voice `.fuz`, music and radio `.xwm` **verified** (original-engine-audio.md section 3). Everything above is written for it |
| Fallout: New Vegas | Gamebryo, xNVSE: **supported hypothesis** (original-engine-audio.md section 3; TTW's own page names xNVSE, findings/precedents.md section 1) | second | voice `.ogg` with `.lip` **verified** (original-engine-audio.md section 3, from findings/asset-conversion.md); music `.ogg` **verified** (original-engine-audio.md section 3, findings/asset-conversion.md Q36). 32-bit: **supported hypothesis** (original-engine-audio.md). Sound functions in JIP LN NVSE: **unresolved**, not checked |
| Fallout 3 | Gamebryo, FOSE: **supported hypothesis** (original-engine-audio.md section 3, "yes in principle") | own FOSE host; or through New Vegas when the player has Tale of Two Wastelands, whose installer needs the player's own English Fallout 3 and New Vegas and builds Fallout 3 into New Vegas **verified** ([findings/precedents.md](findings/precedents.md) section 1; [multi-game-future.md](multi-game-future.md) TTW rows) | same formats as New Vegas (original-engine-audio.md). One host serving both through TTW: **unresolved**, no source |
| Fallout 1 and 2 | Interplay's 2D engine | last, maybe never | little speech (the talking heads; **unresolved**, no source read) and no Creation Engine dialogue to map to. Their audio formats, sfall, and engine reimplementations (fallout1-ce / fallout2-ce) as a host: **unresolved**, no source read for this note |
| Fallout 76 | | none | closed: online only, ban risk, Terms of Service (original-engine-audio.md, REL-60) |

## 7. Stages, each with a go/no-go

The record says do not build it now (REL-61). These stages run only if the owner reopens REL-61, after Bethesda's
answer (BGA-1). Radio leads, because the licensed radio songs are the one case the record says might differ; score
music and voice need BGA-2 as well.

- **S0, PC, no code, about an hour of the owner's time:**
  - set `bAlwaysActive=1` in Fallout 4, start it in a small window off-screen at the lowest settings, load a save in a quiet interior with
    a radio station on, then start Starfield;
  - go if: both run; Fallout 4's radio can be heard while Starfield has focus; memory leaves the PC usable;
  - record whether Starfield clicks reach Fallout 4 (section 4).
- **S1, offline then PC: the Fallout 4 host for radio:**
  - an F4SE plugin (CommonLibF4) serving the pipe and the audio room plugin; `radio` and `volume`;
    input polling off while unfocused;
  - a test client sends the cues: no Starfield needed;
  - go if: each cue takes effect within 100 ms, `started` comes back, no input leak, an hour without a crash.
- **S2, from Starfield:** our SFSE plugin (or the log bridge) sends `radio` cues. Go if the station follows the
  player's radio in time.
- **S3, score and voice (only with BGA-2):** `music` and `combat` for one location; `say` for five fixed lines by Papyrus `Say(..., akActorToSpeakAs)`, then one
  converted conversation with the subtitle held for the host's duration, the speaker placed for 3D sound, and the
  envelope driving one Starfield face.
- **S4, New Vegas (xNVSE), then Fallout 3** through Tale of Two Wastelands or FOSE: radio; score and voice only on
  the same terms as S3.

Work possible now is only what PS-38 and PS-39 already cover: one swappable source per voice line and music track,
and each silent voice file cut to the original line's length. The pipe protocol in code and a launcher setting that starts and stops the host are part of the host, and
wait for REL-61 to be reopened like the rest.

## 8. What the owner would need to decide

- **BGA-1. To reopen REL-61** (build any of this): REL-61 option (b) is "prototype the radio case after Bethesda
  answers", and original-engine-audio.md says radio would need Bethesda's word before any release. So Bethesda's
  answer comes first: the owner would decide whether to ask Bethesda about the radio case (the owner approves any
  text; nothing is sent by a thread), and only after an answer that allows it would S0 to S2 start. The station
  plays as the host has it, DJ lines included, which follow the host's own quest state (original-engine-audio.md
  section 4).
- **BGA-2. To reopen A1 for voice, and to play Bethesda's own score, through a host:** the owner would need to
  reverse the RE-1 decision for voice, and under the record's reading would need Bethesda's written word that "played
  by the original game" differs from conversion, for voice and for the score (the score sits with the voice question,
  original-engine-audio.md section 4). Without that, Fallout 3 and New Vegas voice stay no, Fallout 4 voice stays
  subtitles only, and the score is not played through a host.
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
- Several Steam games at once on one PC: https://steamcommunity.com/discussions/forum/0/1735465524697733891/ (read
  for the first draft, 1 November) and https://steamcommunity.com/discussions/forum/10/2270319347573688560 (read
  for original-engine-audio.md, 19 October)
- `Say` declaration: Fallout 4's Papyrus source `Data\Scripts\Source\ObjectReference.psc` (read 6 November)
- Capital Wasteland: https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod ; Fallout 4: New Vegas
  recast: https://kotaku.com/fallout-4-modders-cant-use-new-vegas-voice-acting-so-t-1829149325
- Project record: findings/original-engine-audio.md; release-community-legal.md (REL-26, REL-60, REL-61);
  people-and-story.md (PS-38, PS-39); engine-mechanics-notes/quests-dialogue-voice.md (A1, Silent Voice);
  versions-and-maintenance.md (VM-01); launcher-sources/fo4source.md (F4SE runtimes); multi-game-future.md (TTW).
