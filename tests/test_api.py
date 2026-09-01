"""Pins the daemon's HTTP surface: status codes, payload shapes, and the security headers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import make_batch
from guide import API_PREFIX, FORMAT_VERSION
from guide.skill import markdown as skill_markdown
from guide.store import Store


def test_meta_reports_daemon_identity(client: TestClient) -> None:
    response = client.get(f"{API_PREFIX}/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "guide"
    assert body["format_version"] == FORMAT_VERSION
    assert body["batches"] == 0


def test_meta_reports_home_matching_the_daemons_own_store(
    client: TestClient, store: Store
) -> None:
    """A CLI that discovers the wrong daemon would push into someone else's inbox."""
    response = client.get(f"{API_PREFIX}/meta")
    assert response.json()["home"] == str(store.home)


def test_push_returns_201_with_id_cards_and_waiting(client: TestClient) -> None:
    response = client.post(f"{API_PREFIX}/batches", json=make_batch())
    assert response.status_code == 201
    body = response.json()
    assert len(body["id"]) == 26
    assert body["cards"] == 2
    assert body["waiting"] == 1
    assert body["url"] == f"/?batch={body['id']}"


def test_push_with_a_bad_envelope_is_422(client: TestClient) -> None:
    document = make_batch()
    del document["title"]
    response = client.post(f"{API_PREFIX}/batches", json=document)
    assert response.status_code == 422


def test_push_declaring_a_future_major_is_409(client: TestClient) -> None:
    response = client.post(f"{API_PREFIX}/batches", json=make_batch(guide_version="9.0.0"))
    assert response.status_code == 409


def test_push_declaring_a_pre_1_0_minor_ahead_is_also_409(client: TestClient) -> None:
    """This build speaks 0.1.0 — pre-1.0, a minor bump acts as a major mismatch."""
    response = client.post(f"{API_PREFIX}/batches", json=make_batch(guide_version="0.2.0"))
    assert response.status_code == 409


def test_get_unknown_batch_is_404(client: TestClient) -> None:
    assert client.get(f"{API_PREFIX}/batches/DOESNOTEXIST").status_code == 404


def test_get_unknown_batch_answers_is_404(client: TestClient) -> None:
    assert client.get(f"{API_PREFIX}/batches/DOESNOTEXIST/answers").status_code == 404


def test_put_answer_for_an_unknown_card_id_is_404(client: TestClient) -> None:
    batch_id = client.post(f"{API_PREFIX}/batches", json=make_batch()).json()["id"]

    response = client.put(
        f"{API_PREFIX}/batches/{batch_id}/answers/no-such-card",
        json={"values": {"verdict": "yes"}},
    )
    assert response.status_code == 404


def test_put_then_get_answers_round_trips(client: TestClient) -> None:
    batch_id = client.post(f"{API_PREFIX}/batches", json=make_batch()).json()["id"]

    put_response = client.put(
        f"{API_PREFIX}/batches/{batch_id}/answers/1",
        json={"values": {"verdict": "yes", "comment": "fine"}},
    )
    assert put_response.status_code == 200

    answers = client.get(f"{API_PREFIX}/batches/{batch_id}/answers").json()
    [record] = answers["answers"]
    assert record["card_id"] == "1"
    assert record["values"] == {"verdict": "yes", "comment": "fine"}


def test_complete_flips_the_flag(client: TestClient) -> None:
    batch_id = client.post(f"{API_PREFIX}/batches", json=make_batch()).json()["id"]

    response = client.post(f"{API_PREFIX}/batches/{batch_id}/complete", json={"complete": True})
    assert response.status_code == 200
    assert response.json()["complete"] is True
    assert client.get(f"{API_PREFIX}/batches/{batch_id}/answers").json()["complete"] is True


def test_complete_with_degraded_cards_records_them_as_degraded(client: TestClient) -> None:
    """A card blocked by an unsupported required field can never be answered, so
    this list is the only way it ever gets flagged at all."""
    batch_id = client.post(f"{API_PREFIX}/batches", json=make_batch()).json()["id"]

    response = client.post(
        f"{API_PREFIX}/batches/{batch_id}/complete",
        json={"complete": True, "degraded_cards": ["2"]},
    )
    assert response.status_code == 200

    answers = client.get(f"{API_PREFIX}/batches/{batch_id}/answers").json()
    assert answers["degraded_cards"] == ["2"]
    assert answers["degraded"] is True


def test_complete_unions_degraded_ids_across_calls_instead_of_replacing_them(
    client: TestClient,
) -> None:
    batch_id = client.post(f"{API_PREFIX}/batches", json=make_batch()).json()["id"]

    client.put(
        f"{API_PREFIX}/batches/{batch_id}/answers/1",
        json={"values": {"verdict": "yes"}, "degraded": True},
    )
    client.post(
        f"{API_PREFIX}/batches/{batch_id}/complete",
        json={"complete": True, "degraded_cards": ["2"]},
    )
    first = client.get(f"{API_PREFIX}/batches/{batch_id}/answers").json()
    assert set(first["degraded_cards"]) == {"1", "2"}

    # Re-completing without repeating "2" must not drop it from the record.
    client.post(f"{API_PREFIX}/batches/{batch_id}/complete", json={"complete": True})
    second = client.get(f"{API_PREFIX}/batches/{batch_id}/answers").json()
    assert set(second["degraded_cards"]) == {"1", "2"}


def test_delete_returns_204_and_removes_the_batch(client: TestClient) -> None:
    batch_id = client.post(f"{API_PREFIX}/batches", json=make_batch()).json()["id"]

    response = client.delete(f"{API_PREFIX}/batches/{batch_id}")

    assert response.status_code == 204
    assert client.get(f"{API_PREFIX}/batches/{batch_id}").status_code == 404


def test_delete_unknown_batch_is_404(client: TestClient) -> None:
    assert client.delete(f"{API_PREFIX}/batches/DOESNOTEXIST").status_code == 404


def test_every_response_carries_the_security_headers(client: TestClient) -> None:
    for response in (
        client.get(f"{API_PREFIX}/meta"),
        client.get(f"{API_PREFIX}/batches/DOESNOTEXIST"),
    ):
        assert "'none'" in response.headers["content-security-policy"]
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"


def test_root_serves_the_inbox_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "GUIde" in response.text


def test_skill_route_serves_the_install_page(client: TestClient) -> None:
    response = client.get("/skill")
    assert response.status_code == 200
    assert "install the skill" in response.text.lower()


def test_api_skill_reports_content_and_install_path(client: TestClient) -> None:
    response = client.get(f"{API_PREFIX}/skill")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "SKILL.md"
    assert body["install_path"].endswith("SKILL.md")
    assert body["content"] == skill_markdown()
    assert isinstance(body["prompt"], str) and body["prompt"]
