"""Conversation overlay and the 'who do you mean?' chooser."""

from __future__ import annotations

from ...core.engine import Target
from .. import keys as K
from ..keys import KeyEvent
from ..renderer import Canvas, wrap
from .base import Screen, key_bar, number_key
from .game import draw_game

BOX_X, BOX_W = 1, 58
TEXT_W = BOX_W - 6


def mood(trust: int) -> str:
    """Trust shown as a word, so colour is never the only signal."""
    if trust >= 60:
        return "warm"
    if trust >= 40:
        return "neutral"
    if trust >= 20:
        return "wary"
    return "cold"


class DialogueScreen(Screen):
    """Talking to one NPC. Options cost no time."""

    overlay = True

    def __init__(self, app, npc_id: str, text: str) -> None:
        super().__init__(app)
        self.npc_id = npc_id
        self.text = text
        self.cursor = 0

    def _options(self) -> list[tuple[str | None, str, bool, bool]]:
        """(topic_id or None for Leave, label, from_notes, already_asked)."""
        game = self.app.game
        opts = [(t.id, t.label, t.from_notes, game.asked(self.npc_id, t.id)) for t in game.topics(self.npc_id)]
        opts.append((None, "Leave", False, False))
        return opts

    def render(self, c: Canvas) -> None:
        draw_game(c, self.app)
        game = self.app.game
        npc = game.content.npc(self.npc_id)
        state = game.state.npcs[self.npc_id]
        options = self._options()
        body = wrap(self.text, TEXT_W)
        height = min(18, len(body) + len(options) + 4)
        title = f"{npc.name.upper()}, {npc.role}, {game.region_name(state.pos)}, {game.clock()}"
        c.box(BOX_X, 2, BOX_W, height, title, style="bold", title_style="title",
              footer=f"mood: {mood(state.trust)}")
        y = 3
        for line in body[: height - len(options) - 4]:
            c.put(BOX_X + 2, y, line, "")
            y += 1
        y += 1
        for i, (_, label, from_notes, asked) in enumerate(options):
            selected = i == self.cursor
            style = "select" if selected else ("dim" if asked else "")
            c.put(BOX_X + 3, y, f"{i + 1}) {label}"[: TEXT_W - 12], style)
            if from_notes:
                c.put(BOX_X + BOX_W - 15, y, "[from notes]", "note_new")
            y += 1
        c.fill(0, 23, 80, 1)
        key_bar(c, 23, "[1-9] choose  [W/S or arrows] select  [Enter] confirm  [Esc] leave")

    def handle(self, key: KeyEvent) -> None:
        options = self._options()
        num = number_key(key)
        if key.name in (K.ESC,) or key.is_char("q", "0"):
            self.app.pop()
            return
        if key.name == K.UP or key.is_char("w"):
            self.cursor = (self.cursor - 1) % len(options)
            return
        if key.name == K.DOWN or key.is_char("s"):
            self.cursor = (self.cursor + 1) % len(options)
            return
        if num is not None and num <= len(options):
            self.cursor = num - 1
        elif key.name != K.ENTER and not key.is_char("e"):
            return
        topic_id = options[self.cursor][0]
        if topic_id is None:
            self.app.pop()
            return
        self.text = self.app.game.choose(self.npc_id, topic_id)
        self.app.collect_events()
        self.cursor = min(self.cursor, len(self._options()) - 1)
        if self.app.game.state.outcome:
            self.app.pop()
            self.app.after_action()


class ChooserScreen(Screen):
    """Several people/things in reach: pick one."""

    overlay = True

    def __init__(self, app, targets: list[Target]) -> None:
        super().__init__(app)
        self.targets = targets

    def render(self, c: Canvas) -> None:
        draw_game(c, self.app)
        h = len(self.targets) + 3
        c.box(16, 6, 30, h, "Who or what?", style="bold")
        for i, t in enumerate(self.targets):
            c.put(18, 7 + i, f"{i + 1}) {t.name}")
        c.fill(0, 23, 80, 1)
        key_bar(c, 23, "[1-9] choose  [Esc] cancel")

    def handle(self, key: KeyEvent) -> None:
        num = number_key(key)
        if key.name == K.ESC or key.is_char("q"):
            self.app.pop()
        elif num is not None and num <= len(self.targets):
            self.app.pop()
            self.app.interact(self.targets[num - 1])
