"""Small derived indexes for the combined simulation event log.

The resettlement lookup matches ``sim._resettle_safe``'s reverse scan only when
event hours are non-decreasing. Callers maintaining an index must preserve that
ordering; the simulation currently appends events at the current world hour.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


HOLDER_CHANGE_KINDS = frozenset(("place_taken", "place_cleared"))
ATTACK_EVENT_KINDS = frozenset(("place_taken", "attack_failed", "place_cleared"))


@dataclass
class LogIndex:
    """Indexes holder losses and the latest fight at each place from an event log.

    ``fought_since`` is equivalent to the log scan in ``sim._resettle_safe``
    when event hours are monotonic non-decreasing, because that reader stops at
    the first event older than its cutoff.
    """

    ever_lost: dict[str, set[str]] = field(default_factory=dict)
    last_fight: dict[str, int] = field(default_factory=dict)

    @classmethod
    def build(cls, events: list[dict]) -> "LogIndex":
        index = cls()
        for event in events:
            index.add(event)
        return index

    def add(self, event: dict) -> None:
        """Index one appended event. The expected update cost is O(1)."""
        kind = event["kind"]
        if kind not in HOLDER_CHANGE_KINDS and kind not in ATTACK_EVENT_KINDS:
            return
        place = event["place"]
        if kind in HOLDER_CHANGE_KINDS:
            previous = event.get("previous")
            if previous is not None:
                self.ever_lost.setdefault(previous, set()).add(place)
        if kind in ATTACK_EVENT_KINDS:
            hour = event["hour"]
            if place not in self.last_fight or hour > self.last_fight[place]:
                self.last_fight[place] = hour

    def lost_places(self, ws: Any, fid: str) -> set[str]:
        """Return places this faction once held and no longer holds."""
        return {place for place in self.ever_lost.get(fid, ())
                if ws.places[place].holder != fid}

    def fought_since(self, place: str, since: int) -> bool:
        """Whether an indexed fight at ``place`` occurred at/after ``since``."""
        return self.last_fight.get(place, since - 1) >= since

    def to_json(self) -> dict:
        """Return a canonical JSON-compatible object with sorted keys and lists."""
        return {
            "ever_lost": {fid: sorted(places) for fid, places in sorted(self.ever_lost.items())},
            "last_fight": dict(sorted(self.last_fight.items())),
        }

    @classmethod
    def from_json(cls, data: dict) -> "LogIndex":
        """Load independent collections from the canonical JSON-compatible shape."""
        if not isinstance(data, dict):
            raise ValueError("log index must be an object")
        try:
            lost_data, fight_data = data["ever_lost"], data["last_fight"]
        except KeyError as exc:
            raise ValueError(f"log index is missing {exc.args[0]!r}") from exc
        if not isinstance(lost_data, dict) or not isinstance(fight_data, dict):
            raise ValueError("log index fields must be objects")
        lost: dict[str, set[str]] = {}
        for fid, places in lost_data.items():
            if not isinstance(fid, str) or not isinstance(places, list) or not all(isinstance(p, str) for p in places):
                raise ValueError("ever_lost must map faction ids to lists of place ids")
            lost[fid] = set(places)
        fights: dict[str, int] = {}
        for place, hour in fight_data.items():
            if not isinstance(place, str) or not isinstance(hour, int) or isinstance(hour, bool):
                raise ValueError("last_fight must map place ids to integer hours")
            fights[place] = hour
        return cls(ever_lost=lost, last_fight=fights)
