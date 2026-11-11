# AGENTS.md — roly a zodpovednosti

Pravidlá projektu, príkazy a konvencie sú v **`CLAUDE.md`** a tu sa neopakujú. Tento súbor hovorí iba to,
**kto čo robí, kto rozhoduje a kde sú hranice** jednotlivých rolí.

## Prehľad rolí
| Rola | Kto | Zodpovednosť | Nerobí |
|---|---|---|---|
| **Vlastník produktu** | používateľ (tím) | schvaľuje plán a každú ďalšiu úlohu; rozhoduje o odchýlkach od TASK.md; robí commity a merge | — |
| **Tech lead / implementátor** | hlavná session Claude Code | vyberá ďalšiu úlohu z `PLANNING.md`, plánuje, implementuje (TDD), spúšťa testy, kontroluje `git diff`, aktualizuje `PLANNING.md`, deleguje revízie | nemení TASK.md; nepokračuje bez súhlasu; necommituje bez požiadavky |
| **`spec-reviewer`** | subagent (`.claude/agents/spec-reviewer.md`) | read-only revízia diffu úlohy voči TASK.md v2.3 a nemenným pravidlám | neupravuje kód; nespúšťa aplikáciu |
| **`golden-verifier`** | subagent (`.claude/agents/golden-verifier.md`) | spúšťa golden/contract testy, porovnáva s TASK.md §12 a hlási rozdiely s číslom sekcie | neopravuje kód ani testy; nemení očakávané hodnoty |
| **`local-ai-engineer`** | subagent (`.claude/agents/local-ai-engineer.md`) | prompty, JSON schémy pre Ollama, validátor čísel/kódov, fallback texty, klient Ollama | nepočíta KPI; nepridáva cloudové API; neinštaluje Ollama |

## Odovzdávanie práce v jednej úlohe
1. **Tech lead:** krátky plán úlohy (rozsah, súbory, testy) → po potrebe súhlas vlastníka.
2. **Tech lead:** implementácia + testy. Pri úlohách v `src/oee/ai/` deleguje návrh promptov a validátora na
   **`local-ai-engineer`**.
3. **`golden-verifier`:** pri úlohách, ktoré menia výpočty (domain, services/analytics, importer).
4. **`spec-reviewer`:** pri každej úlohe nad výsledným `git diff`.
5. **Tech lead:** opraví nálezy, aktualizuje `PLANNING.md`, zhrnie výsledok a **zastaví sa**.
6. **Vlastník:** schváli → (voliteľne commit) → povolí ďalšiu úlohu.

## Kto rozhoduje
| Otázka | Rozhoduje |
|---|---|
| Obchodné pravidlá, priority P0/P1/P2, odchýlky od TASK.md | vlastník produktu |
| Technické detaily v rámci schválenej architektúry | tech lead |
| Či zmena porušuje TASK.md / nemenné pravidlá | `spec-reviewer` hlási, rozhoduje vlastník |
| Či sedia golden hodnoty | `golden-verifier` (fakty z testov), pri spore platí TASK.md §12 |
| Formulácie a štruktúra AI výstupov | `local-ai-engineer` navrhuje, tech lead integruje |

## Konflikty
- Rozpor medzi TASK.md a `PLANNING.md` → platí **denník rozhodnutí v `PLANNING.md`**, ak tam rozhodnutie je.
  Inak platí TASK.md.
- Ak golden test zlyhá, **očakávaná hodnota sa nemení** bez súhlasu vlastníka. Najprv sa hľadá chyba v kóde.
