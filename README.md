# AI OEE Improvement Engine

Prototyp pre **Magna Hackathon, zadanie č. 5**: každá výrobná strata má byť viditeľná a riešiteľná.

**Ako to funguje:**
1. **Manažér** v Settings nastaví linku: výkon (ks/h), začiatok a dĺžku zmeny, prestávku, nastavenie/AM,
   cieľ OEE a pracovné dni. Z toho sa vypočíta target.
2. **Operátor** každú hodinu zmeny zadá na webe počet vyrobených kusov, zmätky a problémy (Top-10 kódov).
3. Po vyplnení všetkých hodín zmeny systém **deterministicky** vypočíta Availability, Performance, Quality, OEE,
   kaskádu strát (Target → Good) a straty podľa problémov.
4. **Manažér** vidí *Shift Dashboard* a *Production History*: týždeň/mesiac, rebríček problémov podľa
   vplyvu, väzby prestoj → zmätok (*Problem Links*).
5. **Lokálne AI** (Qwen 3B cez Ollama, offline) píše zhrnutie zmeny a vysvetľuje väzby medzi problémami.
   Čísla vždy počíta kód.

> Stav: **prípravná fáza** — dokumentácia a kostra repozitára. Funkčný kód vzniká po úlohách v `PLANNING.md`.

## Dokumenty
| Súbor | Obsah |
|---|---|
| `TASK.md` | obchodné požiadavky v2.3 (zdroj pravdy) |
| `PLANNING.md` | roadmap, úlohy P0/P1/P2, závislosti, akceptačné kritériá, denník rozhodnutí |
| `docs/ARCHITECTURE.md` | stack, vrstvy, moduly, databáza, toky, AI |
| `docs/TESTING.md` | stratégia testov, golden hodnoty, Definition of Done |
| `CLAUDE.md`, `AGENTS.md` | pravidlá a roly pre Claude Code agentov |
| `data/README.md` | dataset a pravidlá práce s ním |

## Požiadavky
- Python **≥ 3.12** (vyvíjané na 3.14)
- Git
- **Ollama + `qwen2.5:3b`** — iba na počítači, kde sa testuje AI. Aplikácia funguje aj bez neho (fallback texty).
  Návod: `.claude/skills/ollama-local/SKILL.md`.

## Rýchly štart
Funguje od úlohy P0-01. Server je dostupný od P0-15. `constraints.txt` (presné verzie) vzniká v P0-01.
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]" -c constraints.txt
cp .env.example .env
.venv/Scripts/python -m pytest -q
.venv/Scripts/uvicorn oee.web.app:app --reload
```
Na Linux/macOS použite `.venv/bin/...` namiesto `.venv/Scripts/...`. Aplikácia: http://127.0.0.1:8000.

## Testy
```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m pytest -m golden -q
.venv/Scripts/python -m pytest -m ollama -q
.venv/Scripts/ruff check src tests && .venv/Scripts/mypy
```
- `pytest -q` — všetky testy okrem `ollama`.
- `pytest -m golden` — porovnanie s TASK.md §12.
- `pytest -m ollama` — iba na testovacom notebooku so spusteným Ollama.

## Demo (cieľový stav po P0-25)
Čísla nižšie platia pre dataset organizátorov. Jeho model zmeny je príklad z prezentácie: 60 ks/h, zmena 480 min,
prestávka 30 min, AM 10 min, target 440. Pri inej konfigurácii v Settings sa všetko prepočíta.
1. Import datasetu → 21 zmien v histórii.
2. Production History → mesačný OEE 88,0 %, rebríček problémov, Problem Links.
3. Shift Dashboard 25.11. → OEE 78,2 %, 350 z 440 (79,5 % targetu).
4. Živé zadanie novej zmeny po hodinách.
5. Zhrnutie a vysvetlenie väzby ST-038 → Q-030 od lokálneho AI.

Scenár: TASK.md §14.

## Štruktúra
```
src/oee/
  domain/       čisté výpočty (target, prestoje, KPI, validácia, ranking, korelácie)
  catalog/      Top-10 ST/Q, páry procesov (páky zo slajdu 13 — P2)
  contracts/    Pydantic kontrakty (TASK §10)
  persistence/  SQLite + SQLAlchemy
  services/     reporting, analytics, importer, ai_orchestrator
  ai/           klient Ollama, prompty, validátor, fallback
  web/          FastAPI + Jinja2 + HTMX + Chart.js
tests/          unit, golden, contract, api, ai, arch
data/raw/       dataset organizátorov (opravená verzia)
```
