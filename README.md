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

> Stav: **MVP (P0) hotové** — pozri `PLANNING.md` (DoD). Reálny model Qwen 3B sa overuje na testovacom notebooku.

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

## Demo (TASK §14, 3–5 min)
Čísla nižšie platia pre dataset organizátorov. Jeho model zmeny je príklad z prezentácie: 60 ks/h, zmena 480 min,
prestávka 30 min, AM 10 min, target 440. Pri inej konfigurácii v Settings sa všetko prepočíta.

**Príprava** (bez siete, bez Ollama):
```bash
.venv/Scripts/python scripts/demo_seed.py --hours 3
.venv/Scripts/uvicorn oee.web.app:app
```
`demo_seed.py` importuje dataset (opakovane bez duplicít), aktivuje príkladový model zmeny iba vtedy, keď linka
nemá aktívny model (D8), a vytvorí demo zmenu 01.12.2026: prestoj ST-038 (camera light) a hneď po ňom zmätky
Q-030 (image check). `--hours 3` vyplní prvé 3 hodiny, zvyšok operátor zadá naživo; bez prepínača sa vyplní celá
zmena, `--no-demo-shift` iba importuje. Iná databáza: `OEE_DB_PATH`. Opakovanie: zmažte DB alebo zvoľte `--date`.

**Scenár:**
1. **Import** — 21 zmien v histórii, kontroly §11.7 OK (urobí aj `demo_seed.py`; inak tlačidlo *Import dataset*).
2. **Production History → Month 2026-11** — OEE 88,0 % (cieľ splnený), 4 stredy pod cieľom, rebríček (ST-038 #1).
3. **Shift Dashboard 25.11.** — OEE 78,2 %, 350 z 440 (79,5 % targetu), manko 96: prestoje 48 · rýchlosť 42 ·
   zmätky 6; camera 25 min o 09:08.
4. **Hourly Reporting** — dokončite zmenu 01.12.2026 (ďalšie hodiny s ST-038 a Q-030 v nasledujúcej hodine).
   Dashboard je `provisional`, po N/N `completed` a zmena je v histórii.
5. **Lokálne AI** — sekcia F *Shift summary* a *Links* za 2026-12: väzba **ST-038 → Q-030** (same_process)
   s vysvetlením. Bez Ollama sa zobrazí šablóna („Text from the template"); s Ollama na testovacom notebooku text
   od Qwen 3B overený validátorom. Odporúčania a what-if sú P2.

Offline beh celého scenára overuje `tests/api/test_offline_demo.py` (sieť zablokovaná, Ollama nedostupné).

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
