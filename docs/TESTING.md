# Testovanie — stratégia, golden hodnoty, Definition of Done

Autoritatívne referenčné hodnoty sú v **`TASK.md` §12**. Tento dokument hovorí, ako a kde sa overujú.
Pri rozpore platí TASK.md.

## 1. Princípy
- **TDD pre doménu:** najprv test (aj z príkladov TASK.md), potom kód.
- **Golden hodnoty nie sú konštanty v kóde.** Sú iba v testoch. Kód počíta všeobecne z akýchkoľvek dát.
- **Model zmeny z prezentácie** (60 ks/h, 480 / 30 / 10 min, 85 %, target 440, 8 hodín, Po–Pi) je iba príklad
  (PLANNING D8). Testy musia okrem neho pokryť aj:
  - inú konfiguráciu (napr. 6 h, 45 ks/h, prestávka 20 min v 3. hodine, AM 15 min → target 243,75);
  - obdobie so zmenami s rôznym modelom (agregácia cez súčty).
- **Tolerancie:**
  - KPI a percentá ±0,01 p. b.;
  - kusy, minúty, počty udalostí a poradie zo vstupných dát **presne**;
  - lift na 2 desatinné miesta;
  - vypočítané `float` hodnoty (napr. identita C − D − S − R = G pri targete 366,67) cez
    `math.isclose(..., abs_tol=1e-9)`, nikdy `==`.
- **Izolácia testov** (ARCHITECTURE §10):
  - `Settings(_env_file=None, ...)`, testy nečítajú `.env`;
  - in-memory DB so `StaticPool`;
  - `with TestClient(create_app(settings))` (spustí lifespan);
  - cesta k datasetu odvodená od koreňa repozitára (`Path(__file__)`), nie od CWD.
- Zlyhaný golden test sa rieši opravou kódu, **nie zmenou očakávanej hodnoty** (výnimka iba so súhlasom
  vlastníka, zápis do denníka rozhodnutí v `PLANNING.md`).
- AI testy nikdy nevolajú reálny model, okrem markeru `ollama`, ktorý beží iba na testovacom notebooku.

## 2. Typy testov a priečinky
| Priečinok | Čo testuje | Marker | Rýchlosť |
|---|---|---|---|
| `tests/unit/` | čisté doménové funkcie, katalóg, konfigurácia, služby s in-memory SQLite | — | ms |
| `tests/golden/` | import `data/raw/dummy_data.xlsx` + porovnanie s TASK §12 | `golden` | s |
| `tests/contract/` | Pydantic schémy (TASK §10), výstupy analytiky prejdú schémou | — | ms |
| `tests/api/` | FastAPI `TestClient`: stránky, formuláre, JSON pre grafy | — | s |
| `tests/ai/` | klient Ollama cez `httpx.MockTransport`, `FakeGenerator`, validátor, fallback, orchestrácia | — | ms |
| `tests/ai/` (reálny model) | volania lokálneho `qwen2.5:3b` | `ollama` | s–min |
| `tests/arch/` | pravidlá vrstiev (`domain` bez IO importov), žiadne cloudové AI knižnice ani URL | — | ms |

**Príkazy:**
```bash
pytest -q
pytest -m golden -q
pytest -m "not golden and not ollama" -q
pytest -m ollama -q
pytest --cov=oee --cov-report=term-missing
```
- `pytest -q` spúšťa všetko okrem `ollama`. Zabezpečuje to `addopts = -m "not ollama"` v `pyproject.toml`;
  explicitné `-m` na príkazovom riadku ho prepíše.
- `pytest -m "not golden and not ollama"` je rýchla sada. Vlastné `-m` prepíše predvolené vylúčenie `ollama`,
  preto ho treba zopakovať.
- `pytest -m ollama` sa spúšťa iba na testovacom notebooku.
- **Exit code 5** („no tests collected") pri `-m golden` / `-m ollama` znamená iba, že také testy ešte
  neexistujú. Nie je to chyba kódu.

## 3. Mapa golden hodnôt → testy
| TASK.md | Obsah | Test | Úloha |
|---|---|---|---|
| §12.7 | slajd 11: OEE 79,3 %; slajd 12: OEE 89,7 % | `tests/unit/test_kpi.py` | P0-04 |
| §11.7 + §16 bod 3 | 21 zmien, 168 hodín, 33 udalostí, 112 záznamov zmätkov, všetky kontroly OK; model odvodený zo súboru | `tests/golden/test_import.py` | P0-09 |
| §12.3 | zmena 25.11. celkovo a po hodinách, Pareto, rejects | `tests/golden/test_shift_analytics.py` | P0-10 |
| §12.3 (koniec) | zmena 20.11. | `tests/golden/test_shift_analytics.py` | P0-10 |
| §12.5 | rebríček 1–10, triedy, trendy, tie-break (doména: syntetické testy v P0-11) | `tests/golden/test_ranking_golden.py` | P0-13 |
| §12.8 | Problem Links, presne 5 párov (doména: syntetické testy v P0-12) | `tests/golden/test_links_golden.py` | P0-13 |
| — | vrstvy a zákaz cloudových AI knižníc / URL | `tests/arch/test_layers.py` | P0-01 |
| §12.1, §12.2, §12.4 | mesiac, týždne 45–49, rozpisy | `tests/golden/test_period_analytics.py` | P0-13 |
| §12.6 | patterns P-1…P-7 (má / nemá nájsť) | `tests/golden/test_patterns_golden.py` | P1 |

## 4. Kľúčové hodnoty (rýchly prehľad; autorita = TASK §12)
Platia pre dataset organizátorov. Jeho model zmeny je odvodený zo súboru (60 ks/h, 480 min, prestávka 30, AM 10,
cieľ OEE 0,85 z `Dashboard!E51`, Po–Pi).
**Mesiac 02.–30.11.2026 (21 zmien):**
- Target 9 240, Produced 8 251, Rejects 119, Good 8 132;
- downtime 410 min (33 udalostí), speed loss 579 ks;
- **A 95,56 % · P 93,44 % · Q 98,56 % · OEE 88,01 %**;
- 17/21 zmien splnilo cieľ; 4 pod cieľom (všetky stredy).

**Týždne (OEE):** 45 → 87,68 % · 46 → 88,00 % · 47 → 88,95 % · 48 → 87,09 % · 49 (partial, 1 zmena) → 89,55 %.

**Zmena 25.11.:**
- Target 440, Produced 350 (79,5 %), Rejects 6, Good 344, odchýlka −96 = 48 + 42 + 6;
- **A 89,09 % · P 89,29 % · Q 98,29 % · OEE 78,18 %**;
- hodinový OEE: 84,0 · 71,7 · 88,3 · 51,7 · 80,0 · 73,3 · 88,3 · 90,0 %;
- Pareto: speed loss 42 · ST-038 25 · ST-046 23 · Q-030 3 · Q-020 2 · Q-031 1 (= 96).

**Zmena 20.11.:** Produced 408, Rejects 4, Good 404, OEE 91,82 %.

**Rebríček (§12.5):**
- poradie: ST-038, ST-016, ST-046, ST-001, ST-047, ST-017, Q-031 (všetky A), Q-020, Q-026 (B), Q-030 (C);
- pripnutý riadok: unattributed speed loss 579 ks (52,3 %).

**Problem Links (§12.8):**
- ST-038 → Q-030: same_process, lift 4,80, extra 2,4, low;
- ST-016 → Q-031: cross_process, lift 2,47, medium;
- ST-046 → Q-031: **nie je** väzba (lift 1,93).

## 5. Testovanie AI
- **Bez reálneho modelu (vždy):**
  - `FakeGenerator` vracia pripravené odpovede (správne aj s vymysleným číslom);
  - `MockTransport` simuluje Ollama (200 / timeout / 500 / nevalidný JSON).
- **Validátor:**
  - číslo alebo kód mimo faktov → zamietnutie → 1 opakovanie → fallback;
  - text bez označenia hypotézy pri korelácii → zamietnutie.
- **Fallback:** text pre 25.11. obsahuje fakty z TASK §7.F (OEE 78,2 %, 350 z 440, 79,5 %, 96 ks, ST-038, 25 min,
  09:08).
- **Offline garancia:**
  - test v `tests/arch` zakáže importy `anthropic`, `openai`, `google-genai` / `google.generativeai` a URL mimo
    `localhost` v `src/**/*.py` (vendorované assety v `static/vendor/` sa neskenujú, HTML kontroluje P0-15);
  - konfigurácia odmietne iný host.
- **Reálny model** (`-m ollama`, testovací notebook): kontrolný zoznam v `PLANNING.md`.

## 6. Ručné kontroly
| Kontrola | Kedy |
|---|---|
| Settings: zadanie vlastného modelu zmeny, živý prepočet targetu, „Vyplniť príkladom" | P0-16 |
| Hodinové hlásenie v prehliadači (desktop + šírka tabletu), hodina bez problémov = 2 akcie | P0-17 |
| Dashboard 25.11. vizuálne: KPI karty, waterfall, hodinový graf, tabuľka, Pareto | P0-19 |
| História, rebríček, Problem Links | P0-20, P0-21 |
| Demo scenár TASK §14 od importu po AI zhrnutie | P0-25 |
| Beh bez internetu, reálny Qwen 3B | testovací notebook |

## 7. Definition of Done
**Pre každú úlohu:**
1. Akceptačné kritériá úlohy v `PLANNING.md` splnené.
2. Nové a zmenené testy zelené; celé `pytest -q` zelené.
3. `ruff check` a `mypy` bez chýb.
4. `git diff` skontrolovaný a `spec-reviewer` bez blokujúcich nálezov. Pri výpočtových zmenách aj
   `golden-verifier`.
5. `PLANNING.md` aktualizované: checkbox, denník práce, prípadne denník rozhodnutí.
6. Žiadne nové TODO bez záznamu v `PLANNING.md`; žiadny commit bez požiadavky.

**Pre celé P0:** tabuľka DoD (TASK §16) v `PLANNING.md` vyplnená. Body s reálnym modelom sa overia na
testovacom notebooku.
