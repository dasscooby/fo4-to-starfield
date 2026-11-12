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


IDLE_MODES = ("toggle", "hold")


def slot_names(states, idles="hold"):
    """Every clip the object ends with. idles="hold": each mapped Play slot and the Idle hold made from it. idles="toggle" (add_toggle_idles):
    each mapped Play slot and BOTH Idle slots, whichever Play slots are mapped."""
    if idles not in IDLE_MODES:
        raise ValueError(f"idles {idles!r} is not one of {IDLE_MODES}")
    names = []
    if idles == "toggle":
        names = list(states.values()) + list(IDLE_OF.values())
        return sorted(set(names))
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


def _same_pose(a, b, tol=1e-6):
    """Two samples that pose a bone alike (a quaternion and its negative are one rotation)."""
    if any(abs(p - q) > tol for p, q in zip(a["translation_source_units"], b["translation_source_units"])):
        return False
    if abs(a.get("scale", 1.0) - b.get("scale", 1.0)) > tol:
        return False
    qa, qb = a["quaternion_wxyz"], b["quaternion_wxyz"]
    return (all(abs(p - q) <= tol for p, q in zip(qa, qb)) or all(abs(p + q) <= tol for p, q in zip(qa, qb)))


def _hold_frame(clip, name, which):
    """A one-frame clip holding the FIRST (which=0) or LAST (which=-1) pose of `clip`; hold_frame says which."""
    tracks = []
    for t in clip["tracks"]:
        s = dict(t["samples"][which])
        s["elapsed"] = 0.0
        tracks.append({**t, "samples": [s]})
    return {**clip, "name": name, "duration": 0.0, "events": [], "tracks": tracks, "hold_of": clip["name"],
            "hold_frame": "first" if which == 0 else "last"}


def add_toggle_idles(plan):
    """plan -> plan whose Idle slots are the two poses of a toggle (FAL-489 session 7, an inference of the PC's, not read from the graph):
    on activatorstategraph01 the object rests in StateA_Idle, Play01 plays StateA_Play and holds StateB_Idle, Play02 plays StateB_Play and
    holds StateA_Idle. So StateA_Idle is the FIRST frame of slot A's clip (the shut pose) and StateB_Idle its LAST frame (the open pose),
    and StateB_Play must start from StateB_Idle: a bone slot B's clip leaves standing (every sample the same) is held at the pose slot A's
    clip ends in, instead of at the pose the Fallout 4 clip happens to carry (its own, unrelated to A's end); a bone slot B moves keeps its
    own data. If only one Play slot is mapped it is the source of both Idles. The old rule (each Idle holds the END of its own Play clip)
    is add_holds. Tracks of a clip stay one per rig bone in rig order; a 'static' flag is kept only when the source track was static too
    (a static track is written as identity)."""
    by = {c["name"]: c for c in plan["clips"]}
    source = next((by[n] for n in PLAY_SLOTS if n in by), None)
    if source is None:
        return plan
    clips = list(plan["clips"])
    b = by.get("StateB_Play")
    if b is not None and b is not source:
        last = {t["node"]: t for t in source["tracks"]}
        held, tracks = [], []
        for t in b["tracks"]:
            src = last.get(t["node"])
            stays = all(_same_pose(t["samples"][0], s) for s in t["samples"][1:])
            if src is None or not stays:
                tracks.append(t)
                continue
            pose = src["samples"][-1]
            s0, s1 = t["samples"][0]["elapsed"], t["samples"][-1]["elapsed"]
            row = {**t, "samples": [{**pose, "elapsed": s0}, {**pose, "elapsed": s1}]}
            if t.get("static") and not src.get("static"):
                row.pop("static")
            tracks.append(row)
            held.append(t["name"])
        clips = [{**b, "tracks": tracks, "starts_from": "StateB_Idle", "held_at_idle_pose": held} if c is b else c for c in clips]
    clips += [_hold_frame(source, "StateA_Idle", 0), _hold_frame(source, "StateB_Idle", -1)]
    return {**plan, "clips": clips}


def swap_siblings(plan):
    """plan -> plan with the two sibling bones exchanged in the bone list (an experiment, FAL-489 session 6: does the game number the
    root's two children in another order than the rig file?). Exactly one group of two bones may share a parent, else ValueError.
    Bone i's position, every `parent` index and every attachment's `bone` index follow the exchange; nothing else changes (binds, tracks,
    names). Everything written from plan['bones'] follows: the rig file, the .af blocks (rig order), the model's nodes and the attachments.
    Apply BEFORE fill_static_tracks, which orders the tracks by the bone list."""
    bones = plan["bones"]
    groups = {}
    for i, b in enumerate(bones):
        if b["parent"] != -1:
            groups.setdefault(b["parent"], []).append(i)
    pairs = [g for g in groups.values() if len(g) >= 2]
    if len(pairs) != 1 or len(pairs[0]) != 2:
        raise ValueError(f"swap_siblings needs exactly one parent with exactly two children (found {[len(g) for g in pairs]})")
    i, j = pairs[0]
    perm = list(range(len(bones)))
    perm[i], perm[j] = j, i                                          # old index -> new index
    new = [None] * len(bones)
    for old, b in enumerate(bones):
        new[perm[old]] = {**b, "parent": b["parent"] if b["parent"] == -1 else perm[b["parent"]]}
    attachments = [{**a, "bone": perm[a["bone"]]} for a in plan["attachments"]]
    return {**plan, "bones": new, "attachments": attachments}


def fill_static_tracks(plan):
    """plan -> plan whose every clip has ONE TRACK PER RIG BONE, in rig order: a bone the clip does not move gets a 'static' track
    (identity relative to its bind, zero travel).

    Why (PC dump of the staged console, 12 Nov): CALUMI's read-back lists an .af's blocks in the order they were added, and each .af
    had only the 2 blocks of the moving bones (Lid, Button) against a 3-bone rig (root, Lid, Button), so a block's POSITION (0, 1)
    differed from its bone's rig index (1, 2). Whether the game pairs a block with a bone by position or by name is unread (the PC's
    session reading is an inference that does not settle it either); the oracle script that CALUMI's author pattern follows writes a block
    for every bone, root included. This writes the same: block i is rig bone i, name and position agree. Only objects built through
    anim_object get it; the door path is unchanged. The static sample carries the bone's own bind (so predictions agree) and
    native_door.prepare writes identity for it."""
    bones = plan["bones"]
    clips = []
    for clip in plan["clips"]:
        by_node = {t["node"]: t for t in clip["tracks"]}
        every = sorted({s["elapsed"] for t in clip["tracks"] for s in t["samples"]}) or [0.0]
        times = sorted({every[0], every[-1]})            # a key at the first and the last frame is enough for a bone that stays
        tracks = []
        for bone in bones:
            if bone["node"] in by_node:
                tracks.append(by_node[bone["node"]])
                continue
            if bone.get("node") is None:                   # a '<name>_Bind' parent bone made by animated_identity_binds
                raise ValueError(f"rig bone {bone['name']!r} has no source node: a block for it cannot be written (rotated-bind animated bone)")
            node = bone["node"]
            b = bone["bind"]
            tracks.append({"node": node, "name": bone["name"], "static": True, "target": bone["name"],
                           "samples": [{"elapsed": t, "translation_source_units": list(b["translation_source_units"]),
                                        "quaternion_wxyz": list(b["quaternion_wxyz"]), "scale": 1.0} for t in times]})
        clips.append({**clip, "tracks": tracks})
    return {**plan, "clips": clips}


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


def clip_table(plan, unit_scale):
    """Rows for the stager's report and the card: name, seconds, frames, bones with a track, hold_of, audio frames (no foley),
    and per track what it does from the first to the last sample (door_rig.open_motion: travel in metres, rotation in degrees).
    "bones" lists every track; "motion" says which of them actually move: a track can exist and stand still. unit_scale (source units to metres, convert_static.UNIT_SCALE) is required: travel is in metres."""
    from . import door_rig
    index = {b["node"]: i for i, b in enumerate(plan["bones"])}        # the rig bone index CALUMI files a track under
    rows = []
    for clip in plan["clips"]:
        rows.append({"name": clip["name"], "seconds": round(clip["duration"], 4), "frames": round(clip["duration"] * FPS),
                     "bones": sorted(t["name"] for t in clip["tracks"] if not t.get("static")), "hold_of": clip.get("hold_of"),
                     "hold_frame": clip.get("hold_frame"), "starts_from": clip.get("starts_from"), "held_at_idle_pose": clip.get("held_at_idle_pose"),
                     "tracks": [{"bone": t["name"], "bone_index": index[t["node"]], "keys": len(t["samples"]), "static": bool(t.get("static"))}
                            for t in clip["tracks"]],
                     "motion": door_rig.open_motion(plan, unit_scale, clip["name"]),
                     "sound_keys": [round(e["elapsed"], 3) for e in clip.get("events", [])
                                    if str(e.get("text", e.get("name", ""))).lower().startswith("sound")]})
    return rows
