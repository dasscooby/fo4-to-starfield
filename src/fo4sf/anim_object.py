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
GRAPH_GENERIC = "AnimTextData\\Tables\\Graphs\\GenericStateGraph01.agx"     # the four-state graph (FAL-489 control, PC session 22:35 UTC 12 Nov); the stager reads the real path
PLAY_SLOTS = ("StateA_Play", "StateB_Play")
IDLE_OF = {"StateA_Play": "StateA_Idle", "StateB_Play": "StateB_Idle"}
PLAY_SLOTS4 = ("StateA_Play", "StateB_Play", "StateC_Play", "StateD_Play")          # genericstategraph01's four play slots
IDLE_OF4 = {"StateA_Play": "StateA_Idle", "StateB_Play": "StateB_Idle", "StateC_Play": "StateC_Idle", "StateD_Play": "StateD_Idle"}
FPS = 30


def parse_states(text, slots=PLAY_SLOTS):
    """'Stage1=StateA_Play,Stage2=StateB_Play' -> {"Stage1": "StateA_Play", "Stage2": "StateB_Play"}; refuses anything else. slots: the Play slots a
    sequence may be mapped to (PLAY_SLOTS4 for genericstategraph01)."""
    out = {}
    for part in [p.strip() for p in (text or "").split(",") if p.strip()]:
        if "=" not in part:
            raise ValueError(f"state map entry {part!r} is not <FO4 sequence>=<slot>")
        seq, slot = (x.strip() for x in part.split("=", 1))
        if slot not in slots:
            raise ValueError(f"slot {slot!r} is not one of {slots} (the Idle slots are made, not mapped)")
        if not seq or seq in out or slot in out.values():
            raise ValueError(f"sequence or slot named twice in {text!r}")
        out[seq] = slot
    if not out:
        raise ValueError("an empty state map: name at least one FO4 sequence and its slot")
    return out


IDLE_MODES = ("toggle", "hold", "chain")


def chain_slots(states):
    """The mapped Play slots of a chain in slot order (A, B, C, D): the order the clips run in, each starting from the pose the one before it
    ended in. A slot may be left out (Stage2 on StateA_Play and Stage3 on StateC_Play is a chain of two: the graph returns from StateB_Play to
    the rest pose but from StateC_Play to StateC_Idle, FAL-489 control). ValueError for an empty map."""
    mapped = set(states.values())
    chain = [n for n in PLAY_SLOTS4 if n in mapped]
    if not chain or len(chain) != len(mapped):
        raise ValueError(f"the chain needs at least one of the Play slots {PLAY_SLOTS4}; got {sorted(mapped)}")
    return chain


def slot_names(states, idles="hold"):
    """Every clip the object ends with. idles="hold": each mapped Play slot and the Idle hold made from it. idles="toggle" (add_toggle_idles):
    each mapped Play slot and BOTH Idle slots, whichever Play slots are mapped. idles="chain" (add_chain_idles): all eight slots of
    genericstategraph01 (the mapped Play slots are chained in slot order; a slot may be left out)."""
    if idles not in IDLE_MODES:
        raise ValueError(f"idles {idles!r} is not one of {IDLE_MODES}")
    names = []
    if idles == "chain":                                  # genericstategraph01: all four Play slots and all four Idle slots, whatever is mapped
        chain_slots(states)
        return sorted(list(PLAY_SLOTS4) + list(IDLE_OF4.values()))
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


def parse_slow(text, states):
    """'Stage3=4' -> {"StateC_Play": 4} (FO4 sequence = a whole factor, at least 2, at most 8), looked up in states (parse_states). The factor is
    whole so every key stays on the 30 fps grid the native writer needs. ValueError for a sequence the map does not hold or a factor that is not a whole number in 2..8."""
    out = {}
    for part in [p.strip() for p in (text or "").split(",") if p.strip()]:
        if "=" not in part:
            raise ValueError(f"slow entry {part!r} is not <FO4 sequence>=<whole factor>")
        seq, fac = (x.strip() for x in part.split("=", 1))
        if seq not in states:
            raise ValueError(f"slow names {seq!r}, which the state map {sorted(states)} does not hold")
        if not fac.isdigit() or not 2 <= int(fac) <= 8:
            raise ValueError(f"slow factor {fac!r} for {seq} is not a whole number from 2 to 8")
        out[states[seq]] = int(fac)
    return out


def stretch_clips(plan, factors):
    """plan -> plan with the named clips (by slot name: {"StateC_Play": 4}) run slower by a whole factor: every sample time, the duration and every
    event time are multiplied, nothing else changes (the same poses, the same keys, so the end pose is the end pose; the keys stay on the 30 fps
    grid). A way to catch a 0.6 s motion with a 1.2 s shot (FAL-489, the PC session of 12 Nov 23:57 UTC). ValueError for a clip the plan lacks or a
    factor that is not a whole number of at least 1. Run it BEFORE add_chain_idles: the idles are cut from the stretched clips' own end poses."""
    names = {c["name"] for c in plan["clips"]}
    for name, f in (factors or {}).items():
        if name not in names:
            raise ValueError(f"slow names {name}, which the plan does not hold ({sorted(names)})")
        if not isinstance(f, int) or f < 1:
            raise ValueError(f"slow factor {f!r} for {name} is not a whole number of at least 1")
    clips = []
    for c in plan["clips"]:
        f = (factors or {}).get(c["name"], 1)
        if f == 1:
            clips.append(c)
            continue
        tracks = [{**t, "samples": [{**s, "elapsed": s["elapsed"] * f} for s in t["samples"]]} for t in c["tracks"]]
        events = [{**e, "elapsed": e["elapsed"] * f} for e in c["events"]]
        clips.append({**c, "tracks": tracks, "events": events, "duration": c["duration"] * f, "slowed": f})
    return {**plan, "clips": clips}


def add_chain_idles(plan):
    """plan -> plan for genericstategraph01 (FAL-489, the converted console on four states): the mapped Play slots are a chain, each clip starts
    from the pose the one before it ended in, and the four Idle slots hold four successive poses:
        StateA_Idle = the first frame of the first clip (rest),   StateB_Idle = the pose after the first clip,
        StateC_Idle = the pose after the second,                  StateD_Idle = the pose after the third (the last mapped clip's end).
    With fewer clips than idles the last pose repeats (a chain of two: C and D hold the pose after the second). A bone a clip leaves
    standing (every sample the same) is held at the pose the chain has reached (as add_toggle_idles does for slot B), a bone it moves keeps
    its own samples; a 'static' flag survives only when the pose's source track was static too. The chain is the mapped Play slots in slot
    order (a slot may be left out: then a clip's starts_from names the Idle of its POSITION in the chain, not of its slot). Play slots nobody mapped become SPARE clips:
    a bone-for-bone hold of the final pose, one frame long (1/30 s), so the graph's slot is filled and plays nothing. Every clip keeps one
    track per rig bone in rig order. Which pose each Idle slot SHOULD show is a hypothesis (the idle rule of #747 session 7); the graph's own
    rest after a play is read in the stages kit's card, not here. Needs the clips' tracks to be filled (fill_static_tracks) first."""
    by = {c["name"]: c for c in plan["clips"]}
    chain = [n for n in PLAY_SLOTS4 if n in by]
    if not chain:
        return plan
    first = by[chain[0]]
    effective = {c["name"]: c for c in plan["clips"] if c["name"] not in chain}
    poses = [(None, 0, chain[0], "first")]            # (tracks by node or None for the first clip's own, which sample of them, source clip, frame label)
    cur = {t["node"]: t for t in first["tracks"]}
    cur_sample = {t["node"]: t["samples"][0] for t in first["tracks"]}
    for k, name in enumerate(chain):
        clip = by[name]
        if k == 0:
            effective[name] = clip
        else:
            held, tracks = [], []
            for t in clip["tracks"]:
                src = cur.get(t["node"])
                stays = all(_same_pose(t["samples"][0], x) for x in t["samples"][1:])
                if src is None or not stays:
                    tracks.append(t)
                    continue
                pose = cur_sample[t["node"]]
                s0, s1 = t["samples"][0]["elapsed"], t["samples"][-1]["elapsed"]
                row = {**t, "samples": [{**pose, "elapsed": s0}, {**pose, "elapsed": s1}]}
                if t.get("static") and not src.get("static"):
                    row.pop("static")
                tracks.append(row)
                held.append(t["name"])
            effective[name] = {**clip, "tracks": tracks, "starts_from": f"State{'ABCD'[k]}_Idle", "held_at_idle_pose": held}
        cur = {t["node"]: t for t in effective[name]["tracks"]}
        cur_sample = {t["node"]: t["samples"][-1] for t in effective[name]["tracks"]}
        poses.append((cur, -1, name, "last"))
    clips = [effective[c["name"]] if c["name"] in effective else c for c in plan["clips"]]
    for i, idle in enumerate(IDLE_OF4.values()):
        tracks_of, which, source, label = poses[min(i, len(chain))]
        template = effective[source]
        held_tracks = []
        for t in template["tracks"] if which == 0 else tracks_of.values():
            smp = dict(t["samples"][which])
            smp["elapsed"] = 0.0
            held_tracks.append({**t, "samples": [smp]})
        clips.append({**template, "name": idle, "duration": 0.0, "events": [], "tracks": held_tracks, "hold_of": source, "hold_frame": label})
        for k_ in ("starts_from", "held_at_idle_pose"):
            clips[-1].pop(k_, None)
    last = effective[chain[-1]]
    final_tracks = [{**t, "samples": [{**t["samples"][-1], "elapsed": 0.0}, {**t["samples"][-1], "elapsed": 1.0 / FPS}]} for t in last["tracks"]]
    for slot in [n for n in PLAY_SLOTS4 if n not in chain]:                    # every unmapped slot, wherever it sits in the order
        clips.append({**last, "name": slot, "duration": 1.0 / FPS, "events": [], "tracks": final_tracks, "hold_of": chain[-1], "hold_frame": "last", "spare": True})
        clips[-1].pop("starts_from", None)
        clips[-1].pop("held_at_idle_pose", None)
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
    from . import door_rig
    bones = plan["bones"]
    clips = []
    for clip in plan["clips"]:
        by_node = {t["node"]: t for t in clip["tracks"]}
        every = sorted({s["elapsed"] for t in clip["tracks"] for s in t["samples"]}) or [0.0]
        times = sorted({every[0], every[-1]})            # a key at the first and the last frame is enough for a bone that stays
        tracks = []
        for bone in bones:
            if bone.get("node") is None and not bone.get("bind_for"):       # only a '<name>_Bind' parent bone may lack a node
                raise ValueError(f"rig bone {bone['name']!r} has no source node: a block for it cannot be written")
            key = door_rig.bone_key(bone)                  # a '<name>_Bind' parent bone (animated_identity_binds, bind_for) is keyed 'bind:<name>'
            if key in by_node:
                tracks.append(by_node[key])
                continue
            b = bone["bind"]
            tracks.append({"node": key, "name": bone["name"], "static": True, "target": bone["name"],
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
        out[clip["name"]] = descriptor(clip["name"], audio=audio_frames(clip, foley) if clip["name"] in PLAY_SLOTS4 and not clip.get("spare") else ())
    return out


def clip_table(plan, unit_scale):
    """Rows for the stager's report and the card: name, seconds, frames, bones with a track, hold_of, audio frames (no foley),
    and per track what it does from the first to the last sample (door_rig.open_motion: travel in metres, rotation in degrees).
    "bones" lists every track; "motion" says which of them actually move: a track can exist and stand still. unit_scale (source units to metres, convert_static.UNIT_SCALE) is required: travel is in metres."""
    from . import door_rig
    index = {door_rig.bone_key(b): i for i, b in enumerate(plan["bones"])}        # the rig bone index CALUMI files a track under
    rows = []
    for clip in plan["clips"]:
        rows.append({"name": clip["name"], "seconds": round(clip["duration"], 4), "frames": round(clip["duration"] * FPS),
                     "bones": sorted(t["name"] for t in clip["tracks"] if not t.get("static")), "hold_of": clip.get("hold_of"),
                     "hold_frame": clip.get("hold_frame"), "slowed": clip.get("slowed"), "starts_from": clip.get("starts_from"), "held_at_idle_pose": clip.get("held_at_idle_pose"),
                     "tracks": [{"bone": t["name"], "bone_index": index[t["node"]], "keys": len(t["samples"]), "static": bool(t.get("static"))}
                            for t in clip["tracks"]],
                     "motion": door_rig.open_motion(plan, unit_scale, clip["name"]),
                     "sound_keys": [round(e["elapsed"], 3) for e in clip.get("events", [])
                                    if str(e.get("text", e.get("name", ""))).lower().startswith("sound")]})
    return rows
