# RERUN — Full Build Spec

> Read this whole file before writing code. Build in the phases at the bottom, in order.
> After each phase: run the game, run the tests, commit. Never leave the repo broken.

## 0. Context

This is for the **B.A.L.L.S. 2026 hackathon**.

- Challenge: a **terminal-based, monetizable ASCII art game**. No theme.
- Must run in a terminal on **macOS, Linux and Windows** (Windows Terminal / PowerShell).
- All graphics are ASCII/text.
- **Code deadline: Wed 14 Oct 2026, 12:00 noon** — public GitHub repo. Target finishing by 11:00.
- Pitch: Thu 15 Oct, 7 min + 2 min Q&A.

Judging criteria (treat all as requirements):
1. Monetization and market potential
2. Creativity and originality
3. Pitch and presentation
4. Code quality and structure
5. Error handling and reliability
6. Creative use of ASCII art
7. Game functionality and technical complexity
8. Answers to judges' questions

**Priority order when time is short:** a game that never crashes > a game you can win > pretty visuals > extra features.

---

## 1. The game in one paragraph

**RERUN** — *Same town. Same afternoon. Text only.*

You arrive in the small town of **Marrow** at 08:00. At 14:00 the dam breaks and the town floods. Then the day resets to 08:00. You keep nothing between loops except your **notebook** — the facts you learned. Every townsperson follows a fixed daily schedule and knows something. Some dialogue options only appear once your notebook has the fact that unlocks them. You win by finding the chain of actions that stops the flood. Fewer loops = better score.

The core idea: **knowledge is the only progression.**

---

## 2. Hard rules for the code

- **Python 3.10+, standard library only.** No pip dependencies for the game itself. (`pytest` is allowed for tests only.)
- Do **not** use `curses` (it is not built into Python on Windows). Write a small terminal layer instead (see §8).
- **No network calls. No AI APIs. No accounts.** Fully offline.
- The game must **never write anywhere except its own save folder**.
- The game must **always restore the terminal** (cursor, echo, raw mode) on exit, on crash, and on Ctrl+C.
- All randomness goes through **one seeded RNG object**. Same seed + same key inputs = identical game.
- Game logic must not import UI code. UI reads game state and draws it.
- Use `dataclasses` and type hints. Keep functions short. Docstrings on public functions.
- Content (map, NPCs, dialogue, facts) lives in **data files**, not hard-coded in logic. This matters for the business pitch ("story packs").

---

## 3. Time and the loop

- One loop = **08:00 to 14:00**.
- **Turn-based.** Time only moves when the player acts. Every action = **1 tick = 2 game minutes**. So one loop = 180 ticks.
  - Moving one tile = 1 tick.
  - Talking (opening a conversation) = 1 tick. Choosing options inside a conversation = 0 ticks.
  - Inspecting an object = 1 tick.
  - Waiting (`.` key) = 1 tick.
- **Skip time** (`T` key): player types a target time (e.g. `09:30`). The game advances tick by tick and **stops early** if an NPC enters the player's view or something important happens. Must be impossible to skip past 14:00 without the flood playing.
- At 14:00, if the flood was not stopped: play the **flood animation**, show the "LOOP ENDED" summary (new notebook entries this loop), then reset the world to 08:00. Loop counter +1.
- `R` restarts the current loop early (with a confirm prompt).
- Everything resets each loop (NPC positions, items, trust, doors) **except the notebook and stats**.

---

## 4. The town of Marrow (MVP: one hand-authored town)

Map is about **58 × 18** tiles so it fits next to a side panel in an 80×24 terminal. Sketch (adjust widths so every row is equal length):

```
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
~~~~~~~~~~~~~~~~~~~~ RESERVOIR ~~~~~~~~~~~~~~~~~~~~~~~~~~~
==========================##=============================
 g      +--------+      |  |          ^^^^^^^^^^^^^^^^^^
        | VALVE  |      |  |          ^^  FOREST  ^^^^^^
        |  HUT   |      |  |          ^^^^^^^^^^^^^^^^^^
        +---D----+      |  |       +------+
  . . . . . . . . . . . .  . . . . | MILL |  . . . . . .
  +-------+   +---------+   +------+--x---+   +--------+
  |  BAR  x   |  CAFE   |   | PHARMACY    |   |  TOWN  |
  |       D   |         |   |             |   |  HALL  |
  +---D---+   +----D----+   +------D------+   +---D----+
  , , , , , , , , , , , , , , , , , , , , , , , , , , ,
  , , , , , , ,  MARKET SQUARE  , , , , , , , , , , , ,
  , , , , , , , , , , , , , , , , , , , , , , , , , , ,
  . . . . . . . . . . . . . . . . . . . . . . . . . . . .
  +----------+                       BUS STOP [B]
  |  INN     D
```

Legend:
| Char | Meaning |
|---|---|
| `@` | player |
| `~` | water |
| `=` / `#` | dam wall |
| `+ - \|` | building walls |
| `D` | door (open) |
| `x` | locked door / back door |
| `g` | water gauge (inspectable) |
| `.` `,` | road / square (walkable) |
| `^` | forest (not walkable) |
| `[B]` | bus stop |
| Capital letter | an NPC (see §5) |
| `:` | ghost trail (your path last loop, toggle with `G`) |

Building interiors are walkable floor. Locations are named regions (rectangles) so the UI can say "You: Market Square".

There must be a `--ascii` mode where any non-ASCII character is replaced. (The default map above is already pure ASCII, keep it that way.)

---

## 5. Characters

Six NPCs for the MVP. Each has: a letter, a name, a role, a **schedule** (list of `time -> location`), a list of **facts they can give**, and **dialogue topics** (some gated by facts).

NPCs walk between scheduled locations using simple pathfinding (BFS on the tile grid is fine). They move 1 tile per tick. When they reach a scheduled spot they wait there.

| Letter | Name | Role | Schedule |
|---|---|---|---|
| `V` | Vera | Dam engineer | 08:00 Inn → 09:00 Cafe → 12:00 Town Hall → 13:00 Cafe |
| `T` | Tomas | Barman | 08:00 Bar → 10:00 walks to Bus Stop, **leaves town at 10:20** (disappears) |
| `I` | Ilse | Pharmacist, daughter of the old dam keeper | 08:00 Pharmacy (all day) → 12:30 Market Square → 13:00 Pharmacy |
| `M` | Mayor Halden | Mayor, red herring | 08:00 Town Hall → 11:00 Market Square (speech) → 12:00 Town Hall |
| `K` | Kai | Kid who runs everywhere | Wanders between Square, Mill, Bar on a loop every 20 min |
| `O` | Mari | Vera's assistant | 08:00 Valve Hut → 11:00 Cafe → 11:30 Valve Hut |

### The solution chain (the puzzle)

The flood is stopped only if **Vera is inside the Valve Hut with the valve key before 13:50**. She will only go there if she believes you. A first-time player cannot know any of this.

Facts (IDs in code, text in data files):

| Fact ID | How you get it | What it unlocks |
|---|---|---|
| `gauge_reading` | Inspect the gauge `g` after 11:00. Text: "Water at 9.4 m. Red line is 9.0 m." | Topic with Vera: "The gauge reads 9.4 m." |
| `valve_exists` | Vera tells you, **only after** you show `gauge_reading`: "If that's true, only the relief valve can save us. But the key went missing with old Oskar." | Topic with Ilse: "Ask about your father, Oskar." |
| `key_with_tomas` | Ilse, once you ask about Oskar: "Dad gave the spare key to Tomas to cover his bar tab." | Topic with Tomas: "Oskar's key, for his bar tab." |
| `tomas_leaves` | Kai tells you anytime: "Tomas is getting the 10:20 bus. He's leaving for good." | Nothing directly, but warns the player about timing |
| `back_door` | Kai, if you talk to him **at the Mill**: "The bar's back door doesn't lock when Tomas is gone." | Lets the player open the bar back door `x` after 10:20 |
| `mayor_lie` | Mayor's speech at 11:00: "The dam was inspected last spring. Totally safe." Red herring. | Nothing. Flavour only |

Winning paths (both must work and be tested):

1. **Honest route.** Loop with the knowledge: get the key from **Tomas before 10:20** by using the "bar tab" topic → take it to Vera → show `gauge_reading` (requires being after 11:00 to have inspected it this loop *or* already knowing the fact from an earlier loop — knowledge carries over, so the topic is available any time) → Vera walks to the Valve Hut → if she arrives before 13:50, **win**.
2. **Sneaky route.** Miss Tomas, then after 10:20 enter the bar through the back door (needs `back_door` fact), take the key from the shelf. **Risk:** if Kai or any NPC sees you go in (NPC within 4 tiles with line of sight), a **rumour** starts (see §6). If the rumour reaches Vera before you talk to her, she refuses: "I don't take help from thieves." That loop is then lost unless the player works around it.

Expected first-time solve: 3–5 loops.

Trust: each NPC has a `trust` value (0–100, starts at 50, resets each loop). Gifts or helpful facts raise it, being seen stealing or annoying them (talking >3 times in a loop) lowers it. Vera needs trust ≥ 40 to act. Keep this simple.

---

## 6. Rumours (the emergent bit)

- Some actions are **visible**: entering a locked/back door, picking up an item that isn't yours, shouting a warning in the square.
- If an NPC witnesses one, they get a rumour: `{about: "player", type: "thief", tick: n}`.
- When two NPCs are on the same or adjacent tile, each rumour has a **seeded 50% chance** to spread.
- Effects: Vera with a `thief` rumour refuses to help. Mayor with a `panic` rumour (from shouting) calls the guard and you are **arrested** — the loop ends early.
- Show this to the player: when a rumour spreads in view, a short message line appears ("Kai whispers something to Vera.").

This is a small system but it makes each loop feel alive. Don't overbuild it.

---

## 7. Screens and UI

Target size: **80 × 24 minimum**. If smaller, show a "Please make the window at least 80×24 (now: 70×20)" screen that re-checks size and resumes automatically.

### Main game screen

```
 RERUN   loop 3        09:42  [######.........]  FLOOD in 4h 18m
+----------------------------------------------------------+ +-NOTEBOOK-----+
|                     (map, 58 x 18)                       | | ! 2 new      |
|                                                          | | Gauge 9.4 m  |
|                                                          | | Valve needs  |
|                                                          | |  the key     |
|                                                          | | Key: Tomas   |
|                                                          | |              |
+----------------------------------------------------------+ +--------------+
 You: Market Square.   Nearby: V Vera, K Kai
 > Kai whispers something to Vera.
 [arrows/WASD] move [E] talk/use [.] wait [T] skip [N] notebook [G] ghost [?]
```

- Top bar: loop number, clock, a progress bar of the day, time left.
- Right panel: last few notebook facts (short form). Hidden in compact mode.
- Bottom: location, nearby NPCs with names, one message line, key help.
- **Every screen shows its own keys at the bottom.**

### Dialogue box (overlays the map)

```
+-- TOMAS, the Bar, 09:30 ---------------------------------+
| "We're closed. I've got a bus to catch."                 |
|                                                          |
|   1) Ask about the dam                                   |
|   2) "Oskar's key, for his bar tab."       [from notes]  |
|   3) Leave                                               |
+----------------------------------------------------------+
```

Options unlocked by a fact are marked `[from notes]`, so the player feels the knowledge working.

### Notebook screen (`N`)

Full list of facts, grouped by person, with the loop they were learned in. New ones marked `*`. Plus an "Open questions" section driven by data (e.g. "Who has the valve key?" disappears once `key_with_tomas` is known).

### Flood animation

At 14:00: water `~` fills the map from the dam downward, row by row, over about 2 seconds. Then:

```
            14:00 — THE DAM BROKE
            Loop 3 ended.
            New in your notebook: 2
            [Enter] start loop 4
```

Respect `--reduced-motion` (skip the animation, show the final frame).

### Win screen + share card

```
   THE VALVE OPENS. MARROW IS SAFE.

   Loops: 4    In-game time used: 22h 40m    Rumours started: 1

   Share:  RERUN #4821  SAVED in 4 loops  ~~~^^~^  (no spoilers)
```

The share line is plain text the player can copy. The little symbol string encodes each loop's outcome (`~` flooded, `^` arrested, `*` saved), never the solution.

### Title screen

Big ASCII logo "RERUN", menu: Continue / New game / How to play / Settings / Quit.

### Colours

Use ANSI colours (water blue, NPCs bold, notebook yellow). **Colour is never the only signal.** Respect the `NO_COLOR` env var and a `--mono` flag.

---

## 8. Architecture

```
rerun/
  __main__.py          # entry: python -m rerun
  cli.py               # argparse flags, then starts the app
  app.py               # main loop: read input -> update state -> render
  core/
    rng.py             # one seeded RNG wrapper
    clock.py           # ticks <-> "HH:MM", day length
    world.py           # tile grid, regions, walkability
    npc.py             # NPC dataclass, schedule following, pathfinding
    player.py
    knowledge.py       # notebook: facts, learned_in_loop, new flags
    dialogue.py        # topics, gating by facts/trust/time, effects
    rumours.py
    loop.py            # reset rules, end-of-loop, win/lose checks
    state.py           # GameState dataclass that holds everything
  content/
    marrow/
      map.txt          # the ASCII map
      npcs.json        # schedules, letters, names
      dialogue.json    # topics, required facts, effects
      facts.json       # id -> short text, long text
  ui/
    terminal.py        # enter/exit raw mode, ANSI, size, cleanup
    input_unix.py      # termios/tty key reading
    input_windows.py   # msvcrt key reading, enable VT mode
    keys.py            # normalise to KeyEvent (UP, DOWN, ENTER, CHAR 'e', ...)
    renderer.py        # frame buffer; only redraw changed lines
    screens/           # title, game, dialogue, notebook, flood, win, resize, help
    theme.py           # colours, mono, ascii replacements
  persistence/
    save.py            # load/save JSON, atomic write, versioning, recovery
  extras/
    share.py           # share card string
    replay.py          # record and play back key inputs
  solver/
    bot.py             # plays the game automatically to prove it's winnable
tests/
README.md
```

### Terminal layer (important for Windows)

- Unix: `termios` + `tty.setcbreak`, read with `os.read`, parse escape sequences for arrow keys.
- Windows: `msvcrt.getwch()`, arrow keys arrive as a prefix (`\xe0` or `\x00`) plus a code. Enable ANSI with `os.system("")` or the `SetConsoleMode` VT flag via `ctypes`.
- Hide cursor on start, show on exit. Use the alternate screen buffer (`\x1b[?1049h` / `\x1b[?1049l`).
- Cleanup through `try/finally` in `app.py`, plus `atexit`, plus a `SIGINT`/`SIGTERM` handler on Unix.
- Terminal size: `shutil.get_terminal_size()` checked every frame.
- **Fallback `--plain` mode:** if raw input fails, fall back to line input (type `w`, `a`, `e`, etc. then Enter). Game must still be fully playable.

### Determinism

- `GameState` + seed + list of key inputs fully determines the game.
- `replay.py` records every key with its tick to a file (`--record file`) and plays it back (`--replay file`). Used for tests **and** as the live-demo backup.

### Save file

- Location: `~/.rerun/save.json` on mac/Linux, `%APPDATA%\rerun\save.json` on Windows.
- Contents: `version`, notebook facts with loop learned, loop count, stats, settings, best score.
- Save at every loop boundary and on quit.
- Atomic write: write to `save.json.tmp`, then `os.replace`.
- If the file is missing → new game. If it's corrupt or wrong version → rename to `save.json.bad`, start fresh, show a one-line message. **Never crash on a bad save.**

### CLI flags

```
python -m rerun                 # normal play
  --new                         # ignore save, start fresh
  --seed N                      # seed for rumour chances, Kai's wandering, etc.
  --mono                        # no colours
  --ascii                       # pure ASCII characters only
  --plain                       # line-based input fallback
  --reduced-motion              # no animations
  --record FILE / --replay FILE # record or play back inputs
  --debug                       # show tick number and NPC targets
```

---

## 9. Error handling checklist

- Unknown keys: ignored silently.
- Invalid skip-time input (`25:99`, `abc`, a time in the past): message line, no crash.
- Terminal too small: resize screen, auto-resume.
- Missing or broken content file: clear error message naming the file, clean exit, terminal restored.
- Corrupt save: see §8.
- Ctrl+C anywhere: save, restore terminal, exit with a short goodbye line.
- Any unexpected exception: restore terminal, write the traceback to `~/.rerun/crash.log`, print one friendly line telling the player where the log is.

---

## 10. Solver bot and tests

### Solver (`solver/bot.py`)

A scripted player that knows the solution chain and plays it through the real game engine (same code path as a human, just feeding keys). It must win the **honest route** and the **sneaky route**. This proves the content is winnable and is a strong talking point for judges.

### Tests (pytest)

- `test_clock.py`: tick ↔ time conversion, day ends at 14:00.
- `test_npc_schedule.py`: Tomas is at the bus stop at 10:18 and gone at 10:22. Vera reaches the Cafe by 09:15.
- `test_dialogue_gating.py`: Tomas's key topic is hidden without `key_with_tomas` and shown with it.
- `test_loop_reset.py`: after reset, items and NPCs reset, notebook does not.
- `test_rumours.py`: with a fixed seed, a witnessed break-in reaches Vera and blocks her help.
- `test_save.py`: round trip, corrupt file, empty file, old version.
- `test_determinism.py`: same seed + same inputs twice → identical final state.
- `test_solver.py`: both routes win; a do-nothing player floods every loop.
- `test_keys.py`: escape sequences and Windows key codes map to the right `KeyEvent`.

---

## 11. Business model (for README and pitch, not code)

Put a short version in the README.

- **Free:** the Marrow town + a daily challenge (same seed for everyone each day).
- **Paid, one-time (~€5, an estimate to test):** unlimited seeds, all towns, replays.
- **Story packs (~€2–3 each, estimate):** new towns and disasters, e.g. a ski resort avalanche, a lighthouse storm, a space station leak. Content is data files, so packs are cheap to make.
- **Distribution:** itch.io first (handles payments, no servers). Free version on GitHub / pipx.
- **Growth:** the spoiler-free share line, like Wordle results.
- **Audience (assumption, not verified):** fans of loop and deduction games (Outer Wilds, Obra Dinn, Twelve Minutes, Majora's Mask), plus developers and students who live in the terminal.
- **Validation plan:** one weekend on itch.io with a free demo; measure day-2 returns, shares and purchases.
- No made-up market numbers anywhere.

---

## 12. Build phases (do them in order)

**Phase 1 — Walkable town (target 3 h)**
Terminal layer on Unix and Windows, map loads from `map.txt`, player moves, clock advances per move, 6 NPCs follow schedules, terminal always restored.
*Done when:* you can walk around Marrow and watch Tomas leave on the 10:20 bus.

**Phase 2 — The loop and the notebook (target 5 h) — THIS IS THE MVP**
Talk/inspect, dialogue with fact gating, notebook screen, 14:00 reset, the honest-route win, win screen.
*Done when:* a fresh player can win from a new game. **If time runs out after this phase, it is still a complete, submittable game.**

**Phase 3 — Look and feel (target 3 h)**
Final layout, side panel, flood animation, ghost trail, colours, `--mono`, `--ascii`, resize screen, title screen, help screen.

**Phase 4 — Depth and saving (target 4 h)**
Rumours, sneaky route, trust, arrest, save/load with recovery, share card, stats.

**Phase 5 — Reliability and release (target 3 h)**
Solver bot, all tests passing, `--record`/`--replay`, `--plain` fallback, crash log, README with install + screenshots-as-text + business summary, test a fresh clone on macOS and Windows. `pyproject.toml` so `pipx install .` works and adds a `rerun` command.

**Stretch only if everything above is done:** daily seed mode, a second town as a data-only "pack" to prove the pack system, bell sound with `--sound`.

**Out of scope (future work, mention in pitch only):** multiplayer, online leaderboards, town editor, Steam build.

---

## 13. Acceptance tests (the definition of done)

1. Fresh clone → `python -m rerun` works on macOS/Linux and Windows with no installs.
2. A new player can win; both routes are winnable.
3. `pytest` passes, including the solver.
4. Same seed + same recorded inputs → same result.
5. Ctrl+C at any screen leaves the terminal fully usable.
6. A corrupt save file does not crash the game.
7. Shrinking below 80×24 shows the resize screen and recovers.
8. `--mono`, `--ascii` and `--plain` are fully playable.
9. Nothing is written outside the save folder.
10. README explains install, controls, and the business idea in under one screen each.

---

## 14. Demo script (for the replay file)

Record this with `--record demo.rec` once the game works:

1. Loop 1: walk to the gauge, skip to 11:00, inspect it (fact). Skip to 14:00 → flood animation.
2. Loop 2: talk to Vera with the gauge fact → learn about the valve. Talk to Ilse → learn Tomas has the key. Too late for Tomas; flood.
3. Loop 3: go straight to Tomas at 08:10, use the new "bar tab" option, get the key, bring it to Vera, she walks to the hut → valve opens → win screen and share line.

The whole run should take 60–90 seconds of real time.
