"""
AI Engine: Integration with local Qwen 2.5 3B via Ollama.
Generates engineer instructions, root cause (5-Why) analysis,
and problem correlation without sending any data to the cloud.
"""

import json
import requests
from typing import Dict, Any, Optional
from constants import DOWNTIME_CATALOG, QUALITY_CATALOG

OLLAMA_API_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:3b"

# Pre-cached expert domain knowledge from Magna Slide 13 (Fallback & Few-shot anchors)
EXPERT_KNOWLEDGE = {
    "ST-038": {
        "title": "Svetelný modul kamery prerušil činnosť (Stanica 3)",
        "station": "Stanica 3: Camera inspection",
        "action": "Skontrolovať snímač a svetelný modul kamery. Očistiť optickú šošovku od prachu a mastnoty. Preveriť konektor napájania LED modulu.",
        "lean_tool": "Autonomous Maintenance (AM)",
        "countermeasure": "Zaradiť kontrolu a čistenie osvetlenia kamery do denného 10-minútového AM чеклиста pred štartom zmeny.",
        "correlation": "Tento výpadok priamo spôsobuje falošné zamietnutia optického testu Q-030! Oprava osvetlenia zníži chybný brak o ~80% na Stanici 3.",
        "oee_gain": "+1.08 p.b. OEE (+25 ks/zmena)"
    },
    "ST-046": {
        "title": "Meracia jednotka tesnosti prerušila skúšku (Stanica 9)",
        "station": "Stanica 9: Leak test",
        "action": "Preveriť tlakový snímač a pripojenie pneumatickej hadice. Resetovať meraciu jednotku v servisnom menu.",
        "lean_tool": "Preventive Maintenance & Calibration",
        "countermeasure": "Naplánovať kontrolu kalibrácie prietokomeru a tesnení počas plánovanej údržby.",
        "correlation": "Závada priamo súvisí s chybou Q-031 (únik média). Preveriť tesnosť testovacieho lôžka ST-047.",
        "oee_gain": "+0.76 p.b. OEE (+15 ks/zmena)"
    },
    "ST-016": {
        "title": "Kamerové pracovisko prerušilo činnosť (Stanica 3)",
        "station": "Stanica 3: Camera inspection",
        "action": "Skontrolovať polohovanie dielu v zornom poli kamery. Reštartovať komunikačný modul vision systému.",
        "lean_tool": "Vision Tuning & Standardized Work",
        "countermeasure": "Optimalizovať softvérové prahy (thresholds) detekcie pre zníženie počtu retestov.",
        "correlation": "Časté mikrozastavenia vedú k zníženiu Performance o 4-6% počas ranného rozbehu.",
        "oee_gain": "+0.76 p.b. OEE (+15 ks/zmena)"
    },
    "ST-001": {
        "title": "Diel nie je pripravený na pracovisku (Stanica 1-2)",
        "station": "Stanica 1/2: Zásobovanie",
        "action": "Privolať logistiku (Andon signál). Pripraviť nárazníkový buffer dielov priamo pri linke.",
        "lean_tool": "Kitting & Mizusumashi",
        "countermeasure": "Štandardizovaný reštart: zabezpečiť dodanie materiálu 10 minút pred ukončením prestávky.",
        "correlation": "Spôsobuje domino efekt spomalenia na všetkých nadväzujúcich staniciach linky.",
        "oee_gain": "+0.65 p.b. OEE (+14 ks/zmena)"
    },
    "ST-047": {
        "title": "Skúšobné lôžko prepúšťa vzduch (Stanica 9)",
        "station": "Stanica 9: Leak test",
        "action": "Vymeniť tesniace manžety testovacieho hniezda č. 2. Skontrolovať prítlak pneumatického valca.",
        "lean_tool": "5-Why & Poka-Yoke",
        "countermeasure": "Zaviesť počítadlo cyklov tesnenia s automatickým varovaním pred opotrebovaním.",
        "correlation": "Netesnosť lôžka simuluje chybu výrobku a spôsobuje neoprávnený nárast NOK kusov Q-031.",
        "oee_gain": "+0.65 p.b. OEE (+15 ks/zmena)"
    },
    "ST-017": {
        "title": "Pracovná sekvencia nástroja sa zastavila (Stanica 4/5/8)",
        "station": "Stanica 4, 5, 8: Skrutkovanie",
        "action": "Skontrolovať mechanické zaseknutie skrutkovača, preveriť prívod stlačeného vzduchu a stav bitu.",
        "lean_tool": "SMED & Tool Management",
        "countermeasure": "Pripraviť externé náhradné skrutkovacie vreteno pre rýchlu výmenu do 5 minút.",
        "correlation": "Priamo ovplyvňuje chybu Q-026 (nedotiahnutý skrutkový spoj z dôvodu prerušeného cyklu).",
        "oee_gain": "+0.54 p.b. OEE (+12 ks/zmena)"
    }
}


def analyze_with_qwen(
    downtime_code: str,
    lost_minutes: int,
    nok_code: Optional[str] = None,
    nok_qty: int = 0
) -> Dict[str, Any]:
    """
    Query local Qwen 2.5 3B via Ollama with prompt engineering based on Magna Slide 13.
    Falls back gracefully to instant expert rules if Ollama is unreachable.
    """
    dt_info = DOWNTIME_CATALOG.get(downtime_code, {})
    q_info = QUALITY_CATALOG.get(nok_code, {}) if nok_code else {}
    cached = EXPERT_KNOWLEDGE.get(downtime_code)

    system_prompt = (
        "Si expert na Lean Manufacturing, TPM a automobilovú výrobu (Magna Powertrain, L01 Electric Drive Line). "
        "Tvojou úlohou je poskytnúť zmenovému inžinierovi a manažérovi výroby jasný, vysoko odborný a konkrétny "
        "postup riešenia technického výpadku a nekvality. "
        "Používaj metodiky: SMED, Poka-Yoke, Autonómna údržba (AM), 5-Prečo (5-Why), kalibrácia a vizuálny manažment. "
        "Odpovedaj v slovenskom jazyku. Formátuj odpoveď prehľadne v odrážkach."
    )

    user_prompt = (
        f"Na montážnej linke L01 došlo k výpadku:\n"
        f"- Kód poruchy: {downtime_code} ({dt_info.get('name_sk', 'Neznámy')})\n"
        f"- Pracovisko: {dt_info.get('station', 'Linka L01')}\n"
        f"- Stratený čas: {lost_minutes} minút\n"
    )
    if nok_code:
        user_prompt += (
            f"- Súčasný defekt kvality: {nok_code} ({q_info.get('name_sk', '')}), počet: {nok_qty} ks NOK\n"
        )

    user_prompt += (
        "\nVygeneruj pre zmenového inžiniera:\n"
        "1. OKAMŽITÝ ZÁSAH NA LINKE (Krok za krokom čo skontrolovať a vymeniť)\n"
        "2. KOREŇOVÁ PRÍČINA A PREVENCIA (Lean / TPM nástroj, čo zaradiť do AM чеклиста)\n"
        "3. KORELÁCIA PROBLÉMOV (Ako tento výpadok súvisí s defektmi kvality a taktom linky)\n"
        "4. ODHADOVANÝ PRÍNOS (Ako oprava zlepší OEE a koľko kusov vráti do produkcie)\n"
    )

    # Try connecting to local Ollama
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "top_p": 0.9,
                    "num_predict": 450
                }
            },
            timeout=12
        )
        if response.status_code == 200:
            result = response.json()
            content = result.get("message", {}).get("content", "")
            if content.strip():
                return {
                    "source": f"🧠 Lokálna Qwen 2.5 3B (Ollama - On-Premise AI)",
                    "content": content,
                    "success": True
                }
    except Exception as e:
        pass

    # Fallback to rich pre-cached expert rules
    fallback_content = ""
    if cached:
        fallback_content = (
            f"### 📋 Odporúčaný postup zmenového inžiniera pre {downtime_code}:\n\n"
            f"**1. OKAMŽITÝ ZÁSAH (Pracovisko: {cached['station']}):**\n"
            f"- {cached['action']}\n\n"
            f"**2. PREVENCIA & LEAN METODIKA:**\n"
            f"- Metóda: **`{cached['lean_tool']}`**\n"
            f"- Opatrenie: {cached['countermeasure']}\n\n"
            f"**3. VZÁJOMNÝ VZŤAH A KORELÁCIA PROBLÉMOV:**\n"
            f"- {cached['correlation']}\n\n"
            f"**4. ODHADOVANÝ EFEKT NA OEE:**\n"
            f"- Očakávaný nárast: **{cached['oee_gain']}**."
        )
    else:
        fallback_content = (
            f"### 📋 Štandardný postup pre kód {downtime_code}:\n\n"
            f"**1. Okamžitý zásah:** Vykonať kontrolu mechanických a elektrických prvkov snímačov na {dt_info.get('station', 'pracovisku')}.\n"
            f"**2. Prevencia (Poka-Yoke / 5-Why):** Zvolať krátky 5-minútový review s údržbou a identifikovať koreňovú príčinu zastavenia.\n"
            f"**3. Korelácia:** Zamedziť opakovaniu mikrozastavení a skontrolovať vplyv na kvalitatívne parametre nasledujúcej operácie."
        )

    return {
        "source": "⚡ Expert Knowledge Base (Magna Slide 13 Rules)",
        "content": fallback_content,
        "success": True
    }
