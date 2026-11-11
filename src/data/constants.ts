import { HourlySlot, HourlyData, StationTechInfo } from '../types';

export const SHIFT_PLANNED_MIN = 440;
export const TARGET_OEE = 0.85;

export const HOURLY_SLOTS: Record<number, HourlySlot> = {
  1: { hour: 1, slot: "06:00 - 07:00", am_min: 10, break_min: 0,  planned_min: 50, target_pcs: 50 },
  2: { hour: 2, slot: "07:00 - 08:00", am_min: 0,  break_min: 0,  planned_min: 60, target_pcs: 60 },
  3: { hour: 3, slot: "08:00 - 09:00", am_min: 0,  break_min: 0,  planned_min: 60, target_pcs: 60 },
  4: { hour: 4, slot: "09:00 - 10:00", am_min: 0,  break_min: 0,  planned_min: 60, target_pcs: 60 },
  5: { hour: 5, slot: "10:00 - 11:00", am_min: 0,  break_min: 30, planned_min: 30, target_pcs: 30 },
  6: { hour: 6, slot: "11:00 - 12:00", am_min: 0,  break_min: 0,  planned_min: 60, target_pcs: 60 },
  7: { hour: 7, slot: "12:00 - 13:00", am_min: 0,  break_min: 0,  planned_min: 60, target_pcs: 60 },
  8: { hour: 8, slot: "13:00 - 14:00", am_min: 0,  break_min: 0,  planned_min: 60, target_pcs: 60 },
};

export const DOWNTIME_CATALOG: Record<string, { code: string; station: string; name_sk: string; category: string }> = {
  "ST-038": { code: "ST-038", station: "Stanica 3: Kamera", name_sk: "Svetelný modul kamery prerušil činnosť", category: "Kamera / Camera" },
  "ST-046": { code: "ST-046", station: "Stanica 9: Leak test", name_sk: "Meracia jednotka tesnosti prerušila skúšku", category: "Test tesnosti / Leak test" },
  "ST-016": { code: "ST-016", station: "Stanica 3: Kamera", name_sk: "Kamerové pracovisko prerušilo činnosť", category: "Kamera / Camera" },
  "ST-001": { code: "ST-001", station: "Stanica 1-2: Vstup", name_sk: "Zásobovanie dielmi zlyhalo", category: "Logistika / Vstup dielov" },
  "ST-047": { code: "ST-047", station: "Stanica 9: Leak test", name_sk: "Skúšobné lôžko - netesnosť adaptéra", category: "Test tesnosti / Leak test" },
  "ST-026": { code: "ST-026", station: "Stanica 2: Lisovanie", name_sk: "Lisovacia jednotka prekročila limit sily", category: "Lisovanie / Pressing" },
  "ST-017": { code: "ST-017", station: "Stanica 4-5: Skrutkovanie", name_sk: "Sekvencia nástroja nebola dodržaná", category: "Skrutkovanie / Screwdriving" },
  "ST-032": { code: "ST-032", station: "Stanica 4-5: Skrutkovanie", name_sk: "Skrutkovací automat - pád spojovacieho materiálu", category: "Skrutkovanie / Screwdriving" },
  "ST-020": { code: "ST-020", station: "Stanica 10: Výstup EOL", name_sk: "Výstupný manipulátor prerušil cyklus", category: "Manipulácia / Robot" },
  "ST-041": { code: "ST-041", station: "Stanica 9: Leak test", name_sk: "Kalibračná odchýlka meracieho kanála", category: "Test tesnosti / Leak test" },
};

export const QUALITY_CATALOG: Record<string, { code: string; station: string; name_sk: string; category: string }> = {
  "Q-030": { code: "Q-030", station: "Stanica 3: Kamera", name_sk: "Výrobok neprešiel obrazovou kontrolou", category: "Kamera / Camera" },
  "Q-020": { code: "Q-020", station: "Stanica 2: Lisovanie", name_sk: "Lisovaný prvok nedosiahol cieľovú polohu", category: "Lisovanie / Pressing" },
  "Q-026": { code: "Q-026", station: "Stanica 4/5/8: Skrutkovanie", name_sk: "Skrutkový spoj nemá potrebné dotiahnutie", category: "Skrutkovanie / Screwdriving" },
  "Q-031": { code: "Q-031", station: "Stanica 9: Leak test", name_sk: "Únik testovacieho média z puzdra pohonu", category: "Test tesnosti / Leak test" },
  "Q-008": { code: "Q-008", station: "Stanica 6: Rotácia", name_sk: "Chybná orientácia dielu po otočení", category: "Montáž / Assembly" },
  "Q-032": { code: "Q-032", station: "Stanica 9: Leak test", name_sk: "Poškodenie tesniacej plochy príruby", category: "Test tesnosti / Leak test" },
};

export const LINE_STATIONS: StationTechInfo[] = [
  {
    id: 1,
    name: "Naloženie puzdra",
    name_en: "Loading of housing",
    type: "Manipulácia",
    tech: "Robot ABB IRB 2600 + Schunk Gripper",
    critical_part: "Pneumatická prísavka & optický snímač usadenia",
    related_codes: ["ST-001", "ST-020"],
    telemetry: { temp_c: 34.2, pressure_bar: 6.2, vibration_mm_s: 1.1, cycle_time: 58 },
    description: "Automatický prísun a naloženie hliníkového puzdra prevodovky na montážny paletový unášač.",
    five_why: [
      "Paletka mešká na vstupe",
      "Gravitačný zásobník je prázdny",
      "Operátor nestihol doplniť box",
      "Andon signalizácia nezopla včas",
      "Chýbajúci min-max senzor hladiny dielov"
    ],
    sensors: [
      { name: "Snímač prítomnosti puzdra (DI 10.0)", value: "24V / AKTÍVNY", status: "ok" },
      { name: "Tlakový spínač vákua", value: "-0.82 bar", status: "ok" },
      { name: "Svetelná závora bezpečnosti", value: "OK", status: "ok" }
    ],
    cause: "Oneskorenie dodávky materiálu zo skladu komponentov",
    remedy_steps: [
      "Aktivovať Andon privolanie logistiky",
      "Vytvoriť pohotovostný zásobník dielov priamo pri vstupe",
      "Overiť priechodnosť vstupného gravitačného sklíčka"
    ],
    lean_tool: "Lean Kitting & Andon",
    lean_desc: "Zabezpečiť materiál 10 minút pred ukončením prestávky."
  },
  {
    id: 2,
    name: "Nalisovanie el. motora",
    name_en: "Insertion of electric motor",
    type: "Hydraulické lisovanie",
    tech: "Servoelektrický lis Kistler 50kN",
    critical_part: "Lisovací tŕň & piezoelektrický snímač sily",
    related_codes: ["ST-026", "Q-020"],
    telemetry: { temp_c: 42.5, pressure_bar: 48.1, vibration_mm_s: 3.4, cycle_time: 61 },
    description: "Presné nalisovanie rotora do ložiskového štítu s monitorovaním silovej krivky v reálnom čase.",
    five_why: [
      "Diel vyhodnotený ako NOK (Q-020)",
      "Lisovací prvok nedosiahol cieľovú polohu",
      "Sila prekročila limit 45 kN pred dosadnutím",
      "Zvýšený odpor vlisovania spôsobený toleranciou priemeru",
      "Tepelná rozťažnosť dielu po predchádzajúcom opracovaní"
    ],
    sensors: [
      { name: "Pravítko merania hĺbky vlisovania", value: "42.1 mm (Limit 42±0.2)", status: "ok" },
      { name: "Piezo snímač lisovacej sily", value: "38.4 kN (Max 50 kN)", status: "warning" },
      { name: "Koncový doraz servolôžka", value: "OK", status: "ok" }
    ],
    cause: "Zvýšený odpor vlisovania v dôsledku rozmerovej odchýlky rotora",
    remedy_steps: [
      "Skontrolovať silovú krivku lisovania v systéme Kistler",
      "Skontrolovať prítomnosť nečistôt a otrepov na sedle ložiska",
      "Overiť kalibráciu snímača dráhy lisovania"
    ],
    lean_tool: "Poka-Yoke & 5-Why",
    lean_desc: "Zaviesť automatickú kontrolu priemeru rotora pred vlisovaním."
  },
  {
    id: 3,
    name: "Kamerová kontrola",
    name_en: "Camera inspection",
    type: "Optická kontrola",
    tech: "Cognex In-Sight 8402P + LED Kruhové osvetlenie",
    critical_part: "Svetelný modul (LED ring) & optický polarizačný filter",
    related_codes: ["ST-016", "ST-038", "Q-030"],
    telemetry: { temp_c: 48.0, pressure_bar: 5.8, vibration_mm_s: 4.8, cycle_time: 63 },
    description: "Vysokorýchlostné 3D rozpoznávanie pozície puzdra, tesniacich krúžkov a povrchových chýb.",
    five_why: [
      "Kamerová stanica hlási kritickú chybu ST-038",
      "Intenzita osvetlenia klesla pod minimálnu hranicu 400 lux",
      "Kruhový LED iluminátor zhasol počas snímania",
      "Napájací konektor X2 sa uvoľnil na svorke 24V DC",
      "Mechanické vibrácie dopravníka uvoľnili poistku konektora"
    ],
    sensors: [
      { name: "Svetelný tok osvetlenia", value: "310 lux (Norma > 500 lux)", status: "alarm" },
      { name: "Napájacie napätie LED", value: "21.4 V (Pokles z 24V)", status: "warning" },
      { name: "Ethernet/IP komunikácia PLC", value: "ONLINE", status: "ok" }
    ],
    cause: "Znečistenie optickej šošovky prachom a uvoľnený napájací konektor LED",
    remedy_steps: [
      "Bezpečne odpojiť napájanie osvetľovacieho modulu (LOTO)",
      "Očistiť optickú šošovku a difúzor izopropylalkoholom",
      "Dotiahnuť a zaistiť konektor X2 napájania 24V",
      "Spustiť kalibračný testovací obraz v Cognex In-Sight Exploreri"
    ],
    lean_tool: "Autonomous Maintenance (AM)",
    lean_desc: "Denný 10-minútový checklist autonómnej údržby pred štartom rannej zmeny."
  },
  {
    id: 4,
    name: "Skrutkovanie ložiska A",
    name_en: "Screwdriving Bearing A",
    type: "Automatické skrutkovanie",
    tech: "Atlas Copco Tensor STR + Automatický podávač skrutiek",
    critical_part: "Vreteno skrutkovača & bit Torx T25",
    related_codes: ["ST-017", "ST-032", "Q-026"],
    telemetry: { temp_c: 38.0, pressure_bar: 6.0, vibration_mm_s: 1.8, cycle_time: 59 },
    description: "Utiahnutie 4 skrutiek ložiskového domca predpísaným momentom 12.5 Nm.",
    five_why: [
      "Skrutka nedotiahnutá (Q-026)",
      "Dosiahnutý mezní uhol pred momentom",
      "Nečistota v závitovom otvore",
      "Otrep z obrábania na vstupe",
      "Opotrebený závitník na dodávateľskej linke"
    ],
    sensors: [
      { name: "Uťahovací moment", value: "12.4 Nm (Cieľ 12.5 Nm)", status: "ok" },
      { name: "Uhol natočenia skrutky", value: "482° (Limit 480±20°)", status: "ok" }
    ],
    cause: "Opotrebovaný uťahovací bit spôsobil prešmyknutie na hlave skrutky",
    remedy_steps: [
      "Skontrolovať opotrebenie uťahovacieho bitu a vymeniť pri poškodení",
      "Preveriť tlak v pneumatickom podávači spojovacieho materiálu",
      "Overiť kalibračný protokol uťahovacieho vretena"
    ],
    lean_tool: "Poka-Yoke",
    lean_desc: "Sledovanie gradientu momentu/uhla dN/dalpha."
  },
  {
    id: 5,
    name: "Skrutkovanie ložiska B",
    name_en: "Screwdriving Bearing B",
    type: "Automatické skrutkovanie",
    tech: "Atlas Copco Tensor STR",
    critical_part: "Vreteno skrutkovača & bit Torx T25",
    related_codes: ["ST-017", "Q-026"],
    telemetry: { temp_c: 37.5, pressure_bar: 6.0, vibration_mm_s: 1.6, cycle_time: 58 },
    description: "Finálne symetrické dotiahnutie uloženia statora v magnetickom obvode.",
    five_why: [
      "Hlásenie varovania uhla",
      "Odchýlka uťahovacej krivky",
      "Mierny sklon osi skrutkovača",
      "Opotrebované vodiace puzdro",
      "Predĺžený interval preventívnej výmeny"
    ],
    sensors: [
      { name: "Uťahovací moment", value: "12.6 Nm", status: "ok" },
      { name: "Uhol uťahovania", value: "485°", status: "ok" }
    ],
    cause: "Pád skrutky z vodiacej hubice pri podávaní",
    remedy_steps: [
      "Prefúknuť transportnú hadicu stlačeným vzduchom",
      "Vyčistiť čeľuste uťahovacej hlavy"
    ],
    lean_tool: "5S & Standard Work",
    lean_desc: "Pravidelné čistenie čeľustí každú zmenu."
  },
  {
    id: 6,
    name: "Robotické tesnenie",
    name_en: "Robotic Gasket Dispensing",
    type: "Dávkovanie tmelu",
    tech: "KUKA KR 10 cybertech + Nordson Pro-Meter Dávkovač",
    critical_part: "Dávkovacia tryska tesniaceho silikónu & prietokomer",
    related_codes: ["Q-008", "ST-020"],
    telemetry: { temp_c: 41.0, pressure_bar: 5.5, vibration_mm_s: 1.4, cycle_time: 60 },
    description: "Nanášanie súvislej húsenice anaeróbneho tmelu po obvode deliacej roviny prevodovky.",
    five_why: [
      "Nekonzistentná šírka húsenice tmelu",
      "Kolísanie viskozity tmelu",
      "Teplota ohrevu trysky klesla pod 25°C",
      "Zlyhanie vyhrievacieho odporového článku",
      "Zanesenie snímača teploty"
    ],
    sensors: [
      { name: "Teplota tmelu v tryske", value: "24.8°C (Norma 25±2°C)", status: "ok" },
      { name: "Prietokový tlak dávkovača", value: "142 bar", status: "ok" }
    ],
    cause: "Zaschnutý tmel na výstupnej dýze z dôvodu prestávky vo výrobe",
    remedy_steps: [
      "Spustiť automatický preplach dýzy do odpadovej nádoby",
      "Skontrolovať tvar a spojitosť testovacej húsenice na kontrolnom plechu"
    ],
    lean_tool: "Standardized Work",
    lean_desc: "Automatický preplach trysky po každom prestoji dlhšom ako 15 minút."
  },
  {
    id: 7,
    name: "UV vytvrdzovanie",
    name_en: "UV Curing Chamber",
    type: "Vytvrdzovacia komora",
    tech: "Honle UV Technology LED Komora",
    critical_part: "UV LED žiarič 365nm & snímač ožiarenia",
    related_codes: ["ST-020"],
    telemetry: { temp_c: 52.0, pressure_bar: 6.0, vibration_mm_s: 0.9, cycle_time: 57 },
    description: "Rýchle fotopolymerizačné vytvrdenie tesniacej vrstvy počas 12 sekúnd expozície.",
    five_why: [
      "Čas expozície predĺžený o 2s",
      "Snímač intenzity zaznamenal útlm",
      "Ochranné kremenné sklo zaprášené",
      "Odsávanie pár z tmelu znížilo výkon",
      "Zanesený HEPA filter ventilačného okruhu"
    ],
    sensors: [
      { name: "UV intenzita žiarenia", value: "2450 mW/cm²", status: "ok" },
      { name: "Teplota chladiaceho okruhu", value: "28.5°C", status: "ok" }
    ],
    cause: "Pokles intenzity UV v dôsledku zaprášenia ochranného skla",
    remedy_steps: [
      "Očistiť ochranné kremenné sklo jemnou utierkou",
      "Overiť prietok chladiaceho vzduchu cez filter"
    ],
    lean_tool: "Preventive Maintenance",
    lean_desc: "Kontrola kremenného skla raz za týždeň."
  },
  {
    id: 8,
    name: "Finálne skrutkovanie",
    name_en: "Final Cover Screwdriving",
    type: "Automatické skrutkovanie",
    tech: "Atlas Copco viacvretenový uťahovák (6 vretien)",
    critical_part: "Uťahovacie vretená & unášače skrutiek",
    related_codes: ["ST-017", "Q-026"],
    telemetry: { temp_c: 39.0, pressure_bar: 6.2, vibration_mm_s: 2.1, cycle_time: 60 },
    description: "Súčasné dotiahnutie 6 skrutiek vonkajšieho krytu prevodovky krížovým vzorom.",
    five_why: [
      "Vreteno 3 hlási odchýlku",
      "Zvýšený odpor v úvodnom nábehu",
      "Kríženie závitu skrutky",
      "Nesprávny nábehový uhol podávača",
      "Opotrebované vystredovacie lôžko"
    ],
    sensors: [
      { name: "Synchronizácia vretien", value: "VŠETKY OK", status: "ok" },
      { name: "Priemerný moment", value: "14.2 Nm (Norma 14±1 Nm)", status: "ok" }
    ],
    cause: "Kríženie závitu pri nábehu skrutky",
    remedy_steps: [
      "Vizuálne skontrolovať závit na bloku",
      "Vymeniť poškodenú skrutku manuálne",
      "Zresetovať viacvretenový cyklus"
    ],
    lean_tool: "Poka-Yoke",
    lean_desc: "Automatické zastavenie pri prekročení uhlového odporu v prvých 2 otáčkach."
  },
  {
    id: 9,
    name: "Test tesnosti (Leak test)",
    name_en: "Pneumatic Leak Testing",
    type: "Pneumatická skúška tesnosti",
    tech: "Ateq F620 Diferenciálny tester úniku vzduchu",
    critical_part: "Tesniace adaptéry, rýchlospojky a diferenčný snímač tlaku",
    related_codes: ["ST-041", "ST-046", "ST-047", "Q-031", "Q-032"],
    telemetry: { temp_c: 24.5, pressure_bar: 3.2, vibration_mm_s: 1.0, cycle_time: 62 },
    description: "Tlakovanie puzdra na 3.0 bar a meranie mikropoklesu tlaku počas 30s stabilizácie.",
    five_why: [
      "Chyba ST-046 — Skúška tesnosti prerušená",
      "Tlak v testovacej komore klesol pod limit tolerancie",
      "Rýchlospojka pneumatického adaptéra nedosadla tesne",
      "O-krúžok na testovacom adaptéri vykazuje mikrotrhlinu",
      "O-krúžok nebol vymenený v predpísanom intervale (prekročených 10 000 cyklov)"
    ],
    sensors: [
      { name: "Testovací pretlak v komore", value: "2.98 bar (Norma 3.00±0.05)", status: "warning" },
      { name: "Diferenčný únik dP", value: "48 Pa (Limit max 30 Pa)", status: "alarm" },
      { name: "Stav upínacieho prípravku", value: "ZOPNUTÝ", status: "ok" }
    ],
    cause: "Netesnosť pneumatického adaptéra na testovacom lôžku ST-047 spôsobená opotrebovaným O-krúžkom",
    remedy_steps: [
      "Vymeniť tesniaci O-krúžok na testovacom lôžku ST-047",
      "Skontrolovať čistotu dosadacej plochy puzdra prevodovky",
      "Vykonať nulovanie a kalibráciu snímača Ateq F620 referenčným etalónom"
    ],
    lean_tool: "Preventive Maintenance",
    lean_desc: "Plánovaná výmena tesnení testovacieho lôžka každé 2 týždne."
  },
  {
    id: 10,
    name: "Výstup na EOL test",
    name_en: "Transfer to EOL testing",
    type: "Manipulácia a EOL výstup",
    tech: "Fanuc M-20iD/25 Robot + EOL Dopravník",
    critical_part: "Výstupné dopravníkové hniezdo & RFID čítačka",
    related_codes: ["ST-020"],
    telemetry: { temp_c: 32.0, pressure_bar: 6.0, vibration_mm_s: 1.2, cycle_time: 56 },
    description: "Konečný odber hotového pohonu, zápis rodného listu do RFID čipu a odoslanie na EOL.",
    five_why: [
      "Výstupný manipulátor prerušil cyklus (ST-020)",
      "Výstupné hniezdo hlási blokovanie",
      "EOL vyrovnávací dopravník je plný",
      "Tester na EOL stanici mal zdržanie",
      "Nerovnomerný takt medzi montážnou linkou a koncovým testom"
    ],
    sensors: [
      { name: "Snímač prevzatia EOL", value: "PRIPRAVENÝ", status: "ok" },
      { name: "RFID zápis rodného listu", value: "ÚSPEŠNÝ", status: "ok" }
    ],
    cause: "Zaplnenie vyrovnávacieho zásobníka EOL testovacej komory",
    remedy_steps: [
      "Uvoľniť výstupné hniezdo a preveriť stav EOL komory",
      "Potvrdiť odber hotového kusu v riadiacom PLC"
    ],
    lean_tool: "Kanban & One-Piece-Flow",
    lean_desc: "Rovnomerné taktovanie toku jedného kusu medzi montážou a testom."
  }
];

export const SLIDE_11_RAW = [
  { hour: 1, produced_pcs: 48, nok_pcs: 0, downtime_min: 0, downtime_code: null, nok_code: null },
  { hour: 2, produced_pcs: 57, nok_pcs: 0, downtime_min: 0, downtime_code: null, nok_code: null },
  { hour: 3, produced_pcs: 40, nok_pcs: 1, downtime_min: 15, downtime_code: "ST-046", nok_code: "Q-030", downtime_from: "08:15", downtime_to: "08:30" },
  { hour: 4, produced_pcs: 20, nok_pcs: 1, downtime_min: 30, downtime_code: "ST-038", nok_code: "Q-026", downtime_from: "09:10", downtime_to: "09:40" },
  { hour: 5, produced_pcs: 25, nok_pcs: 0, downtime_min: 0, downtime_code: null, nok_code: null },
  { hour: 6, produced_pcs: 52, nok_pcs: 1, downtime_min: 0, downtime_code: null, nok_code: "Q-020" },
  { hour: 7, produced_pcs: 55, nok_pcs: 1, downtime_min: 0, downtime_code: null, nok_code: "Q-020" },
  { hour: 8, produced_pcs: 56, nok_pcs: 0, downtime_min: 0, downtime_code: null, nok_code: null },
];

export const CURRENT_WEEK_DAYS = [
  { day: "Pondelok", shortDay: "Po", date: "16.11.2026", target: 440, produced: 407, good: 398, nok: 9, downtime_min: 9,  a: 0.9795, p: 0.9443, q: 0.9779, oee: 0.9045, goal_met: true },
  { day: "Utorok",   shortDay: "Ut", date: "17.11.2026", target: 440, produced: 399, good: 393, nok: 6, downtime_min: 15, a: 0.9659, p: 0.9388, q: 0.9850, oee: 0.8932, goal_met: true },
  { day: "Streda",   shortDay: "St", date: "18.11.2026", note: "Dnešná zmena", target: 440, produced: 377, good: 370, nok: 7, downtime_min: 25, a: 0.9432, p: 0.9084, q: 0.9814, oee: 0.8409, goal_met: false },
  { day: "Štvrtok",  shortDay: "Št", date: "19.11.2026", target: 440, produced: 396, good: 392, nok: 4, downtime_min: 15, a: 0.9659, p: 0.9318, q: 0.9899, oee: 0.8909, goal_met: true },
  { day: "Piatok",   shortDay: "Pi", date: "20.11.2026", target: 440, produced: 408, good: 404, nok: 4, downtime_min: 9,  a: 0.9795, p: 0.9466, q: 0.9902, oee: 0.9182, goal_met: true },
];

export const WEEKLY_DATA = [
  { week: "Týždeň 45 (02-06.11)", shifts: 5, target: 2200, produced: 1960, good: 1929, nok: 31, downtime_min: 112, a: 0.9491, p: 0.9387, q: 0.9842, oee: 0.8768 },
  { week: "Týždeň 46 (09-13.11)", shifts: 5, target: 2200, produced: 1962, good: 1936, nok: 26, downtime_min: 92,  a: 0.9582, p: 0.9307, q: 0.9867, oee: 0.8800 },
  { week: "Týždeň 47 (16-20.11)", shifts: 5, target: 2200, produced: 1987, good: 1957, nok: 30, downtime_min: 73,  a: 0.9668, p: 0.9342, q: 0.9849, oee: 0.8895 },
  { week: "Týždeň 48 (23-27.11)", shifts: 5, target: 2200, produced: 1940, good: 1916, nok: 24, downtime_min: 120, a: 0.9455, p: 0.9327, q: 0.9876, oee: 0.8709 },
  { week: "Týždeň 49 (30.11)",    shifts: 1, target: 440,  produced: 402,  good: 394,  nok: 8,  downtime_min: 13,  a: 0.9705, p: 0.9415, q: 0.9801, oee: 0.8955 },
];

export const MONTH_SHIFTS_DATA = [
  { date: "2026-11-02", day: "Po", plan_min: 440, downtime_min: 23, produced: 393, ok: 384, nok: 9, a: 0.9477, p: 0.9424, q: 0.9771, oee: 0.8727, goal_met: true },
  { date: "2026-11-03", day: "Ut", plan_min: 440, downtime_min: 17, produced: 403, ok: 396, nok: 7, a: 0.9614, p: 0.9527, q: 0.9826, oee: 0.9000, goal_met: true },
  { date: "2026-11-04", day: "St", plan_min: 440, downtime_min: 35, produced: 366, ok: 359, nok: 7, a: 0.9205, p: 0.9037, q: 0.9809, oee: 0.8159, goal_met: false },
  { date: "2026-11-05", day: "Št", plan_min: 440, downtime_min: 28, produced: 391, ok: 388, nok: 3, a: 0.9364, p: 0.9490, q: 0.9923, oee: 0.8818, goal_met: true },
  { date: "2026-11-06", day: "Pi", plan_min: 440, downtime_min: 9,  produced: 407, ok: 402, nok: 5, a: 0.9795, p: 0.9443, q: 0.9877, oee: 0.9136, goal_met: true },
  { date: "2026-11-09", day: "Po", plan_min: 440, downtime_min: 11, produced: 403, ok: 397, nok: 6, a: 0.9750, p: 0.9394, q: 0.9851, oee: 0.9023, goal_met: true },
  { date: "2026-11-10", day: "Ut", plan_min: 440, downtime_min: 15, produced: 400, ok: 394, nok: 6, a: 0.9659, p: 0.9412, q: 0.9850, oee: 0.8955, goal_met: true },
  { date: "2026-11-11", day: "St", plan_min: 440, downtime_min: 36, produced: 368, ok: 362, nok: 6, a: 0.9182, p: 0.9109, q: 0.9837, oee: 0.8227, goal_met: false },
  { date: "2026-11-12", day: "Št", plan_min: 440, downtime_min: 15, produced: 397, ok: 392, nok: 5, a: 0.9659, p: 0.9341, q: 0.9874, oee: 0.8909, goal_met: true },
  { date: "2026-11-13", day: "Pi", plan_min: 440, downtime_min: 15, produced: 394, ok: 391, nok: 3, a: 0.9659, p: 0.9271, q: 0.9924, oee: 0.8886, goal_met: true },
  { date: "2026-11-16", day: "Po", plan_min: 440, downtime_min: 9,  produced: 407, ok: 398, nok: 9, a: 0.9795, p: 0.9443, q: 0.9779, oee: 0.9045, goal_met: true },
  { date: "2026-11-17", day: "Ut", plan_min: 440, downtime_min: 15, produced: 399, ok: 393, nok: 6, a: 0.9659, p: 0.9388, q: 0.9850, oee: 0.8932, goal_met: true },
  { date: "2026-11-18", day: "St", plan_min: 440, downtime_min: 25, produced: 377, ok: 370, nok: 7, a: 0.9432, p: 0.9084, q: 0.9814, oee: 0.8409, goal_met: false },
  { date: "2026-11-19", day: "Št", plan_min: 440, downtime_min: 15, produced: 396, ok: 392, nok: 4, a: 0.9659, p: 0.9318, q: 0.9899, oee: 0.8909, goal_met: true },
  { date: "2026-11-20", day: "Pi", plan_min: 440, downtime_min: 9,  produced: 408, ok: 404, nok: 4, a: 0.9795, p: 0.9466, q: 0.9902, oee: 0.9182, goal_met: true },
  { date: "2026-11-23", day: "Po", plan_min: 440, downtime_min: 23, produced: 394, ok: 390, nok: 4, a: 0.9477, p: 0.9448, q: 0.9898, oee: 0.8864, goal_met: true },
  { date: "2026-11-24", day: "Ut", plan_min: 440, downtime_min: 16, produced: 399, ok: 394, nok: 5, a: 0.9636, p: 0.9410, q: 0.9875, oee: 0.8955, goal_met: true },
  { date: "2026-11-25", day: "St", plan_min: 440, downtime_min: 48, produced: 350, ok: 344, nok: 6, a: 0.8909, p: 0.8929, q: 0.9829, oee: 0.7818, goal_met: false },
  { date: "2026-11-26", day: "Št", plan_min: 440, downtime_min: 15, produced: 400, ok: 393, nok: 7, a: 0.9659, p: 0.9412, q: 0.9825, oee: 0.8932, goal_met: true },
  { date: "2026-11-27", day: "Pi", plan_min: 440, downtime_min: 18, produced: 397, ok: 395, nok: 2, a: 0.9591, p: 0.9408, q: 0.9950, oee: 0.8977, goal_met: true },
  { date: "2026-11-30", day: "Po", plan_min: 440, downtime_min: 13, produced: 402, ok: 394, nok: 8, a: 0.9705, p: 0.9415, q: 0.9801, oee: 0.8955, goal_met: true },
];

export const PARETO_DOWNTIME = [
  { code: "ST-038", name: "Svetelný modul kamery", minutes: 100, cum_pct: 24.4, percent: 24.4 },
  { code: "ST-016", name: "Kamerové pracovisko (Vision)", minutes: 70, cum_pct: 41.5, percent: 17.1 },
  { code: "ST-046", name: "Meracia jednotka tesnosti", minutes: 70, cum_pct: 58.5, percent: 17.1 },
  { code: "ST-001", name: "Zásobovanie dielmi zlyhalo", minutes: 60, cum_pct: 73.2, percent: 14.6 },
  { code: "ST-047", name: "Testovacie lôžko - netesnosť", minutes: 60, cum_pct: 87.8, percent: 14.6 },
  { code: "ST-017", name: "Prerušená sekvencia nástroja", minutes: 50, cum_pct: 100.0, percent: 12.2 },
];

export const PARETO_DEFECTS = [
  { code: "Q-031", name: "Únik testovacieho média (Leak)", pcs: 38, cum_pct: 31.9, percent: 31.9 },
  { code: "Q-020", name: "Lisovaný prvok mimo polohy", pcs: 28, cum_pct: 55.5, percent: 23.5 },
  { code: "Q-026", name: "Skrutkový spoj nedotiahnutý", pcs: 28, cum_pct: 79.0, percent: 23.5 },
  { code: "Q-030", name: "Výrobok neprešiel kamerou", pcs: 25, cum_pct: 100.0, percent: 21.0 },
];
