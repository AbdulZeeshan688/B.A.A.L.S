"""The main game screen: top bar, map, notebook panel, messages, key help."""

from __future__ import annotations

from ...core.clock import DAY_TICKS, time_left_text
from ...core.engine import Game
from ...core.state import Event
from ...core.world import Pos
from .. import keys as K
from ..keys import KeyEvent
from ..renderer import Canvas, wrap
from .base import Screen, key_bar

MAP_X, MAP_Y = 1, 2  # where map tile (0, 0) is drawn
PANEL_X, PANEL_W = 61, 19
MOVES = {K.UP: (0, -1), K.DOWN: (0, 1), K.LEFT: (-1, 0), K.RIGHT: (1, 0)}
WASD = {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}
KIND_STYLE = {"water": "water", "dam": "dam", "wall": "wall", "forest": "forest", "label": "label",
              "object": "object", "door": "door"}
EVENT_STYLE = {"fact": "fact", "rumour": "rumour", "warn": "warn", "important": "bold", "info": ""}
GAME_KEYS = "[WASD/arrows] move [E] talk/use [.] wait [T] skip [N] notes [!] shout [?] help"


def tile_char(game: Game, pos: Pos) -> tuple[str, str]:
    """Static tile appearance, with live door state."""
    world = game.world
    ch = world.char(pos)
    kind = world.kind(pos)
    if kind == "floor":
        return ch, "road" if ch in ".," else ""
    if kind == "door":
        door = game.door_at(pos)
        if door is not None:
            return ("D", "door") if game.door_open(door) else ("x", "locked")
        return ch, "door" if ch == "D" else "locked"
    return ch, KIND_STYLE.get(kind, "")


def draw_map(c: Canvas, game: Game, ghost: bool, flood_rows: int = 0, debug: bool = False) -> None:
    """Draw the town, the ghost trail, NPCs and the player."""
    world, s = game.world, game.state
    for y in range(world.height):
        for x in range(world.width):
            ch, style = tile_char(game, (x, y))
            c.put(MAP_X + x, MAP_Y + y, ch, style)
    if ghost:
        for pos in set(s.ghost):
            if world.is_floor(pos):
                c.put(MAP_X + pos[0], MAP_Y + pos[1], ":", "ghost")
    if debug:
        for npc in game.content.npcs:
            target = s.npcs[npc.id].target
            if target and s.npcs[npc.id].present:
                c.put(MAP_X + target[0], MAP_Y + target[1], "*", "dim")
    for npc in game.content.npcs:
        st = s.npcs[npc.id]
        if st.present:
            c.put(MAP_X + st.pos[0], MAP_Y + st.pos[1], npc.letter, f"npc:{npc.color}")
    c.put(MAP_X + s.player.pos[0], MAP_Y + s.player.pos[1], "@", "player")
    for y in range(min(flood_rows, world.height)):
        for x in range(world.width):
            if world.kind((x, y)) not in ("wall", "dam"):
                c.put(MAP_X + x, MAP_Y + y, "~", "water_hi" if (x + y) % 7 == 0 else "water")


def draw_top_bar(c: Canvas, game: Game, debug: bool) -> None:
    """Loop counter, clock, day progress and time left."""
    s = game.state
    x = c.put(1, 0, "RERUN", "title")
    x = c.put(x + 2, 0, f"loop {s.loop}", "bold")
    x = c.put(x + 3, 0, game.clock(), "bold")
    width = 20
    filled = min(width, s.tick * width // DAY_TICKS)
    late = s.tick >= DAY_TICKS - 30
    x = c.put(x + 2, 0, "[", "dim")
    x = c.put(x, 0, "█" * filled, "bar_late" if late else "bar_fill")
    x = c.put(x, 0, "░" * (width - filled), "dim")
    x = c.put(x, 0, "]", "dim")
    c.put(x + 2, 0, f"FLOOD in {time_left_text(s.tick)}", "warn" if late else "")
    if debug:
        c.put(70, 0, f"t={s.tick}", "dim")


def draw_panel(c: Canvas, game: Game, debug: bool) -> None:
    """Right panel: recent notebook facts, pocket, loop history."""
    s = game.state
    c.box(PANEL_X, 1, PANEL_W, 20, "DEBUG" if debug else "NOTEBOOK", title_style="note")
    inner = PANEL_W - 3
    lines: list[tuple[str, str]] = []
    if debug:
        for npc in game.content.npcs:
            st = s.npcs[npc.id]
            where = game.place_of(npc.id) or "gone"
            lines.append((f"{npc.letter} {where[:10]} {st.trust}", ""))
            if st.rumours:
                lines.append((f"  !{','.join(st.rumours)}", "rumour"))
    else:
        unseen = s.notebook.unseen()
        lines.append((f"! {len(unseen)} new  [N]" if unseen else "[N] open", "note_new" if unseen else "dim"))
        for fact_id in reversed(list(s.notebook.entries)):
            fact = game.content.facts[fact_id]
            style = "note_new" if fact_id in unseen else "note"
            for i, part in enumerate(wrap(fact.short, inner - 2)):
                lines.append((("• " if i == 0 else "  ") + part, style))
        if len(s.notebook.entries) == 0:
            lines.append(("Empty. Talk to", "dim"))
            lines.append(("people. Look at", "dim"))
            lines.append(("things.", "dim"))
    footer = []
    if s.player.items:
        footer.append(("POCKET", "bold"))
        footer += [(f"• {game.content.item_name(i)}"[:inner], "ok") for i in sorted(s.player.items)]
    history = "".join(s.stats.outcomes)
    if history:
        footer.append((f"Loops {history[-(inner - 6):]}", "dim"))
    room = 18 - len(footer)
    for i, (text, style) in enumerate(lines[:room]):
        c.put(PANEL_X + 2, 2 + i, text[:inner], style)
    for i, (text, style) in enumerate(footer):
        c.put(PANEL_X + 2, 2 + room + i, text[:inner], style)


def draw_messages(c: Canvas, log: list[Event]) -> None:
    """Two most recent messages, newest at the bottom."""
    recent = log[-2:]
    for i, event in enumerate(recent):
        y = 22 - (len(recent) - 1 - i)
        older = i < len(recent) - 1
        style = "dim" if older else EVENT_STYLE.get(event.kind, "")
        c.put(1, y, ("> " + event.text)[:78], style)


def draw_game(c: Canvas, app) -> None:
    """Full game screen. Also used as the background for overlays."""
    game: Game = app.game
    debug = app.options.debug
    draw_top_bar(c, game, debug)
    nearby = [f"{n.letter} {n.name}" for n in game.visible_npcs()]
    c.box(0, 1, 60, 20, f"You: {game.region_name()}",
          footer=("Nearby: " + ", ".join(nearby)) if nearby else "Nobody in sight")
    draw_map(c, game, app.settings.ghost, debug=debug)
    draw_panel(c, game, debug)
    draw_messages(c, app.log)
    key_bar(c, 23, GAME_KEYS)


class GameScreen(Screen):
    """Walking around Marrow."""

    def render(self, c: Canvas) -> None:
        draw_game(c, self.app)

    def handle(self, key: KeyEvent) -> None:
        from .dialogue import ChooserScreen
        from .menus import ConfirmScreen, HelpScreen, PromptScreen
        from .notebook import NotebookScreen

        app, game = self.app, self.app.game
        step = MOVES.get(key.name) or (WASD.get(key.char.lower()) if key.name == K.CHAR else None)
        if step:
            game.move(*step)
            app.after_action()
        elif key.name == K.ENTER or key.is_char("e"):
            targets = game.interactables()
            if not targets:
                app.notify("Nobody and nothing within reach. Stand next to someone and press E.")
            elif len(targets) == 1:
                app.interact(targets[0])
            else:
                app.push(ChooserScreen(app, targets))
        elif key.is_char(".", " "):
            game.wait()
            app.after_action()
        elif key.is_char("t"):
            app.push(PromptScreen(app, f"Skip to what time? Now {game.clock()}. Stops early if something happens.",
                                  app.skip_to, placeholder="e.g. 11:00"))
        elif key.is_char("n"):
            app.push(NotebookScreen(app))
        elif key.is_char("g"):
            app.settings.ghost = not app.settings.ghost
            app.notify("Ghost trail " + ("on: ':' marks your path last loop." if app.settings.ghost else "off."))
            app.persist()
        elif key.is_char("!"):
            game.shout()
            app.after_action()
        elif key.is_char("?", "h"):
            app.push(HelpScreen(app))
        elif key.is_char("r"):
            app.push(ConfirmScreen(app, "Give up on this loop and wake at 08:00?", app.restart_loop))
        elif key.is_char("q") or key.name == K.ESC:
            app.push(ConfirmScreen(app, "Save and return to the title screen?", app.to_title))
