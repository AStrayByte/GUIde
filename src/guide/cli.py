"""The ``guide`` command.

``argparse`` rather than a CLI framework, for the same reason the page has no
build step: the dependency would buy decoration, not capability.

The commands split cleanly in two. ``push``, ``list``, ``read`` and ``clean``
talk to the daemon, starting it if it isn't running. ``wait`` deliberately does
not: it watches ``answers.json`` on disk, so a session that is waiting survives
a daemon restart, a ``guide stop``, or a crash. That redundancy is small and it
is the difference between "your review is still there" and "start again".
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from guide import FORMAT_VERSION, __version__
from guide.client import Client
from guide.daemon import lifecycle
from guide.errors import GuideError
from guide.skill import default_install_dir, install, install_prompt, markdown
from guide.source import describe_environment, fill_source
from guide.store import Store, Summary
from guide.ulid import timestamp_ms

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_TIMEOUT = 3

_WAIT_POLL_SECONDS = 0.25
_SECONDS_PER_DAY = 86_400


# ── push ─────────────────────────────────────────────────────────────────


def cmd_push(args: argparse.Namespace) -> int:
    """Send a batch to the daemon, starting it if necessary."""
    document = _read_document(args.file)
    if isinstance(document, dict):
        document = fill_source(document, label=args.label)

    client = _connect()
    result = client.push(document)
    page = f"{client.url}/?batch={result['id']}"

    if args.json:
        print(json.dumps({**result, "url": page}, indent=2))
    else:
        print(f"  pushed {result['id'][:12]}… · {_count(result['cards'], 'card')}")
        print(f"  {_count(result['waiting'], 'batch', 'batches')} waiting · {page}")

    if args.open:
        webbrowser.open(page)
    return EXIT_OK


# ── wait ─────────────────────────────────────────────────────────────────


def cmd_wait(args: argparse.Namespace) -> int:
    """Block until a batch is marked done, then print its answers.

    Watches the file rather than the daemon. The daemon writes answers
    continuously, so by the time ``complete`` flips, everything is already on
    disk and there is nothing to fetch.
    """
    store = Store()
    batch_id = _resolve_wait_target(store, args.id)
    deadline = time.monotonic() + args.timeout if args.timeout else None

    if not args.quiet:
        title = next((one.title for one in store.summaries() if one.id == batch_id), batch_id)
        print(f"  waiting on {title} ({batch_id[:12]}…)", file=sys.stderr)

    while True:
        answers = store.read_answers(batch_id)
        if answers.get("complete"):
            print(json.dumps(answers, indent=2))
            return EXIT_OK
        if deadline and time.monotonic() > deadline:
            print(
                f"timed out after {args.timeout:g}s — "
                f"{answers['stats']['answered']}/{answers['stats']['total']} answered",
                file=sys.stderr,
            )
            return EXIT_TIMEOUT
        time.sleep(_WAIT_POLL_SECONDS)


def _resolve_wait_target(store: Store, wanted: str | None) -> str:
    """The batch to wait on: the one named, or this session's most recent.

    With several sessions pushing into one inbox, "the most recent batch" is the
    wrong default — it could be someone else's. So an unqualified ``guide wait``
    matches on session id when there is one, and falls back to the working
    directory, which is the next most honest signal about whose batch it is.
    """
    if wanted:
        return store.resolve(wanted)

    environment = describe_environment()
    mine = [summary for summary in store.summaries() if _belongs_to(summary, environment)]
    if not mine:
        raise GuideError(
            "no batch from this session. Pass a batch id, or run `guide list` to "
            "see what is waiting."
        )
    # Prefer something still open; but if the human answered and pressed Done
    # before `wait` even started, the answers are sitting right there and
    # refusing to look at them would be perverse.
    unfinished = [summary for summary in mine if not summary.complete]
    return (unfinished or mine)[-1].id


def _belongs_to(summary: Summary, environment: dict[str, Any]) -> bool:
    """Whether a batch looks like it came from the session asking."""
    session_id = environment.get("session_id")
    if session_id and summary.session_id:
        return summary.session_id == session_id
    return summary.cwd == environment.get("cwd")


# ── list / read ──────────────────────────────────────────────────────────


def cmd_list(args: argparse.Namespace) -> int:
    """Show the inbox."""
    summaries = Store().summaries()
    if not args.all:
        summaries = [summary for summary in summaries if not summary.complete]

    if args.json:
        print(json.dumps([summary.as_dict() for summary in summaries], indent=2))
        return EXIT_OK

    if not summaries:
        print("  nothing waiting")
        return EXIT_OK

    for summary in summaries:
        mark = "✓" if summary.complete else " "
        progress = f"{summary.answered}/{summary.cards}"
        where = summary.repo or "—"
        print(
            f"  {mark} {summary.id[:12]}…  {progress:>7}  "
            f"{where:<16} {summary.label or summary.title}"
        )
    return EXIT_OK


def cmd_read(args: argparse.Namespace) -> int:
    """Print a batch's answers without waiting for it to finish."""
    store = Store()
    print(json.dumps(store.read_answers(store.resolve(args.id)), indent=2))
    return EXIT_OK


# ── open ─────────────────────────────────────────────────────────────────


def cmd_open(args: argparse.Namespace) -> int:
    """Open the inbox in a browser, starting the daemon if necessary."""
    client = _connect()
    target = client.url
    if args.id:
        target = f"{client.url}/?batch={Store().resolve(args.id)}"
    print(f"  {target}")
    webbrowser.open(target)
    return EXIT_OK


# ── clean ────────────────────────────────────────────────────────────────


def cmd_clean(args: argparse.Namespace) -> int:
    """Remove finished batches from the store.

    Deleting rather than archiving is the default because batches may hold real
    client data, and the safe default for data nobody asked to keep is not
    keeping it.
    """
    store = Store()
    doomed = _batches_to_clean(store, args)
    if not doomed:
        print("  nothing to clean")
        return EXIT_OK

    verb = "archive" if args.archive else "delete"
    if not args.yes and not _confirm(f"  {verb} {_count(len(doomed), 'batch', 'batches')}?"):
        print("  cancelled")
        return EXIT_OK

    client = _connect()
    for summary in doomed:
        client.remove(summary.id, archive=args.archive)
    print(f"  {verb}d {_count(len(doomed), 'batch', 'batches')}")
    return EXIT_OK


def _batches_to_clean(store: Store, args: argparse.Namespace) -> list[Summary]:
    """Which batches ``clean`` would remove, given the flags."""
    summaries = store.summaries()
    if args.id:
        wanted = {store.resolve(one) for one in args.id}
        return [summary for summary in summaries if summary.id in wanted]
    if args.all:
        return summaries

    cutoff = time.time() - args.days * _SECONDS_PER_DAY
    return [
        summary for summary in summaries if summary.complete and _last_touched(summary) < cutoff
    ]


def _last_touched(summary: Summary) -> float:
    """When a batch was last written, as a Unix timestamp.

    Age-out is measured from when a batch was *finished*, not when it was
    created — a batch pushed three weeks ago and answered this morning is fresh,
    and deleting it would be a surprise. The creation time in the ULID is the
    fallback for an answers file too old or too broken to carry a timestamp.
    """
    if summary.updated_at:
        try:
            return datetime.fromisoformat(summary.updated_at).timestamp()
        except ValueError:
            pass
    return timestamp_ms(summary.id) / 1000


# ── daemon ───────────────────────────────────────────────────────────────


def cmd_serve(args: argparse.Namespace) -> int:
    """Run the daemon in the foreground."""
    try:
        lifecycle.serve(port=args.port)
    except lifecycle.AlreadyRunning as running:
        # Losing the start-up race is the design working, not a failure.
        print(f"  {running}")
    return EXIT_OK


def cmd_stop(_: argparse.Namespace) -> int:
    """Stop the running daemon."""
    url = lifecycle.stop()
    print(f"  stopped the daemon on {url}" if url else "  no daemon running")
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    """Report whether a daemon is running, and what it holds."""
    # discover() only returns a URL it has already probed, so a second probe
    # would buy nothing on its own. What it does buy is which build is actually
    # running, which is not necessarily the one this CLI came from.
    url = lifecycle.discover()
    daemon_meta = lifecycle.probe(url) if url else None
    store = Store()
    waiting = sum(not summary.complete for summary in store.summaries())

    status = {
        "running": bool(url),
        "url": url,
        "daemon_version": (daemon_meta or {}).get("version"),
        "version": __version__,
        "format_version": FORMAT_VERSION,
        "home": str(store.home),
        "batches": len(store.ids()),
        "waiting": waiting,
    }
    if args.json:
        print(json.dumps(status, indent=2))
        return EXIT_OK

    print(
        f"  daemon    {url} · guide {status['daemon_version']}"
        if url
        else "  daemon    not running"
    )
    print(f"  this cli  {__version__} · format {FORMAT_VERSION}")
    print(f"  home      {store.home}")
    print(f"  batches   {len(store.ids())} stored · {waiting} waiting")
    return EXIT_OK


# ── skill ────────────────────────────────────────────────────────────────


def cmd_skill(args: argparse.Namespace) -> int:
    """Install, print, or explain how to install the Claude Code skill."""
    if args.what == "show":
        print(markdown())
        return EXIT_OK

    if args.what == "prompt":
        print(install_prompt())
        return EXIT_OK

    if args.what == "page":
        client = _connect()
        print(f"  {client.url}/skill")
        webbrowser.open(f"{client.url}/skill")
        return EXIT_OK

    written = install(Path(args.to) if args.to else None)
    print(f"  wrote {written}")
    print("  restart Claude Code, then use /guide")
    return EXIT_OK


# ── plumbing ─────────────────────────────────────────────────────────────


def _connect() -> Client:
    """Reach the daemon, starting it if necessary, and say so exactly once.

    Starting a background process the user did not ask for is convenient and
    slightly rude; the notice makes it only convenient. On stderr, so it never
    pollutes piped JSON. Every command that needs a daemon comes through here so
    the notice cannot be forgotten by the next one.
    """
    client, started = Client.connect()
    if started:
        print(f"  started the guide daemon on {client.url}", file=sys.stderr)
    return client


def _read_document(source: str) -> Any:
    """Load a batch from a path or from stdin when given ``-``."""
    try:
        text = sys.stdin.read() if source == "-" else Path(source).read_text("utf-8")
    except OSError as exc:
        raise GuideError(f"could not read {source}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        where = "stdin" if source == "-" else source
        raise GuideError(f"{where} is not valid JSON: {exc}") from exc


def _count(number: int, singular: str, plural: str | None = None) -> str:
    """``1 card`` / ``17 cards``, because the alternative is ``1 cards``."""
    return f"{number} {singular if number == 1 else plural or singular + 's'}"


def _confirm(question: str) -> bool:
    """Ask before destroying something. Refuses by default when not a terminal."""
    if not sys.stdin.isatty():
        raise GuideError("this deletes batches — pass --yes to confirm non-interactively")
    return input(f"{question} [y/N] ").strip().lower() in {"y", "yes"}


def build_parser() -> argparse.ArgumentParser:
    """The whole command surface, in one place."""
    parser = argparse.ArgumentParser(
        prog="guide",
        description="A local inbox for the questions your agents need answered.",
    )
    parser.add_argument("--version", action="version", version=f"guide {__version__}")
    parser.add_argument(
        "--format-version",
        action="version",
        version=FORMAT_VERSION,
        help="print the batch format version this build speaks, and exit",
    )
    subcommands = parser.add_subparsers(dest="command", required=True, metavar="command")

    push = subcommands.add_parser("push", help="send a batch to the inbox")
    push.add_argument("file", help="a batch JSON file, or - for stdin")
    push.add_argument("--label", help="short name for the inbox rail")
    push.add_argument("--open", action="store_true", help="open the batch in a browser")
    push.add_argument("--json", action="store_true", help="print the result as JSON")
    push.set_defaults(handler=cmd_push)

    wait = subcommands.add_parser("wait", help="block until a batch is done")
    wait.add_argument("id", nargs="?", help="batch id or prefix (default: this session's)")
    wait.add_argument("--timeout", type=float, default=0, help="seconds; 0 means forever")
    wait.add_argument("--quiet", action="store_true", help="no progress notice on stderr")
    wait.set_defaults(handler=cmd_wait)

    listing = subcommands.add_parser("list", help="show the inbox")
    listing.add_argument("--all", action="store_true", help="include finished batches")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(handler=cmd_list)

    read = subcommands.add_parser("read", help="print a batch's answers now")
    read.add_argument("id", help="batch id or prefix")
    read.set_defaults(handler=cmd_read)

    opener = subcommands.add_parser("open", help="open the inbox in a browser")
    opener.add_argument("id", nargs="?", help="jump straight to this batch")
    opener.set_defaults(handler=cmd_open)

    clean = subcommands.add_parser("clean", help="remove finished batches")
    clean.add_argument("id", nargs="*", help="specific batches to remove")
    clean.add_argument("--days", type=int, default=7, help="age-out threshold (default 7)")
    clean.add_argument("--all", action="store_true", help="everything, finished or not")
    clean.add_argument("--archive", action="store_true", help="move to ~/.guide/archive")
    clean.add_argument("--yes", action="store_true", help="do not ask")
    clean.set_defaults(handler=cmd_clean)

    serve = subcommands.add_parser("serve", help="run the daemon in the foreground")
    serve.add_argument("--port", type=int, help="exact port; default scans from 7777")
    serve.set_defaults(handler=cmd_serve)

    subcommands.add_parser("stop", help="stop the daemon").set_defaults(handler=cmd_stop)

    status = subcommands.add_parser("status", help="is anything running, and what's waiting")
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=cmd_status)

    skill = subcommands.add_parser("skill", help="the Claude Code skill")
    skill.add_argument(
        "what",
        nargs="?",
        default="install",
        choices=["install", "show", "prompt", "page"],
        help="install (default), show the file, print a prompt for Claude, or open the page",
    )
    skill.add_argument("--to", help=f"skills directory (default {default_install_dir()})")
    skill.set_defaults(handler=cmd_skill)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Every expected failure is one line and a non-zero exit."""
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except GuideError as exc:
        print(f"guide: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
