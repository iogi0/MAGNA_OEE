# Dáta

## `raw/dummy_data.xlsx`
Dummy dataset od organizátorov (Magna Hackathon, zadanie č. 5): 21 ranných zmien (02.11.–30.11.2026),
linka L01, produkt P01. Hárky: `Vyroba_hodiny`, `Prestoje`, `NOK_detail`, `Ciselnik_chyb`, `Kontrola_zmien`,
`Chart Data`, `Dashboard`. Popis stĺpcov a mapovanie importu: `TASK.md` §11.

**Toto je opravená verzia (TASK.md v2.1):** v číselníku `Ciselnik_chyb!C17` má kód ST-016 kategóriu
„Kamera / Camera" (v origináli „Všeobecné / General"). Aktualizované boli aj cache hodnoty `Prestoje!J`
pre 7 udalostí ST-016. Vzorce, grafy a KPI dashboardu sú bez zmeny.

## Pravidlá
- Súbor **nikdy neukladajte** cez openpyxl ani inú knižnicu: stratili by sa grafy. Čítajte ho iba
  `openpyxl.load_workbook(path, read_only=True, data_only=True)` (cache hodnoty vzorcov) a vždy zatvorte
  `wb.close()` (inak zostane na Windows zamknutý).
- V read-only režime nie sú dostupné pomenované tabuľky (`ws.tables`, napr. `tblVyroba`). Stĺpce sa mapujú podľa
  názvov v 1. riadku hárku.
- Referenčné (golden) hodnoty pre tento súbor sú v `TASK.md` §12 a v `docs/TESTING.md`.
  Sú to testovacie orientačné body, **nie konštanty** v logike aplikácie.
- Lokálna databáza a iné generované dáta patria do `data/local/` (ignorované v gite).
