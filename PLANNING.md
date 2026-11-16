# PLANNING.md — roadmap MVP

Zdroj požiadaviek: `TASK.md` v2.3. Pravidlá práce: `CLAUDE.md` (cyklus `task-cycle`: jedna úloha → stop → súhlas).

## Stav
| | |
|---|---|
| **Aktuálna fáza** | M1 Základ |
| **Ďalšia úloha** | P0 hotové — overenie reálneho Qwen 3B na testovacom notebooku, potom P1 (čaká na súhlas vlastníka) |
| **Hotové úlohy** | 25 / 25 (P0) |
| **Posledná aktualizácia** | 11.11.2026 |

### Denník práce
| Dátum | Úloha | Výsledok |
|---|---|---|
| 10.11.2026 | PREP | Vytvorené: CLAUDE.md, AGENTS.md, README.md, PLANNING.md, docs/, .claude/agents, .claude/skills, pyproject.toml, kostra `src/oee`, `tests/`, dataset v `data/raw/`, `git init` (bez commitov). Závislosti ani Ollama v projekte neinštalované. |
| 10.11.2026 | PREP-CHECK | Skúšobná inštalácia v dočasnej kópii (mimo projektu) na Python 3.14: `pip install -e ".[dev]"` OK, pytest 1 passed, ruff a mypy OK. Opravené: dlhý riadok v `contracts/__init__.py` (ruff E501), pravidlo PLW1514 (kódovanie), horné hranice verzií, `tests/__init__.py`, `.gitattributes`, filter varovania Starlette. Overené pasce → ARCHITECTURE §10. |
| 10.11.2026 | P0-01 | `.venv` (Python 3.14.3), `constraints.txt` (44 balíkov: fastapi 0.162.4, starlette 1.10.0, SQLAlchemy 2.1.8, pydantic 2.14.3, pytest 9.2.0, mypy 2.4.1, ruff 0.17.4). `src/oee/config.py` (prefix `OEE_`, UTF-8 `.env`, cesty voči koreňu, Ollama iba localhost/127.0.0.1, `ai_lang` en/sk). `tests/unit/test_config.py`, `tests/arch/test_layers.py` (doména bez IO/vrstiev/pandas, žiadne cloudové AI importy, URL ani závislosti). **52 passed**, ruff + mypy OK. Revízia spec-reviewer: bez blokujúcich nálezov. |
| 10.11.2026 | D11 + P0-02 | D11: `OEE_AI_LANG` iba `en`/`sk` (`uk` odstránené z kódu, testov, ARCHITECTURE, agenta a skillu). P0-02: `src/oee/domain/shift_model.py`: `ShiftModelConfig` (výkon, začiatok, dĺžka v min = N × 60, `Allowance` prestávky/AM s hodinou a posunom, cieľ OEE, pracovné dni), `validate_shift_model` → zoznam `ConfigIssue`, `build_shift_plan` → `ShiftPlan` (N slotov ako `datetime`, cez polnoc, plánované minúty, targety, `ideal_cycle_s`), `ShiftModelError`. Prestávka a AM sa v jednej hodine nesmú prekrývať. Bez pevných čísel (D8). `tests/unit/test_shift_model.py` (37 testov: príklad, 50 ks/h, 6 h / 45 ks/h, nočná zmena, chyby). **93 passed**, ruff + mypy OK. spec-reviewer: bez blokujúcich nálezov. |
| 10.11.2026 | P0-03 | `src/oee/domain/downtime.py`: `count_downtime(plan, events)` → `DowntimeSummary` (segmenty s `counted_min` a `root_id`, minúty po hodinách, súčet, frekvencia). Zjednotenie prekryvov, vylúčenie okien AM/prestávky, orezanie na slot, strop plánovanými minútami, pokračovania (reťaze, neznámy cieľ, cyklus). `shift_model`: `HourSlot.allowance_windows` (okná z hodiny + posunu). Pravidlá → D10. `tests/unit/test_downtime.py` (32 testov) + 3 testy okien. **131 passed**, ruff + mypy OK. spec-reviewer: bez blokujúcich nálezov. |
| 10.11.2026 | P0-04 | `src/oee/domain/kpi.py`: `Cascade` (sčítateľné primárne veličiny: planned/downtime min, target C, strata D v ks, produced, rejects; odvodené S, G, odchýlka, A/P/Q/OEE, `goal_gap_pp`), `Cascade.from_minutes`, `sum_cascades`. Rozhodnutie D12 (KPI v kusoch). `tests/fixtures/slides.yaml` (slajdy 11, 12) + `tests/unit/test_kpi.py` (25 testov: slajdy 79,3 % / 89,7 %, identita, súčet hodín = zmena, obdobie s rôznym taktom, Run = 0, Produced = 0, záporná S). **159 passed**, ruff + mypy OK. spec-reviewer: bez blokujúcich nálezov. |
| 10.11.2026 | P0-05 | `src/oee/domain/validation.py`: `validate_hour(plan, hour, other_issues, codes)` → `ValidationMessage{level, rule, field, message}` (chyby pred varovaniami), `has_errors`; vstupy `HourInput`, `IssueInput`, `RejectLine`, `ActiveCodes` (Top-10 + Other ako parameter). V1–V12, V14 + varovanie D10 (presah slotu bez pokračovania). Oprava z revízie: V7 neporovnáva udalosť s jej pokračovaním. `tests/unit/test_validation.py` (55 testov vrátane 6 h / 45 ks/h a nočnej zmeny). **217 passed**, ruff + mypy OK. spec-reviewer: 1 nález opravený. |
| 10.11.2026 | P0-06 | `scripts/extract_codebook.py` (read-only Excel → `codes.yaml`, 82 kódov, ST-016 = camera; Excel overený kontrolným súčtom ako nezmenený). `src/oee/catalog/`: `top10.yaml` (10 ST + ST-048, 10 Q + Q-034, kategórie a ich názvy), `links.yaml` (5 procesov same_process), `example_shift_model.yaml` (D8), `loader.py` (`load_catalog` → `Catalog` s `category_of`, `category_name`, `active_codes`, `link_type`; `load_example_shift_model` cez doménovú validáciu; `CatalogError`). `tests/unit/test_catalog.py` (54) + `tests/golden/test_catalog_dataset.py` (2, voči Excelu). **275 passed**, ruff + mypy OK. spec-reviewer: bez blokujúcich nálezov. |
| 10.11.2026 | P0-07 | `src/oee/contracts/`: `common.py` (`Contract`: extra=forbid, frozen, aliasy `from`/`class`; typy kódov, striktné počty, `HHMM`), `hourly_report.py` (`HourlyReport`, `HourlyReportResponse`), `shift_analytics.py`, `period_analytics.py`. Príklady TASK §10 ako platný JSON v `tests/fixtures/*.json` (hodina 4 zmeny 25.11. podľa §12.3). `tests/contract/test_schemas.py` (73 testov: príklady, round-trip, aliasy, nevalidné vstupy, provisional `null`, iná dĺžka zmeny). **356 passed**, ruff + mypy (strict) OK. spec-reviewer: bez blokujúcich nálezov, pripomienky zapracované. |
| 10.11.2026 | P0-08 | `src/oee/persistence/`: `db.py` (`make_engine` — súbor s priečinkom a WAL / in-memory `StaticPool`; `foreign_keys=ON`, `busy_timeout`, `check_same_thread=False`; `init_db`), `models.py` (9 tabuliek podľa ARCHITECTURE §5 s CHECK a UNIQUE; 1 aktívny model zmeny na linku), `repositories.py` (`replace_hour_quality` — invariant Σ qty = rejects, „Unspecified"; soft delete; `find_issue_by_client_key` vrátane zmazaných), `seed.py` (číselník + Top-10, nemení výber manažéra, model zmeny sa neseeduje). `tests/conftest.py` (fixtures `engine`, `session`). `tests/unit/test_persistence.py` (36 testov). ARCHITECTURE §5 zladené. **400 passed**, ruff + mypy OK. spec-reviewer: bez blokujúcich nálezov, pripomienky zapracované. |
| 10.11.2026 | P0-09 | `src/oee/services/importer.py`: `import_excel(session, path, now)` → `ImportResult` (počty, preskočené hodiny, odvodené modely, kontroly §11.7 po zmenách); read-only čítanie, stĺpce podľa hlavičky, model zmeny zo súboru, prirodzené kľúče, jedna transakcia, `DatasetError`. `domain/shift_model`: `config_to_snapshot` / `config_from_snapshot` (katalóg ich využíva). `QualityLine.external_ref`. Testy: `tests/golden/test_import.py` (6 — 21/168/33/112, 119 ks, 8251, 410 min, model → target 440, opakovaný import = 0, kontroly OK, Excel nezmenený), `tests/unit/test_importer.py` (23 — 6 h / 45 ks/h, nočná zmena, poškodené dáta, rollback, doplnenie hodín). **435 passed** (8 golden), ruff + mypy OK. golden-verifier: §12.1 (88,01 %) a §12.3 (78,18 %) z DB sedia. spec-reviewer: bez blokujúcich nálezov, pripomienky zapracované. |
| 10.11.2026 | P0-10 | `src/oee/services/analytics.py`: `build_shift(session, shift_id, catalog, now)` → `ShiftAnalytics` (hlavička, model, KPI, target vs actual, waterfall, straty podľa kategórie, zmätky, hodiny, udalosti, Pareto, data_quality V3). Nový `domain/losses.py` (Pareto, príznaky, stav cieľa); `kpi.ratio`/`EPS` verejné; `validation.speed_loss_exceeds_tolerance`; `repositories.active_issues_for_hours`; kontrakt: `DefectQty.code` môže byť `null`, `IssueRow.comment`, `ParetoBucket.category`. Oprava pasce: many-to-one vzťahy v modeloch (poradie INSERT-ov). Testy: `tests/golden/test_shift_analytics.py` (10, §12.3 + 20.11.), `tests/golden/conftest.py` (spoločný import), `tests/unit/test_analytics_shift.py` (8, 6 h / 45 ks/h, provisional), `tests/unit/test_losses.py` (11). Skilly: TDD, systematic-debugging (FK poradie INSERT), golden-verifier (všetko PASS), spec-reviewer (bez blokujúcich), /simplify (4 revízie, zapracované), verification-before-completion. **469 passed** (18 golden), ruff + mypy OK. |
| 10.11.2026 | P0-11 | `src/oee/domain/ranking.py`: `rank_problems(problems, weeks, period_target, all_losses, settings)` → `RankedProblem` (ABC 80/95 z kumulatívneho podielu pred položkou, eskalácia ↑ a ≥ 5 %, tie-break kusy → frekvencia → posledný výskyt → kód, trend na zmenu z úplných týždňov, n/a, D10). `RankingSettings` s prahmi z TASK. `tests/unit/test_ranking.py` (28). TDD; spec-reviewer: bez blokujúcich, logika ručne overená voči §12.5; doplnené C → B a ochrana pri 1 týždni. |
| 10.11.2026 | P0-12 | `src/oee/domain/correlation.py`: `find_problem_links(hours, events, stop_codes, defect_codes, same_process, stop_lost_pcs, settings)` → `PairResult` (okná hodina + nasledujúca v zmene, zjednotenie, základná miera mimo okien, lift, extra, typ, istota, súhrnný vplyv, stav link / below_threshold / insufficient_data). `LinkSettings` s prahmi z TASK. `tests/unit/test_correlation.py` (23). TDD + systematic-debugging (chybné testovacie dáta istoty); spec-reviewer: bez blokujúcich, logika overená voči §12.8; pripomienky zapracované. |
| 10.11.2026 | P0-13 | `services/analytics.py`: spoločné jadro `_ShiftCore`/`_compute` (segmenty raz), `build_period` (súčty, cieľ obdobia, FPQ, ISO týždne s úplnosťou, issue/defect stats, speed loss po hodinách zmeny, rebríček cez `domain.ranking`, väzby cez `domain.correlation`). Nový čistý `domain/period.py` (`period_goal`, `first_pass_quality`, `is_week_complete`). `pyproject`: pydantic mypy plugin. Testy: golden `test_period_analytics.py`, `test_ranking_golden.py`, `test_links_golden.py` (spoločná fixture `month`), unit `test_analytics_period.py`, `test_period.py`, `tests/builders.py`. Skilly: golden-check + golden-verifier (§12.1, §12.2, §12.4 vrátane OEE podľa dňa a hodiny, §12.5, §12.8 — všetko PASS), spec-reviewer (bez blokujúcich), /simplify (pripomienky zapracované), verification. **565 passed (37 golden)**, ruff + mypy OK. |
| 11.11.2026 | P0-14 | `src/oee/services/shift_models.py` (`activate_shift_model` — verzie, 1 aktívny na linku; `get_active_model`), `src/oee/services/reporting.py` (`open_shift`, `save_hour` → `SaveResult`, `effective_status`, `NoActiveShiftModel`; jedna transakcia, idempotencia, soft delete, revision). Importer berie `SHIFT_CODE` z reporting. `tests/unit/test_reporting.py` (29: bez modelu, nová verzia, snapshot, importovaná zmena, chyby / varovania, idempotencia, obnova, pokračovanie, V7 naprieč hodinami, 8 h aj 6 h → completed, revision, incomplete po grace, rollback chybových vetiev, nočná zmena). TDD + systematic-debugging (testovacie dáta nad target hodiny); spec-reviewer: bez blokujúcich, pripomienky zapracované; verification. **598 passed (37 golden)**, ruff + mypy OK. |
| 11.11.2026 | P0-15 | Vendorované so súhlasom vlastníka: htmx 2.0.11, Chart.js 4.6.1, Pico.css 2.1.1 (`static/vendor/VERSIONS.md` so SHA-256). `src/oee/web/app.py`: `create_app(settings)`, `lifespan` (priečinok + schéma DB, seed číselníka, katalóg, `dispose`), session dependency, stránky `/report`, `/shift`, `/history`, `/settings`, `/import` (kostry; `/report` bez modelu odkazuje na Settings), `/healthz`, prepínač roly (cookie, ochrana pred open redirect), `/` → `/report`. Šablóny `base.html` + stránky, `static/app.css`. Nové nastavenie `OEE_LINE_ID` (predvolene L01). Arch test skenuje aj šablóny a nevendorované JS/CSS. `.claude/launch.json` (uvicorn 127.0.0.1:8000). Testy `tests/api/test_pages.py` (23, aj stránky s aktívnym modelom 6 h / 75 ks/h). Prezentačné filtre `num` a `pct` (výpočty mimo šablón). **630 passed**, ruff + mypy OK. spec-reviewer: bez blokujúcich, pripomienky zapracované. Ručne v prehliadači: navigácia, prepínač roly, všetky požiadavky iba na 127.0.0.1, bez chýb v konzole. |
| 11.11.2026 | P0-16 | `src/oee/services/codebook.py` (`get_active_codes` z DB, `list_codes`, `set_top10` — presne 10 ST + 10 Q, bez duplicít, neznámych kódov a „Other"; Other vždy aktívne; `Top10Error`). `src/oee/web/forms.py` (formulár → `ShiftModelConfig`: dĺžka v h, cieľ OEE v %, chyby prevodu + doménová validácia s názvom poľa; prázdny formulár bez predvolených hodnôt, D8). Routy `GET /settings` (`?example=1` = Fill with example, nič neukladá), `POST /settings/preview` (HTMX fragment, čísla z `build_shift_plan`), `POST /settings/model` (422 pri chybe, inak nová verzia + 303), `POST /settings/top10`. Šablóny `settings.html`, `_model_preview.html`. `domain/shift_model`: `ShiftPlan.goal_good_pcs`. Katalóg: `load_example_settings` (+ `product`, `grace_min` v príklade; grace 60 podľa TASK §4.3). Testy: `tests/unit/test_codebook.py` (11), `tests/api/test_settings.py` (24: 6 h / 45 ks/h, nevalidné vstupy, snapshot starých zmien, Top-10, deaktivovaný kód → V11 a zostáva v histórii), +2 katalóg, +1 doména. TDD; spec-reviewer: bez blokujúcich, pripomienky zapracované (cieľ v kusoch v doméne, hodiny mimo šablóny, bez default grace, silnejšie testy). **671 passed (37 golden)**, ruff + mypy OK. Ručne v prehliadači: Fill with example (440 / 374), živý prepočet (45 ks/h → 330), chyba prestávky mimo zmeny, Top-10; bez chýb v konzole (do DB sa v prehliadači neukladalo). |
| 11.11.2026 | P0-16 úpravy (D14) | Odstránený prepínač operátor / manažér (route `/role`, cookie, `data-role`, CSS), texty UI bez rolí. „Save shift model" je hlavné tlačidlo, „Fill with example" malé sekundárne. Testy rolí nahradené `test_single_interface_without_roles` a `test_role_endpoint_is_gone`. **674 passed**, ruff + mypy OK; tlačidlá overené v prehliadači. |
| 11.11.2026 | P0-16 úpravy (D15) | Ručný výber Top-10 nahradený číselníkom: `services/codebook.py` (`get_active_codes` = všetky kódy + Other, `list_codes`, `code_categories`, `add_code` — ďalšie číslo v rade, kontrola názvu, duplicity a kategórie, `CodeError`). Settings: zoznam ST / Q a formulár „Add a problem code" (`POST /settings/codes`). Texty V11 bez „Top-10". Testy prepísané (`test_codebook.py` 10, `test_settings.py`). **674 passed (37 golden)**, ruff + mypy OK; overené v prehliadači. |
| 11.11.2026 | P0-17 | `services/reporting.py`: `shift_overview` (hlavička, N dlaždíc: stav, Produced, Rejects, počet problémov, target hodiny), `hour_state` (predvyplnenie, udalosti predchádzajúcej hodiny na pokračovanie; „Unspecified" sa neukazuje). `web/forms.py`: `parse_hour_form` (prevod polí, Rejects predvolene 0, chyby prevodu bez 500). Routy `GET/POST /report` (výber dňa, predvolene dnes; bez modelu → odkaz na Settings, 422), `GET /report/{shift_id}?hour=n`, `POST /report/{shift_id}/hour/{n}` (HTMX fragment s chybami alebo `HX-Redirect`; bez JS 303/422), `GET …/row?kind=issue|defect` (HTMX „+ Add problem / defect", celý číselník + Other, D15). Šablóny `report.html`, `report_shift.html`, `_hour_form.html`, `_issue_row.html`, `_defect_row.html`. Testy `tests/api/test_hourly_reporting.py` (31, konfigurácia 6 h / 45 ks/h). spec-reviewer: bez blokujúcich, pripomienky zapracované (banner podľa stavu zmeny, jeden `now_local`, zrozumiteľná chyba). **704 passed (37 golden)**, ruff + mypy OK. Ručne v prehliadači (dočasná DB v scratchpade): hodina na 2 akcie (55 → Enter → 1/8), Other bez komentára → inline chyba, hodnoty zostanú; bez chýb v konzole. |
| 11.11.2026 | P0-18 (+ úprava P0-17) | `GET /import` (nakonfigurovaný dataset `OEE_DATASET_PATH`, tlačidlo neaktívne, ak súbor chýba), `POST /import` volá tú istú službu `import_excel` a ukáže počty (zmeny, hodiny, udalosti, záznamy zmätkov, preskočené hodiny), odvodený model zmeny a kontroly TASK §11.7 po zmenách (✓ / ✗ / —); `DatasetError` → 422, nič sa neimportuje. `importer._read`: `OSError` (napr. zamknutý súbor) → `DatasetError`. Šablóna `import.html`, filter `hours`. P0-17: tlačidlo „Open shift" zarovnané s výberom dátumu (`.inline-form`). Testy `tests/api/test_import_page.py` (6: počty 21/168/33/112, 21/21 kontrol, opakovaný import 0 + 168 preskočených, Excel nezmenený (SHA-256), chýbajúci a poškodený súbor, zlyhaná a neoveriteľná kontrola). spec-reviewer: bez blokujúcich, pripomienky zapracované. **711 passed (37 golden)**, ruff + mypy OK. Ručne v prehliadači (dočasná DB): 21/168/33/112, 21/21 zmien OK; bez chýb v konzole. |
| 11.11.2026 | P0-18 doplnok | Vzorový Excel na stiahnutie (požiadavka vlastníka): `services/import_template.py` `build_example_workbook` — hárky `Instructions` (popis stĺpcov), `Vyroba_hodiny`, `Prestoje`, `NOK_detail`, `Dashboard!E51`; hlavičky = konštanty importéra, model zmeny z `example_shift_model.yaml` (D8), kódy z katalógu; generuje sa v pamäti, dataset sa nečíta. Route `GET /import/example.xlsx`, odkaz hneď pod „Import dataset". Testy: `tests/unit/test_import_template.py` (2: hlavičky; vzor sa importuje bez chýb, všetky kontroly §11.7 OK), +1 API. systematic-debugging: importér odvodzuje pracovné dni z dátumov v súbore (očakávané). **716 passed (37 golden)**, ruff + mypy OK; overené v prehliadači. |
| 11.11.2026 | P0-19 | `domain/losses.group_by_category` (Pareto podľa kategórie, súčty bez zdvojenia). `services/shift_view.py`: `status_label` (completed / in_progress n/N — provisional / incomplete cez `effective_status` / edited), `sorted_issues` (čas, dĺžka, vplyv), `group_issues` (bez zlúčenia), `pareto`, `waterfall_steps`, `charts_payload`. Routy `/shift` (výber, `?id` → presmerovanie s escapovaním), `/shift/{id}?sort=&group=&pareto=`, `/api/shift/{id}/charts`. Šablóna `shift.html` (A: 4 KPI karty, stav voči cieľu v p. b., D/S/R v kusoch; B: waterfall + tabuľka; C: hodinový OEE s čiarou cieľa, ▼ pod cieľom, ⏱ prestoj ≥ 5 min, „not submitted"; D: udalosti, triedenie, zoskupenie, zmätky; E: Pareto typ / kategória), `static/shift_charts.js` (vendorovaný Chart.js, iba kreslí; hranice waterfallu pripraví server). Filtre `signed`, `pp`, `pct2`. Testy: `tests/api/test_shift_dashboard.py` (15; golden 25.11. = §12.3, API = ShiftAnalytics, JS bez aritmetiky, provisional 6 h / 45 ks/h), +2 doména. spec-reviewer: bez blokujúcich, pripomienky zapracované. **736 passed (46 golden)**, ruff + mypy OK. Ručne v prehliadači (dočasná DB s importom): A–E pre 25.11. sedia s §12.3, 3 grafy vykreslené, bez chýb v konzole. Mimo rozsahu: stĺpec waterfallu „Technical losses" nie je rozložený podľa kategórií (kategórie majú minúty, nie kusy); podtabuľka zmätkov ukazuje typ a počty po hodinách oddelene (kontrakt nemá hodinu × typ). |
| 11.11.2026 | P0-19 úpravy | Podľa vlastníka: tlačidlo „Show" zarovnané so `select` (`.inline-form select`); grafy v kontajneri s pevnou výškou (`.chart-box`, `maintainAspectRatio: false`), tabuľka waterfallu pod grafom; popisy hodnôt nad stĺpcami (waterfall: hodnota so znamienkom zo servera `waterfall_steps[].value`), čiara cieľa OEE cez celú šírku s popisom na pozadí. Test JS spresnený: zakázaná aritmetika nad dátami zo servera, pixelová geometria plátna povolená. **736 passed**; overené v prehliadači. |
| 11.11.2026 | P0-19 úpravy 2 | Odsadenie pod výberom zmeny (`.inline-form` margin-bottom). Waterfall: spojnice schodov (úrovne `waterfall_steps[].connect` zo servera — Target → C−D → Produced → Good; JS ich iba kreslí), zaoblené stĺpce. Test API rozšírený o úrovne spojníc. **736 passed**; overené v prehliadači. |
| 11.11.2026 | UI mierka | Podľa vlastníka kompaktnejšie UI (`static/app.css`): základné písmo 15 px (Pico na širokých obrazovkách zväčšoval až na 125 %), menšie nadpisy, odsadenia a polia formulárov, šírka obsahu max. 1200 px, menšie KPI karty a dlaždice, grafy 15rem. Iba CSS; overené v prehliadači (1400 px), bez chýb v konzole. |
| 11.11.2026 | UI grafy | Grafy v ráme (`.chart-box`: pozadie karty, jemný okraj, zaoblenie, tieň, vnútorný odstup; výška 17rem). Popis čiary cieľa s pozadím karty. Overené v prehliadači, testy dashboardu prechádzajú. |
| 11.11.2026 | UI grafy 2 | Popis „OEE goal" sa kreslí za koncom čiary v rezervovanom pravom okraji grafu (`layout.padding.right`), v dvoch riadkoch, mimo stĺpcov. Overené v prehliadači, bez chýb v konzole. |
| 11.11.2026 | P0-20 | `domain/period.py`: `top_by_frequency` (D15: výskyty ↓, minúty/kusy ↓, kód; doplnenie štartovacím zoznamom s nulami), `losses_by_category`. `services/history.py`: ISO týždeň / mesiac (`parse_week`, `parse_month`, `neighbour_periods`), `shift_history` (riadok = `build_shift` + stav dát a cieľa), `top10`, `category_losses`, `series_payload`. Routy `/history` (filter dátumov, predvolene mesiac poslednej zmeny), `/history/week?week=YYYY-Www`, `/history/month?month=YYYY-MM` (422 pri chybnom období), navigácia ‹ ›. Šablóny `history.html`, `history_period.html`, `_history_tabs.html`; `static/history_charts.js` (OEE po zmenách s cieľom, klik → dashboard; trend OEE/A/P/Q po týždňoch). Mesiac: tabuľka typov, straty podľa kategórie, zmätky podľa typu, týždne s „partial", Top-10 z rebríčka s pripnutou nepriradenou stratou rýchlosti; týždeň: najčastejšie a najdlhšie problémy. Testy: `tests/api/test_history.py` (16: 21 riadkov, filter, §12.1, §12.2, Top-10 november a prázdna DB, nový kód v Top-10, navigácia, 422, JS bez aritmetiky), +4 doména. spec-reviewer: bez blokujúcich. **760 passed (55 golden)**, ruff + mypy OK. Ručne v prehliadači (1400 px): všetky 3 záložky, grafy, bez chýb v konzole. Pozn.: vstavaný Chromium nezobrazuje `input type=month/week` → textové pole so vzorom + tlačidlá ‹ ›. |
| 11.11.2026 | P0-21 | `services/analytics._links`: páry z Top-10 najčastejších kódov obdobia (`top_by_frequency`, D15) namiesto `active_top10`; kategória prestoja z DB + nové `Catalog.process_for_category` (kód zo Settings dostane správny typ väzby). `services/history.py`: `ranking_view` (väzby pri riadku — iba informácia), `linked_defects_by_stop`, `TREND_ARROWS`. Routy `/history/ranking`, `/history/links` (`?month` alebo `?week`), záložky v histórii. Šablóna `history_analysis.html`: Ranking s pripnutým riadkom „Unattributed speed loss" (odkaz na `#speed-by-hour` v mesiaci), triedy A/B/C, trend ↑↓→, „linked + combined impact" mimo skóre; Links: 5 párov, okno, lift, extra, typ, istota, „Correlation is not a proven cause". Dashboard zmeny: odznak „linked defect Q-xxx" pri udalosti (väzby za mesiac zmeny). Mesiac: sekcia nepriradenej straty rýchlosti po hodinách zmeny. Filter `num1` (odhady na 1 desatinné miesto, bez „-0"). Testy: `tests/api/test_ranking_links_pages.py` (11, golden §12.5 a §12.8), +2 analytika (nový kód vo väzbách, same_process z kategórie), +1 katalóg. Oprava pasce: `Result.tuples()` je v SQLAlchemy 2.1 deprecated → rozbalenie riadkov. spec-reviewer: bez blokujúcich, pripomienky zapracované. **774 passed (63 golden)**, ruff + mypy OK. Ručne v prehliadači: Ranking, Links, odznaky na 25.11.; bez chýb v konzole. |
| 11.11.2026 | P0-22 | `src/oee/ai/client.py`: `OllamaClient` (`/api/chat` so `stream: false`, `format` = JSON schéma, temperature 0,2, timeout, zámok; iba localhost/127.0.0.1), `health()` cez `/api/tags` (nikdy nevyhodí výnimku, aj pri nečakanom JSON), chyby `AiTimeout` / `AiUnavailable` / `AiInvalidOutput`, protokol `Generator`, `FakeGenerator`, `facts_hash` (SHA-256 kanonického JSON). `persistence/repositories.py`: cache `ai_output` — `AiKey`, `get_ai_output`, `claim_ai_output` (`pending` cez savepoint, bez dvojitého generovania, atomické prevzatie zaseknutého `pending` podmieneným UPDATE), `finish_ai_output`. Web: `app.state.ai_client` (None pri `OEE_AI_ENABLED=false`), `GET /health` (stav AI, bez chyby, keď Ollama nebeží). `scripts/check_ollama.py` pripravený pre testovací notebook (tu bez Ollama skončí zrozumiteľne s exit 1). Testy `tests/ai/test_client.py` (25, `httpx.MockTransport`). Ollama sa neinštalovala (D2). spec-reviewer: bez blokujúcich, pripomienky zapracované. **801 passed (63 golden)**, ruff + mypy OK. |
| 11.11.2026 | P0-23 (bez revízie) | `domain/facts.py` (`shift_summary_facts` zo `ShiftAnalytics`, `link_facts` z `ProblemLink`; podiely v %). `ai/validator.py` (čísla podľa jazyka en/sk vrátane NBSP, tolerancia polovice poslednej číslice, zlý desatinný oddeľovač = chyba; kódy iba z faktov / povoleného zoznamu; časy, dátumy, ID zmeny osobitne; `validate_payload`). `ai/fallback.py` (Shift Summary §7.F a vysvetlenie väzby §8.6 en/sk, bez odporúčaní — D1; texty prejdú validátorom). `ai/prompts/shift_summary.md`, `link_explanation.md` (verzia v1), `ai/prompting.py` (`load_prompt`, `SCHEMAS`), `ai/engine.py` (`run_task`: neplatný výstup → 1 opakovanie → fallback; timeout/nedostupnosť → hneď fallback). Testy: `tests/ai/test_validator.py` (19), `test_fallback.py` (8, golden 25.11. + konfigurácia 6 h / 45 ks/h), `test_engine.py` (11). **850 passed (69 golden)**, ruff + mypy OK. spec-reviewer: bez blokujúcich; opravené potvrdené nálezy — v `en` sa krátky dátum „dd.mm." nečíta (inak „10.53." na konci vety = falošné zamietnutie), časy sa porovnávajú normalizovane (nie ako podreťazec), sk „3 120" sa prijme aj ako dve čísla, sk text „Manko"; +4 regresné testy. **854 passed (69 golden)**, ruff + mypy OK. Známe obmedzenie (P0): celé číslo v texte sa porovnáva s toleranciou ±0,5 voči všetkým faktom a znamienko sa nehodnotí — prijateľné, priradenie čísla ku kľúču je P2. |
| 11.11.2026 | P0-24 | `services/ai_orchestrator.py`: `AiJob` (Shift Summary zmeny, vysvetlenie väzby za mesiac), `lookup` (hotový výstup pre `facts_hash` / rezervácia `pending` / prevzatie po `stale_after` = 2 × timeout), `run_job` (vlastná session, globálna fronta, `run_task`, uloženie `ok` / `fallback` / `error`). Routy `GET /ai/shift_summary/{shift_id}`, `GET /ai/link_explanation/{month}/{cause}/{effect}` (BackgroundTasks); po dokončení zmeny (posledná hodina) sa zhrnutie generuje na pozadí (chyba AI nezhodí uloženie hodiny). Šablóna `_ai_block.html` (HTMX polling každé 3 s iba pri `pending`, potom bez `hx-trigger`), dashboard sekcia F, vysvetlenie pri každej väzbe v Links. `/health` znesie aj iný generátor. Fallback zhrnutia bez dvojitej bodky. Testy: `tests/ai/test_orchestrator.py` (10), `tests/api/test_ai_block.py` (10), +2 fallback. spec-reviewer: bez blokujúcich, pripomienky zapracované (urlencode v šablónach, `/health`, try/except pri plánovaní). **879 passed (78 golden)**, ruff + mypy OK. Ručne v prehliadači bez Ollama: sekcia F a 5 vysvetlení väzieb zobrazia šablónu, polling sa zastaví, bez chýb v konzole. Reálny model nie je overený (D2) — `scripts/check_ollama.py` na testovacom notebooku. |
| 11.11.2026 | P0-25 | `services/demo.py`: `ensure_active_model` (príkladový model iba bez aktívneho modelu — D8; model manažéra ostáva), `build_demo_shift` (cez `save_hour` a validáciu; ST-038 v hodinách 2–4, Q-030 v hodine po každom, 1 ks Q-030 v 1. hodine ako základ; kusy z plánu zmeny; `hours` = čiastočná zmena na živé zadanie; existujúca zmena / zmena kratšia ako 6 h → `DemoError`). `scripts/demo_seed.py` (seed, import, model, demo zmena; `--date`, `--hours`, `--no-demo-shift`). README: demo podľa TASK §14. Testy: `tests/unit/test_demo.py` (7: príklad aj 6 h / 45 ks/h → väzba ST-038 → Q-030 same_process, lift ≥ 2), `tests/api/test_offline_demo.py` (1 golden: sieť zablokovaná okrem loopback, port Ollama zablokovaný, skutočný `OllamaClient` → mesiac 88,0 %, 25.11. 78,2 %, väzba v 2026-12 s vysvetlením zo šablóny, `/health` ai.available = false). Skript overený na dočasnej DB (21 zmien, kontroly OK; druhé spustenie bez duplicít, demo zmena → jasná chyba). **889 passed (79 golden)**, ruff + mypy OK. DoD prejdené (tabuľka nižšie). Neoverené: reálny Qwen 3B (testovací notebook), ručné demo v prehliadači. |

## Denník rozhodnutí (odchýlky a spresnenia voči TASK.md)
| # | Rozhodnutie | Dôvod | Dopad |
|---|---|---|---|
| D1 | `improvement_plan` (TASK §10.4: AI odporúčania, 5-Why, plán akcií, what-if) je **P2** | rozhodnutie vlastníka | V P0 robí AI iba Shift Summary (§7.F) a vysvetlenia Problem Links (§8.6). Vysvetlenie väzby obsahuje fakt, väzbu, hypotézu a súhrnný vplyv (číslo z kódu), **bez konkrétnych akcií**. TASK §15/§16 bod 11 sa v P0 overuje iba pre Shift Summary. |
| D2 | Ollama sa na vývojovom počítači **neinštaluje** | testuje sa na výkonnejšom notebooku | AI testy tu iba s `FakeGenerator` / `MockTransport`; reálny model → kontrolný zoznam „Testovací notebook". |
| D3 | Dokumentácia **po slovensky**; kód, identifikátory a UI po anglicky | rozhodnutie vlastníka | — |
| D4 | Jazyk odpovedí AI = parameter `OEE_AI_LANG`, predvolene `en` | 3B model píše najlepšie po anglicky (TASK §17.2 otvorené) | prepnutie na `sk` v `.env`; `uk` sa nepodporuje (D11) |
| D5 | Samostatná entita `IssueCategory` (TASK §9.1) sa nerobí | pri Top-10 je kategória atribútom kódu (TASK §5.4) | menej konfigurácie |
| D6 | Analytika sa necachuje, počíta sa na požiadanie; cachuje sa iba AI výstup | malé dáta, žiadne chyby invalidácie | — |
| D7 | Stack: FastAPI + Jinja2 + HTMX + Chart.js + SQLite/SQLAlchemy + Pydantic; doména v čistom Pythone | rýchly, testovateľný MVP v jednom jazyku, funguje offline | `docs/ARCHITECTURE.md` |
| D8 | **Čísla 60 ks/h, 480 / 30 / 10 min, 85 %, target 440, 8 hodín a pracovné dni Po–Pi sú iba príklady** (prezentácia, dataset), ako má výpočet fungovať. Skutočné hodnoty zadáva manažér v Settings. | rozhodnutie vlastníka (TASK §3.2) | Kód počíta všetko z konfigurácie. Zmena má N hodín (dĺžka v celých hodinách → N slotov); dokončenie = N/N. Bez aktívnej konfigurácie sa zmena nedá začať (odkaz na Settings). Príkladové hodnoty sú iba v `catalog/example_shift_model.yaml` (tlačidlo „Vyplniť príkladom", testy, demo). Import Excelu odvodí model zmeny zo samotného súboru. |
| D9 | V katalógu je celý číselník (82 kódov), aktívnych je 10 ST + 10 Q + „Other"; kategória z Top-10 má prednosť | TASK §5.4: Top-10 je nastavenie, dá sa zmeniť v Settings, preto musia existovať kandidáti na výmenu | operátor vidí iba aktívne kódy; manažér mení výber v Settings |
| D10 | **Spresnenie nejednoznačností TASK** (bez vplyvu na golden hodnoty) | TASK ich nedefinuje; bez pravidla by implementácia hádala alebo padala (delenie nulou) | pozri zoznam nižšie |
| D11 | Jazyk AI `uk` sa **nepodporuje**; `OEE_AI_LANG` ∈ {`en`, `sk`} | rozhodnutie vlastníka (10.11.2026) | konfigurácia `uk` odmietne; validátor čísel rieši iba `en` a `sk` |
| D12 | A a P sa počítajú **v kusoch**: A = (C − D) / C, P = Produced / (C − D), Q = G / Produced, OEE = G / C | pri jednom takte totožné s TASK §3.3 (`Run / Plan`, `ideal time / run`); pri období zo zmien s rôznym taktom (D8) iba táto forma zachová A × P × Q = OEE a TASK §6 (`D / Target = 1 − Availability`) | golden hodnoty bez zmeny (dataset má jeden takt); minúty (`planned_min`, `downtime_min`) sa ďalej sčítajú a zobrazujú |
| D13 | Zdroj aktívnych kódov pre hlásenie je **DB** (`active_top10`, `services.codebook.get_active_codes`), `top10.yaml` je iba predvolený stav seedu | Top-10 sa mení v Settings (D9) a seed výber neprepisuje | P0-17 berie kódy z `get_active_codes` |
| D14 | **Jedno rozhranie** bez rozdelenia na operátora a manažéra: prepínač roly (`/role`, cookie) je odstránený; Settings je iba formulár vstupov | rozhodnutie vlastníka (11.11.2026) | všetky stránky sú dostupné z jednej navigácie; texty UI nespomínajú roly; test `test_single_interface_without_roles` |
| D15 | **Top-10 sa nevyberá ručne.** Hlásenie ponúka celý číselník + Other; Settings iba zobrazí číselník a umožní pridať nový kód; Top-10 najčastejších problémov ukazujú dva dashboardy (týždeň, mesiac); bez dát štartovací zoznam TASK §5.4 s nulami. Nahrádza D9 (ručný výber) a mení TASK §5.4 | rozhodnutie vlastníka (11.11.2026) | `services.codebook`: `get_active_codes` = celý číselník, `add_code`, `set_top10` zrušené; route `/settings/top10` → `/settings/codes`; `active_top10` = iba štartovací zoznam; CLAUDE.md pravidlo 5 upravené; P0-17, P0-20, P0-21 doplnené |
| D16 | Odznak „linked defect" v udalostiach Shift Dashboardu berie väzby **za kalendárny mesiac zmeny**; väzby sa hľadajú medzi Top-10 najčastejšími kódmi obdobia | TASK §8.6 neurčuje obdobie odznaku; mesiac má dosť dát na štatistiku a zodpovedá Monthly | dashboard počíta `build_period` za mesiac zmeny; golden §12.8 bez zmeny |
| D17 | Výpadok AI (timeout / Ollama nebeží) sa ukladá ako `error`, nie ako trvalý `fallback`; po `stale_after` (2 × timeout) sa generovanie skúsi znova. Zlý text AI (neprešiel validátorom ani po opakovaní) sa ukladá ako `fallback` natrvalo | po neskoršom spustení Ollama majú existujúce zmeny dostať AI text; rovnaké fakty by dali rovnaký zlý text | kým AI nebeží, otvorenie stránky po `stale_after` spustí nový krátky pokus (fronta je sekvenčná, veľa väzieb naraz obsadí vlákna threadpoolu — pre P0 akceptované); zmena šablóny fallbacku sa neprejaví v už uložených `fallback` záznamoch (kľúč obsahuje verziu promptu, nie šablóny) |
| D20 | **Záložka Correlations** (medzi Production History a Line X-Ray): týždeň / mesiac (iba obdobia so zmenami), matica väzieb prestoj → zmätok, karta vybraného páru, časová os výskytov „Where the failure began" a súhrn „first recorded anomaly" | požiadavka vlastníka (11.11.2026): vidieť, ktorý problém prichádza skôr a ktorý treba riešiť | väzby = `build_period.problem_links` (TASK §8.6, golden §12.8 bez zmeny); časová os iba zo zaznamenaných udalostí (prestoj s časom, zmätky po hodinách — bez vymyslených parametrov procesu); vysvetlenie AI pri mesiaci |
| D19 | **Záložka Line X-Ray** (medzi Production History a Settings): 10 staníc z TASK §2, úroveň stanice z počtu a minút záznamov prestoja (none / low / elevated / high), zmätky po staniciach, hodinová páska intervalov prestojov zmeny; zmena alebo celý mesiac | požiadavka vlastníka (11.11.2026): vidieť, na ktorej stanici je najviac problémov | mapovanie kategória → stanica a prahy úrovní = nastavenie `catalog/stations.yaml` (predpoklad, TASK §2); kategória na viacerých staniciach sa počíta na každej a označí „assumed"; nič nepočíta KPI |
| D18 | **„Unattributed speed loss" nie je riadok v rebríčku problémov** (Ranking aj Top-10 v Production History). Mení TASK §8 (pripnutý riadok nad rebríčkom) | rozhodnutie vlastníka (11.11.2026): nie je to problém procesu, v tabuľke problémov mätie | výpočet bez zmeny (S ostáva v kaskáde, Pareto zmeny a `period_analytics.unattributed_speed_loss`; golden §12.5 bez zmeny); Top-10 critical problems ukazuje podiel medzi stratami z hlásených problémov (`share_of_recorded`, ST-038 = 100 / 528 = 18,9 %), Ranking ukazuje oba podiely; pod rebríčkom odkaz na analýzu S podľa hodín zmeny |

**D10 — pravidlá:**
- **Trend (§8.4).**
  - Pri nepárnom počte úplných týždňov sa stredný týždeň vynechá.
  - „< 3 udalosti v porovnávanom okne" = spolu v oboch polovičkách.
  - Pri zmätkoch sa počítajú záznamy (nie kusy).
- **Rebríček (§8.4, P0-11).**
  - Staršia polovica s nulovou stratou a novšia > 0 → trend `up`, zmena `None` (nedefinovaná); obe 0 → `stable`.
  - Porovnáva sa strata **na zmenu** v polovici (týždne môžu mať rôzny počet zmien).
  - ABC sa počíta v poradí tie-breaku; podiel `None` (nulový celkový vplyv) = 0 pre kumuláciu.
  - `weeks` sú zoradené chronologicky (dodá P0-13).
- **Problem Links (§8.6).**
  - Okno udalosti s pokračovaním = všetky jej hodiny + hodina po poslednom segmente.
  - Ak mimo okien nie je výroba alebo je základná miera 0, lift sa nepočíta (`None`) a pár nie je väzba
    („insufficient data"); extra = 0 a istota low, aby UI ani AI nepodali zavádzajúci údaj.
  - Mapa same_process sa do domény odovzdáva ako parameter (doména nečíta katalóg); páry = aktívne ST
    s aspoň jednou udalosťou × aktívne Q; support = počet koreňových udalostí (pokračovania zlúčené).
- **Model zmeny (§3.1).**
  - Každá hodina musí mať plánovaný čas > 0, teda prestávka + AM v jednej hodine < 60 min.
  - Prestávka ani AM nesmú presahovať svoju hodinu.
- **Prestoje (§3.4 pravidlá 2–4, P0-03).**
  - Prekryv sa v minútach počíta raz (zjednotenie); prekryté minúty patria udalosti, ktorá začala skôr.
    Vo frekvencii zostávajú obe nahlásené udalosti — prekryv musí zablokovať validácia V7 (error).
  - Časovaná udalosť sa oreže na svoj slot; čas za koncom hodiny patrí pokračovaniu v ďalšej hodine
    (bez pokračovania sa nezapočíta → varovanie v P0-05).
  - Udalosti bez času zaberajú zvyšok plánovaných minút hodiny v poradí zadania (strop = plánované minúty).
  - Udalosť celá v prestávke/AM má 0 minút, ale vo frekvencii sa počíta (V6 je iba varovanie).
  - Pokračovanie s neznámym cieľom (zmazaná udalosť, iná zmena) = samostatná udalosť.
  - Trvanie ≤ 0, NaN alebo ∞ sa počíta ako 0 (chybu hlási V4).
- **Validácia (§5.5, P0-05).**
  - V5 kontroluje nahlásené minúty pred stropom: zjednotenie časovaných (bez prestávky/AM) + súčet nečasovaných.
  - V6: navyše varovanie, keď časovaná udalosť presahuje koniec hodiny a nemá pokračovanie.
  - V7: intervaly `[začiatok, začiatok + trvanie)` aj naprieč hodinami; udalosť a jej priame pokračovanie sa
    neporovnávajú (čas za koncom hodiny patrí pokračovaniu).
  - V11: „Other" vyžaduje komentár aj v rozpise zmätkov → riadok `rejects_by_defect` má pole `comment` (P0-07).
  - V14 v doméne = hodina patrí do zmeny; jedinečnosť (zmena, hodina) a V9 idempotenciu vynucuje perzistencia.
- **Katalóg (§5.4, P0-06).**
  - Zobrazované názvy kategórií: z golden §12.4 „Camera malfunction", „Leak test issue", „Material shortage",
    „Tool issue"; náš návrh pre ostatné: „Robot issue", „Pressing issue", „Screwdriving issue", „General", „Other".
  - same_process = efektívna kategória kódu prestoja (Top-10 má prednosť, D9) patrí procesu z `links.yaml` a zmätok
    je v jeho zozname (vrátane „Robot ST → Q-003" z §5.4).
  - Jediný zdroj kategórie kódu po seede = DB (P0-08 seeduje efektívnu kategóriu z `top10.yaml`; kód aktivovaný
    v Settings mimo predvoleného Top-10 má kategóriu číselníka).
- **Kontrakty (§10, P0-07).**
  - `hourly_report`: bez `category_id` a bez `name` (voľný text = povinný komentár pri Other); `issue_type_code`
    povinný; `rejects_by_defect[].comment`; celé čísla striktne; `start_time` iba „HH:MM".
  - `shift_analytics.shift.hours_total` = N hodín (stav „n/N"); nevyplnené hodiny majú v `hourly` hodnoty `null`.
  - `problem_links[].process` = názov procesu pri same_process; trend rebríčka `up` / `down` / `stable` / `n/a`.
  - `ai_recommendations` (P2) a `patterns` (P1) sú voliteľné prázdne zoznamy.
  - `flags`, `Alert.kind`, `DataQualityIssue.rule` sú zatiaľ voľné reťazce — zoznam hodnôt ustáliť v P0-10 / P0-13.
- **Perzistencia (P0-08).**
  - `issue_event.start_at` = celý dátum a čas (nočná zmena), nie iba `start_time`.
  - `hourly_report.status` ∈ {`submitted`, `needs_attention`} (bez duplicitného bool stĺpca).
  - DB CHECK `rejects_qty ≤ produced_qty`; pokračovanie `ON DELETE SET NULL`; deti hodiny `ON DELETE CASCADE`.
  - Seed iba dopĺňa chýbajúce kódy; v už naplnenej DB je nový kód neaktívny (Top-10 zo Settings ostáva 10).
  - `station_id` sa neseeduje (väzba stanica ↔ kód je iba predpoklad, TASK §2).
  - `quality_record` sa pri uložení hodiny nahrádza celý (bez soft delete); bez rozpisu = jeden „Unspecified".
- **Import (§11, P0-09).**
  - Existujúca hodina (aj ručne zadaná) sa importom nemení; doplnia sa iba chýbajúce hodiny. Keď import doplní
    všetkých N hodín zmeny podľa jej snapshotu, zmena sa stane `completed`.
  - Existujúca zmena si drží svoj snapshot; rozdiel voči modelu zo súboru = kontrola `model_snapshot` = False.
  - Nesúlad `NOK_detail` vs `NOK_ks`, neznámy kód / hodina, chýbajúci stĺpec, nečíselná bunka → `DatasetError`
    a rollback celého importu (DoD 8).
  - `external_ref` udalosti = `Hodina_ID|kód|HH:MM:SS`; zmätku = `NOK_ID`.
  - Kontroly §11.7, ktorým chýba stĺpec s cache hodnotou (`Plan_min`, `OK_ks`, `Mikrostop_s` …), = None.
- **Analytika zmeny (§6, §7, P0-10).**
  - Provisional zmena: KPI, kaskáda a Pareto iba z odoslaných hodín; nevyplnená hodina = `null` + `not_submitted`.
  - Príznaky: hodina `below_goal`, `downtime_ge_5_min` (≥ 5 min, §7C); udalosť `over_5_min` podľa trvania celej
    zastávky (koreň + pokračovania, > 5 min, §6.6) a `continuation`.
  - Pareto: kódy prestojov, `unattributed_speed_loss` (aj záporná, aby Σ = C − G), kódy zmätkov,
    `unspecified_defect`; každé vedro nesie kategóriu (prepínač typ / kategória).
  - `IssueRow.comment` = text operátora (pri „Other" popis problému); rozklad S v sekundách = P1.
  - Výpočty strát, príznakov a stavu cieľa sú v `domain/losses.py` (CLAUDE.md pravidlo 1).
  - Modely majú many-to-one `relationship(lazy="raise")` iba kvôli poradiu INSERT-ov (ARCHITECTURE §10.2).
- **Obdobie (§8, P0-13).**
  - Do obdobia vstupujú iba zmeny `completed`; ostatné = `shifts_excluded_incomplete`.
  - Úplný týždeň: každý pracovný deň zo snapshotov leží v období a má dokončenú zmenu (týždeň 49 = partial).
  - FPQ sa počíta (TASK §12.1), iba ak sú retesty zadané vo všetkých hodinách (inak `null`).
  - Odznak `recurring` = `false`, kým ho neurčia Patterns (P1).
  - Zmätky bez rozpisu sú v rebríčku ako `unspecified_defect`, v `defect_stats` nie (nemajú kód).
  - Problem Links používajú **aktuálny** Top-10 z DB (bez „Other") a mapu same_process z katalógu.
  - `unattributed_speed_loss.by_hour_of_shift` zlučuje hodiny podľa poradia; pri období s rôznymi modelmi
    to UI (P0-20) musí uviesť.
- **Hlásenie (§4.3, §5, P0-14).**
  - Chyby validácie → nič sa neuloží; varovania → hodina `needs_attention`.
  - Udalosť sa páruje podľa `issue_id` (musí patriť tej istej hodine), inak podľa `client_key` (aj soft-deleted →
    obnova); pôvodný `client_key` sa nemení. Cudzia hodina, neznáme pokračovanie, duplicitné `issue_id` →
    `ValueError` a rollback.
  - `start_time` HH:MM sa prevedie na dátum a čas v rámci slotu (pred začiatkom slotu → +1 deň, nočná zmena).
  - Snapshot zmeny obsahuje aj `grace_min` aktívneho modelu; importované zmeny ho nemajú → grace 0.
  - Úprava importovanej hodiny prepíše `source` výroby na `manual` (posledný zdroj zmeny).
- **Stav `incomplete` (§4.3)** sa nevypočítava plánovačom, ale pri čítaní (porovnanie s „teraz").
- **Kód problému (§5.3 vs §10.1).**
  - `issue_type_code` je vždy povinný; voľný text iba s „Other" (+ povinný komentár).
  - `category_id` sa neposiela, odvodí sa z kódu (D5).

### Kde rozhodnutia prepisujú text TASK.md
TASK.md sa nemení. Pri implementácii platia tieto rozhodnutia namiesto citovaného textu:

| Miesto v TASK.md | Text v TASK.md | Platí |
|---|---|---|
| §3.1, §3.2, §4.3, §5.2, §7 (hlavička, sekcia C), §11.7 („Plan = 440"), §11.8 („якщо 8/8"), §19 | pevné 480 / 440 / 60 / 85 % / 8 hodín / Po–Pi, „8/8", „n/8" | **D8**: všetko z konfigurácie; N hodín; kontrola `Plan_min = Interval − AM − Pauza` |
| §7.F, §13.2, §13.4 bod 2, §15 (P0 „AI-рекомендації"), §16 bod 11 | AI odporúčania pre top problémy v P0 | **D1**: odporúčania sú P2; v P0 Shift Summary + vysvetlenia väzieb |
| §9.1 (`IssueCategory`, `category_id`), §9.2, §10.1 (`category_id`, `issue_type_code` alebo `null`) | samostatná entita kategórií, typ nepovinný | **D5, D9, D10**: kategória = atribút kódu; kód povinný |
| §5.4 („список можна змінити в Settings") | výber Top-10 | **D9**: výber z celého číselníka v Settings |
| §18 (stack: Streamlit alebo FastAPI) | možnosti | **D7**: FastAPI + Jinja2 + HTMX |
| §8.4, §8.6 (okrajové prípady) | nedefinované | **D10** |

---

## P0 — MVP (detailne)
Každá úloha = jeden cyklus `task-cycle`. Stĺpec **Test** = čo musí byť zelené pred označením ✅.

### M1 Základ
- [x] **P0-01 Bootstrap prostredia** ✅ 10.11.2026
  - *Závisí od:* PREP
  - *Rozsah:*
    - `.venv`, `pip install -e ".[dev]"` (na Python 3.14 overené 10.11.2026 — všetky balíky majú wheely);
    - `constraints.txt` = `pip freeze` bez riadku projektu; ďalšie inštalácie (aj na notebooku) s `-c constraints.txt`;
    - `src/oee/config.py` (pydantic-settings, prefix `OEE_`, `env_file_encoding="utf-8"`, relatívne cesty voči
      koreňu projektu — ARCHITECTURE §10.1);
    - architektonický test `tests/arch/test_layers.py`: `domain` bez IO importov; v `src/**/*.py` žiadne cloudové AI
      knižnice ani URL mimo localhost (vendorované assety sa neskenujú)
  - *AC:*
    - `pytest -q` zelený (smoke + arch); testy `ollama` sú predvolene vynechané;
    - `ruff check` a `mypy` bez chýb;
    - konfigurácia odmietne `OEE_OLLAMA_URL` s iným hostom ako `localhost` / `127.0.0.1`;
    - `Settings(_env_file=None, ...)` v teste nečíta `.env`; relatívna cesta sa rozlíši voči koreňu projektu
  - *Test:* `tests/unit/test_config.py`, `tests/arch/test_layers.py`
- [x] **P0-02 `domain/shift_model` — model zmeny a target** (TASK §3.1–3.2) ✅ 10.11.2026
  - *Závisí od:* P0-01
  - *Rozsah:*
    - vstup = konfigurácia: výkon ks/h, začiatok a dĺžka zmeny v celých hodinách, prestávka a AM (minúty,
      hodina, posun), cieľ OEE, pracovné dni;
    - výpočet: N slotov (začiatok/koniec ako `datetime` — zmena môže prechádzať cez polnoc), plánované minúty
      hodiny, target zmeny a hodiny, `ideal_cycle_s = 3600 / výkon`;
    - validácia konfigurácie (vrátane D10: každá hodina má plánovaný čas > 0). Žiadne pevné čísla v kóde (D8).
  - *AC* (testy s rôznymi konfiguráciami, nielen príkladom):
    - príklad z prezentácie: 480 − 30 − 10 = 440 min; 60 ks/h → target 440, hodinový 50/60/60/60/30/60/60/60;
    - iný výkon: 50 ks/h pri rovnakom čase → 366,67;
    - iná zmena: napr. 6 h, prestávka 20 min v 3. hodine, AM 15 min v 1. hodine, 45 ks/h → 6 slotov, 325 min,
      target 243,75;
    - nočná zmena 22:00, 8 h → sloty 22:00 … 06:00 nasledujúceho dňa, dátum zmeny = dátum začiatku;
    - chyby: výkon ≤ 0; dĺžka nie je v celých hodinách; prestávka + AM ≥ dĺžka zmeny; prestávka/AM mimo svojej
      hodiny; hodina s plánovaným časom 0; cieľ OEE mimo (0, 1]; žiadny pracovný deň
  - *Test:* `tests/unit/test_shift_model.py`
- [x] **P0-03 `domain/downtime` — evidencia prestojov** (TASK §3.4 pravidlá 2–4) ✅ 10.11.2026
  - *Závisí od:* P0-02
  - *Rozsah:* zjednotenie prekrývajúcich sa intervalov, vylúčenie minút AM/prestávky, segmenty-pokračovania
    (`continues_issue_id`), strop ≤ plánované minúty
  - *AC:*
    - prekryv = jedna zastávka;
    - pokračovanie: minúty v 2 hodinách, ale 1 udalosť vo frekvencii;
    - minúty v prestávke sa nerátajú
  - *Test:* `tests/unit/test_downtime.py`
- [x] **P0-04 `domain/kpi` — kaskáda a 4 KPI** (TASK §3.3–3.4) ✅ 10.11.2026
  - *Závisí od:* P0-02, P0-03
  - *Rozsah:* C→D→S→R→G; A, P, Q, OEE pre hodinu / zmenu / obdobie cez súčty; kanonický OEE = G / C;
    hraničné prípady
  - *AC:*
    - slajd 11 → 89,8 / 89,4 / 98,9 / **79,3 %**;
    - slajd 12 → 95,9 / 94,4 / 99,1 / **89,7 %**;
    - Run = 0 a Produced = 0 bez chyby;
    - identita `C − D − S − R = G` (parametrizovaný test)
  - *Test:* `tests/unit/test_kpi.py`, `tests/fixtures/slides.yaml`
- [x] **P0-05 `domain/validation` — pravidlá V1–V12, V14** (TASK §5.5) ✅ 10.11.2026
  - *Závisí od:* P0-03, P0-04
  - *Rozsah:* čistá funkcia; vstup = hodina + udalosti celej zmeny (pre V7) + množina aktívnych kódov (parameter,
    bez DB); výstup = správy `{level, rule, field, message}`
    a varovanie, keď časovaná udalosť presahuje koniec slotu bez pokračovania (D10, P0-03)
  - *AC:* pre každé pravidlo test (error vs warning), vrátane „Other bez komentára", neaktívneho kódu, prekryvu
    naprieč hodinami, rejects > produced
  - *Test:* `tests/unit/test_validation.py`
- [x] **P0-06 `catalog` — Top-10 a páry procesov** ✅ 10.11.2026
  - *Závisí od:* P0-01, P0-02 (príkladový model sa validuje cez `domain/shift_model`)
  - *Rozsah:*
    - `codes.yaml`: celý číselník 48 ST + 34 Q (kód, typ, kategória, názvy EN/SK) — jednorazovo extrahovaný
      read-only skriptom `scripts/extract_codebook.py` z `Ciselnik_chyb`;
    - `top10.yaml`: predvolene aktívne kódy (10 ST + ST-048, 10 Q + Q-034) a ich kategórie podľa TASK §5.4.
      Kategória z Top-10 má prednosť pred kategóriou číselníka (ST-001 → Material shortage, ST-017 → Tool) — D9;
    - `links.yaml` (páry same_process);
    - `example_shift_model.yaml` (príklad z prezentácie: 60 ks/h, 480 / 30 / 10 min, 85 % — D8);
    - loader.
    - `levers.yaml` (slajd 13) slúži iba odporúčaniam → P2 (D1)
  - *AC:*
    - `codes.yaml` má 82 kódov, ST-016 = Camera;
    - 10 + 1 aktívnych kódov každého druhu, všetky existujú v `codes.yaml`;
    - všetky kódy datasetu (6 ST, 4 Q) sú v Top-10;
    - páry zodpovedajú TASK §5.4;
    - príkladový model prejde validáciou P0-02
  - *Test:* `tests/unit/test_catalog.py`
- [x] **P0-07 `contracts` — Pydantic schémy** ✅ 10.11.2026 (TASK §10.1–10.3; §10.4 = P2)
  - *Závisí od:* P0-04, P0-06
  - *Rozsah:* schémy podľa TASK §10 s úpravami D5/D10 (`issue_type_code` povinný, `category_id` sa neposiela;
    `rejects_by_defect[].comment` pre „Other"; `produced` / `rejects` / `qty` iba celé čísla — V1, V10)
  - *AC:*
    - príklady z TASK §10 prepísané do `tests/fixtures/*.json` ako **platný JSON** (TASK používa JSONC
      s komentármi `//` a zástupnými `…`, priamo sa načítať nedajú) prejdú validáciou;
    - nevalidné vstupy sa odmietnu
  - *Test:* `tests/contract/test_schemas.py`

### M2 Dáta
- [x] **P0-08 `persistence` — modely a seed** ✅ 10.11.2026 (schéma: `docs/ARCHITECTURE.md` §5)
  - *Závisí od:* P0-06, P0-07
  - *Rozsah:* modely, engine a session podľa ARCHITECTURE §10.2:
    - `PRAGMA foreign_keys=ON`, `check_same_thread=False`, WAL a busy timeout;
    - vytvorenie priečinka DB;
    - testovacia továreň s `StaticPool`
  - *AC:*
    - in-memory SQLite;
    - FK sa vynucujú (vloženie hodiny s neexistujúcou zmenou zlyhá);
    - UNIQUE(shift_id, hour_no), UNIQUE `client_key` (NULL pri importe povolené viackrát);
    - soft delete;
    - Σ `quality_record.qty` = `rejects_qty` (aplikačný invariant v repozitári);
    - `ai_output` s kľúčom podľa `facts_hash`;
    - seed celého číselníka s príznakom `active_top10` podľa `top10.yaml` a efektívnou kategóriou
      (`Catalog.category_of`, D10 Katalóg); **model zmeny sa neseeduje**
      (zadáva ho manažér, D8)
  - *Test:* `tests/unit/test_persistence.py`
- [x] **P0-09 `services/importer` — import Excelu** ✅ 10.11.2026 (TASK §11.8, kontroly §11.7)
  - *Závisí od:* P0-08
  - *Rozsah:* snapshot modelu každej importovanej zmeny sa **odvodí zo súboru**:
    - výkon = 3600 / `Ideal_cyklus_s`;
    - začiatok zmeny z `Cas_od` 1. hodiny, dĺžka zo súčtu `Interval_min`;
    - AM a prestávka z `AM_min` / `Pauza_min` a ich hodiny; posun = začiatok hodiny (TASK §3.1);
    - cieľ OEE z `Dashboard!E51`;
    - pracovné dni = dni týždňa prítomné v súbore.

    Nastavenia v Settings sa importom nemenia.

    Technicky (ARCHITECTURE §10.4):
    - čítanie `read_only=True, data_only=True` + `wb.close()`;
    - stĺpce podľa názvov v hlavičke (bez `ws.tables`);
    - trvanie zaokrúhlené na sekundy;
    - celý import v jednej transakcii.
  - *AC:*
    - 21 zmien / 168 hodín / 33 udalostí / 112 záznamov zmätkov;
    - odvodený model pre dataset: 60 ks/h, 06:00, 480 min, prestávka 30 min (hod. 5), AM 10 min (hod. 1),
      cieľ 0,85, Po–Pi → target 440;
    - opakovaný import pridá 0 záznamov;
    - kontroly TASK §11.7 prejdú pre všetkých 21 zmien (SEDI): `Plan_min` = Interval − AM − Pauza,
      `Bilancia_s` = 0, `Kontrola_ks` = 0, NOK a prestoje sedia so súčtami detailov, A/P/Q v [0, 1];
    - súbor sa neukladá
  - *Test:* `tests/golden/test_import.py`
- [x] **P0-10 `services/analytics.build_shift` → `ShiftAnalytics`** ✅ 10.11.2026 (TASK §10.2, §6), vrátane provisional
  - *Závisí od:* P0-04, P0-09
  - *AC:*
    - **golden §12.3** (25.11. po hodinách, Pareto 96 ks, rejects po hodinách);
    - **zmena 20.11.**;
    - výstup prejde schémou
  - *Test:* `tests/golden/test_shift_analytics.py`
- [x] **P0-11 `domain/ranking` — rebríček problémov** ✅ 10.11.2026 (TASK §8.4)
  - *Závisí od:* P0-04
  - *Rozsah:* čistá funkcia nad štatistikami problémov po týždňoch:
    - ABC 80/95 %, eskalácia (trend ↑ a podiel ≥ 5 %), tie-break;
    - trend iba z týždňov označených ako úplné (príznak dodá P0-13), n/a pri nedostatku dát;
    - okrajové prípady podľa D10 (nepárny počet týždňov, počítanie záznamov zmätkov)
  - *AC:* syntetické prípady pre každé pravidlo vrátane tie-breakov zo §12.5 (rovnaký vplyv → frekvencia →
    posledný výskyt → kód). Golden §12.5 na celom datasete sa overuje v P0-13.
  - *Test:* `tests/unit/test_ranking.py`
- [x] **P0-12 `domain/correlation` — Problem Links** ✅ 10.11.2026 (TASK §8.6)
  - *Závisí od:* P0-04, P0-06
  - *Rozsah:* čistá funkcia nad hodinovými záznamami:
    - okno = hodina prestoja + nasledujúca v tej istej zmene; okná sa zjednocujú, hodina sa počíta raz;
    - lift, extra rejects, `same_process`/`cross_process`, istota, prahy;
    - okrajové prípady podľa D10 (pokračovanie udalosti, základná miera 0, žiadna výroba mimo okien)
  - *AC:* syntetické prípady (prahy, hranica zmeny, prekrývajúce sa okná, insufficient data, základná miera 0 —
    bez delenia nulou). Golden §12.8 na celom datasete sa overuje v P0-13.
  - *Test:* `tests/unit/test_correlation.py`
- [x] **P0-13 `services/analytics.build_period` → `PeriodAnalytics`** ✅ 10.11.2026 (TASK §10.3)
  - *Závisí od:* P0-10, P0-11, P0-12
  - *Pravidlá agregácie* (zmeny môžu mať rôzne snapshoty, D8):
    - target obdobia = Σ targetov zmien;
    - cieľ OEE obdobia = Σ (target × cieľ OEE) / Σ target;
    - úplný týždeň = každý pracovný deň zo snapshotov má dokončenú zmenu
  - *AC:*
    - **golden §12.1, §12.2, §12.4**: 4 zmeny pod cieľom = stredy; týždne 45–49 (49 partial); unattributed speed
      loss 579 ks;
    - syntetický test: obdobie z dvoch zmien s rôznym modelom (iný výkon a cieľ) → správny target, cieľ a OEE
      cez súčty;
    - **golden §12.5:** poradie 1–10, triedy A/B/C, trendy, tie-break;
    - **golden §12.8:**
      - ST-038→Q-030: lift 4,8, low, same_process;
      - ST-016→Q-031: medium;
      - ST-046→Q-031 nie je väzba (lift 1,93 < 2);
      - spolu presne 5 párov
  - *Test:* `tests/golden/test_period_analytics.py`, `tests/golden/test_ranking_golden.py`,
    `tests/golden/test_links_golden.py`

### M3 Operátor
- [x] **P0-14 `services/reporting` — zmena a hodinové hlásenie** ✅ 11.11.2026 (TASK §4.3, §5)
  - *Závisí od:* P0-05, P0-08
  - *Rozsah:*
    - vytvorenie zmeny na zadaný dátum (predvolene dnes) so snapshotom aktívneho modelu;
    - `save_hour` (celý stav, idempotencia podľa `client_key` vrátane soft-deleted, soft delete) v jednej transakcii;
    - stavy `open → in_progress → completed / incomplete`; `incomplete` sa vyhodnocuje pri čítaní s parametrom
      „teraz" (D10, ARCHITECTURE §10.3); `revision`
  - *AC:*
    - bez aktívneho modelu zmeny sa zmena nevytvorí (zrozumiteľná chyba);
    - zmena na dátum, ktorý už existuje (aj importovaný), sa neduplikuje, otvorí sa existujúca;
    - všetkých N hodín vyplnených → `completed` (test pre 8 aj pre iný počet hodín);
    - opakované odoslanie bez duplicít;
    - úprava po dokončení → `revision + 1`;
    - po grace → `incomplete`
  - *Test:* `tests/unit/test_reporting.py`
- [x] **P0-15 Web kostra + napojenie DB** ✅ 11.11.2026
  - *Závisí od:* P0-01, P0-08
  - *Rozsah:*
    - `web/app.py` s továrňou `create_app(settings)`; `lifespan`: priečinok DB, `create_all`, seed číselníka;
      session dependency;
    - layout, navigácia (Hourly Reporting / Shift Dashboard / Production History / Settings / Import),
      prepínač roly;
    - vendorované htmx, Chart.js, Pico.css v `static/vendor/` + `VERSIONS.md`. Stiahnutie vyžaduje súhlas
      vlastníka (ARCHITECTURE §10.7);
    - pravidlá Starlette 1.x (ARCHITECTURE §10.5)
  - *AC:*
    - `with TestClient(create_app(test_settings))`: všetky stránky (zatiaľ kostry) vracajú 200;
    - HTML neobsahuje externé URL (offline); rozšíriť `tests/arch/test_layers.py` o kontrolu URL aj v šablónach
      a nevendorovaných `*.js` / `*.css` (dnes skenuje iba `*.py`);
    - testy nepoužívajú `data/local/oee.db`
  - *Test:* `tests/api/test_pages.py`
- [x] **P0-16 UI Settings** ✅ 11.11.2026 (TASK §3.2, §5.4) — manažér najprv nastaví target, až potom operátor hlási
  - *Závisí od:* P0-02, P0-08, P0-14, P0-15
  - *Rozsah:*
    - formulár modelu zmeny (výkon ks/h, začiatok a dĺžka zmeny, prestávka, AM, cieľ OEE, pracovné dni) so živým
      prepočtom plánovaného času, targetu zmeny a hodinových targetov;
    - tlačidlo „Vyplniť príkladom" (D8);
    - ~~úprava Top-10: výber aktívnych kódov z celého číselníka (D9)~~ → číselník + pridanie nového kódu (D15)
  - *AC:*
    - nová konfigurácia sa použije pre nové zmeny, staré si držia snapshot;
    - nevalidná konfigurácia sa neuloží;
    - číselník sa iba zobrazuje, nový kód dostane ďalšie číslo v rade (ST-049, Q-035 …) a je hneď voliteľný (D15);
    - „Other" je vždy k dispozícii; neznámy kód hlásenie odmietne (V11)
  - *Test:* `tests/api/test_settings.py`
- [x] **P0-17 UI Hourly Reporting** ✅ 11.11.2026 (TASK §5.1–5.3)
  - *Závisí od:* P0-14, P0-15, P0-16
  - *Rozsah:*
    - výber dátumu zmeny (predvolene dnes; iný dátum pre demo a dopĺňanie, TASK §4.3);
    - hlavička zmeny, N dlaždíc so stavmi;
    - formulár: Produced, Rejects = 0 + rozpis, riadky problémov z celého číselníka + Other (`get_active_codes`, D15), čas, pokračovanie;
    - chyby inline (HTMX)
  - *AC:*
    - bez nastaveného targetu → hláška s odkazom na Settings;
    - hodina bez problémov = 2 akcie;
    - Other bez komentára → chyba;
    - ručná kontrola v prehliadači
  - *Test:* `tests/api/test_hourly_reporting.py`
- [x] **P0-18 UI Import** ✅ 11.11.2026
  - *Závisí od:* P0-09, P0-15
  - *AC:* import cez UI = import cez službu; zobrazí počty a výsledky kontrol
  - *Test:* `tests/api/test_import_page.py`

### M4 Manažér
- [x] **P0-19 Shift Dashboard A–E + provisional** ✅ 11.11.2026 (TASK §7)
  - *Závisí od:* P0-10, P0-15
  - *Rozsah:*
    - **hlavička:** výber zmeny, stav (`completed` / `in_progress n/N — provisional` / `incomplete` / „edited");
    - **A:** 4 KPI karty, stav OEE voči cieľu a odchýlka v p. b., príspevok D/S/R v kusoch;
    - **B:** waterfall Target → Good s čiarou cieľa OEE + tabuľka;
    - **C:** hodinový OEE s čiarou cieľa; zvýraznené hodiny pod cieľom a s prestojom ≥ 5 min; nevyplnené hodiny
      ako „not submitted", nie 0;
    - **D:** tabuľka všetkých udalostí s príznakmi (> 5 min, pokračovanie — TASK §6.6), triedenie, zoskupenie
      bez zlúčenia, podtabuľka zmätkov;
    - **E:** základné Pareto vedier s prepínačom typ / kategória (kumulatívna čiara je P1)
  - *AC:*
    - stránka 25.11. obsahuje hodnoty §12.3;
    - `/api/shift/{id}/charts` vracia tie isté čísla ako `ShiftAnalytics` (žiadny výpočet v šablóne ani v JS)
  - *Test:* `tests/api/test_shift_dashboard.py`
- [x] **P0-20 Production History: Shift History, Weekly, Monthly** ✅ 11.11.2026 (TASK §8.1–8.3)
  - *Závisí od:* P0-13, P0-15
  - *Rozsah:*
    - **Shift History:** tabuľka zmien so stavom (dáta + cieľ OEE), filter dátumov, klik → dashboard;
    - **Weekly:** KPI cez súčty, target vs produced, prestoje, zmätky, najčastejšie a najdlhšie problémy,
      Pareto, dynamika OEE po zmenách;
    - **Monthly:** navyše tabuľka typov (počet, Σ a priemerná dĺžka, podiely), straty podľa kategórií,
      Top-5/10, porovnanie týždňov na zmenu (partial), trend A/P/Q;
    - **D15: dva dashboardy Top-10 najčastejších problémov** — za týždeň a za mesiac, zvlášť ST a Q (poradie podľa
      frekvencie výskytov). Bez dát sa ukáže štartovací zoznam TASK §5.4 (`active_top10` zo seedu) s nulovými hodnotami;
      keď dáta pribudnú, Top-10 tvoria najčastejšie kódy (aj nové, pridané v Settings)
  - *AC:*
    - 21 riadkov, filter dátumov, klik → dashboard;
    - týždne = §12.2;
    - mesiac = §12.1
  - *Test:* `tests/api/test_history.py`
- [x] **P0-21 Záložky Problem Ranking a Problem Links** ✅ 11.11.2026 (TASK §8.4, §8.6)
  - *Závisí od:* P0-11, P0-12, P0-13, P0-19, P0-20
  - *Rozsah:*
    - záložka Ranking s pripnutým riadkom unattributed speed loss a stĺpcami „pridružený zmätok" a „súhrnný
      vplyv" (mimo skóre rebríčka, TASK §8.6);
    - záložka Problem Links (tabuľka párov);
    - odznak „pridružený zmätok" v tabuľke udalostí dashboardu (TASK §8.6 „Kde je to vidieť");
    - D15: `services/analytics._links` dnes berie kódy z `active_top10` (štartovací zoznam) — rozšíriť na kódy,
      ktoré sa v období vyskytli, aby väzby videli aj nové kódy (golden §12.8 sa nesmie zmeniť)
  - *AC:*
    - pripnutý riadok unattributed speed loss;
    - poradie a triedy = §12.5;
    - páry = §12.8;
    - súhrnný vplyv nemení poradie
  - *Test:* `tests/api/test_ranking_links_pages.py`

### M5 Lokálne AI (bez inštalácie Ollama)
- [x] **P0-22 `ai/client` — klient Ollama** ✅ 11.11.2026 (TASK §13.4)
  - *Závisí od:* P0-07, P0-08
  - *Rozsah:*
    - `/api/chat` (`stream: false`, `format` = JSON schéma, temperature 0,2, timeout); predvolene
      `http://127.0.0.1:11434`;
    - health check (`/api/tags`), `FakeGenerator`;
    - repozitár `ai_output` v `persistence` s kľúčom `(kind, subject_key, facts_hash, model, lang, prompt_version)`;
    - `scripts/check_ollama.py` (iba pripraviť)
  - *AC:*
    - `MockTransport` — úspech / timeout / 500 / nevalidný JSON; každá požiadavka obsahuje `stream: false`;
    - rovnaké fakty → cache hit, zmenené fakty → nový kľúč
  - *Test:* `tests/ai/test_client.py`
- [x] **P0-23 `domain/facts` + `ai/validator` + `ai/fallback` + prompty** ✅ 11.11.2026
  - *Závisí od:* P0-22, P0-06, P0-10, P0-13
  - *Rozsah:*
    - `domain/facts`: fakty pre Shift Summary (z `ShiftAnalytics`) a pre vysvetlenie väzby (z `problem_links`);
    - validátor: čísla a kódy iba z faktov / Top-10; parsovanie čísel podľa jazyka a tolerancia zaokrúhlenia
      (ARCHITECTURE §10.6);
    - fallback šablóny (Shift Summary §7.F, vysvetlenie väzby §8.6);
    - `ai/prompts/*.md` s verziou
  - *AC:*
    - vymyslené číslo → 1 opakovanie → fallback;
    - správne čísla v tvaroch „9,240" (en), „9 240" a „78,2" (sk) a zaokrúhlené „78.2" (fakt 78,18) sa prijmú;
    - fallback text pre 25.11. obsahuje fakty §7.F
  - *Test:* `tests/ai/test_validator.py`, `tests/ai/test_fallback.py`
- [x] **P0-24 `services/ai_orchestrator` + AI blok v UI** ✅ 11.11.2026
  - *Závisí od:* P0-14, P0-19, P0-21, P0-23
  - *Rozsah:*
    - Shift Summary + vysvetlenia Problem Links (**bez odporúčaní — D1**);
    - generovanie na pozadí (`BackgroundTasks`) po dokončení zmeny **a na požiadanie**, keď výstup pre aktuálny
      `facts_hash` chýba (importované zmeny, obdobia);
    - podľa ARCHITECTURE §10.6:
      - vlastná DB session;
      - sekvenčná fronta;
      - riadok `pending` ako zámok;
      - zastaraný `pending` → nový pokus;
    - HTMX polling bloku AI, ktorý sa po dokončení zastaví
  - *AC:*
    - s `FakeGenerator` sa výstup uloží a zobrazí;
    - importovaná zmena bez AI výstupu ho dostane pri prvom otvorení dashboardu;
    - dve súbežné spustenia pre ten istý kľúč → jedno generovanie, žiadny `IntegrityError`;
    - polling sa zastaví po stave `ok` / `fallback`;
    - bez Ollama → fallback, stránky fungujú
  - *Test:* `tests/ai/test_orchestrator.py`, `tests/api/test_ai_block.py`

### M6 Demo a DoD
- [x] **P0-25 Demo a záverečná kontrola** (TASK §14, §16) ✅ 11.11.2026
  - *Závisí od:* všetky P0
  - *Rozsah:*
    - `scripts/demo_seed.py`: ak nie je aktívny model, použije príkladový (D8); demo zmena s Q-030 hneď po ST-038;
    - demo v README;
    - prechod DoD;
    - test bez siete
  - *AC:*
    - všetky testy zelené;
    - DoD tabuľka nižšie vyplnená;
    - demo podľa TASK §14 prejde
  - *Test:* celý `pytest -q`

### Poradie podľa závislostí
Úlohy v jednej vrstve sú navzájom nezávislé (v zátvorke priame závislosti).
| Vrstva | Úlohy |
|---|---|
| 1 | P0-01 |
| 2 | P0-02 (01) |
| 3 | P0-03 (02) · P0-06 (01, 02) |
| 4 | P0-04 (02, 03) |
| 5 | P0-05 (03, 04) · P0-07 (04, 06) · P0-11 (04) · P0-12 (04, 06) |
| 6 | P0-08 (06, 07) |
| 7 | P0-09 (08) · P0-14 (05, 08) · P0-15 (01, 08) · P0-22 (07, 08) |
| 8 | P0-10 (04, 09) · P0-16 (02, 08, 14, 15) · P0-18 (09, 15) |
| 9 | P0-13 (10, 11, 12) · P0-17 (14, 15, 16) · P0-19 (10, 15) |
| 10 | P0-20 (13, 15) · P0-23 (06, 10, 13, 22) |
| 11 | P0-21 (11, 12, 13, 19, 20) |
| 12 | P0-24 (14, 19, 21, 23) |
| 13 | P0-25 (všetky) |

Odporúčané poradie pre jedného vývojára: číselné (01 → 25) rešpektuje všetky závislosti.

---

## P1 — dôležité vylepšenia (stručne)
- [ ] **Patterns P-1…P-7** (TASK §8.5) + golden §12.6 (má / nemá nájsť) + odznaky „recurring" + AI hypotézy
- [ ] **Alerty** (TASK §6.6): zastávka > 5 min, hodina pod cieľom, provisional zmena pod cieľom
- [ ] **Týždenná / mesačná textová správa** od lokálneho AI
- [ ] **Rozšírené filtre, porovnanie období, detailné Pareto:** kumulatívna čiara, drill-down podľa hodín,
  rozklad speed loss z rozšírených polí
- [ ] **Retesty a First-pass quality**, nápoveda V13, okamžitá spätná väzba operátorovi (TASK §5.7)
- [ ] **Demo pomocník:** „prehrať" zmenu z datasetu cez Hourly Reporting

## P2 — backlog
- [ ] **`improvement_plan`** (TASK §10.4, §13.2): AI odporúčania (5-Why, akcie, rola, efekt, „jedna akcia —
  dva problémy") — rozhodnutie D1
- [ ] What-if modelovanie
- [ ] Databáza pák zo slajdu 13 (`catalog/levers.yaml`) ako kontext AI odporúčaní + statické nápovedy v UI
- [ ] Väčší lokálny model (7B) / doladenie na histórii riešení
- [ ] Export PDF/Excel; ďalšie manažérske správy
- [ ] Autentifikácia a roly; viac liniek / zmien / produktov
- [ ] Automatický zber dát z linky v reálnom čase
- [ ] Generátor syntetických scenárov
- [ ] Alembic migrácie

---

## Definition of Done (TASK §16) — sledovanie
| # | Kritérium | Úloha | Stav |
|---|---|---|---|
| 1 | Hodina bez problémov ≤ 2 akcie, viac problémov, úprava, bez duplicít, V1–V12, V14 | P0-05, P0-14, P0-17 | ✅ |
| 2 | všetky hodiny zmeny (napr. 8/8) → `completed` + analytika; po grace → `incomplete` | P0-14 | ✅ (služba) |
| 3 | Import: 21 / 168 / 33 / 112, opakovaný import bez duplicít, kontroly §11.7 | P0-09 | ✅ |
| 4 | Golden §12.1, §12.2, §12.3, 20.11., §12.7 (±0,01 p. b.; kusy/minúty presne) | P0-04, P0-10, P0-13 | ✅ (`pytest -m golden`: 79) |
| 5 | Identita C − D − S − R = G pre hodinu/zmenu/obdobie | P0-04 | ✅ (doména) |
| 6 | Obrazovka 1 (25.11.) a obrazovka 2 (21 zmien, 4 stredy, týždne, rebríček §12.5) | P0-13, P0-19 … P0-21 | ✅ (tests/api) |
| 7 | Nová ručne zadaná zmena je v histórii a prepočíta rebríček | P0-17, P0-20 | ✅ (demo zmena → Links 2026-12) |
| 8 | Validácia zachytí poškodené dáta a nepadá | P0-05, P0-09 | ✅ (doména + import) |
| 9 | KPI nepočíta AI; bez Ollama všetko funguje | P0-23, P0-24 | ✅ (`test_offline_demo`) |
| 10 | AI bez internetu; žiadne cloudové AI API v kóde/konfigurácii | P0-01, P0-22 | ◐ kód bez cloud API (tests/arch), bez siete ✅; Qwen offline → testovací notebook |
| 11 | Shift Summary 25.11. obsahuje fakty §7.F, čísla overené validátorom (odporúčania → P2, D1) | P0-23, P0-24 | ◐ fallback s faktami prejde validátorom ✅; text od Qwen → testovací notebook |
| 12 | Problem Links = §12.8; demo zmena nájde ST-038 → Q-030 a AI ho vysvetlí | P0-12, P0-13, P0-24, P0-25 | ◐ §12.8 ✅, demo väzba ✅, vysvetlenie šablónou ✅; od Qwen → notebook |
| 13 | V UI celý číselník ST / Q + Other s komentárom; Top-10 najčastejších v dashboarde týždňa a mesiaca (D15) | P0-17, P0-20 | ✅ |
| D8 | Target sa počíta z konfigurácie manažéra; iná konfigurácia (napr. 6 h, 45 ks/h) funguje end-to-end | P0-02, P0-16, P0-17 | ✅ (6 h / 45 ks/h v Settings, reporting, demo) |
| 14 (P1) | Patterns §12.6 bez falošných nálezov | P1 | ☐ |

## Kontrolný zoznam: testovací notebook (reálny Qwen 3B)
Postup: `.claude/skills/ollama-local/SKILL.md`.
- [ ] Vlastné `.venv` na notebooku (venv sa nekopíruje): `pip install -e ".[dev]" -c constraints.txt`
- [ ] Ollama nainštalovaný, `ollama pull qwen2.5:3b`, `.venv/Scripts/python scripts/check_ollama.py` → OK
- [ ] `pytest -m ollama -q` zelené
- [ ] Shift Summary 25.11. prejde validátorom (bez fallbacku) v ≤ 30 s
- [ ] Vysvetlenie väzby ST-038 → Q-030 na demo zmene je zrozumiteľné a označené ako hypotéza
- [ ] Beh s vypnutou sieťou (DoD 10)
- [ ] Zastavený Ollama → aplikácia ukáže fallback texty
