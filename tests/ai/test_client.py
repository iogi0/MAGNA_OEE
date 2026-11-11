"""P0-22: klient Ollama a cache `ai_output` (TASK §13.4, ARCHITECTURE §8, §10.6).

Ollama sa tu neinštaluje (D2): HTTP sa testuje cez `httpx.MockTransport`, aplikácia cez `FakeGenerator`.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx
import pytest
from sqlalchemy.orm import Session

from oee.ai.client import (
    AiInvalidOutput,
    AiTimeout,
    AiUnavailable,
    FakeGenerator,
    OllamaClient,
    facts_hash,
)
from oee.persistence.repositories import AiKey, claim_ai_output, finish_ai_output, get_ai_output

BASE = "http://127.0.0.1:11434"
SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
NOW = datetime(2026, 12, 1, 9, 0)


def chat_reply(content: object, status: int = 200) -> httpx.Response:
    body = {
        "model": "qwen2.5:3b",
        "message": {"role": "assistant", "content": json.dumps(content)},
        "done": True,
    }
    return httpx.Response(status, json=body)


def client_with(handler: object) -> tuple[OllamaClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)  # type: ignore[operator]

    client = OllamaClient(BASE, "qwen2.5:3b", timeout_s=5, transport=httpx.MockTransport(wrapped))
    return client, seen


# --- /api/chat -----------------------------------------------------------------------------------


def test_success_returns_parsed_json_and_request_is_non_streaming() -> None:
    client, seen = client_with(lambda r: chat_reply({"text": "OEE 78.2 %"}))
    assert client.generate(system="sys", user="facts", schema=SCHEMA) == {"text": "OEE 78.2 %"}
    (request,) = seen
    assert request.url == f"{BASE}/api/chat" and request.method == "POST"
    body = json.loads(request.content)
    assert body["stream"] is False  # ARCHITECTURE §10.6: inak NDJSON
    assert body["model"] == "qwen2.5:3b" and body["format"] == SCHEMA
    assert body["options"]["temperature"] == pytest.approx(0.2)
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_every_request_has_stream_false() -> None:
    client, seen = client_with(lambda r: chat_reply({"text": "x"}))
    for _ in range(3):
        client.generate(system="s", user="u", schema=SCHEMA)
    assert all(json.loads(r.content)["stream"] is False for r in seen)


def test_timeout() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client, _ = client_with(boom)
    with pytest.raises(AiTimeout):
        client.generate(system="s", user="u", schema=SCHEMA)


def test_server_error_500() -> None:
    client, _ = client_with(lambda r: httpx.Response(500, json={"error": "model crashed"}))
    with pytest.raises(AiUnavailable, match="500"):
        client.generate(system="s", user="u", schema=SCHEMA)


def test_connection_refused_is_unavailable() -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client, _ = client_with(refused)
    with pytest.raises(AiUnavailable):
        client.generate(system="s", user="u", schema=SCHEMA)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"message": {"content": "not json at all"}}),
        httpx.Response(200, json={"message": {"content": json.dumps(["a", "list"])}}),
        httpx.Response(200, json={"unexpected": True}),
        httpx.Response(200, text="<html>proxy</html>"),
    ],
)
def test_invalid_output(response: httpx.Response) -> None:
    client, _ = client_with(lambda r: response)
    with pytest.raises(AiInvalidOutput):
        client.generate(system="s", user="u", schema=SCHEMA)


@pytest.mark.parametrize(
    "url", ["https://api.example.com", "http://10.0.0.5:11434", "http://ollama.local:11434"]
)
def test_non_local_host_is_rejected(url: str) -> None:
    with pytest.raises(ValueError, match="localhost or 127.0.0.1"):
        OllamaClient(url, "qwen2.5:3b", timeout_s=5)


# --- health (/api/tags) --------------------------------------------------------------------------


def test_health_ok_with_model_present() -> None:
    tags = {"models": [{"name": "qwen2.5:3b"}, {"name": "llama3:8b"}]}
    client, seen = client_with(lambda r: httpx.Response(200, json=tags))
    health = client.health()
    assert (health.available, health.model_present) == (True, True)
    assert seen[0].url == f"{BASE}/api/tags" and seen[0].method == "GET"


def test_health_model_missing() -> None:
    client, _ = client_with(lambda r: httpx.Response(200, json={"models": [{"name": "llama3:8b"}]}))
    health = client.health()
    assert (health.available, health.model_present) == (True, False)
    assert "ollama pull qwen2.5:3b" in health.message


def test_health_never_raises_when_ollama_is_down() -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client, _ = client_with(refused)
    health = client.health()
    assert (health.available, health.model_present) == (False, False) and "not reachable" in health.message


# --- FakeGenerator a facts_hash ------------------------------------------------------------------


def test_fake_generator_records_calls_and_can_fail() -> None:
    fake = FakeGenerator([{"text": "a"}, AiTimeout("slow")])
    assert fake.generate(system="s", user="u1", schema=SCHEMA) == {"text": "a"}
    with pytest.raises(AiTimeout):
        fake.generate(system="s", user="u2", schema=SCHEMA)
    assert [c.user for c in fake.calls] == ["u1", "u2"]


def test_facts_hash_is_canonical() -> None:
    a = {"oee": 0.7818, "codes": ["ST-038"], "name": "Kamera"}
    b = {"name": "Kamera", "codes": ["ST-038"], "oee": 0.7818}
    assert facts_hash(a) == facts_hash(b) and len(facts_hash(a)) == 64
    assert facts_hash(a) != facts_hash({**a, "oee": 0.7819})


# --- cache ai_output -----------------------------------------------------------------------------


def key(facts: dict[str, object]) -> AiKey:
    return AiKey("shift_summary", "L01-20261125-M", facts_hash(facts), "qwen2.5:3b", "en", "v1")


def test_same_facts_hit_cache_changed_facts_new_key(session: Session) -> None:
    facts = {"oee": 0.7818}
    row = claim_ai_output(session, key(facts), now=NOW, stale_after=timedelta(seconds=60))
    assert row is not None and row.status == "pending"
    finish_ai_output(session, row, status="ok", payload={"text": "OEE 78.2 %"}, now=NOW)
    session.commit()

    hit = get_ai_output(session, key({"oee": 0.7818}))
    assert hit is not None and (hit.status, hit.payload) == ("ok", {"text": "OEE 78.2 %"})
    assert (
        claim_ai_output(session, key(facts), now=NOW, stale_after=timedelta(seconds=60)) is None
    )  # už hotové
    assert get_ai_output(session, key({"oee": 0.79})) is None  # zmenené fakty = nový kľúč
    other = claim_ai_output(session, key({"oee": 0.79}), now=NOW, stale_after=timedelta(seconds=60))
    assert other is not None and other.id != row.id


def test_pending_is_not_generated_twice(session: Session) -> None:
    k = key({"oee": 0.5})
    assert claim_ai_output(session, k, now=NOW, stale_after=timedelta(seconds=60)) is not None
    session.commit()
    later = NOW + timedelta(seconds=30)
    assert claim_ai_output(session, k, now=later, stale_after=timedelta(seconds=60)) is None


def test_stale_pending_is_taken_over(session: Session) -> None:
    k = key({"oee": 0.5})
    first = claim_ai_output(session, k, now=NOW, stale_after=timedelta(seconds=60))
    assert first is not None
    session.commit()
    later = NOW + timedelta(seconds=61)  # proces padol: pending starší ako 2 × timeout
    again = claim_ai_output(session, k, now=later, stale_after=timedelta(seconds=60))
    assert again is not None and again.id == first.id and again.updated_at == later


# --- /health v aplikácii -------------------------------------------------------------------------


def test_health_endpoint_reports_ai_without_failing(tmp_path: object) -> None:
    from pathlib import Path

    from fastapi.testclient import TestClient

    from oee.config import Settings
    from oee.web.app import create_app

    base = Path(str(tmp_path))
    disabled = Settings(_env_file=None, db_path=base / "a.db", ai_enabled=False)  # type: ignore[call-arg]
    with TestClient(create_app(disabled)) as c:
        body = c.get("/health").json()
        assert body["status"] == "ok"
        assert body["ai"] == {
            "enabled": False,
            "available": False,
            "model": "qwen2.5:3b",
            "model_present": False,
            "message": "AI is disabled (OEE_AI_ENABLED=false)",
        }

    enabled = Settings(_env_file=None, db_path=base / "b.db", ai_enabled=True)  # type: ignore[call-arg]
    with TestClient(create_app(enabled)) as c:

        def down(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        c.app.state.ai_client = OllamaClient(
            BASE, "qwen2.5:3b", timeout_s=5, transport=httpx.MockTransport(down)
        )  # type: ignore[attr-defined]
        r = c.get("/health")
        assert r.status_code == 200 and r.json()["status"] == "ok"  # aplikácia beží aj bez Ollama
        assert r.json()["ai"]["available"] is False

        ok = httpx.MockTransport(lambda req: httpx.Response(200, json={"models": [{"name": "qwen2.5:3b"}]}))
        c.app.state.ai_client = OllamaClient(BASE, "qwen2.5:3b", timeout_s=5, transport=ok)  # type: ignore[attr-defined]
        ai = c.get("/health").json()["ai"]
        assert (ai["enabled"], ai["available"], ai["model_present"]) == (True, True, True)


@pytest.mark.parametrize("body", [{"models": None}, ["not", "a", "dict"], {"models": [None, "x"]}])
def test_health_survives_unexpected_json(body: object) -> None:
    client, _ = client_with(lambda r: httpx.Response(200, json=body))
    health = client.health()  # nesmie vyhodiť výnimku (ARCHITECTURE §7)
    assert health.model_present is False


def test_stale_takeover_is_atomic(session: Session) -> None:
    from oee.persistence.models import AiOutput

    k = key({"oee": 0.6})
    first = claim_ai_output(session, k, now=NOW, stale_after=timedelta(seconds=60))
    assert first is not None
    session.commit()
    later = NOW + timedelta(seconds=61)
    assert claim_ai_output(session, k, now=later, stale_after=timedelta(seconds=60)) is not None
    session.commit()
    # druhý proces, ktorý videl pôvodný čas, už riadok neprevezme (updated_at sa zmenil)
    session.expire_all()
    row = session.get(AiOutput, first.id)
    assert row is not None and row.updated_at == later
    assert (
        claim_ai_output(session, k, now=later + timedelta(seconds=1), stale_after=timedelta(seconds=60))
        is None
    )
