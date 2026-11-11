"""Klient lokálneho AI — Ollama na 127.0.0.1 s modelom qwen2.5:3b (TASK §13.4, ARCHITECTURE §8, §10.6).

Pravidlá:
- iba lokálny host (`localhost` / `127.0.0.1`); cloudové AI API sa nepoužíva (CLAUDE.md bod 2);
- `/api/chat` vždy so `stream: false` (inak Ollama vracia NDJSON) a `format` = JSON schéma výstupu;
- volania idú sekvenčne (zámok) — paralelné požiadavky sa v Ollama radia a padajú na timeout;
- AI nepočíta čísla: dostane hotové fakty, výstup overí validátor (P0-23); pri chybe sa použije fallback.

Testuje sa cez `httpx.MockTransport` a `FakeGenerator`; reálny model iba na testovacom notebooku (D2).
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from oee.config import LOCAL_OLLAMA_HOSTS

TEMPERATURE = 0.2
HEALTH_TIMEOUT_S = 3.0

JsonObject = dict[str, Any]


class AiError(RuntimeError):
    """Lokálne AI nevrátilo použiteľný výsledok — volajúci použije fallback."""


class AiUnavailable(AiError):
    """Ollama nebeží, nie je dostupná alebo vrátila chybový stav."""


class AiTimeout(AiError):
    """Odpoveď neprišla v časovom limite."""


class AiInvalidOutput(AiError):
    """Odpoveď nie je JSON objekt v očakávanom tvare."""


class Generator(Protocol):
    """Čokoľvek, čo z promptu vyrobí JSON objekt podľa schémy (Ollama alebo FakeGenerator)."""

    def generate(self, *, system: str, user: str, schema: Mapping[str, Any]) -> JsonObject: ...


@dataclass(frozen=True)
class Health:
    available: bool
    model_present: bool
    message: str


def facts_hash(facts: Mapping[str, Any]) -> str:
    """SHA-256 kanonického JSON faktov — kľúč cache `ai_output` (rovnaké fakty = rovnaký hash)."""
    canonical = json.dumps(facts, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_local(base_url: str) -> str:
    url = base_url.strip().rstrip("/")
    if (urlsplit(url).hostname or "") not in LOCAL_OLLAMA_HOSTS:
        raise ValueError("Ollama URL must point to localhost or 127.0.0.1 (cloud / remote AI is not allowed)")
    return url


class OllamaClient:
    """Synchrónny klient `/api/chat` a `/api/tags`.

    Zámok serializuje generovanie v rámci inštancie — aplikácia má jednu inštanciu na proces (`app.state`).
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout_s: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = _check_local(base_url)
        self.model = model
        self.timeout_s = timeout_s
        self._transport = transport
        self._lock = threading.Lock()  # ARCHITECTURE §10.6: AI úlohy sekvenčne

    def _client(self, timeout: float) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=timeout, transport=self._transport)

    def generate(self, *, system: str, user: str, schema: Mapping[str, Any]) -> JsonObject:
        payload = {
            "model": self.model,
            "stream": False,
            "format": dict(schema),
            "options": {"temperature": TEMPERATURE},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        with self._lock:
            try:
                with self._client(self.timeout_s) as http:
                    response = http.post("/api/chat", json=payload)
            except httpx.TimeoutException as exc:
                raise AiTimeout(f"Ollama did not answer within {self.timeout_s:g} s") from exc
            except httpx.HTTPError as exc:
                raise AiUnavailable(f"Ollama is not reachable at {self.base_url}: {exc}") from exc
        if response.status_code >= 400:
            raise AiUnavailable(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")
        try:
            content = response.json()["message"]["content"]
            result = json.loads(content)
        except (ValueError, KeyError, TypeError) as exc:
            raise AiInvalidOutput(f"Ollama returned no JSON object: {exc}") from exc
        if not isinstance(result, dict):
            raise AiInvalidOutput("Ollama returned JSON that is not an object")
        return result

    def health(self) -> Health:
        """Stav Ollama a prítomnosť modelu; nikdy nevyhodí výnimku (aplikácia funguje aj bez AI)."""
        try:
            with self._client(HEALTH_TIMEOUT_S) as http:
                response = http.get("/api/tags")
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return Health(False, False, f"Ollama is not reachable at {self.base_url} ({type(exc).__name__})")
        models = body.get("models") if isinstance(body, dict) else None
        names = {str(m.get("name", "")) for m in models or [] if isinstance(m, dict)}
        if self.model in names or f"{self.model}:latest" in names:
            return Health(True, True, f"Ollama is running with {self.model}")
        return Health(True, False, f"Model {self.model} is missing — run: ollama pull {self.model}")


@dataclass
class FakeCall:
    system: str
    user: str
    schema: Mapping[str, Any]


@dataclass
class FakeGenerator:
    """Testovací generátor: vracia pripravené odpovede (dict) alebo vyhodí pripravenú výnimku."""

    responses: Sequence[JsonObject | Exception]
    calls: list[FakeCall] = field(default_factory=list)

    def generate(self, *, system: str, user: str, schema: Mapping[str, Any]) -> JsonObject:
        self.calls.append(FakeCall(system, user, schema))
        item = self.responses[min(len(self.calls), len(self.responses)) - 1]
        if isinstance(item, Exception):
            raise item
        return dict(item)
