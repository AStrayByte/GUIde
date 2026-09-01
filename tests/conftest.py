"""Shared fixtures.

Every test that touches disk gets its own ``GUIDE_HOME`` under ``tmp_path``.
Nothing in this suite can see, let alone write to, a real ``~/.guide``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from guide import FORMAT_VERSION
from guide.daemon.app import create_app
from guide.store import Store

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def guide_home(tmp_path, monkeypatch):
    """An isolated store root, exported so subprocesses inherit it too."""
    home = tmp_path / "guide-home"
    home.mkdir()
    monkeypatch.setenv("GUIDE_HOME", str(home))
    return home


@pytest.fixture
def store(guide_home):
    """A store rooted in the isolated home."""
    return Store(guide_home)


@pytest.fixture
def app(store):
    """A daemon application over the isolated store."""
    return create_app(store)


@pytest.fixture
def client(app):
    """A synchronous test client for the daemon."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def version_compat():
    """The shared version-gate truth table."""
    return json.loads((FIXTURES / "version_compat.json").read_text())


def make_batch(**overrides):
    """A minimal valid batch, with ``guide_version`` first as the format demands."""
    batch = {
        "guide_version": FORMAT_VERSION,
        "title": "Test batch",
        "cards": [
            {
                "id": "1",
                "title": "First",
                "blocks": [{"type": "text", "text": "evidence"}],
                "meta": {"run": 1},
            },
            {"id": "2", "title": "Second"},
        ],
        "defaults": {
            "response": {
                "prompt": "Verdict",
                "fields": [
                    {
                        "id": "verdict",
                        "type": "choice",
                        "required": True,
                        "options": [
                            {"value": "yes", "label": "Yes"},
                            {"value": "no", "label": "No"},
                        ],
                    },
                    {"id": "comment", "type": "text", "multiline": True},
                ],
            }
        },
    }
    batch.update(overrides)
    return batch
