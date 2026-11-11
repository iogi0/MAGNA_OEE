"""Kontrola lokálneho AI na TESTOVACOM notebooku (skill `ollama-local`). Na vývojovom počítači sa nespúšťa.

Použitie (z koreňa projektu):
    .venv/Scripts/python scripts/check_ollama.py

Overí: 1) Ollama beží na 127.0.0.1, 2) model qwen2.5:3b je stiahnutý, 3) `/api/chat` vráti JSON podľa schémy.
Exit code 0 = všetko OK, 1 = problém (vypíše, čo urobiť). Nič neinštaluje a nič nemení.
"""

from __future__ import annotations

import sys
import time

from oee.ai.client import AiError, OllamaClient
from oee.config import get_settings

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}, "number": {"type": "integer"}},
    "required": ["answer", "number"],
}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # konzola cp1251
    settings = get_settings()
    client = OllamaClient(settings.ollama_url, settings.ollama_model, timeout_s=settings.ai_timeout_s)
    print(f"Ollama URL: {client.base_url} · model: {client.model} · timeout: {client.timeout_s:g} s")

    health = client.health()
    print(f"[{'OK' if health.available else 'FAIL'}] server: {health.message}")
    if not health.available:
        print("  → start Ollama (ollama serve) and check that it listens on 127.0.0.1:11434")
        return 1
    print(f"[{'OK' if health.model_present else 'FAIL'}] model present")
    if not health.model_present:
        print(f"  → ollama pull {client.model}")
        return 1

    started = time.perf_counter()
    try:
        result = client.generate(
            system="Answer only with JSON that matches the schema.",
            user="Return answer='ready' and number=42.",
            schema=SCHEMA,
        )
    except AiError as exc:
        print(f"[FAIL] chat: {exc}")
        return 1
    elapsed = time.perf_counter() - started
    ok = result.get("answer") == "ready" and result.get("number") == 42
    print(f"[{'OK' if ok else 'WARN'}] chat in {elapsed:.1f} s: {result}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
