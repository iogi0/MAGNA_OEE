# Architektúra — AI OEE Improvement Engine (MVP)

Obchodné požiadavky: `TASK.md` v2.3. Plán úloh: `PLANNING.md`. Testy: `docs/TESTING.md`.

## 1. Ciele architektúry
- **Rýchly MVP v jednom jazyku** (Python), bez build kroku frontendu.
- **Deterministické výpočty:** všetky KPI, straty, rebríček a korelácie počíta čistý doménový kód. Ten sa dá
  otestovať proti golden hodnotám.
- **Lokálne AI a offline beh:** AI beží iba cez Ollama na `localhost`, frontend assety sú vendorované.
  Demo funguje bez internetu.
- **Malé, testovateľné úlohy:** vrstvy s jasnými hranicami a kontraktmi (TASK §10).

## 2. Technologický stack
| Oblasť | Voľba |
|---|---|
| Jazyk | Python ≥ 3.12 |
| Doména | čistý Python (`dataclasses`), bez pandas |
| Web | FastAPI + Jinja2 (server-rendered) + HTMX |
| Grafy | Chart.js 4 (waterfall cez plávajúce stĺpce, Pareto, hodinový OEE) |
| Štýly | Pico.css + `app.css` |
| Assety | vendorované v `src/oee/web/static/vendor/` (žiadne CDN) |
| Databáza | SQLite + SQLAlchemy 2.0 (`create_all` + seed; Alembic až v P2) |
| Kontrakty / konfigurácia | Pydantic v2, pydantic-settings (`.env`, prefix `OEE_`) |
| Import Excelu | openpyxl `read_only=True, data_only=True` (súbor sa nikdy neukladá) |
| Lokálne AI | Ollama HTTP API (`/api/chat`, `format` = JSON schéma) cez httpx, model `qwen2.5:3b` |
| Testy | pytest, pytest-cov, `httpx.MockTransport`, FastAPI `TestClient` |
| Kvalita | ruff (lint + format), mypy (strict pre `domain` a `contracts`) |

## 3. Vrstvy a pravidlo závislostí
```
web  (FastAPI routery, Jinja2 šablóny, HTMX, Chart.js)
  └─► services  (orchestrácia: reporting, analytics, importer, ai_orchestrator)
        ├─► domain       ČISTÉ funkcie: shift_model, downtime, kpi, validation, ranking, correlation, facts
        ├─► persistence  SQLAlchemy modely, session, repozitáre, seed
        ├─► catalog      Top-10 ST/Q + Other, páry same_process (YAML); páky slajdu 13 až v P2
        ├─► contracts    Pydantic: hourly_report, shift_analytics, period_analytics (improvement_plan = P2)
        └─► ai           OllamaClient, prompty, validátor, fallback, cache
```
**Pravidlá:**
- `domain` neimportuje `persistence`, `web`, `ai`, `services`, `httpx`, `sqlalchemy`, `fastapi`.
  Kontroluje to `tests/arch/test_layers.py`.
- `ai` dostáva iba hotové fakty (kontrakty) a vracia text alebo štruktúru. **Nikdy nepočíta KPI.**
- `web` nevolá repozitáre ani modely `persistence` priamo, iba cez `services`. Výnimka: `persistence.db`
  (engine, session dependency, lifespan inicializácia).
- Analytika sa počíta **na požiadanie** z primárnych záznamov (8 alebo 168 hodín = milisekundy).
  Cachuje sa iba výstup AI.

## 4. Moduly a mapovanie na TASK.md
| Modul | Zodpovednosť | TASK.md |
|---|---|---|
| `config.py` | nastavenia (`OEE_*`); validácia: AI URL iba localhost | §13.4, §18 |
| `domain/shift_model.py` | z konfigurácie manažéra: N slotov, plánované minúty, target zmeny/hodiny, `ideal_cycle_s` (žiadne pevné čísla, PLANNING D8) | §3.1–3.2 |
| `domain/downtime.py` | zjednotenie intervalov, vylúčenie AM/prestávky, pokračovania, strop | §3.4 (2–4) |
| `domain/kpi.py` | kaskáda C→D→S→R→G, A/P/Q/OEE cez súčty, identita | §3.3–3.5, §6 |
| `domain/validation.py` | V1–V12, V14 | §5.5 |
| `domain/ranking.py` | ABC, eskalácia, trend, tie-break | §8.4 |
| `domain/correlation.py` | Problem Links: okno, lift, extra rejects, typ, istota | §8.6 |
| `domain/facts.py` | fakty pre AI a šablóny | §7.F, §6.7 |
| `catalog/` | `codes.yaml` (celý číselník 82 kódov), `top10.yaml` (aktívne kódy + kategórie), `links.yaml`, `example_shift_model.yaml` (iba príklad pre tlačidlo „Vyplniť príkladom", demo a testy), loader (`levers.yaml` pre odporúčania — P2) | §5.4, §13.3 |
| `contracts/` | schémy JSON | §10.1–10.3 |
| `persistence/` | tabuľky (§5), session, repozitáre, seed | §9 |
| `services/importer.py` | Excel → entity, idempotentne, kontroly | §11.7–11.8 |
| `services/reporting.py` | zmena so snapshotom, `save_hour`, životný cyklus, revízia | §4.3, §5 |
| `services/analytics.py` | `build_shift` → ShiftAnalytics, `build_period` → PeriodAnalytics | §6–§8, §10.2–10.3 |
| `services/ai_orchestrator.py` | Shift Summary, vysvetlenia Problem Links, background, cache | §7.F, §8.6, §13.4 |
| `ai/client.py` | Ollama `/api/chat`, health, `FakeGenerator` | §13.4 |
| `ai/validator.py`, `ai/fallback.py`, `ai/prompts/` | kontrola čísel/kódov, šablóny, prompty s verziou | §6.7, §13.4 |
| `web/` | stránky, API pre grafy, šablóny, statické súbory | §4.2, §5, §7, §8 |

## 5. Databáza (SQLite)
| Tabuľka | Kľúčové stĺpce | Obmedzenia |
|---|---|---|
| `shift_model` | id, version, line_id, product_id, line_rate_pcs_per_hour, shift_start, shift_length_min (celé hodiny → N slotov), break_min, break_hour_no, break_offset_min, am_min, am_hour_no, am_offset_min, target_oee, working_days, grace_min, active | jeden aktívny na linku; vytvára ho manažér v Settings, neseeduje sa |
| `shift` | shift_id PK (`L01-YYYYMMDD-M`), line_id, product_id, date, shift_code, model_snapshot JSON, status, revision, created/completed/updated_at | UNIQUE(line_id, date, shift_code) |
| `hourly_report` | hour_id PK (`L01-YYYYMMDD-HH`), shift_id FK, hour_no, slot_start/end, planned_min, status (`submitted` / `needs_attention`), submitted_by/at, updated_at, comment | UNIQUE(shift_id, hour_no) |
| `production_record` | hour_id PK/FK, produced_qty, rejects_qty, retests?, microstop_s?, slowdown_s?, source | qty ≥ 0; rejects ≤ produced |
| `issue_type` | code PK (ST-xxx), name_en, name_sk, category, station_id?, active_top10, is_other | seed celý číselník (48 ST); aktívnych 10 + ST-048 (D9) |
| `defect_type` | code PK (Q-xxx), name_en, name_sk, category, active_top10, is_other | seed celý číselník (34 Q); aktívnych 10 + Q-034 (D9) |
| `issue_event` | issue_id PK (uuid), client_key UNIQUE? (iba ručné hlásenia; import ho nemá), hour_id FK, issue_type_code FK, free_text_name, start_at? (celý dátum a čas, nočná zmena), duration_min, continues_issue_id FK? (ON DELETE SET NULL), comment, source, external_ref UNIQUE?, created/updated/deleted_at | soft delete; upsert podľa `client_key` vrátane soft-deleted |
| `quality_record` | quality_id PK, hour_id FK, defect_type_code FK? (NULL = Unspecified), qty, source, external_ref UNIQUE?, comment | Σ qty = rejects_qty hodiny — **aplikačný invariant** (kontroluje služba, nie DB) |
| `ai_output` | id, kind, subject_key, facts_hash, model, lang, prompt_version, status (pending/ok/fallback/error), payload JSON, created_at, updated_at | UNIQUE(kind, subject_key, facts_hash, model, lang, prompt_version) |

`facts_hash` = SHA-256 kanonického JSON faktov (zoradené kľúče). Funguje pre zmenu aj obdobie (obdobie nemá
`revision`). Akákoľvek zmena dát alebo faktov automaticky znamená nový kľúč.

Vzťahy: `shift 1─N hourly_report 1─1 production_record`, kde N = dĺžka zmeny v hodinách zo snapshotu (príklad: 8).
Na `hourly_report` sú naviazané:
`1─N issue_event` a `1─N quality_record`. Kategória je atribútom kódu, preto samostatná tabuľka kategórií nie je
(PLANNING D5).

## 6. Toky
1. **Hodinové hlásenie (operátor):**
   1. `POST /report/{shift_id}/hour/{hour_no}` (formulár HTMX) → `contracts.HourlyReportIn`.
   2. `domain.validation` (V1–V12, V14): chyby sa vrátia inline, varovania nastavia `needs_attention`.
   3. `services.reporting.save_hour` uloží celý stav hodiny: upsert, idempotencia cez `client_key`, soft delete
      chýbajúcich udalostí.
   4. Prepočíta sa stav zmeny. Pri prechode na `completed` sa pridá AI úloha do `BackgroundTasks`.
2. **Shift Dashboard (manažér):**
   1. `GET /shift/{shift_id}` → `services.analytics.build_shift` → `ShiftAnalytics` → šablóna.
   2. Grafy z `GET /api/shift/{shift_id}/charts`.
   3. Blok AI sa načíta cez HTMX (`hx-trigger="load, every 3s"`, kým je `pending`). Dovtedy sa zobrazí fallback
      text.
   4. Ak AI výstup pre aktuálny `facts_hash` chýba (napr. importovaná zmena), prvé načítanie bloku spustí
      generovanie na pozadí.
3. **Production History:** `GET /history?start=&end=` → `build_period` → `PeriodAnalytics` (týždne, mesiac,
   `problem_ranking`, `problem_links`, `unattributed_speed_loss`).
   - Zmeny môžu mať rôzne snapshoty modelu, preto sa agreguje iba cez súčty:
     - target obdobia = Σ targetov zmien;
     - cieľ OEE obdobia = Σ (target × cieľ) / Σ target;
     - úplný týždeň = všetky pracovné dni majú dokončenú zmenu.
4. **Import:** `POST /import` → `services.importer.import_excel(path)`:
   - natural keys (`external_ref`), opakovaný import nič nepridá;
   - snapshot modelu každej zmeny sa odvodí zo súboru (`Ideal_cyklus_s`, `Cas_od`, `Interval_min`, `AM_min`,
     `Pauza_min`, cieľ OEE z `Dashboard!E51`, pracovné dni z dátumov). Nastavenia v Settings sa nemenia.
5. **AI:**
   1. `domain.facts` pripraví fakty.
   2. Prompt (`ai/prompts/*.md`, verzia) → Ollama `/api/chat`: `stream: false`, temperature 0,2,
      `format` = schéma, timeout `OEE_AI_TIMEOUT_S`.
   3. `ai.validator` overí, že všetky čísla a kódy pochádzajú z faktov / Top-10.
   4. Pri neúspechu 1 opakovanie, inak `ai.fallback`. Výsledok uloží `services.ai_orchestrator` do `ai_output`
      (cez repozitár v `persistence`; balík `ai` s databázou nepracuje).

## 7. Webové routy (plán)
| Route | Účel | Úloha |
|---|---|---|
| `GET /` | presmerovanie na `/report` (jedno rozhranie, D14) | P0-15 |
| `GET /report` | dnešná zmena (alebo výber dátumu); bez aktívneho modelu → odkaz na Settings | P0-17 |
| `POST /report` | otvorí / vytvorí zmenu na zvolený dátum so snapshotom aktívneho modelu | P0-17 |
| `GET /report/{shift_id}` | Hourly Reporting: N dlaždíc zmeny | P0-17 |
| `GET/POST /report/{shift_id}/hour/{hour_no}` | formulár hodiny (HTMX) | P0-17 |
| `GET /shift/{shift_id}` | Shift Dashboard A–F | P0-19, P0-24 |
| `GET /api/shift/{shift_id}/charts` | dáta grafov (JSON) | P0-19 |
| `GET /history?start=&end=` | Shift History + Weekly + Monthly (`from` je kľúčové slovo Pythonu — nepoužívať) | P0-20 |
| `GET /history/ranking`, `GET /history/links` | Problem Ranking, Problem Links | P0-21 |
| `GET /ai/{kind}/{subject}` | fragment AI bloku (polling) | P0-24 |
| `GET /settings`, `POST /settings/preview`, `/settings/model`, `/settings/top10` | model zmeny / target (živý prepočet cez HTMX, „Fill with example" = `?example=1`), Top-10 | P0-16 |
| `GET/POST /import` | import datasetu | P0-18 |
| `GET /health` | stav aplikácie a Ollama (bez chyby, ak Ollama nebeží) | P0-15, P0-22 |

## 8. Lokálne AI
**Model a beh:**
- Model `qwen2.5:3b` (Qwen 3B, 4-bit), Ollama na `http://127.0.0.1:11434`. Iný host ako `127.0.0.1` /
  `localhost` konfigurácia odmietne.
- Na vývojovom počítači Ollama **nie je** (PLANNING D2). Testuje sa cez `FakeGenerator` a `MockTransport`,
  reálny model na testovacom notebooku (`.claude/skills/ollama-local`).

**Úlohy v P0:**
- Shift Summary (TASK §7.F);
- vysvetlenia Problem Links (TASK §8.6).

Odporúčania (`improvement_plan`) sú P2 (D1).

**Bezpečnosť faktov:**
- prompt obsahuje iba vypočítané fakty;
- výstup je JSON podľa schémy;
- validátor kontroluje čísla a kódy;
- korelácia sa označuje ako hypotéza.

**Fallback:** šablóny z faktov. Aplikácia je plne funkčná bez Ollama.

## 9. Konfigurácia (`.env`)
| Premenná | Predvolená hodnota | Význam |
|---|---|---|
| `OEE_DB_PATH` | `data/local/oee.db` | SQLite (relatívne voči koreňu projektu) |
| `OEE_DATASET_PATH` | `data/raw/dummy_data.xlsx` | dataset pre import a golden testy (relatívne voči koreňu projektu) |
| `OEE_OLLAMA_URL` | `http://127.0.0.1:11434` | iba 127.0.0.1 / localhost |
| `OEE_OLLAMA_MODEL` | `qwen2.5:3b` | lokálny model |
| `OEE_AI_ENABLED` | `true` | vypnutie AI → vždy fallback |
| `OEE_AI_LANG` | `en` | jazyk odpovedí AI (`en` / `sk`) |
| `OEE_AI_TIMEOUT_S` | `30` | timeout jedného volania |

## 10. Implementačné pravidlá a známe pasce
Overené 10.11.2026 na tomto počítači: Windows 10, Python 3.14, testovacia inštalácia závislostí. Každé pravidlo
nižšie bráni konkrétnej chybe, ktorá sa pri implementácii reálne objaví.

### 10.1 Prostredie a súbory
| Pravidlo | Prečo |
|---|---|
| Každé `open()`, `read_text()`, `write_text()` s `encoding="utf-8"` | Predvolené kódovanie je **cp1251** a Python 3.14 nemá UTF-8 mód. YAML, prompty a texty so slovenčinou by sa poškodili. Stráži to ruff `PLW1514`. |
| Výpis UTF-8 textu do konzoly: `sys.stdout.reconfigure(encoding="utf-8")` alebo `PYTHONIOENCODING=utf-8` | Inak `UnicodeEncodeError` (cp1251 konzola). |
| Cesty k šablónam, statike, promptom a YAML cez `Path(__file__)` / `importlib.resources`; relatívne cesty z `.env` rozlišovať voči koreňu projektu | Spustenie z iného priečinka (pytest, uvicorn, skript) by nenašlo súbory. |
| `pydantic-settings`: `env_file_encoding="utf-8"`; aplikácia cez továreň `create_app(settings)`; testy vytvárajú `Settings` explicitne s `_env_file=None` | Testy nesmú čítať vývojárov `.env` ani zapisovať do `data/local/oee.db`. |
| Závislosti inštalovať s `-c constraints.txt` (vzniká v P0-01) | pip inak berie najnovšie hlavné verzie (dnes SQLAlchemy 2.1, Starlette 1.x, pytest 9, mypy 2); notebook musí mať rovnaké verzie. |

### 10.2 SQLite a SQLAlchemy
| Pravidlo | Prečo |
|---|---|
| Pri každom pripojení `PRAGMA foreign_keys=ON` (event `connect`) | SQLite má cudzie kľúče predvolene **vypnuté** (overené: `0`) — FK by sa ticho ignorovali. |
| `connect_args={"check_same_thread": False}`; WAL + `busy_timeout` | FastAPI volá sync endpointy a background úlohy v iných vláknach; inak „SQLite objects created in a thread…" a „database is locked". |
| Pred vytvorením DB vytvoriť priečinok (`mkdir(parents=True, exist_ok=True)`) | Inak „unable to open database file". |
| Testy: `sqlite://` + `StaticPool` (jedna zdieľaná in-memory DB); pri súborovej DB `engine.dispose()` pred zmazaním | In-memory DB je inak pre každé spojenie iná (tabuľky „zmiznú"); na Windows zamknutý súbor = `PermissionError`. |
| Množstvá `Integer`, minúty a percentá `Float`; nepoužívať `Numeric`/`Decimal` | SQLite nemá natívny Decimal (varovania, strata presnosti). |
| Invarianty naprieč tabuľkami (Σ quality = rejects_qty, N/N hodín) kontroluje služba v transakcii | SQLite CHECK nevidí iné tabuľky. |
| Každý FK stĺpec modelu má many-to-one `relationship(lazy="raise")` (iba na poradie INSERT-ov, nenačítava sa) | Bez `relationship()` SQLAlchemy neradí INSERT podľa FK → pri vložení rodiča a detí v jednom flush-i „FOREIGN KEY constraint failed“ (overené v P0-10). |

### 10.3 Dátum a čas, čísla
| Pravidlo | Prečo |
|---|---|
| Časy zmeny a slotov = **naivný lokálny čas linky** ako `datetime` (zmena môže prechádzať cez polnoc); auditné timestampy = **naivný UTC**; nikdy ich nemiešať v porovnaní | Porovnanie naive vs aware = `TypeError`; SQLite časovú zónu neukladá. |
| „Teraz" sa do domény a služieb odovzdáva ako parameter (`now`/`clock`); `incomplete` sa vyhodnocuje pri čítaní | Testovateľnosť a v MVP nie je plánovač úloh. |
| Výpočty vo `float`, porovnanie `math.isclose(..., abs_tol=1e-9)`; zaokrúhľovať iba na výstupe jednou funkciou (ROUND_HALF_UP) | Identita C − D − S − R = G pri targete 366,67 inak „nesedí"; Python `round()` zaokrúhľuje bankársky (`round(2.5)` = 2, `round(0.125, 2)` = 0.12). |

### 10.4 Excel (openpyxl)
| Pravidlo | Prečo |
|---|---|
| `load_workbook(path, read_only=True, data_only=True)` a vždy `wb.close()` (try/finally) | Read-only zošit drží súbor otvorený — na Windows zamknutý súbor. |
| Stĺpce mapovať podľa **názvov v hlavičke** (1. riadok); nespoliehať sa na `ws.tables` (`tblVyroba` …) | V read-only režime `ws.tables` **neexistuje** (overené). |
| Trvanie udalosti z `Cas_do − Cas_od`, zaokrúhlené na celé sekundy | Prevod Excel serial → datetime môže mať mikrosekundové odchýlky. |
| Import v jednej transakcii (pri chybe rollback); súbor nikdy neukladať | Čiastočný import = nekonzistentné dáta a duplicity; uloženie zničí grafy. |

### 10.5 FastAPI / Starlette 1.x / HTMX
| Pravidlo | Prečo |
|---|---|
| `templates.TemplateResponse(request, "x.html", {...})` — `request` ako 1. argument | Stará syntax `TemplateResponse("x.html", {"request": request})` padá v Starlette 1.10 na `TypeError` (overené). |
| Inicializácia cez `lifespan`, nie `@app.on_event` | `on_event` je deprecated (overené varovanie). |
| V testoch `with TestClient(app) as client:` | Inak sa nespustí lifespan (DB, seed). |
| Background úloha si otvára **vlastnú** DB session | Session požiadavky je po odpovedi zatvorená. |
| Query parametre nepomenúvať kľúčovými slovami (`from`) → `start`, `end` | `from` nemôže byť názov parametra funkcie. |
| HTMX polling zastaviť: po dokončení vrátiť fragment bez `hx-trigger` (alebo HTTP 286) | Inak polling beží donekonečna. |
| Varovanie „Using httpx with starlette.testclient is deprecated" je filtrované v `pyproject.toml` | Je to iba deprecation v Starlette 1.x. |

### 10.6 Lokálne AI (Ollama)
| Pravidlo | Prečo |
|---|---|
| `/api/chat` vždy s `"stream": false` | Predvolene Ollama streamuje NDJSON → `response.json()` zlyhá. |
| Base URL `http://127.0.0.1:11434` | Na Windows sa `localhost` môže preložiť na IPv6 `::1`, Ollama počúva na IPv4. |
| AI úlohy spracúvať sekvenčne (jedna fronta / zámok) | Paralelné volania sa v Ollama radia do fronty a padajú na timeout. |
| Pred generovaním vložiť riadok `pending` (UNIQUE kľúč); pri konflikte negenerovať znova; `pending` starší ako 2 × timeout = zlyhanie → nový pokus / fallback | Dvojité spustenie (dokončenie zmeny + otvorenie stránky) = `IntegrityError`; pád procesu = večný `pending`. |
| Validátor parsuje čísla podľa `OEE_AI_LANG`: `en` „9,240" a „78.2"; `sk` „9 240" (aj NBSP) a „78,2". Časy (09:08), dátumy a kódy (ST-038) sa kontrolujú osobitne. Zhoda = rozdiel ≤ polovica poslednej zobrazenej číslice. | Inak falošné zamietnutia („9,240" ako 9,24) a zamietnutie korektne zaokrúhlených čísel (78,2 vs 78,18). |

### 10.7 Frontend assety
Stiahnutie htmx, Chart.js a Pico.css (presné verzie z npm registry / jsDelivr) vyžaduje sieť a súhlas vlastníka.
Verzie sa zapíšu do `src/oee/web/static/vendor/VERSIONS.md`. Do HTML sa linkujú iba lokálne.
