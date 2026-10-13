# RERUN

**Same town. Same afternoon. Text only.**

A time-loop mystery you play in the terminal. At 08:00 you step off the bus in the small town of
Marrow. At 14:00 the dam breaks and the town floods. Then it's 08:00 again.

You keep nothing between loops except your **notebook**: the facts you learned. Everyone in town
follows the same schedule every day, and everyone knows something. Dialogue options appear only when
your notebook holds the fact that unlocks them. **Knowledge is the only progression.**

```
 RERUN  loop 3   09:04  [███░░░░░░░░░░░░░░░░░]  FLOOD in 4h 56m
┌─ You: the Market Square ─────────────────────────────────┐ ┌─ NOTEBOOK ──────┐
│┌─ TOMAS, barman, the Market Square, 09:04 ──────────────┐│ │ ! 6 new  [N]    │
││ "We're closed. I've got a bus to catch."               ││ │ • Mayor: 'safe' │
││                                                        ││ │ • Key: Tomas has│
││  1) Ask about the dam                                  ││ │   it            │
││  2) "Where are you going?"                             ││ │ • Valve needs a │
││  3) "Oskar's key, for his bar tab."      [from notes]  ││ │   key           │
││  4) Leave                                              ││ │ • Dam breaks    │
││                                                        ││ │   14:00         │
│└─ mood: neutral ────────────────────────────────────────┘│ │ • Gauge 9.4m >  │
│  |&      |  |  CAFE  |  | PHARMACY |  | TOWN HALL |      │ │   red           │
│  |    BAR|  |        |  |  I::     |  |        M  |      │ │ • Gauge 8.7m,   │
│  +---x---+  +---D----+  +----D-----+  +-----D-----+      │ │   rising        │
│  , , T@, , , :::V::::::::::::: , , , , , , , , , , , ,   │ │                 │
│  , , , , , , : MARKET SQUARE , , , , , , , , , , , , ,   │ │                 │
│  , , , , , , : , , , , , , , , , , , , , , , , , , , ,   │ │                 │
│  . . . . . . : . . . . . . . . . : . . . . . . . . . . . │ │                 │
│  +----------+:                   :[B] BUS STOP           │ │                 │
│  |  INN     D:::::::::::::::::::::                       │ │ Loops ~~        │
└─ Nearby: T Tomas ────────────────────────────────────────┘ └─────────────────┘
 > Vera comes into view.
```
*(`:` is your ghost trail from the previous loop. `x` is a door that's locked right now.)*

---

## Run it

You only need **Python 3.10+**. There's nothing to install and no internet connection is needed.

```bash
git clone <this repo> && cd rerun-game
python -m rerun                # macOS / Linux / Windows Terminal / PowerShell
```

You can also install it as a command with `pipx install .`, then run `rerun`.

| Flag | What it does |
|---|---|
| `--new` | ignore the saved run and start fresh |
| `--daily` | today's daily challenge: same seed for everyone, never touches your save |
| `--seed N` | fix the day's randomness (gossip, Kai's running around) |
| `--mono` / `--ascii` | no colours / pure ASCII characters (`NO_COLOR` is respected too) |
| `--plain` | line mode: type keys, then Enter. Works in any console |
| `--reduced-motion` | no animations |
| `--record FILE` / `--replay FILE` | record your key presses, or play them back |
| `--replay-speed X` | faster or slower playback |
| `--debug` | tick counter, NPC targets, trust and rumours |

**Demo:** `python -m rerun --replay demo.rec` plays a full solve (flood, flood, saved) in about 60 seconds.

## Controls

| Key | Action | Time |
|---|---|---|
| `W A S D` / arrows | move | 2 min |
| `E` / Enter | talk to, or use, whatever is next to you | 2 min |
| `1`–`9` | pick a dialogue option | free |
| `.` / space | wait | 2 min |
| `T` | skip to a time (stops early if something happens) | — |
| `N` | notebook: every fact, who told you, open questions | free |
| `G` | toggle the ghost trail of your last loop | free |
| `!` | shout a warning (careful: it causes panic) | 2 min |
| `R` / `Q` | restart the loop / save and quit | — |

Every screen shows its own keys on the bottom line.

## How it plays

- **6 townspeople, 6 schedules.** Vera the dam engineer, Tomas the barman (who leaves on the 10:20
  bus), Ilse the pharmacist, the Mayor, Kai the kid and Mari the assistant. They walk around town
  using pathfinding, on the same timetable every loop.
- **12 facts, gated dialogue.** You can't convince Vera without a gauge reading. You can't ask Ilse
  about her father until you know why it matters. Options unlocked by your notebook are marked
  `[from notes]`.
- **Two ways to win.** The honest way: reach Tomas before his bus. The sneaky way: slip in through
  the bar's back door after he leaves. If anyone sees you, a **rumour** starts, and rumours spread
  from person to person. If it reaches Vera, she won't take help from a thief.
- **Trust.** Pester people and they stop listening. Shout "the dam will break!" near the Mayor and
  you're arrested.
- Expect a first solve to take 3–5 loops. The share line at the end has no spoilers:
  `RERUN #4821  SAVED in 4 loops  ~~^*`

## Business model

| | |
|---|---|
| **Free** | The town of Marrow, plus a daily challenge (`--daily`, same day for everyone) |
| **One-time unlock (~€5, price to be tested)** | Unlimited seeds, all towns, replays |
| **Story packs (~€2–3 each, estimate)** | New towns and disasters: ski-resort avalanche, lighthouse storm, space-station leak |
| **Distribution** | itch.io first (it handles payments, no servers needed). Free version on GitHub / pipx |
| **Growth** | Spoiler-free share lines, Wordle-style |

**Why packs are cheap to make:** a whole town is just a map, schedules, dialogue and facts in plain
data files (`rerun/content/marrow/`). The engine doesn't change. The content loader validates every
reference, so a broken pack fails with a clear message instead of a crash.

**Audience (an assumption, not yet verified):** fans of loop and deduction games (Outer Wilds, Return
of the Obra Dinn, Twelve Minutes, Majora's Mask), and developers and students who live in the terminal.
**How we'll validate it:** one weekend on itch.io with a free demo, measuring day-2 return rate, shares
and purchases. We use no made-up market numbers.

## Technical overview

```
rerun/
  core/         pure game logic, no UI imports: clock, world (BFS pathfinding, line of sight),
                NPC schedules, data-driven conditions & dialogue, rumours, loop rules, engine
  content/      story packs as data: map.txt + world/npcs/dialogue/facts JSON
  ui/           own terminal layer (no curses): termios on Unix, msvcrt + VT mode on Windows,
                frame-diff renderer, screens (title, game, dialogue, notebook, flood, win, help…)
  persistence/  versioned save file with atomic writes and corruption recovery
  extras/       share line, record/replay
  solver/       a bot that plays the real game by pressing keys
```

- **Standard library only.** It runs anywhere Python runs, with no curses dependency on Windows.
- **Deterministic.** A seeded RNG per loop means the same seed and the same keys always give the same
  game. Replays and tests rely on this.
- **Reliability.**
  - The terminal is always restored: `try/finally`, `atexit` and a SIGTERM handler.
  - Ctrl+C saves and exits cleanly.
  - A corrupt save is moved aside to `save.json.bad`.
  - Unexpected errors are written to `crash.log` with a friendly message.
  - A window smaller than 80×24 gets a resize screen, and the game resumes by itself.
  - Without a TTY, the game falls back to `--plain` automatically.
  - It never writes outside `~/.rerun` (`%APPDATA%\rerun` on Windows).
- **Proven winnable.** `python -m rerun.solver.bot --route honest|sneaky` plays through the real input
  path and wins.

## Tests

```bash
pip install pytest && python -m pytest
```

There are 116 tests:
- the clock and NPC schedules (Tomas is at the bus stop at 10:18 and gone at 10:22)
- dialogue gating, loop resets, rumours and arrests
- save recovery from corrupt, empty or old-version files
- key parsing for both Unix and Windows
- content validation
- headless UI flows
- record/replay equality
- the solver winning both routes on several seeds
- a **fuzz test**: 10,000 random key presses across every screen with no crash, plus a determinism check

---

Built in 48 hours for the **B.A.L.L.S. 2026** hackathon.
