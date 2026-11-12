"""An animated Fallout 4 object that is no door, on one of Starfield's activator graphs (FAL-489 variant D, the Vault 111 console).

The game's own activators (variant A, 12 Nov) are a skeleton rig plus one .af clip per graph state and an .afx descriptor per
clip, in the record's CNAM folder, under a graph such as activatorstategraph01.agx whose clip slots are StateA_Idle,
StateA_Play, StateB_Idle and StateB_Play. This module is the part the door recipe lacks: it picks which of the object's
sequences feed which slot, makes the one-frame hold clips the Idle slots need, and writes the .afx descriptors (the vanilla
shape: is_state, tag, filename, and an optional audio frame carrying a sound). Everything else is the door path's:
door_motion.inspect (sequences -> clip slots), door_rig.plan (rig), native_door (the .rig and .af through CALUMI) and
convert_static.convert_multipart_door (the model, one keyframed body per moving bone).

Unread (said, not assumed): which slot the graph plays for which input event; whether the Idle slots want is_state 1; whether
a hold clip of one frame is accepted; whether the engine takes the audio frame without a sound record the game knows.
"""
from xml.etree import ElementTree as ET

GRAPH = "AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx"
PLAY_SLOTS = ("StateA_Play", "StateB_Play")
IDLE_OF = {"StateA_Play": "StateA_Idle", "StateB_Play": "StateB_Idle"}
FPS = 30


def parse_states(text):
    """'Stage1=StateA_Play,Stage2=StateB_Play' -> {"Stage1": "StateA_Play", "Stage2": "StateB_Play"}; refuses anything else."""
    out = {}
    for part in [p.strip() for p in (text or "").split(",") if p.strip()]:
        if "=" not in part:
            raise ValueError(f"state map entry {part!r} is not <FO4 sequence>=<slot>")
        seq, slot = (x.strip() for x in part.split("=", 1))
        if slot not in PLAY_SLOTS:
            raise ValueError(f"slot {slot!r} is not one of {PLAY_SLOTS} (the Idle slots are made, not mapped)")
        if not seq or seq in out or slot in out.values():
            raise ValueError(f"sequence or slot named twice in {text!r}")
        out[seq] = slot
    if not out:
        raise ValueError("an empty state map: name at least one FO4 sequence and its slot")
    return out


def slot_names(states):
    """Every clip the object ends with: each mapped Play slot and the Idle hold made from it."""
    names = []
    for slot in states.values():
        names += [slot, IDLE_OF[slot]]
    return sorted(names)


def hold_clip(clip, name):
    """A one-frame clip holding the last pose of `clip` (the Idle slot after a Play): the same tracks, one sample, duration 0."""
    tracks = []
    for t in clip["tracks"]:
        last = dict(t["samples"][-1])
        last["elapsed"] = 0.0
        tracks.append({**t, "samples": [last]})
    return {**clip, "name": name, "duration": 0.0, "events": [], "tracks": tracks, "hold_of": clip["name"]}


def add_holds(plan):
    """plan -> plan with a hold clip after every Play slot it holds (the plan_hook of convert_multipart_door)."""
    clips = list(plan["clips"])
    for clip in plan["clips"]:
        if clip["name"] in IDLE_OF:
            clips.append(hold_clip(clip, IDLE_OF[clip["name"]]))
    return {**plan, "clips": clips}


def descriptor(tag, filename=None, is_state=1, audio=()):
    """The .afx bytes of one clip, in the vanilla shape (statea_play.afx of the artifact holder, read 12 Nov):
    <root><is_state>1</is_state><tag>StateA_Play</tag><filename>StateA_Play.af</filename><audios><audio><frame>1</frame>
    <foley>NAME</foley></audio></audios></root>. audio: [(frame, foley name)]."""
    root = ET.Element("root")
    ET.SubElement(root, "is_state").text = str(int(is_state))
    ET.SubElement(root, "tag").text = tag
    ET.SubElement(root, "filename").text = filename or tag + ".af"
    if audio:
        audios = ET.SubElement(root, "audios")
        for frame, foley in audio:
            a = ET.SubElement(audios, "audio")
            ET.SubElement(a, "frame").text = str(int(frame))
            ET.SubElement(a, "foley").text = foley
    return ET.tostring(root, encoding="utf-8")


def audio_frames(clip, foley):
    """[(frame, foley)] for the clip's sound text keys when a foley name is given, else [] (no sound record named: left out).
    A sound text key is one whose text starts with 'Sound' (FO4's SoundPlay.<name> / Sound: <name>); frame = seconds x 30, at
    least 1 (the vanilla holder's frame for a sound at 0)."""
    if not foley:
        return []
    out = []
    for e in clip.get("events", []):
        text = str(e.get("text", e.get("name", ""))).lower()
        if text.startswith("sound") and e.get("in_playback_range", True):
            out.append((max(1, round(e["elapsed"] * FPS)), foley))
    return out


def descriptors(plan, foley=None):
    """{clip name: .afx bytes} for every clip of the plan: a Play slot carries its own sounds, an Idle slot none."""
    out = {}
    for clip in plan["clips"]:
        out[clip["name"]] = descriptor(clip["name"], audio=audio_frames(clip, foley) if clip["name"] in PLAY_SLOTS else ())
    return out


def clip_table(plan, unit_scale=1.0):
    """Rows for the stager's report and the card: name, seconds, frames, bones moved, hold_of, audio frames (no foley)."""
    rows = []
    for clip in plan["clips"]:
        rows.append({"name": clip["name"], "seconds": round(clip["duration"], 4), "frames": round(clip["duration"] * FPS),
                     "bones": sorted(t["name"] for t in clip["tracks"]), "hold_of": clip.get("hold_of"),
                     "sound_keys": [round(e["elapsed"], 3) for e in clip.get("events", [])
                                    if str(e.get("text", e.get("name", ""))).lower().startswith("sound")]})
    return rows
