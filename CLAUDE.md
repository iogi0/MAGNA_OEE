# CLAUDE.md — trvalý kontext projektu

## Projekt
**AI OEE Improvement Engine** (Magna Hackathon, zadanie č. 5).

**Hlavný scenár:**
1. Operátor každú hodinu ručne zadá na webe vyrobené kusy, zmätky a problémy.
2. Keď sú vyplnené všetky hodiny zmeny (napr. 8/8), systém deterministicky vypočíta OEE a straty zmeny.
3. Manažér vidí Shift Dashboard a Production History (týždeň/mesiac, rebríček problémov, väzby prestoj → zmätok).
4. Lokálne AI (Qwen 3B cez Ollama) píše zhrnutia a vysvetlenia.

## Zdroj pravdy
- **`TASK.md` (v2.3) je jediný zdroj obchodných požiadaviek. Nikdy ho neupravuj.**
- Rozhodnutia, ktoré sa od TASK.md odchyľujú, sú v `PLANNING.md` → „Denník rozhodnutí".
- Plán úloh a stav: `PLANNING.md`. Architektúra: `docs/ARCHITECTURE.md`. Testy a golden hodnoty: `docs/TESTING.md`.
  Roly agentov: `AGENTS.md`.

## Nemenné pravidlá (porušenie = chyba)
1. **KPI počíta iba deterministický kód** (`src/oee/domain`). AI nikdy nepočíta čísla, iba formuluje text
   z vypočítaných faktov. Validátor overuje, že každé číslo a kód v texte AI pochádza z faktov.
2. **Žiadne cloudové AI API** (žiadne `anthropic`, `openai`, `google-genai` …). Len Ollama na `127.0.0.1`
   (alebo `localhost`) s modelom `qwen2.5:3b`. Konfigurácia iný host odmietne.
3. **Ollama sa na tomto počítači neinštaluje.** AI sa tu testuje cez `FakeGenerator` / `httpx.MockTransport`.
   Skutočný model sa overuje na testovacom notebooku (skill `ollama-local`). Bez Ollama musí všetko fungovať
   (fallback texty).
4. **Target zadáva manažér:**
   - vzorec: `target (ks) = výkon linky (ks/h) × plánovaný čas (min) / 60`, kde `/ 60` je prevod minút na hodiny;
   - plánovaný čas = dĺžka zmeny − prestávka − nastavenie/AM;
   - dĺžka zmeny je v celých hodinách, teda N hodinových slotov;
   - snapshot modelu zmeny sa ukladá so zmenou.

   **Čísla 60 ks/h, 480 / 30 / 10 min, 85 %, target 440 a 8 hodín sú iba príklady** (PLANNING D8). V kóde sa
   nesmú objaviť ako pravidlo ani ako skrytý predvolený stav. Žijú iba v `catalog/example_shift_model.yaml`
   (tlačidlo „Vyplniť príkladom", demo) a v testoch. Testy musia pokryť aj inú konfiguráciu.
5. **Číselník + „Other"; Top-10 z frekvencie** (TASK §5.4 upravené PLANNING D15). Hodinové hlásenie ponúka celý
   číselník ST / Q + „Other" s povinným komentárom. V Settings sa číselník iba zobrazuje a dá sa doň pridať nový kód
   (ručný výber Top-10 neexistuje). Top-10 najčastejších problémov počíta analytika (dashboard týždňa a mesiaca);
   bez dát ukazuje štartovací zoznam TASK §5.4 s nulovými hodnotami.
6. **Žiadne dvojité započítanie strát** (TASK §3.4). Identita `C − D − S − R = G` platí pre hodinu, zmenu aj
   obdobie. Agregácia iba cez súčty primárnych veličín, nikdy priemer percent.
7. **Correlation Analysis** (TASK §8.6) počíta kód (lift, extra rejects, typ, istota). AI iba vysvetľuje.
   Korelácia ≠ dokázaná príčina.
8. **Golden hodnoty** z TASK §12 musia sedieť (KPI ±0,01 p. b., kusy a minúty presne).
9. **Excel `data/raw/dummy_data.xlsx` nikdy neukladaj** (stratili by sa grafy). Iba čítaj s `data_only=True`.
10. `improvement_plan` (AI odporúčania, 5-Why, what-if) je **P2**. V P0 robí AI iba Shift Summary a vysvetlenia
    Problem Links.

## Pracovný cyklus (povinný)
Používaj skill **`task-cycle`**:
1. jedna malá úloha z `PLANNING.md`;
2. krátky plán;
3. implementácia (TDD);
4. testy;
5. kontrola `git diff`;
6. aktualizácia `PLANNING.md`;
7. **zastav a čakaj na povolenie**.

- Nepokračuj na ďalšiu úlohu bez súhlasu používateľa.
- **Necommituj** a nepushuj, kým o to používateľ výslovne nepožiada.
- Neinštaluj systémový softvér (Ollama, Python …). Python balíky iba do `.venv` v rámci úlohy P0-01 a ďalších.

## Príkazy
Windows, Git Bash alebo PowerShell:
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]" -c constraints.txt
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m pytest -m golden -q
.venv/Scripts/ruff check src tests
.venv/Scripts/ruff format src tests
.venv/Scripts/mypy
.venv/Scripts/uvicorn oee.web.app:app --reload
```
Poznámky k príkazom:
- `constraints.txt` vzniká v P0-01 (presné overené verzie). Pred P0-01 inštaluj bez `-c constraints.txt`.
- `pytest -m golden` spúšťa iba golden testy. Exit code 5 = zatiaľ žiadne také testy, nie chyba.
- `uvicorn` (server na http://127.0.0.1:8000) je dostupný od P0-15.
- Testy s markerom `ollama` sú predvolene vypnuté (`addopts` v `pyproject.toml`). Spúšťajú sa iba na
  testovacom notebooku príkazom `pytest -m ollama`.

## Architektúra (skrátene)
- Vrstvy: `web → services → {domain, persistence, catalog, contracts, ai}`.
- `domain` je čistý Python bez IO a bez importov `persistence/services/web/ai/httpx/sqlalchemy/fastapi`
  (kontroluje `tests/arch`).
- Analytika sa počíta na požiadanie z primárnych záznamov. Cachuje sa iba výstup AI (`ai_output` podľa
  `facts_hash`).
- Detaily: `docs/ARCHITECTURE.md`.
- **Technické pravidlá a overené pasce sú povinné: `docs/ARCHITECTURE.md` §10.** Pred každou úlohou si prečítaj
  časť, ktorá sa jej týka. Najčastejšie:
  - `encoding="utf-8"` (systém je cp1251);
  - cesty voči koreňu projektu;
  - `PRAGMA foreign_keys=ON`;
  - `TemplateResponse(request, …)` a `lifespan` (Starlette 1.x);
  - Ollama `stream: false` na `127.0.0.1`;
  - naivný lokálny čas vs naivný UTC.

## Konvencie
- **Kód, identifikátory, UI texty:** angličtina. **Dokumentácia:** slovenčina. **Jazyk odpovedí AI:** parameter
  `OEE_AI_LANG` (predvolene `en`).
- **Typy:** typové anotácie všade. Pre `domain` a `contracts` platí prísny režim mypy (nastavený v
  `pyproject.toml`).
- **Doména:** `dataclasses`, bez pandas; čísla zaokrúhľuj iba pri prezentácii.
- **Testy:** zrkadlia štruktúru `src/oee` v `tests/unit`. Golden testy sú v `tests/golden` s markerom `golden`.
- **Frontend:** assety (htmx, Chart.js, Pico.css) vendorované v `src/oee/web/static/vendor/`, žiadne CDN.
  Demo musí fungovať offline.

## Kedy použiť skills / agentov
| Situácia | Skill / agent |
|---|---|
| Začiatok každej úlohy | skill `task-cycle` |
| Nová doménová logika | skill `superpowers:test-driven-development` |
| Overenie golden hodnôt | skill `golden-check`, agent `golden-verifier` |
| Revízia diffu voči TASK.md | agent `spec-reviewer` |
| Prompty, validátor, Ollama | agent `local-ai-engineer`, skill `ollama-local` |
| Chyba / padajúci test | skill `superpowers:systematic-debugging` |
| Pred vyhlásením „hotovo" | skill `superpowers:verification-before-completion` |
| Spustenie aplikácie | skill `run` |

## Windows poznámky
- Python 3.14 je lokálne, projekt podporuje ≥ 3.12. Ak niektorý balík nemá wheel pre 3.14, **zastav sa a opýtaj
  sa vlastníka** (inštalácia iného Pythonu je systémová zmena). Ak je už nainštalovaný, použi `py -3.12`.
- Konzola môže mať cp1251: pri výpise UTF-8 použi `sys.stdout.reconfigure(encoding="utf-8")` alebo
  `PYTHONIOENCODING=utf-8`.
