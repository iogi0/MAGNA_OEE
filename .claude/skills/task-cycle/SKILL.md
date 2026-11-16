---
name: task-cycle
description: Povinný pracovný cyklus projektu OEE — jedna malá úloha z PLANNING.md, krátky plán, TDD implementácia, testy, kontrola git diff, aktualizácia PLANNING.md a zastavenie s čakaním na súhlas. Použi na začiatku každej vývojovej úlohy (P0/P1/P2) a vždy, keď používateľ povie „ďalšia úloha" alebo „pokračuj".
---

# Pracovný cyklus jednej úlohy

## 0. Výber úlohy
- Otvor `PLANNING.md`. Vezmi úlohu, ktorú určil používateľ, inak prvú nehotovú úlohu, ktorej závislosti sú hotové.
- Ak používateľ výslovne nepovolil začať, **iba navrhni** úlohu a čakaj.

## 1. Krátky plán (pred kódom)
Napíš 5–10 riadkov:
- cieľ a odkazy na TASK.md (§);
- súbory, ktoré vzniknú / zmenia sa;
- testy, ktoré pokryjú akceptačné kritériá z `PLANNING.md`;
- riziká a otvorené otázky.

Ak úloha mení obchodné pravidlo alebo sa odchyľuje od TASK.md, **opýtaj sa používateľa**.

## 2. Implementácia (TDD)
- Pre doménovú logiku použi skill `superpowers:test-driven-development`: najprv padajúci test, potom kód.
- Drž sa rozsahu úlohy. Nič „navyše".
- Rešpektuj nemenné pravidlá a vrstvy z `CLAUDE.md`.

## 3. Testy a kvalita
```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/ruff check src tests
.venv/Scripts/mypy
```
- Pri výpočtových zmenách spusti aj `pytest -m golden -q` alebo deleguj na agenta `golden-verifier`.
- Pri chybe použi skill `superpowers:systematic-debugging`. Očakávané golden hodnoty nemeň.

## 4. Kontrola diffu
- `git status` a `git diff`: iba zamýšľané súbory, žiadne ladiace výpisy, žiadne tajomstvá, žiadne zmeny
  v `TASK.md` ani v `data/raw/`.
- Deleguj revíziu na agenta `spec-reviewer`. Blokujúce nálezy oprav.
- Pred vyhlásením „hotovo" použi skill `superpowers:verification-before-completion`.

## 5. Aktualizácia PLANNING.md
- Zaškrtni úlohu, doplň riadok do „Denníka práce" (dátum, úloha, výsledok, počet testov).
- Nové rozhodnutia zapíš do „Denníka rozhodnutí". Nové TODO doplň ako úlohy.
- Aktualizuj tabuľku „Stav" a prípadne riadok DoD.

## 6. Stop
Zhrň používateľovi po slovensky:
- čo je hotové;
- výsledky testov;
- čo nie je overené;
- návrh ďalšej úlohy.

**Nezačínaj ďalšiu úlohu** a **necommituj**, kým o to používateľ nepožiada.
