"""
Constants and catalogs for Magna AI OEE Improvement Engine.
Based on Electric Drive Assembly Line (L01) specification.
"""

# Shift model constants
SHIFT_CALENDAR_MIN = 480       # 8 hours = 480 min (06:00 - 14:00)
SHIFT_PLANNED_MIN = 440        # 480 min - 10 AM - 30 Break = 440 min
IDEAL_CYCLE_TIME_S = 60        # 60 seconds per piece
TARGET_OEE = 0.85              # 85% OEE goal
TARGET_OEE_PIECES = 374        # 374 good pieces per shift (85% of 440)
TARGET_PIECES_100 = 440        # 440 ideal pieces per shift

# Hourly slot breakdown (1 to 8)
HOURLY_SLOTS = {
    1: {"slot": "06:00 - 07:00", "am_min": 10, "break_min": 0,  "planned_min": 50, "target_pcs": 50},
    2: {"slot": "07:00 - 08:00", "am_min": 0,  "break_min": 0,  "planned_min": 60, "target_pcs": 60},
    3: {"slot": "08:00 - 09:00", "am_min": 0,  "break_min": 0,  "planned_min": 60, "target_pcs": 60},
    4: {"slot": "09:00 - 10:00", "am_min": 0,  "break_min": 0,  "planned_min": 60, "target_pcs": 60},
    5: {"slot": "10:00 - 11:00", "am_min": 0,  "break_min": 30, "planned_min": 30, "target_pcs": 30},
    6: {"slot": "11:00 - 12:00", "am_min": 0,  "break_min": 0,  "planned_min": 60, "target_pcs": 60},
    7: {"slot": "12:00 - 13:00", "am_min": 0,  "break_min": 0,  "planned_min": 60, "target_pcs": 60},
    8: {"slot": "13:00 - 14:00", "am_min": 0,  "break_min": 0,  "planned_min": 60, "target_pcs": 60},
}

# TOP 10 Downtime Alarms (ST-xxx)
DOWNTIME_CATALOG = {
    "ST-038": {
        "code": "ST-038",
        "station": "Stanica 3: Kamera",
        "name_sk": "Svetelný modul kamery prerušil činnosť",
        "name_en": "Camera light module interrupted operation",
        "name_ua": "Збій світлового модуля камери",
        "category": "Kamera / Camera"
    },
    "ST-046": {
        "code": "ST-046",
        "station": "Stanica 9: Leak test",
        "name_sk": "Meracia jednotka tesnosti prerušila skúšku",
        "name_en": "Leak measurement unit interrupted test",
        "name_ua": "Блок вимірювання герметичності перервав тест",
        "category": "Test tesnosti / Leak test"
    },
    "ST-016": {
        "code": "ST-016",
        "station": "Stanica 3: Kamera",
        "name_sk": "Kamerové pracovisko prerušilo činnosť",
        "name_en": "Vision station interrupted operation",
        "name_ua": "Оптичний пост контролю зупинив роботу",
        "category": "Kamera / Camera"
    },
    "ST-001": {
        "code": "ST-001",
        "station": "Stanica 1-2: Zásobovanie",
        "name_sk": "Diel nie je pripravený na pracovisku",
        "name_en": "Part unavailable at station",
        "name_ua": "Деталь не підготовлена на станції (постачання)",
        "category": "Všeobecné / Logistics"
    },
    "ST-047": {
        "code": "ST-047",
        "station": "Stanica 9: Leak test",
        "name_sk": "Skúšobné lôžko prepúšťa vzduch",
        "name_en": "Test nest allows air leakage",
        "name_ua": "Протікання повітря в тестовому гнізді",
        "category": "Test tesnosti / Leak test"
    },
    "ST-017": {
        "code": "ST-017",
        "station": "Stanica 4/5/8: Nástroj",
        "name_sk": "Pracovná sekvencia nástroja sa zastavila",
        "name_en": "Tool work sequence halted",
        "name_ua": "Зупинка робочої послідовності інструменту",
        "category": "Nástroj / Tool"
    },
    "ST-026": {
        "code": "ST-026",
        "station": "Stanica 2: Lisovanie",
        "name_sk": "Sila lisovania prekročila povolené pásmo",
        "name_en": "Press force exceeded allowed band",
        "name_ua": "Зусилля запресовки перевищило допуск",
        "category": "Lisovanie / Pressing"
    },
    "ST-032": {
        "code": "ST-032",
        "station": "Stanica 4/5/8: Skrutkovanie",
        "name_sk": "Krútiaci moment mimo nastavenej oblasti",
        "name_en": "Tightening torque outside configured range",
        "name_ua": "Крутний момент поза налаштованим діапазоном",
        "category": "Skrutkovanie / Screwdriving"
    },
    "ST-034": {
        "code": "ST-034",
        "station": "Stanica 4/5/8: Podávač",
        "name_sk": "Podávač nepotvrdil prítomnosť skrutky",
        "name_en": "Feeder did not confirm screw presence",
        "name_ua": "Живильник не підтвердив наявність гвинта",
        "category": "Skrutkovanie / Screwdriving"
    },
    "ST-020": {
        "code": "ST-020",
        "station": "Stanica 1/10: Robot",
        "name_sk": "Robotické pracovisko hlási odstávku",
        "name_en": "Robot station reports downtime",
        "name_ua": "Роботизована станція звітує про зупинку",
        "category": "Robot / Automation"
    }
}

# TOP 10 Quality Defects (Q-xxx)
QUALITY_CATALOG = {
    "Q-031": {
        "code": "Q-031",
        "station": "Stanica 9: Leak test",
        "name_sk": "Okruh výrobku prepúšťa médium",
        "name_en": "Product circuit allows fluid escape",
        "name_ua": "Витік рідини/середовища з контуру виробу",
        "category": "Test tesnosti / Leak test"
    },
    "Q-020": {
        "code": "Q-020",
        "station": "Stanica 2: Lisovanie",
        "name_sk": "Lisovaný prvok nedosiahol cieľovú polohu",
        "name_en": "Press-fit element short of target position",
        "name_ua": "Запресований елемент недопресований до мітки",
        "category": "Lisovanie / Pressing"
    },
    "Q-026": {
        "code": "Q-026",
        "station": "Stanica 4/5/8: Skrutkovanie",
        "name_sk": "Skrutkový spoj nemá potrebné dotiahnutie",
        "name_en": "Threaded joint lacks required tightening",
        "name_ua": "Недостатня затяжка гвинтового з'єднання",
        "category": "Skrutkovanie / Screwdriving"
    },
    "Q-030": {
        "code": "Q-030",
        "station": "Stanica 3: Kamera",
        "name_sk": "Výrobok neprešiel obrazovou kontrolou",
        "name_en": "Product failed image-based check",
        "name_ua": "Виріб не пройшов оптичний контроль камери",
        "category": "Kamera / Camera"
    },
    "Q-021": {
        "code": "Q-021",
        "station": "Stanica 2: Lisovanie",
        "name_sk": "Lisovaný prvok prekročil cieľovú polohu",
        "name_en": "Press-fit element beyond target position",
        "name_ua": "Перепресовка (елемент зайшов за межу)",
        "category": "Lisovanie / Pressing"
    },
    "Q-025": {
        "code": "Q-025",
        "station": "Stanica 4/5/8: Skrutkovanie",
        "name_sk": "Skrutkový spoj nemá vloženú skrutku",
        "name_en": "Screw absent from threaded joint",
        "name_ua": "У гвинтовому з'єднанні відсутній гвинт",
        "category": "Skrutkovanie / Screwdriving"
    },
    "Q-027": {
        "code": "Q-027",
        "station": "Stanica 4/5/8: Skrutkovanie",
        "name_sk": "Závit spoja stratil funkčnosť",
        "name_en": "Joint thread no longer functional",
        "name_ua": "Пошкодження різьби під час закручування",
        "category": "Skrutkovanie / Screwdriving"
    },
    "Q-032": {
        "code": "Q-032",
        "station": "Stanica 9: Leak test",
        "name_sk": "Výrobok nemožno naplniť na skúšobný tlak",
        "name_en": "Product cannot reach test fill pressure",
        "name_ua": "Неможливо наповнити виріб до випробувального тиску",
        "category": "Test tesnosti / Leak test"
    },
    "Q-003": {
        "code": "Q-003",
        "station": "Stanica 1-10: Všeobecné",
        "name_sk": "Na komponente je zistené poškodenie",
        "name_en": "Component shows physical damage",
        "name_ua": "Виявлено фізичне пошкодження компонента",
        "category": "Všeobecné / General"
    },
    "Q-008": {
        "code": "Q-008",
        "station": "Stanica 6: Rotácia / Zostava",
        "name_sk": "Osi spojených prvkov nie sú zarovnané",
        "name_en": "Joined element axes not aligned",
        "name_ua": "Осі з'єднаних деталей не вирівняні (перекіс)",
        "category": "Všeobecné / Assembly"
    }
}
