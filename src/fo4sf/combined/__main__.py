"""python -m fo4sf.combined: offline tools for the combined core (nothing here touches a game).

  seed OUT_DIR PLUGIN...           read-only draft of a pack from the player's own plugins (seed.py)
  seed-pack DRAFT.json OUT_DIR     a pack that runs, generated from that draft by placeholder rules (seedpack.py)
  simulate --pack FILE [--pack FILE] --seed N --days D [--out STATE.json] [--resume STATE.json]
  demo --seed N --days D           the built-in synthetic fixtures (placeholder names, not game facts)
  balance --seeds N --days D [--pack FILE ...] [--set NAME=VALUE ...]   tuning sweep (balance.py); exit 1 on a broken bound
  news [--pack FILE ...] [--resume STATE.json] --place ID                the terminal page a place shows (news.py)
  present [--pack FILE ...] [--resume STATE.json] --place ID             the presence plan around a place (present.py)
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter

from . import balance, news, present
from . import seed as _seed
from . import seedpack, sim
from .fixtures import REGION_1, REGION_2
from .model import WorldState, load_pack

HOURS_PER_DAY = 24


def summary(ws: WorldState) -> dict:
    """What a run changed, small enough to print: event counts by kind, who holds what, settlement sizes."""
    return {
        "hour": ws.hour,
        "events": dict(sorted(Counter(e["kind"] for e in ws.events).items())),
        "holders": {k: p.holder for k, p in sorted(ws.places.items())},
        "settlements": {k: {"population": s.population, "stage": s.stage, "morale": s.morale}
                        for k, s in sorted(ws.settlements.items())},
        "squads": len(ws.squads),
    }


def _print(obj) -> None:
    print(json.dumps(obj, indent=1, sort_keys=True))


def cmd_seed(args) -> int:
    report = _seed.seed(args.out_dir, args.plugins)
    _print({k: report[k] for k in ("locations", "settlement_candidates", "base_candidates", "factions",
                                   "overrides", "deleted_records", "compressed_records", "problems")})
    return 0


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_seedpack(args) -> int:
    draft = _load_json(args.draft)
    if not isinstance(draft, dict) or not draft.get("draft") or "places" not in draft:
        raise ValueError(f"{args.draft}: not a seed draft (want the commonwealth_seed.draft.json that `seed` writes)")
    gateway_args = {"gateways": _load_json(args.gateways)} if args.gateways else {}
    pack, report = seedpack.generate(draft, **gateway_args)
    paths = seedpack.write(args.out_dir, pack, report)
    print(f"{seedpack.summary(report)} -> {paths['pack']}")
    gateway_problems = report.get("gateways", {}).get("problems", [])
    for problem in gateway_problems:
        print(f"error: {problem}", file=sys.stderr)
    return 1 if report["validation_problems"] or gateway_problems else 0


def _world(args, seed: int = 1) -> WorldState | None:
    """The world a command works on: --resume STATE.json, then every --pack added; None (and a message) if empty."""
    if getattr(args, "resume", None):
        with open(args.resume, encoding="utf-8") as f:
            ws = WorldState.from_json(f.read())   # the save carries its own seed; --seed is ignored
    else:
        ws = WorldState(seed=seed)
    for path in args.pack or []:
        load_pack(ws, _load_json(path))          # raises ValueError listing every problem
    if not ws.places:
        print(f"{args.cmd}: no places; give at least one --pack or a --resume state", file=sys.stderr)
        return None
    return ws


def _place(args, ws: WorldState) -> bool:
    if args.place not in ws.places:
        print(f"{args.cmd}: unknown place {args.place!r}; known: {', '.join(sorted(ws.places))}", file=sys.stderr)
        return False
    return True


def cmd_simulate(args) -> int:
    ws = _world(args, args.seed)
    if ws is None:
        return 2
    sim.run(ws, args.days * HOURS_PER_DAY)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(ws.to_json())
    _print(summary(ws))
    return 0


def cmd_demo(args) -> int:
    ws = WorldState(seed=args.seed)
    load_pack(ws, copy.deepcopy(REGION_1))
    load_pack(ws, copy.deepcopy(REGION_2))
    sim.run(ws, args.days * HOURS_PER_DAY)
    _print(summary(ws))
    return 0


def _parse_set(item: str) -> tuple[str, object]:
    """NAME=VALUE for --set; the value must be JSON (0.5, 3, true, "text"), so a typo is an error, not a string."""
    name, eq, raw = item.partition("=")
    if not eq or not name:
        raise ValueError(f"--set wants NAME=VALUE, got {item!r}")
    try:
        return name, json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"--set {name}: value {raw!r} is not JSON (quote a string: '\"text\"')") from None


# The balance command's yardsticks. The fixtures' bounds are absolute counts for 11 places, so a real Commonwealth pack
# read against them reports churn that is normal for its size (docs/combined-core.md, "Real pack, all DLC").
BOUNDS = {"fixtures": balance.DEFAULT_BOUNDS, "scale": balance.SCALE_BOUNDS}


def cmd_balance(args) -> int:
    packs = [_load_json(p) for p in args.pack] if args.pack else [copy.deepcopy(REGION_1), copy.deepcopy(REGION_2)]
    overrides = dict(_parse_set(item) for item in args.set or [])
    result = balance.sweep(packs, range(args.seeds), args.days, overrides)
    broken = balance.check(result["aggregate"], BOUNDS[args.bounds])
    _print({"aggregate": result["aggregate"], "bounds": args.bounds, "broken": broken, "days": args.days,
            "overrides": overrides, "seeds": args.seeds})
    return 1 if broken else 0


def cmd_news(args) -> int:
    ws = _world(args)
    if ws is None:
        return 2
    if not _place(args, ws):
        return 2
    print(news.terminal_page(ws, args.place))
    return 0


def cmd_present(args) -> int:
    ws = _world(args)
    if ws is None:
        return 2
    if not _place(args, ws):
        return 2
    _print(present.plan(ws, args.place).to_dict())
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m fo4sf.combined", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed", help="draft a pack from plugins (read-only)")
    s.add_argument("out_dir")
    s.add_argument("plugins", nargs="+", metavar="PLUGIN")
    s.set_defaults(fn=cmd_seed)
    s = sub.add_parser("seed-pack", help="generate a runnable pack from a seed draft (placeholder rules)")
    s.add_argument("draft", metavar="DRAFT.json")
    s.add_argument("out_dir")
    s.add_argument("--gateways", metavar="FILE", help="explicit inter-world gateway pairs (a, b, hours)")
    s.set_defaults(fn=cmd_seedpack)
    s = sub.add_parser("simulate", help="run the simulation on JSON packs")
    s.add_argument("--pack", action="append", metavar="FILE")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--days", type=int, required=True)
    s.add_argument("--out", metavar="STATE.json")
    s.add_argument("--resume", metavar="STATE.json")
    s.set_defaults(fn=cmd_simulate)
    s = sub.add_parser("demo", help="run the built-in synthetic fixtures")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--days", type=int, default=30)
    s.set_defaults(fn=cmd_demo)
    s = sub.add_parser("balance", help="sweep seeds and check the aggregate against the chosen bounds")
    s.add_argument("--seeds", type=int, required=True, help="run seeds 0..N-1")
    s.add_argument("--days", type=int, required=True)
    s.add_argument("--pack", action="append", metavar="FILE", help="default: the built-in fixtures")
    s.add_argument("--set", action="append", metavar="NAME=VALUE",
                   help="override a sim constant for the sweep (VALUE as JSON), e.g. sim.UPKEEP_PER_PLACE=2")
    s.add_argument("--bounds", choices=sorted(BOUNDS), default="fixtures",
                   help="fixtures: balance.DEFAULT_BOUNDS, written for the 11-place fixtures; scale: "
                        "balance.SCALE_BOUNDS, per place and per faction, for a Commonwealth-size pack")
    s.set_defaults(fn=cmd_balance)
    for name, fn, what in (("news", cmd_news, "print the terminal news page at a place"),
                           ("present", cmd_present, "print the presence plan around a place")):
        s = sub.add_parser(name, help=what)
        s.add_argument("--pack", action="append", metavar="FILE")
        s.add_argument("--resume", metavar="STATE.json")
        s.add_argument("--place", required=True, metavar="ID")
        s.set_defaults(fn=fn)
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.fn(args)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
