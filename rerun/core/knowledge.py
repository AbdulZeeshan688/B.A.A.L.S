"""The notebook: the only thing that survives a loop."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Fact:
    """A piece of knowledge, defined in facts.json."""

    id: str
    source: str
    short: str
    text: str


@dataclass(frozen=True)
class Question:
    """An open question shown while `after` is known and `until` is not."""

    text: str
    after: str | None
    until: str


@dataclass
class Entry:
    """When a fact was learned, and whether the player has looked at it yet."""

    loop: int
    seen: bool = False


@dataclass
class Notebook:
    """Facts the player knows, in the order they were learned."""

    entries: dict[str, Entry] = field(default_factory=dict)

    def knows(self, fact_id: str) -> bool:
        """True if the fact is in the notebook."""
        return fact_id in self.entries

    def learn(self, fact_id: str, loop: int) -> bool:
        """Add a fact. Returns True if it was new."""
        if fact_id in self.entries:
            return False
        self.entries[fact_id] = Entry(loop=loop)
        return True

    def unseen(self) -> list[str]:
        """Facts not yet viewed in the notebook screen."""
        return [f for f, e in self.entries.items() if not e.seen]

    def mark_all_seen(self) -> None:
        """Called when the notebook screen is opened."""
        for entry in self.entries.values():
            entry.seen = True

    def learned_in(self, loop: int) -> list[str]:
        """Facts first learned during a given loop."""
        return [f for f, e in self.entries.items() if e.loop == loop]

    def open_questions(self, questions: list[Question]) -> list[str]:
        """Questions the player can't answer yet."""
        return [q.text for q in questions
                if (q.after is None or self.knows(q.after)) and not self.knows(q.until)]

    def to_dict(self) -> dict:
        """Serialise for the save file."""
        return {f: {"loop": e.loop, "seen": e.seen} for f, e in self.entries.items()}

    @classmethod
    def from_dict(cls, data: dict, valid_ids: set[str]) -> "Notebook":
        """Load from save data, silently dropping facts the content doesn't know."""
        book = cls()
        for fact_id, raw in data.items():
            if fact_id in valid_ids and isinstance(raw, dict) and isinstance(raw.get("loop"), int):
                book.entries[fact_id] = Entry(loop=raw["loop"], seen=bool(raw.get("seen", True)))
        return book
