"""Load and validate a story pack (map + JSON files) into immutable Content.

A pack is a folder: map.txt, world.json, npcs.json, dialogue.json, facts.json.
Every problem is reported with the file it came from, so a broken pack
gives one clear message instead of a crash deep inside the game.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .clock import hhmm_to_tick
from .conditions import validate_condition
from .dialogue import Branch, NpcDialogue, parse_branches, parse_dialogue
from .knowledge import Fact, Question
from .npc import GONE, NpcDef, ScheduleEntry, Wander, minutes_to_ticks
from .world import Pos, Region, World

PACKS_DIR = Path(__file__).resolve().parent.parent / "content"
DEFAULT_PACK = "marrow"


class ContentError(Exception):
    """A content file is missing or broken. `file` names the culprit."""

    def __init__(self, file: str, problems: list[str]) -> None:
        self.file = file
        self.problems = problems
        super().__init__(f"{file}: " + "; ".join(problems[:5]))


@dataclass(frozen=True)
class Door:
    """A door whose state depends on conditions (evaluated live)."""

    id: str
    pos: Pos
    building: str
    open_if: dict | None
    locked_if: dict | None
    locked_text: str
    on_enter: tuple[dict, ...]


@dataclass(frozen=True)
class GameObject:
    """Something the player can inspect, like the gauge."""

    id: str
    pos: Pos
    name: str
    use: tuple[Branch, ...]


@dataclass(frozen=True)
class Announcement:
    """An NPC says something to everyone nearby, once per loop."""

    npc: str
    tick: int
    place: str
    radius: int
    text: str
    effects: tuple[dict, ...]


@dataclass(frozen=True)
class Omen:
    """Atmospheric message at a fixed time."""

    tick: int
    text: str


@dataclass(frozen=True)
class Hint:
    """A 'what to try next' line, shown while `cond` holds. `target` is e.g. 'npc:vera'."""

    cond: dict | None
    text: str
    target: str | None = None


@dataclass(frozen=True)
class WinRule:
    """The flood is stopped when `npc` stands in `place` with `flag` set before `before_tick`."""

    npc: str
    place: str
    flag: str
    before_tick: int


@dataclass(frozen=True)
class Rules:
    """Tunable numbers for the simulation."""

    view_radius: int = 9
    witness_radius: int = 4
    shout_radius: int = 8
    spread_chance: float = 0.5
    witness_trust_penalty: int = 30
    annoy_after_talks: int = 3
    annoy_trust_penalty: int = 10
    arrest_npc: str = ""
    arrest_rumour: str = ""


@dataclass(frozen=True)
class Content:
    """Everything loaded from one story pack."""

    pack: str
    name: str
    tagline: str
    intro: str
    world: World
    start: Pos
    npcs: tuple[NpcDef, ...]
    dialogue: dict[str, NpcDialogue]
    facts: dict[str, Fact]
    questions: tuple[Question, ...]
    doors: tuple[Door, ...]
    objects: tuple[GameObject, ...]
    announcements: tuple[Announcement, ...]
    omens: tuple[Omen, ...]
    win: WinRule
    flood_learn: str | None
    rules: Rules = field(default_factory=Rules)
    items: dict[str, str] = field(default_factory=dict)
    hints: tuple[Hint, ...] = ()

    def npc(self, npc_id: str) -> NpcDef:
        """NPC definition by id."""
        return next(n for n in self.npcs if n.id == npc_id)

    def item_name(self, item_id: str) -> str:
        """Display name for an inventory item."""
        return self.items.get(item_id, item_id)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ContentError(path.name, ["file is missing"]) from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ContentError(path.name, [f"cannot read file ({exc})"]) from None
    except json.JSONDecodeError as exc:
        raise ContentError(path.name, [f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"]) from None


def _pos(raw: Any, where: str, problems: list[str]) -> Pos:
    if isinstance(raw, list) and len(raw) == 2 and all(isinstance(v, int) for v in raw):
        return (raw[0], raw[1])
    problems.append(f"{where}: expected [x, y], got {raw!r}")
    return (0, 0)


def _tick(raw: Any, where: str, problems: list[str]) -> int:
    try:
        return hhmm_to_tick(raw)
    except (ValueError, TypeError) as exc:
        problems.append(f"{where}: {exc}")
        return 0


def _fail_if(file: str, problems: list[str]) -> None:
    if problems:
        raise ContentError(file, problems)


def load_map(path: Path) -> list[str]:
    """Read map.txt; every row must be the same width."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ContentError(path.name, ["file is missing"]) from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ContentError(path.name, [f"cannot read file ({exc})"]) from None
    rows = text.rstrip("\n").split("\n")
    if not rows or not rows[0]:
        raise ContentError(path.name, ["map is empty"])
    widths = {len(r) for r in rows}
    if len(widths) != 1:
        raise ContentError(path.name, [f"rows have different widths: {sorted(widths)}"])
    if any(ord(c) > 127 for r in rows for c in r):
        raise ContentError(path.name, ["map must be pure ASCII"])
    return rows


def _load_world(raw: dict, rows: list[str], problems: list[str]) -> tuple[World, list[GameObject], list[Door]]:
    regions = []
    for i, r in enumerate(raw.get("regions", [])):
        rect = r.get("rect", [])
        if not (isinstance(rect, list) and len(rect) == 4):
            problems.append(f"regions[{i}]: 'rect' must be [x0, y0, x1, y1]")
            continue
        spots = tuple(_pos(s, f"regions[{i}].spots", problems) for s in r.get("spots", []))
        regions.append(Region(r.get("id", f"r{i}"), r.get("name", r.get("id", "?")), tuple(rect), spots))
    objects = []
    for i, o in enumerate(raw.get("objects", [])):
        use = parse_branches(o.get("use"), f"objects[{i}].use", problems)
        objects.append(GameObject(o.get("id", f"o{i}"), _pos(o.get("pos"), f"objects[{i}]", problems),
                                  o.get("name", "thing"), use))
    world = World(rows, regions, {o.pos for o in objects})
    doors = []
    for i, d in enumerate(raw.get("doors", [])):
        where = f"doors[{i}]"
        pos = _pos(d.get("pos"), where, problems)
        if not world.is_door(pos):
            problems.append(f"{where}: {pos} is not a door tile on the map")
        problems.extend(validate_condition(d.get("open_if"), where))
        problems.extend(validate_condition(d.get("locked_if"), where))
        if not world.has_region(d.get("building", "")):
            problems.append(f"{where}: unknown building {d.get('building')!r}")
        doors.append(Door(d.get("id", where), pos, d.get("building", ""), d.get("open_if"), d.get("locked_if"),
                          d.get("locked_text", "It's locked."), tuple(d.get("on_enter", []))))
    for region in regions:
        for spot in region.spots:
            if not world.is_floor(spot):
                problems.append(f"region '{region.id}': spot {spot} is not walkable")
    return world, objects, doors


def _load_npcs(raw: Any, world: World, problems: list[str]) -> list[NpcDef]:
    if not isinstance(raw, list) or not raw:
        problems.append("must be a non-empty list of NPCs")
        return []
    npcs = []
    for i, n in enumerate(raw):
        where = f"npcs[{i}]"
        schedule = []
        for j, e in enumerate(n.get("schedule", [])):
            place = e.get("place", "")
            if place != GONE and not world.has_region(place):
                problems.append(f"{where}.schedule[{j}]: unknown place {place!r}")
            schedule.append(ScheduleEntry(_tick(e.get("time"), f"{where}.schedule[{j}]", problems),
                                          place, int(e.get("slot", 0)), e.get("text", "")))
        wander = None
        if "wander" in n:
            w = n["wander"]
            places = tuple(w.get("places", []))
            for p in places:
                if not world.has_region(p):
                    problems.append(f"{where}.wander: unknown place {p!r}")
            wander = Wander(_tick(w.get("start", "08:00"), f"{where}.wander", problems),
                            minutes_to_ticks(int(w.get("every", 20))), places)
        start = n.get("start", {})
        if not schedule and not start:
            problems.append(f"{where}: needs a 'schedule' or a 'start'")
        letter = n.get("letter", "?")
        if not (isinstance(letter, str) and len(letter) == 1 and letter.isupper()):
            problems.append(f"{where}: 'letter' must be one capital letter")
        npcs.append(NpcDef(n.get("id", where), letter, n.get("name", "?"), n.get("role", ""),
                           n.get("color", "white"), int(n.get("speed", 1)), tuple(schedule), wander,
                           start.get("place", ""), int(start.get("slot", 0))))
    ids = [n.id for n in npcs]
    if len(set(ids)) != len(ids):
        problems.append("NPC ids must be unique")
    return npcs


def _load_facts(raw: Any, problems: list[str]) -> tuple[dict[str, Fact], tuple[Question, ...]]:
    facts: dict[str, Fact] = {}
    for i, f in enumerate(raw.get("facts", []) if isinstance(raw, dict) else []):
        if not all(isinstance(f.get(k), str) for k in ("id", "source", "short", "text")):
            problems.append(f"facts[{i}]: needs id, source, short, text")
            continue
        facts[f["id"]] = Fact(f["id"], f["source"], f["short"], f["text"])
    if not facts:
        problems.append("no facts defined")
    questions = []
    for i, q in enumerate(raw.get("questions", []) if isinstance(raw, dict) else []):
        for key in ("after", "until"):
            if q.get(key) not in (None, "never") and q.get(key) not in facts:
                problems.append(f"questions[{i}]: unknown fact {q.get(key)!r}")
        questions.append(Question(q.get("text", "?"), q.get("after"), q.get("until", "never")))
    return facts, tuple(questions)


def _load_hints(raw: Any, world: World, objects: list[GameObject], npcs: list[NpcDef],
                problems: list[str]) -> tuple[Hint, ...]:
    """Parse hints.json; every target must name a real npc, object or place."""
    valid = ({f"npc:{n.id}" for n in npcs} | {f"object:{o.id}" for o in objects}
             | {f"place:{r.id}" for r in world.regions})
    hints = []
    for branch, item in zip(parse_branches(raw, "hints", problems), raw if isinstance(raw, list) else [],
                            strict=False):
        target = item.get("target")
        if target is not None and target not in valid:
            problems.append(f"hints: unknown target {target!r} (use npc:, object: or place:)")
        hints.append(Hint(branch.cond, branch.text, target))
    return tuple(hints)


def _check_references(content_bits: dict, facts: dict[str, Fact], npc_ids: set[str], world: World) -> list[str]:
    """Every fact / npc / place mentioned in conditions and effects must exist."""
    problems = []

    def check_cond(cond: dict | None, where: str) -> None:
        if not cond:
            return
        for key in ("facts", "no_facts"):
            for fact in cond.get(key, []):
                if fact not in facts:
                    problems.append(f"{where}: unknown fact {fact!r}")
        if "npc_at" in cond and cond["npc_at"][0] not in npc_ids:
            problems.append(f"{where}: unknown npc {cond['npc_at'][0]!r}")
        if "npc_gone" in cond and cond["npc_gone"] not in npc_ids:
            problems.append(f"{where}: unknown npc {cond['npc_gone']!r}")

    def check_branches(branches: tuple[Branch, ...], where: str) -> None:
        for b in branches:
            check_cond(b.cond, where)
            for e in b.effects:
                if "learn" in e and e["learn"] not in facts:
                    problems.append(f"{where}: learns unknown fact {e['learn']!r}")
                if "goto" in e and not world.has_region(e["goto"]):
                    problems.append(f"{where}: goto unknown place {e['goto']!r}")

    for npc_id, dlg in content_bits["dialogue"].items():
        if npc_id not in npc_ids:
            problems.append(f"dialogue for unknown npc {npc_id!r}")
        check_branches(dlg.greeting, f"dialogue.{npc_id}.greeting")
        for t in dlg.topics:
            check_cond(t.requires, f"dialogue.{npc_id}.{t.id}")
            check_branches(t.replies, f"dialogue.{npc_id}.{t.id}")
    for npc_id in npc_ids - set(content_bits["dialogue"]):
        problems.append(f"npc {npc_id!r} has no dialogue")
    for obj in content_bits["objects"]:
        check_branches(obj.use, f"objects.{obj.id}")
    for hint in content_bits.get("hints", ()):
        check_cond(hint.cond, "hints")
    for door in content_bits["doors"]:
        check_cond(door.open_if, f"doors.{door.id}")
        check_cond(door.locked_if, f"doors.{door.id}")
    return problems


def load_content(pack: str = DEFAULT_PACK, packs_dir: Path | None = None) -> Content:
    """Load and validate a story pack. Raises ContentError naming the bad file."""
    root = (packs_dir or PACKS_DIR) / pack
    if not root.is_dir():
        raise ContentError(str(root), ["story pack folder not found"])
    rows = load_map(root / "map.txt")

    problems: list[str] = []
    world_raw = _read_json(root / "world.json")
    if not isinstance(world_raw, dict):
        raise ContentError("world.json", ["must be a JSON object"])
    world, objects, doors = _load_world(world_raw, rows, problems)
    start = _pos(world_raw.get("start"), "start", problems)
    if not world.is_floor(start):
        problems.append(f"start {start} is not walkable")
    _fail_if("world.json", problems)

    npcs = _load_npcs(_read_json(root / "npcs.json"), world, problems)
    _fail_if("npcs.json", problems)

    facts, questions = _load_facts(_read_json(root / "facts.json"), problems)
    _fail_if("facts.json", problems)

    dialogue_raw = _read_json(root / "dialogue.json")
    if not isinstance(dialogue_raw, dict):
        raise ContentError("dialogue.json", ["must be a JSON object"])
    dialogue = {npc_id: parse_dialogue(d, npc_id, problems) for npc_id, d in dialogue_raw.items()}
    _fail_if("dialogue.json", problems)

    hints: tuple[Hint, ...] = ()
    if (root / "hints.json").exists():
        hints = _load_hints(_read_json(root / "hints.json"), world, objects, npcs, problems)
        _fail_if("hints.json", problems)

    npc_ids = {n.id for n in npcs}
    problems = _check_references({"dialogue": dialogue, "objects": objects, "doors": doors, "hints": hints},
                                 facts, npc_ids, world)
    _fail_if("dialogue.json / world.json / hints.json", problems)

    announcements = []
    for i, a in enumerate(world_raw.get("announcements", [])):
        announcements.append(Announcement(a.get("npc", ""), _tick(a.get("after"), f"announcements[{i}]", problems),
                                          a.get("place", ""), int(a.get("radius", 10)), a.get("text", ""),
                                          tuple(a.get("effects", []))))
        if a.get("npc") not in npc_ids:
            problems.append(f"announcements[{i}]: unknown npc {a.get('npc')!r}")
    omens = tuple(Omen(_tick(o.get("time"), f"omens[{i}]", problems), o.get("text", ""))
                  for i, o in enumerate(world_raw.get("omens", [])))
    win_raw = world_raw.get("win", {})
    win = WinRule(win_raw.get("npc", ""), win_raw.get("place", ""), win_raw.get("flag", ""),
                  _tick(win_raw.get("before", "14:00"), "win", problems))
    if win.npc not in npc_ids or not world.has_region(win.place):
        problems.append("win: needs a known 'npc' and 'place'")
    flood_learn = world_raw.get("flood", {}).get("learn")
    if flood_learn and flood_learn not in facts:
        problems.append(f"flood: unknown fact {flood_learn!r}")
    r = world_raw.get("rules", {})
    arrest = r.get("arrest", {})
    rules = Rules(int(r.get("view_radius", 9)), int(r.get("witness_radius", 4)), int(r.get("shout_radius", 8)),
                  float(r.get("spread_chance", 0.5)), int(r.get("witness_trust_penalty", 30)),
                  int(r.get("annoy_after_talks", 3)), int(r.get("annoy_trust_penalty", 10)),
                  arrest.get("npc", ""), arrest.get("rumour", ""))
    _fail_if("world.json", problems)

    return Content(pack, world_raw.get("name", pack), world_raw.get("tagline", ""), world_raw.get("intro", ""),
                   world, start, tuple(npcs), dialogue, facts, questions, tuple(doors), tuple(objects),
                   tuple(announcements), omens, win, flood_learn, rules,
                   {str(k): str(v) for k, v in world_raw.get("items", {}).items()}, hints)
