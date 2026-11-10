"""L3 news: the simulation's events as short lines of our own writing, for terminals and on-screen text.

The design's default for seeing the off-screen world is "radio and terminal text first" in our own
words (combined-core design, docs/research/framework/combined-core.md, CC-30 and "The legal
fence", which lists terminal and radio news text we author as ours). Spoken news waits on the voice
question, so this module makes text only. The event feed itself comes from sim.news_for, so a place
only reports what has had time to reach it along the routes.

Templates are plain, neutral English keyed by event kind; they quote no game's writing. Unknown kinds
are skipped so a newer simulation never breaks an older presenter. Output is deterministic: newest
first, ties kept in event order, exact repeats collapsed.
"""
from __future__ import annotations

import textwrap

from .model import WorldState
from .sim import news_for

HEADLINE_LIMIT = 12               # placeholder: lines a terminal page shows
TERMINAL_WIDTH = 60               # placeholder: columns of a terminal page
HOURS_PER_DAY = 24

# One template per event kind; {name} fields are filled from the event by _fields. Our own wording.
TEMPLATES = {
    "place_taken": "{faction} took {place} from {previous}.",
    "place_retaken": "{faction} took back {place} from {previous}.",
    "place_claimed": "{faction} moved into {place}.",
    "attack_launched": "{faction} sent fighters from {place} toward {target}.",
    "attack_failed": "An attack by {faction} on {place} was beaten off.",
    "attack_called_off": "{faction} called off an attack on {place}.",
    "caravan_raided": "A caravan from {origin} to {place} was raided by {raider}.",
    "caravan_arrived": "A caravan reached {place} carrying {cargo}.",
    "caravan_lost": "A caravan bound for {place} never arrived.",
    "stage_grew": "{place} has grown.",
    "stage_shrank": "{place} has shrunk.",
    "settler_left": "A settler left {place}.",
    "settler_arrived": "A new settler arrived at {place}.",
    "settlement_emptied": "The last settler has left {place}; it stands empty.",
    "settlement_resettled": "Settlers of {faction} have moved back into {place}.",
    "player_defended": "A traveller stood guard at {place}.",
    "player_gave": "A traveller brought supplies to {place}.",
    "player_took": "A traveller bought supplies at {place}.",
    # jobs.py outcomes
    "place_cleared": "{faction} drove {previous} out of {place}.",
    "job_done": "A traveller finished a job for {faction} at {place}.",
    "job_failed": "A traveller let {faction} down at {place}.",
    # manage.py actions
    "roles_changed": "Settlers at {place} were moved from {from_role} work to {to_role} work.",
    "beds_added": "New beds were built at {place}.",
    "priority_set": "{place} is now putting its effort into {good}.",
    "priority_cleared": "{place} has gone back to working as usual.",
    "supplies_sent": "A caravan left {place} for {target} carrying {cargo}.",
}


def display_name(ident: str | None, names: dict[str, str] | None = None) -> str:
    """Pack ids are machine names; a pack may ship display names, else underscores become spaces."""
    if ident is None:
        return "no one"
    if names and ident in names:
        return names[ident]
    return ident.replace("_", " ")


def _cargo(cargo: dict | None) -> str:
    if not cargo:
        return "nothing"
    return ", ".join(f"{n} {g}" for g, n in sorted(cargo.items()) if n)


def _template_key(e: dict) -> str | None:
    """Pick the template for an event, or None for kinds this module does not write about."""
    kind = e.get("kind")
    if kind == "place_taken":
        if e.get("previous") is None:
            return "place_claimed"
        return "place_retaken" if e.get("retaken") else "place_taken"
    if kind == "stage_changed":
        return "stage_grew" if e.get("new", 0) >= e.get("old", 0) else "stage_shrank"
    if kind == "player_traded":
        given = sum(n for n in (e.get("goods") or {}).values() if n > 0)
        return "player_gave" if given else "player_took"
    if kind == "priority_set":
        return "priority_cleared" if e.get("new") is None else "priority_set"
    return kind if kind in TEMPLATES else None


def _fields(e: dict, names) -> dict[str, str]:
    out = {}
    for k in ("place", "faction", "previous", "target", "origin", "raider", "defender", "holder",
              "from_role", "to_role"):
        if k in e:
            out[k] = display_name(e[k], names)
    out["cargo"] = _cargo(e.get("cargo"))
    if e.get("kind") == "priority_set":
        out["good"] = display_name(e.get("new"), names)
    return out


def headline(e: dict, names: dict[str, str] | None = None) -> str | None:
    """One event as a line, or None when its kind has no template."""
    key = _template_key(e)
    if key is None:
        return None
    text = TEMPLATES[key].format(**_fields(e, names))
    return text[0].upper() + text[1:]


def items(ws: WorldState, place: str, since: int = 0, limit: int = HEADLINE_LIMIT,
          names: dict[str, str] | None = None) -> list[dict]:
    """Headlines that have reached `place`, newest first, as {hour, kind, place, text}; exact repeats
    keep only their newest occurrence; at most `limit`."""
    out, seen = [], set()
    reached = news_for(ws, place, since)
    newest_first = sorted(range(len(reached)), key=lambda n: (-reached[n]["hour"], n))   # ties in event order
    for e in (reached[n] for n in newest_first):
        if len(out) >= limit:
            break
        text = headline(e, names)
        if text is None or text in seen:
            continue
        seen.add(text)
        out.append({"hour": e["hour"], "kind": e["kind"], "place": e["place"], "text": text})
    return out


def headlines(ws: WorldState, place: str, since: int = 0, limit: int = HEADLINE_LIMIT,
              names: dict[str, str] | None = None) -> list[str]:
    """The lines of items(), newest first."""
    return [i["text"] for i in items(ws, place, since, limit, names)]


def _stamp(hour: int) -> str:
    return f"Day {hour // HOURS_PER_DAY + 1}, {hour % HOURS_PER_DAY:02d}:00"


class _Wrapper(textwrap.TextWrapper):
    """textwrap.TextWrapper with one long-word rule on every Python. CPython 3.14 breaks a long word
    only while the line has room left (space_left > 0); older releases also cut an empty piece off it
    when the line was already full, so a whitespace chunk before the word survived drop_whitespace
    (a line " " or "s at "). This is the 3.14 rule, which the C++ port (sfse/FOCCSim/news.cpp) follows."""

    def _handle_long_word(self, reversed_chunks, cur_line, cur_len, width):
        space_left = 1 if width < 1 else width - cur_len
        if self.break_long_words and space_left > 0:
            end = space_left
            chunk = reversed_chunks[-1]
            if self.break_on_hyphens and len(chunk) > space_left:
                hyphen = chunk.rfind("-", 0, space_left)
                if hyphen > 0 and any(c != "-" for c in chunk[:hyphen]):
                    end = hyphen + 1
            cur_line.append(chunk[:end])
            reversed_chunks[-1] = chunk[end:]
        elif not cur_line:
            cur_line.append(reversed_chunks.pop())


def wrap(text: str, width: int = 70, subsequent_indent: str = "") -> list[str]:
    """textwrap.wrap(text, width, subsequent_indent=...), the same on every Python (see _Wrapper)."""
    return _Wrapper(width, subsequent_indent=subsequent_indent).wrap(text)


def shorten(text: str, width: int, placeholder: str = " [...]") -> str:
    """textwrap.shorten(text, width, placeholder=...), the same on every Python (see _Wrapper)."""
    return _Wrapper(width, max_lines=1, placeholder=placeholder).fill(" ".join(text.strip().split()))


def terminal_page(ws: WorldState, place: str, since: int = 0, limit: int = HEADLINE_LIMIT,
                  width: int = TERMINAL_WIDTH, names: dict[str, str] | None = None) -> str:
    """Plain text for a terminal: a title line, then one wrapped entry per headline, every line at
    most `width` columns. Says so when nothing has reached the place yet."""
    title = f"{display_name(place, names)} news, {_stamp(ws.hour)}"
    lines = [shorten(title, width, placeholder="..."), "-" * min(width, len(title))]
    found = items(ws, place, since, limit, names)
    if not found:
        lines.extend(wrap(f"No news has reached {display_name(place, names)}.", width))
    for i in found:
        lines.extend(wrap(f"{_stamp(i['hour'])}: {i['text']}", width, subsequent_indent="  "))
    return "\n".join(lines)
