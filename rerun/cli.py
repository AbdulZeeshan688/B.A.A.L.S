"""Command line entry point: parse flags, pick a terminal backend, never leave a mess.

Exit codes: 0 ok, 1 unexpected crash (logged), 2 bad content/replay file, 130 Ctrl+C.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from . import __version__
from .app import App, Options
from .core.content import ContentError, load_content
from .extras.replay import ReplayError, load_replay
from .persistence.save import SaveStore, save_dir
from .ui.terminal import PlainIO, TerminalIO
from .ui.theme import Theme, can_encode_unicode


def build_parser() -> argparse.ArgumentParser:
    """All command-line flags."""
    p = argparse.ArgumentParser(prog="rerun", description="RERUN - same town, same afternoon, text only.")
    p.add_argument("--new", action="store_true", help="ignore the saved run and start fresh")
    p.add_argument("--seed", type=int, help="seed for gossip and Kai's wandering (same seed = same day)")
    p.add_argument("--mono", action="store_true", help="no colours")
    p.add_argument("--ascii", action="store_true", help="pure ASCII characters only")
    p.add_argument("--plain", action="store_true", help="line-based input: type keys, then Enter")
    p.add_argument("--reduced-motion", action="store_true", help="no animations")
    p.add_argument("--record", type=Path, metavar="FILE", help="record your key presses to FILE")
    p.add_argument("--replay", type=Path, metavar="FILE", help="play back a recorded FILE (demo mode)")
    p.add_argument("--replay-speed", type=float, default=1.0, help="replay speed multiplier (default 1.0)")
    p.add_argument("--debug", action="store_true", help="show tick counter and NPC targets")
    p.add_argument("--pack", default="marrow", help="story pack to load (default: marrow)")
    p.add_argument("--version", action="version", version=f"rerun {__version__}")
    return p


def _prepare_stdout() -> bool:
    """Try to get a UTF-8 stdout. Returns True if box-drawing characters must be avoided."""
    if hasattr(sys.stdout, "reconfigure") and os.name == "nt":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass
    return not can_encode_unicode(getattr(sys.stdout, "encoding", None))


def write_crash_log() -> Path | None:
    """Save the current traceback to crash.log in the save folder."""
    try:
        directory = save_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "crash.log"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n=== {datetime.now().isoformat(timespec='seconds')} rerun {__version__} ===\n")
            fh.write(traceback.format_exc())
        return path
    except OSError:
        return None


def main(argv: list[str] | None = None) -> int:
    """Run the game. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    if args.record and args.replay:
        print("rerun: use either --record or --replay, not both.", file=sys.stderr)
        return 2
    options = Options(new=args.new, seed=args.seed, mono=args.mono, ascii=args.ascii, plain=args.plain,
                      reduced_motion=args.reduced_motion, record=args.record, replay=args.replay,
                      debug=args.debug, pack=args.pack, replay_delay=0.04 / max(0.1, args.replay_speed))
    replay_keys = []
    if args.replay:
        try:
            options.seed, options.pack, replay_keys = load_replay(args.replay)
        except ReplayError as exc:
            print(f"rerun: {exc}", file=sys.stderr)
            return 2
    try:
        content = load_content(options.pack)
    except ContentError as exc:
        print(f"rerun: the story files are broken - {exc.file}:", file=sys.stderr)
        for problem in exc.problems[:10]:
            print(f"  - {problem}", file=sys.stderr)
        return 2

    force_ascii = _prepare_stdout()
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not options.plain and not interactive:
        print("rerun: no interactive terminal found, switching to --plain mode.")
        options.plain = True
    store = SaveStore()
    app: App | None = None
    try:
        if not options.plain:
            theme = Theme(ascii_only=force_ascii)
            terminal = TerminalIO(theme)
            try:
                terminal.start()
            except Exception as exc:  # raw mode unsupported here: fall back, don't die
                terminal.restore()
                print(f"rerun: raw keyboard input unavailable ({exc}); using --plain mode.")
                options.plain = True
            else:
                try:
                    app = App(options, terminal, store, theme, content, force_ascii)
                    app.replay_keys = replay_keys
                    app.run()
                finally:
                    terminal.restore()
        if options.plain:
            theme = Theme(color=False, ascii_only=True, ansi=False)
            app = App(options, PlainIO(theme), store, theme, content, force_ascii=True)
            app.replay_keys = replay_keys
            app.run()
    except (KeyboardInterrupt, EOFError):
        if app is not None:
            app.persist()
            if app.recorder is not None:
                app.recorder.close()
        print("\nThe water can wait. Your notebook is saved. Bye!")
        return 130
    except Exception:
        if app is not None:
            try:
                app.persist()
            except Exception:
                pass
        log = write_crash_log()
        where = f" Details were written to {log}" if log else ""
        print(f"\nRERUN hit an unexpected error and closed safely. Your notebook is saved.{where}", file=sys.stderr)
        return 1
    if app is not None and app.recorder is not None:
        print(f"Recording saved to {app.recorder.path}")
    print("Thanks for playing RERUN.")
    return 0
