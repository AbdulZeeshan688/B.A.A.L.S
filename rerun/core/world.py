"""The static town: tile grid, named regions, line of sight, pathfinding."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable

Pos = tuple[int, int]

FLOOR_CHARS = frozenset(" .,")
WALL_CHARS = frozenset("+-|")
WATER_CHARS = frozenset("~")
DAM_CHARS = frozenset("=#")
FOREST_CHARS = frozenset("^")
DOOR_CHARS = frozenset("Dx")

# Fixed neighbour order keeps pathfinding deterministic.
NEIGHBOURS: tuple[Pos, ...] = ((0, -1), (1, 0), (0, 1), (-1, 0))


@dataclass(frozen=True)
class Region:
    """A named rectangle of the map, e.g. 'the Cafe'."""

    id: str
    name: str
    rect: tuple[int, int, int, int]
    spots: tuple[Pos, ...] = ()

    def contains(self, pos: Pos) -> bool:
        """True if pos is inside this region."""
        x0, y0, x1, y1 = self.rect
        return x0 <= pos[0] <= x1 and y0 <= pos[1] <= y1

    def spot(self, slot: int) -> Pos:
        """Standing spot for a slot index (wraps around)."""
        if not self.spots:
            x0, y0, x1, y1 = self.rect
            return ((x0 + x1) // 2, (y0 + y1) // 2)
        return self.spots[slot % len(self.spots)]


@dataclass
class World:
    """Tile grid plus regions. Never changes during play."""

    rows: list[str]
    regions: list[Region]
    object_tiles: set[Pos] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.height = len(self.rows)
        self.width = max((len(r) for r in self.rows), default=0)
        self.rows = [r.ljust(self.width) for r in self.rows]
        self._regions_by_id = {r.id: r for r in self.regions}
        self._dist_cache: dict[tuple[Pos, str], dict[Pos, int]] = {}

    def in_bounds(self, pos: Pos) -> bool:
        """True if pos is on the map."""
        return 0 <= pos[0] < self.width and 0 <= pos[1] < self.height

    def char(self, pos: Pos) -> str:
        """Raw map character at pos (space when off-map)."""
        if not self.in_bounds(pos):
            return " "
        return self.rows[pos[1]][pos[0]]

    def kind(self, pos: Pos) -> str:
        """Tile kind: floor, wall, water, dam, forest, door, object, label or void."""
        if not self.in_bounds(pos):
            return "void"
        if pos in self.object_tiles:
            return "object"
        ch = self.char(pos)
        for kind, chars in (("floor", FLOOR_CHARS), ("wall", WALL_CHARS), ("water", WATER_CHARS),
                            ("dam", DAM_CHARS), ("forest", FOREST_CHARS), ("door", DOOR_CHARS)):
            if ch in chars:
                return kind
        return "label"

    def is_floor(self, pos: Pos) -> bool:
        """Walkable ground (not counting doors)."""
        return self.kind(pos) == "floor"

    def is_door(self, pos: Pos) -> bool:
        """True if pos is a door tile."""
        return self.kind(pos) == "door"

    def opaque(self, pos: Pos) -> bool:
        """True if the tile blocks line of sight."""
        kind = self.kind(pos)
        return kind in ("wall", "forest", "void") or (kind == "door" and self.char(pos) == "x")

    def region(self, region_id: str) -> Region:
        """Region by id. Raises KeyError if unknown."""
        return self._regions_by_id[region_id]

    def has_region(self, region_id: str) -> bool:
        """True if a region with this id exists."""
        return region_id in self._regions_by_id

    def region_at(self, pos: Pos) -> Region | None:
        """First region containing pos (list order = priority)."""
        for region in self.regions:
            if region.contains(pos):
                return region
        return None

    def line_of_sight(self, a: Pos, b: Pos) -> bool:
        """True if a can see b. Symmetric: either Bresenham direction being clear is enough,
        so someone beside a doorway can see a person stepping into it."""
        return self._clear_line(a, b) or self._clear_line(b, a)

    def _clear_line(self, a: Pos, b: Pos) -> bool:
        """Bresenham line from a to b; blocked by opaque tiles strictly in between."""
        (x0, y0), (x1, y1) = a, b
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        x, y = x0, y0
        while (x, y) != (x1, y1):
            if (x, y) != a and self.opaque((x, y)):
                return False
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy
        return True

    def distance_map(self, target: Pos, passable: Callable[[Pos], bool], key: str) -> dict[Pos, int]:
        """BFS distances from every reachable tile to target (cached per key)."""
        cache_key = (target, key)
        cached = self._dist_cache.get(cache_key)
        if cached is not None:
            return cached
        dist = {target: 0}
        queue = deque([target])
        while queue:
            cur = queue.popleft()
            for dx, dy in NEIGHBOURS:
                nxt = (cur[0] + dx, cur[1] + dy)
                if nxt not in dist and self.in_bounds(nxt) and passable(nxt):
                    dist[nxt] = dist[cur] + 1
                    queue.append(nxt)
        self._dist_cache[cache_key] = dist
        return dist

    def step_towards(self, start: Pos, dist: dict[Pos, int]) -> Pos:
        """Next tile from start that gets closer on a distance map (or start)."""
        here = dist.get(start)
        if here is None or here == 0:
            return start
        for dx, dy in NEIGHBOURS:
            nxt = (start[0] + dx, start[1] + dy)
            if dist.get(nxt, here) < here:
                return nxt
        return start


def chebyshev(a: Pos, b: Pos) -> int:
    """King-move distance between two tiles."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def tiles(world: World) -> Iterable[Pos]:
    """Every tile position on the map."""
    for y in range(world.height):
        for x in range(world.width):
            yield (x, y)
