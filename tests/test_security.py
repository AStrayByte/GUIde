"""Pins the origin/Host guards in ``guide.daemon.app`` and the store's path-traversal guard.

The daemon binds ``127.0.0.1``, but every web page in every open tab is on that
socket too. A cross-origin ``POST`` with no custom headers is a *simple
request* — no preflight — so a page you merely had open could otherwise stop
the daemon or install a skill file. ``SameOriginOnly`` is the guard against
that; ``LoopbackHostOnly`` is the guard against a page served from a domain
that merely resolves to 127.0.0.1, which passes the same-origin check because
it controls both sides of the Origin-vs-Host comparison; ``Store._dir`` is the
guard against a batch id that is not really an id but an attempt to walk out
of the store.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import make_batch
from guide import API_PREFIX
from guide.errors import BatchNotFound
from guide.store import Store

_CROSS_SITE = {"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}

_NOT_A_BATCH_ID = ["../../etc", "..%2f..", "not-a-ulid", ""]


@pytest.fixture
def pushed(client: TestClient) -> dict[str, str]:
    """A batch pushed the way the CLI would: no browser headers at all."""
    response = client.post(f"{API_PREFIX}/batches", json=make_batch())
    return {"batch_id": response.json()["id"], "card_id": "1"}


# -- SameOriginOnly: state-changing requests -------------------------------


def test_cross_site_write_requests_are_rejected_on_every_state_changing_route(
    client: TestClient, pushed: dict[str, str]
) -> None:
    batch_id, card_id = pushed["batch_id"], pushed["card_id"]
    requests = [
        ("POST", f"{API_PREFIX}/batches", {"json": make_batch()}),
        (
            "PUT",
            f"{API_PREFIX}/batches/{batch_id}/answers/{card_id}",
            {"json": {"values": {"verdict": "yes"}}},
        ),
        ("POST", f"{API_PREFIX}/batches/{batch_id}/complete", {"json": {"complete": True}}),
        ("DELETE", f"{API_PREFIX}/batches/{batch_id}", {}),
        ("POST", f"{API_PREFIX}/skill/install", {}),
    ]
    for method, path, kwargs in requests:
        response = client.request(method, path, headers=_CROSS_SITE, **kwargs)
        assert response.status_code == 403, f"{method} {path} was not blocked"


def test_cross_site_403_body_has_a_detail_and_still_carries_security_headers(
    client: TestClient,
) -> None:
    response = client.post(f"{API_PREFIX}/batches", json=make_batch(), headers=_CROSS_SITE)

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert isinstance(detail, str) and detail
    assert "'none'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_same_origin_sec_fetch_site_is_allowed_through(client: TestClient) -> None:
    response = client.post(
        f"{API_PREFIX}/batches", json=make_batch(), headers={"Sec-Fetch-Site": "same-origin"}
    )
    assert response.status_code == 201


def test_none_sec_fetch_site_is_allowed_through(client: TestClient) -> None:
    """``none`` marks a user-initiated navigation — typing the URL, a bookmark."""
    response = client.post(
        f"{API_PREFIX}/batches", json=make_batch(), headers={"Sec-Fetch-Site": "none"}
    )
    assert response.status_code == 201


def test_no_origin_and_no_sec_fetch_site_at_all_is_allowed_through(client: TestClient) -> None:
    """The CLI is a plain HTTP client: it sends neither header."""
    response = client.post(f"{API_PREFIX}/batches", json=make_batch())
    assert response.status_code == 201


def test_origin_matching_the_requests_own_host_is_allowed_through(client: TestClient) -> None:
    own_origin = str(client.base_url).rstrip("/")
    response = client.post(
        f"{API_PREFIX}/batches", json=make_batch(), headers={"Origin": own_origin}
    )
    assert response.status_code == 201


def test_get_is_never_blocked_regardless_of_headers(client: TestClient) -> None:
    assert client.get(f"{API_PREFIX}/batches", headers=_CROSS_SITE).status_code == 200
    assert client.get("/", headers=_CROSS_SITE).status_code == 200


# -- LoopbackHostOnly: the Host header guard --------------------------------
#
# SameOriginOnly compares Origin against Host — a rebound page (a domain that
# resolves to 127.0.0.1) controls both sides of that comparison equally, so it
# always passes and only guards non-safe methods. LoopbackHostOnly closes that:
# it checks Host against a fixed allowlist the attacker has no way to spoof,
# and it applies to every method, GET included, because an unauthenticated
# same-origin read is damage enough on its own.

_LOOPBACK_HOSTS = ["127.0.0.1", "localhost", "[::1]"]


def test_foreign_host_is_rejected_on_a_plain_get(client: TestClient) -> None:
    response = client.get(f"{API_PREFIX}/batches", headers={"Host": "evil.example"})
    assert response.status_code == 421


def test_foreign_host_is_rejected_on_a_state_changing_route(client: TestClient) -> None:
    response = client.post(
        f"{API_PREFIX}/batches", json=make_batch(), headers={"Host": "evil.example"}
    )
    assert response.status_code == 421


@pytest.mark.parametrize("host", _LOOPBACK_HOSTS)
def test_each_loopback_host_is_accepted_regardless_of_port(
    client: TestClient, host: str
) -> None:
    """The daemon scans ports 7777-7796, so the bound port varies request to
    request — only the hostname half of Host may gate the decision."""
    response = client.get(f"{API_PREFIX}/batches", headers={"Host": f"{host}:7796"})
    assert response.status_code == 200


def test_foreign_host_421_still_carries_the_security_headers(client: TestClient) -> None:
    response = client.get(f"{API_PREFIX}/batches", headers={"Host": "evil.example"})
    assert response.status_code == 421
    assert "'none'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


# -- Store: the batch-id path guard -----------------------------------------


@pytest.mark.parametrize("bad_id", _NOT_A_BATCH_ID)
def test_dir_rejects_anything_that_is_not_a_well_formed_ulid(store: Store, bad_id: str) -> None:
    with pytest.raises(BatchNotFound):
        store._dir(bad_id)


@pytest.mark.parametrize("bad_id", _NOT_A_BATCH_ID)
def test_read_batch_rejects_a_non_ulid_id(store: Store, bad_id: str) -> None:
    with pytest.raises(BatchNotFound):
        store.read_batch(bad_id)


@pytest.mark.parametrize("bad_id", _NOT_A_BATCH_ID)
def test_delete_rejects_a_non_ulid_id(store: Store, bad_id: str) -> None:
    with pytest.raises(BatchNotFound):
        store.delete(bad_id)


@pytest.mark.parametrize("bad_id", _NOT_A_BATCH_ID)
def test_archive_rejects_a_non_ulid_id(store: Store, bad_id: str) -> None:
    with pytest.raises(BatchNotFound):
        store.archive(bad_id)


def test_read_batch_with_a_traversal_id_never_touches_a_file_beside_the_store(
    store: Store, guide_home: Path
) -> None:
    secret = guide_home.parent / "secret.txt"
    secret.write_text("do not touch", encoding="utf-8")

    with pytest.raises(BatchNotFound):
        store.read_batch("../secret.txt")

    assert secret.read_text(encoding="utf-8") == "do not touch"
