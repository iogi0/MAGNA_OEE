# Magna AI OEE Improvement Engine (CityCare Web App)

Moderná priemyselná aplikácia pre **Manažéra výroby (Production Manager)** a **Zmenového údržbára (Shift Maintenance Engineer)** na montážnej linke elektrických pohonov Magna (L01).

Navrhnutá presne podľa dizajn-špecifikácie **CityCare Dashboard (Light/Dark Mode Fusion)**.

---

## 🚀 Rýchle spustenie
1. Dvakrát kliknite na súbor **`run_app.bat`** v koreňovom priečinku projektu.
2. V prehliadači sa automaticky otvorí moderná aplikácia na adrese:
   👉 **`http://localhost:5173`**

*(Alebo manuálne cez terminál: `npm run dev`)*

---

## 🌟 Architektúra a kľúčové funkcie

### 1. CityCare Light/Dark Mode Fusion Design
* **Horná sekcia (Light Theme `#F3F6F9`):**
  * **White Cards (`#FFFFFF`, `rounded-24`, jemný tieň `0 4px 24px rgba(0,0,0,0.04)`):** 4 kľúčové karty (Availability, Performance, Quality, Downtime) s tmavým bridlicovým textom `#111827`.
  * **Glassmorphism Card (`rounded-28`, `backdrop-filter: blur(20px)`):** Karta výrobnej efektivity s veľkým OEE indexom a porovnaním s cieľom 85.0%.
  * **SVG Trendová krivka:** Priebeh OEE (%) po hodinách s červenou cieľovou čiarou 85%.
  * **Po-hodinový report & Alarm:** Intuitívny formulár na manuálne zadávanie vyrobených kusov, braku a prestojov (H1–H8) s indikáciou zadaných hodín (`✓ Zadané` vs. `○ Čaká`).

### 2. Interaktívny станок / Montážna linka (10 staníc)
* **Vizuálna schéma celej linky L01:**
  1. *ST-1: Naloženie puzdra (ABB Robot)*
  2. *ST-2: Nalisovanie motora (Kistler Lis 50kN)*
  3. *ST-3: Kamerová inšpekcia (Cognex In-Sight + LED Ring)*
  4. *ST-4 & ST-5: Skrutkovanie (Atlas Copco)*
  5. *ST-6: Rotácia 90° (Festo otočný stôl)*
  6. *ST-7 & ST-8: Invertor montáž a skrutkovanie*
  7. *ST-9: Test tesnosti (Ateq F620 Leak test)*
  8. *ST-10: Výstup na EOL test (Fanuc)*
* **Interaktivita pri kliknutí:**
  * Kliknite na ktorúkoľvek stanicu — okamžite sa zobrazí jej **technický pas**:
    * Živá telemetria senzorov (tlak 6 bar, 24V napájanie, svetelný tok lux).
    * Ak je na stanici porucha (`ST-038` alebo `ST-046`), stanica pulzuje červeným/oranžovým neónovým obrysom.
    * 5-Why koreňová príčina.
    * **Interaktívny checklist zásahu údržbára:** odškrtávacie políčka `[✔] Krok dokončený`.
    * Tlačidlo: **«Potvrdiť vyriešenie a obnoviť stanicu»** — po splnení krokov odstráni poruchu a obnoví nominálny stav!

### 3. Dolná sekcia (Dark Theme `#09090B`, `rounded-t-[40px]`)
* **Neónové Glow karty (`#18181B`):**
  * 🟡 **Neon Orange Glow (`#F59E0B`):** TOP 3 Prestoje (Availability).
  * 🔴 **Neon Red Glow (`#EF4444`):** TOP 3 Defekty kvality (NOK brak).
  * 🟢 **Neon Green Glow (`#10B981`):** AI Maintenance Copilot s odporúčaným okamžitým zásahom, metodikou Lean AM a tlačidlom na spustenie hĺbkovej analýzy cez lokálny model **Qwen 2.5 3B (Ollama)**.
* **Waterfall rozpad výrobných strát (Magna Slide 11):**
  Presná identita: `440 (Plán) -> -45 min (Prestoje) -> -42 ks (Rýchlosť) = 353 ks -> -4 ks (Brak) -> 349 ks (OK)`.

### 4. Nástroje pre 3-minútovú prezentáciu (Live Demo)
* **`🪄 Automaticky doplniť zvyšok zmeny`** — ponechá manuálne zadané hodiny (napr. H1..H3) a automaticky doplní zvyšok zmeny (H4..H8) pre bleskové predvedenie poroty.
* **`🔄 Resetovať zmenu (Nový Live Demo)`** — vyčistí všetky hodiny na 0, aby ste mohli začať prezentáciu načisto.

### 5. Týždenný (7 dní) a Mesačný (30 dní) prehľad
* **Týždenná analýza (W45–W49):** Stĺpcový graf OEE po týždňoch a podrobná tabuľka výsledkov.
* **Mesačná história (21 zmien):** Celomesačný trend OEE a samostatné **Pareto 80/20 diagramy** pre prestoje a brak.

---

## 🛠️ Použité technológie
* **Frontend:** React 18, TypeScript, Vite 5, Tailwind CSS
* **Dizajn systém:** CityCare Dashboard Specification (Light/Dark Fusion, Glassmorphism, Neon Glow)
* **Ikony:** Lucide React
* **AI Engine:** Lokálna neurónová sieť Qwen 2.5 3B cez Ollama (`localhost:11434`)
