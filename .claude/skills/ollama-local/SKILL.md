---
name: ollama-local
description: Návod na lokálne AI pre projekt OEE — inštalácia a overenie Ollama s modelom qwen2.5:3b na TESTOVACOM notebooku, kontrola spojenia, diagnostika a pravidlo „iba localhost". Použi, keď sa má overiť reálny model alebo riešiť problém s Ollama. Na vývojovom počítači sa Ollama neinštaluje.
---

# Lokálne AI: Ollama + Qwen 3B

> **Vývojový počítač:** Ollama sa **neinštaluje ani nespúšťa** (PLANNING D2). Vývoj a testy idú cez
> `FakeGenerator` / `MockTransport`. Postup nižšie je pre **testovací notebook** a vykonáva sa iba na výslovnú
> požiadavku používateľa.

## 1. Inštalácia (testovací notebook, Windows)
Projekt na notebooku potrebuje **vlastné** `.venv` (prostredie sa nekopíruje):
```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]" -c constraints.txt
```
Potom Ollama a model:
```powershell
winget install Ollama.Ollama
ollama pull qwen2.5:3b
ollama list
```
- Alternatíva: inštalátor z oficiálnej stránky Ollama.
- Model `qwen2.5:3b` (4-bit) má cca 2 GB, potrebuje ~3 GB RAM. Funguje na CPU, GPU zrýchli odpovede.
- Ollama počúva na `http://127.0.0.1:11434`. **Nemeň `OLLAMA_HOST` na verejnú adresu.**
- V projekte používaj `127.0.0.1`, nie `localhost`: na Windows sa `localhost` môže preložiť na IPv6 `::1`.

## 2. Konfigurácia projektu
V `.env` (pozri `.env.example`):
```
OEE_OLLAMA_URL=http://127.0.0.1:11434
OEE_OLLAMA_MODEL=qwen2.5:3b
OEE_AI_ENABLED=true
OEE_AI_LANG=en
OEE_AI_TIMEOUT_S=30
```
- Konfigurácia odmietne iný host ako `localhost` / `127.0.0.1`.
- Cloudové AI API sa v projekte nepoužívajú.

## 3. Overenie
Skript `scripts/check_ollama.py` vzniká v úlohe P0-22.
```bash
curl http://127.0.0.1:11434/api/tags
.venv/Scripts/python scripts/check_ollama.py
.venv/Scripts/python -m pytest -m ollama -q
```
- `curl …/api/tags` má vrátiť JSON so zoznamom modelov, vrátane `qwen2.5:3b`.
- `check_ollama.py` overí dostupnosť, model a jedno krátke volanie s JSON schémou.
- Potom prejdi kontrolný zoznam „Testovací notebook" v `PLANNING.md` (vrátane behu s vypnutou sieťou).

## 4. Diagnostika
| Problém | Riešenie |
|---|---|
| `connection refused` | Ollama nebeží → spusti aplikáciu Ollama alebo `ollama serve` |
| `model not found` | `ollama pull qwen2.5:3b`; skontroluj `OEE_OLLAMA_MODEL` |
| timeout | prvé volanie načítava model (pomalé); zvýš `OEE_AI_TIMEOUT_S`; zatvor náročné aplikácie |
| nevalidný JSON / zamietnuté validátorom | skontroluj prompt a schému (`src/oee/ai/prompts`); pozri agenta `local-ai-engineer` |
| `JSONDecodeError` / „Extra data" pri čítaní odpovede | chýba `"stream": false` — Ollama predvolene streamuje NDJSON |
| spojenie trvá dlho alebo zlyhá iba s `localhost` | použi `127.0.0.1` (IPv6 `::1` vs IPv4) |
| slabá slovenčina | 3B model píše najlepšie po anglicky → `OEE_AI_LANG=en` |

Pri akomkoľvek probléme aplikácia musí fungovať ďalej s fallback textami. Ak nefunguje, je to chyba v kóde.
