"""Full notebook: every fact grouped by who told you, plus open questions."""

from __future__ import annotations

from .. import keys as K
from ..keys import KeyEvent
from ..renderer import Canvas, wrap
from .base import Screen, key_bar

VIEW_ROWS = 20


class NotebookScreen(Screen):
    """Scrollable notebook. Opening it marks everything as seen."""

    def __init__(self, app) -> None:
        super().__init__(app)
        notebook = app.game.state.notebook
        self.new = set(notebook.unseen())
        notebook.mark_all_seen()
        self.scroll = 0
        self.lines = self._build()

    def _build(self) -> list[tuple[str, str]]:
        game = self.app.game
        notebook = game.state.notebook
        lines: list[tuple[str, str]] = []
        groups: dict[str, list[str]] = {}
        for fact_id in game.content.facts:  # content order keeps groups stable
            if notebook.knows(fact_id):
                groups.setdefault(game.content.facts[fact_id].source, []).append(fact_id)
        if not groups:
            lines.append(("Nothing yet. Talk to people, look at things, live through a loop.", "dim"))
        for source, fact_ids in groups.items():
            lines.append((source.upper(), "bold"))
            for fact_id in fact_ids:
                fact = game.content.facts[fact_id]
                is_new = fact_id in self.new
                mark = "*" if is_new else "-"
                prefix = f" {mark} L{notebook.entries[fact_id].loop:<2} "
                for i, part in enumerate(wrap(fact.text, 70)):
                    lines.append(((prefix if i == 0 else " " * len(prefix)) + part, "note_new" if is_new else "note"))
            lines.append(("", ""))
        questions = notebook.open_questions(list(game.content.questions))
        if questions:
            lines.append(("OPEN QUESTIONS", "bold"))
            lines += [(f" ? {q}", "") for q in questions]
        return lines

    def render(self, c: Canvas) -> None:
        game = self.app.game
        count = len(game.state.notebook.entries)
        c.box(0, 0, 80, 23, f"NOTEBOOK  ·  loop {game.state.loop}  ·  {count} facts  ·  * = new",
              style="note", title_style="note_new")
        for i, (text, style) in enumerate(self.lines[self.scroll: self.scroll + VIEW_ROWS]):
            c.put(3, 2 + i, text[:75], style)
        if len(self.lines) > VIEW_ROWS:
            c.put(70, 22, f" {self.scroll + 1}-{min(len(self.lines), self.scroll + VIEW_ROWS)}/{len(self.lines)} ", "dim")
        key_bar(c, 23, "[W/S or arrows] scroll  [N/Esc] close")

    def handle(self, key: KeyEvent) -> None:
        max_scroll = max(0, len(self.lines) - VIEW_ROWS)
        if key.name == K.UP or key.is_char("w"):
            self.scroll = max(0, self.scroll - 1)
        elif key.name == K.DOWN or key.is_char("s"):
            self.scroll = min(max_scroll, self.scroll + 1)
        elif key.name in (K.ESC, K.ENTER) or key.is_char("n", "q"):
            self.app.pop()
