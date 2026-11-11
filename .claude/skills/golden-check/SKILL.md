---
name: golden-check
description: Ako overiť výpočty OEE proti referenčným (golden) hodnotám z TASK.md §12 — kde sú testy, tolerancie, ako spustiť a ako čítať rozdiel. Použi pri písaní alebo ladení golden testov a pri každej zmene v domain/, services/analytics alebo services/importer.
---

# Golden kontrola

## Kde čo je
- **Autorita:** `TASK.md` §12 (12.1 mesiac, 12.2 týždne, 12.3 zmena 25.11., 12.4 rozpisy, 12.5 rebríček,
  12.6 patterns – P1, 12.7 slajdy, 12.8 Problem Links).
- **Mapa §12 → testovacie súbory a rýchly prehľad čísel:** `docs/TESTING.md` §3–4.
- **Dataset:** `data/raw/dummy_data.xlsx` (opravená verzia, ST-016 = Camera). Čítaj iba
  `openpyxl.load_workbook(path, read_only=True, data_only=True)`, vždy `wb.close()` a **nikdy neukladaj**.
  Cestu odvoď od koreňa repozitára, nie od aktuálneho priečinka.

## Spustenie
```bash
.venv/Scripts/python -m pytest -m golden -q
.venv/Scripts/python -m pytest tests/golden/test_shift_analytics.py -q -vv
```

Exit code 5 („no tests collected") = golden testy pre danú časť ešte neexistujú, nie chyba.

## Tolerancie
- **KPI a percentá:** ±0,01 p. b. Porovnávaj zlomky (0,8801), nie zaokrúhlené reťazce.
- **Kusy, minúty, počty udalostí, poradie, triedy A/B/C:** presne.
- **Lift:** 2 desatinné miesta.
- **Vypočítané `float` hodnoty** (identita C − D − S − R = G): `math.isclose(..., abs_tol=1e-9)`, nie `==`.

## Písanie golden testu
- Golden hodnoty patria **iba do testov** (konštanty v teste alebo `tests/fixtures/*.yaml`), nikdy do `src/`.
- Pri každej hodnote uveď v komentári sekciu TASK (napr. `# TASK §12.3`).
- Najprv otestuj čisté doménové funkcie na malých príkladoch (slajd 11/12), až potom celý dataset.

## Keď test zlyhá — typické príčiny
| Symptóm | Pravdepodobná príčina |
|---|---|
| Mesačné KPI mierne mimo | priemer percent namiesto súčtov primárnych veličín |
| Availability príliš nízka | chýba vylúčenie AM / prestávky alebo strop downtime ≤ planned |
| Počet udalostí väčší | pokračovania (`continues_issue_id`) sa rátajú ako nové udalosti |
| C − D − S − R ≠ G | rejects odpočítané dvakrát alebo produced bez zmätkov |
| Zlé poradie rebríčka | chýba tie-break (frekvencia → posledný výskyt → kód) alebo eskalácia |
| Trend pre týždeň 49 | neúplné týždne sa do trendu nezahŕňajú |
| Problem Links iné | okno nie je hodina + nasledujúca v rámci tej istej zmeny; prekrývajúce sa okná započítané dvakrát (hodina sa má počítať raz); základná miera nie je z hodín mimo okien |

**Očakávanú hodnotu nemeň.** Ak si myslíš, že TASK §12 je chybný, nahlás to používateľovi s dôkazom
(read-only výpočet).
