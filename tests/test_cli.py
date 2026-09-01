"""Pins the CLI's disk-facing commands: exit codes and stdout/stderr, no daemon involved."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pytest

from conftest import make_batch
from guide import cli
from guide.errors import GuideError
from guide.skill import install_prompt, markdown
from guide.source import describe_environment
from guide.store import Store, Summary
from guide.ulid import new_ulid


def test_list_on_an_empty_store_prints_nothing_waiting(
    guide_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = cli.main(["list"])
    captured = capsys.readouterr()
    assert exit_code == cli.EXIT_OK
    assert "nothing waiting" in captured.out


def test_list_json_on_an_empty_store_prints_an_empty_array(
    guide_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = cli.main(["list", "--json"])
    captured = capsys.readouterr()
    assert exit_code == cli.EXIT_OK
    assert json.loads(captured.out) == []


def test_read_prints_the_answers_for_a_resolved_batch(
    store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    stored = store.create(make_batch())

    exit_code = cli.main(["read", stored["id"][:8]])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_OK
    assert json.loads(captured.out)["batch_id"] == stored["id"]


def test_status_json_reports_no_daemon_and_the_store_home(
    store: Store,
    guide_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli.lifecycle, "discover", lambda: None)
    store.create(make_batch())

    exit_code = cli.main(["status", "--json"])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_OK
    status = json.loads(captured.out)
    assert status["running"] is False
    assert status["home"] == str(guide_home)
    assert status["batches"] == 1
    assert status["waiting"] == 1


def test_skill_show_prints_the_installed_skill_markdown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(["skill", "show"])
    captured = capsys.readouterr()
    assert exit_code == cli.EXIT_OK
    assert captured.out == markdown() + "\n"


def test_skill_prompt_prints_the_install_prompt(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(["skill", "prompt"])
    captured = capsys.readouterr()
    assert exit_code == cli.EXIT_OK
    assert captured.out == install_prompt() + "\n"


def test_skill_install_writes_the_file_to_the_given_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target_dir = tmp_path / "skills"

    exit_code = cli.main(["skill", "install", "--to", str(target_dir)])
    captured = capsys.readouterr()

    written = target_dir / "SKILL.md"
    assert exit_code == cli.EXIT_OK
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == markdown()
    assert str(written) in captured.out


def test_wait_on_an_incomplete_batch_times_out_with_exit_code_3(
    store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    stored = store.create(make_batch())

    exit_code = cli.main(["wait", stored["id"], "--timeout", "0.5", "--quiet"])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_TIMEOUT
    assert "timed out" in captured.err


def test_wait_on_a_complete_batch_prints_the_answers_and_returns_0(
    store: Store, capsys: pytest.CaptureFixture[str]
) -> None:
    stored = store.create(make_batch())
    store.set_complete(stored["id"])

    exit_code = cli.main(["wait", stored["id"], "--quiet"])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_OK
    assert json.loads(captured.out)["complete"] is True


def test_wait_on_an_unknown_batch_id_prints_a_guide_error_and_returns_1(
    guide_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = cli.main(["wait", "NOSUCHBATCH", "--quiet"])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_ERROR
    assert captured.err.startswith("guide: ")


# ── clean: ages out by finish time, not creation time ─────────────────────


def _clean_args(
    *, days: int = 7, ids: list[str] | None = None, all_: bool = False
) -> argparse.Namespace:
    return argparse.Namespace(id=ids or [], all=all_, days=days)


def test_clean_ages_out_by_when_a_batch_finished_not_when_it_was_created(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A batch created a month ago but finished moments ago must not look ancient."""
    ancient_id = new_ulid(when_ms=int((time.time() - 30 * 86_400) * 1000))
    monkeypatch.setattr("guide.store.new_ulid", lambda: ancient_id)
    stored = store.create(make_batch())
    store.set_complete(stored["id"])

    doomed = cli._batches_to_clean(store, _clean_args(days=7))

    assert doomed == []


def test_clean_with_a_very_large_days_spares_a_batch_finished_moments_ago(store: Store) -> None:
    stored = store.create(make_batch())
    store.set_complete(stored["id"])

    doomed = cli._batches_to_clean(store, _clean_args(days=3650))

    assert doomed == []


def test_clean_with_days_zero_selects_a_batch_finished_moments_ago(store: Store) -> None:
    stored = store.create(make_batch())
    store.set_complete(stored["id"])

    doomed = cli._batches_to_clean(store, _clean_args(days=0))

    assert [summary.id for summary in doomed] == [stored["id"]]


# ── _last_touched: falls back to the ULID timestamp ────────────────────────


def _make_summary(**overrides: object) -> Summary:
    defaults: dict[str, object] = {
        "id": new_ulid(),
        "title": "t",
        "subtitle": None,
        "label": None,
        "repo": None,
        "branch": None,
        "cwd": None,
        "session_id": None,
        "guide_version": "0.1.0",
        "created_at": None,
        "updated_at": None,
        "cards": 1,
        "answered": 0,
        "complete": True,
    }
    defaults.update(overrides)
    return Summary(**defaults)  # type: ignore[arg-type]


def test_last_touched_falls_back_to_the_ulid_timestamp_when_updated_at_is_missing() -> None:
    batch_id = new_ulid(when_ms=1_700_000_000_000)
    summary = _make_summary(id=batch_id, updated_at=None)

    assert cli._last_touched(summary) == pytest.approx(1_700_000_000.0)


def test_last_touched_falls_back_to_the_ulid_timestamp_when_updated_at_is_unparseable() -> None:
    batch_id = new_ulid(when_ms=1_700_000_000_000)
    summary = _make_summary(id=batch_id, updated_at="not-a-real-timestamp")

    assert cli._last_touched(summary) == pytest.approx(1_700_000_000.0)


# ── _resolve_wait_target ────────────────────────────────────────────────────


def test_resolve_wait_target_with_only_a_completed_batch_from_this_session_returns_it(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Previously raised "no unfinished batch" even though the answers were
    sitting right there on disk."""
    monkeypatch.setattr(cli, "describe_environment", lambda: {"cwd": "/repo"})
    stored = store.create(make_batch(source={"cwd": "/repo"}))
    store.set_complete(stored["id"])

    assert cli._resolve_wait_target(store, None) == stored["id"]


def test_resolve_wait_target_prefers_the_unfinished_batch_over_a_completed_one(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "describe_environment", lambda: {"cwd": "/repo"})
    completed = store.create(make_batch(source={"cwd": "/repo"}))
    store.set_complete(completed["id"])
    unfinished = store.create(make_batch(source={"cwd": "/repo"}))

    assert cli._resolve_wait_target(store, None) == unfinished["id"]


def test_resolve_wait_target_raises_when_nothing_belongs_to_this_session(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "describe_environment", lambda: {"cwd": "/nowhere"})
    store.create(make_batch(source={"cwd": "/somewhere/else"}))

    with pytest.raises(GuideError):
        cli._resolve_wait_target(store, None)


# ── guide.source.describe_environment: session id discovery ────────────────


def test_describe_environment_uses_claude_code_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "cc-session")
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

    assert describe_environment()["session_id"] == "cc-session"


def test_describe_environment_falls_back_to_claude_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "legacy-session")

    assert describe_environment()["session_id"] == "legacy-session"


def test_describe_environment_omits_session_id_when_neither_var_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load-bearing: with no session id, `guide wait` falls back to matching on
    the working directory, so two sessions in one repo would otherwise wake on
    each other's answers."""
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

    assert "session_id" not in describe_environment()
