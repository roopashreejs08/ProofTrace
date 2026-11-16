"""HTTP layer: the retry endpoint starts a fresh run of the same text.

Retrying a failed investigation must not overwrite the original run, so
the endpoint creates a new investigation from the stored input and keeps
the old one in history.
"""

from fastapi.testclient import TestClient

import app.main as main
from app.memory import Memory


def _client(monkeypatch, tmp_path):
    mem = Memory(str(tmp_path / "t.db"))
    runs = []

    # Point the app at an isolated database and record pipeline runs
    # instead of hitting the network.
    monkeypatch.setattr(main, "memory", mem)
    monkeypatch.setattr(main.pipeline, "run", lambda inv: runs.append(inv))

    return TestClient(main.app), mem, runs


def test_retry_starts_a_new_investigation_with_the_same_text(
    monkeypatch, tmp_path
):
    client, mem, runs = _client(monkeypatch, tmp_path)

    original = mem.create_investigation(
        "Deep learning transformed vision [1]."
    )

    res = client.post(f"/api/investigations/{original}/retry")

    assert res.status_code == 200

    new_id = res.json()["id"]

    assert new_id != original
    assert mem.get_input(new_id) == mem.get_input(original)
    assert runs == [new_id]

    # The original run is kept, not overwritten.
    assert mem.get_investigation(original) is not None


def test_retry_unknown_investigation_is_not_found(monkeypatch, tmp_path):
    client, _, _ = _client(monkeypatch, tmp_path)

    res = client.post("/api/investigations/does-not-exist/retry")

    assert res.status_code == 404
