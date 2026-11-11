import React, { useState, useRef, useEffect } from 'react';
import { 
  Bot, 
  Send, 
  Sparkles, 
  BookOpen, 
  ShieldAlert, 
  Wrench, 
  HelpCircle, 
  CheckCircle2, 
  ExternalLink,
  Info,
  CornerDownLeft,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { StationTechInfo } from '../types';

interface Message {
  id: string;
  sender: 'ai' | 'user';
  text: string;
  timestamp: string;
  reference?: string;
  tools?: string[];
  safetyNote?: string;
}

interface Props {
  station: StationTechInfo;
  activeStepIdx: number | null;
}

// Technical Knowledge Base derived from OEM manuals and Magna SOP standards
const STATION_KNOWLEDGE: Record<number, {
  oemDocs: string[];
  defaultSuggestions: string[];
  stepDetails: Record<number, {
    title: string;
    tools: string[];
    specs: string;
    solvents: string;
    safety: string;
    docRef: string;
    instructions: string[];
  }>;
  customQA: { patterns: string[]; answer: string; ref: string }[];
}> = {
  // OP30: Cognex Vision Inspection
  3: {
    oemDocs: [
      "Cognex In-Sight 8402P Manual (Rev. 6.2)",
      "Magna SOP-L01-ST038: Optická inšpekcia puzdra",
      "EN ISO 14120 / LOTO Bezpečnostný predpis"
    ],
    defaultSuggestions: [
      "Čím bezpečne očistiť polarizátor a šošovku?",
      "Aký je uťahovací moment konektora M12?",
      "Ako postupovať pri LOTO odpojení 24V?",
      "Aká je minimálna intenzita LED osvetlenia?"
    ],
    stepDetails: {
      0: {
        title: "Krok 1: LOTO Bezpečné odpojenie napájania 24V DC",
        tools: ["Bezpečnostný visiaci zámok LOTO (červený)", "Skúšačka napätia Fluke 179 (kalibrovaná)", "Kľúč od rozvádzača R03"],
        specs: "Napätie: 24V DC ±5%, Istič QF3 (16A, C-charakteristika)",
        solvents: "Nevyžaduje sa",
        safety: "EN ISO 14120 — Vždy aplikujte pravidlo 'Zero Energy State'. Overte beznapäťový stav na svorkovnici X2 pred dotykom kabeláže.",
        docRef: "Magna Bezpečnostný predpis LOTO-03 • Rozvádzač R03",
        instructions: [
          "Otočte hlavný istič QF3 na rozvádzaчі R03 do polohy '0' (OFF).",
          "Nasaďte červený bezpečnostний zámok LOTO a umiestnite svoju osobnú visačku operátora.",
          "Multimetrom overte nulové napätie na svorkách 1(+) a 2(-) konektora X2.",
          "Odpojte montážnu zástrčku M12 jemným pootočením poistnej matice."
        ]
      },
      1: {
        title: "Krok 2: Očistenie optickej šošovky Cognex & polarizátora",
        tools: ["Mikrovláknové bezprašné utierky Kimwipes (ISO Class 4)", "Optický ofukovač s HEPA filtrom", "Antistatické nitrilové rukavice"],
        specs: "Objektív C-Mount 16mm F1.4, Polarizačný filter s antireflexnou vrstvou",
        solvents: "99.8% čistý izopropanol (IPA). Nikdy nepoužívajte acetón, lieh ani priemyselné odmasťovače!",
        safety: "Zákaz dotýkať sa optického skla holými rukami. Tlak na šošovku nesmie presiahnuť 2 N (jemný kruhový pohyb).",
        docRef: "Cognex In-Sight 8400 Series Maintenance Guide, Sekcia 4.2: Optics Cleaning",
        instructions: [
          "Ofukovačom odstráňte voľné hrubé častice prachu z povrchu polarizátora.",
          "Navlhčite 2 kvapkami 99.8% IPA utierku Kimwipes (nikdy nekvapkajte priamo na šošovku!).",
          "Kruhovým špirálovým pohybom od stredu k okrajom zotrite mastnotu a prach.",
          "Suchou stranou utierки jemne vyleštite do sucha bez zanechania šmúh."
        ]
      },
      2: {
        title: "Krok 3: Kontrola a dotiahnutie konektora X2",
        tools: ["Momentový skrutkovač pre M12 (0.4 – 1.0 Nm)", "Priemyselná lupa 10×", "Čistič kontaktov Kontakt 60"],
        specs: "Konektor M12 A-coded 8-pin, predpísaný uťahovací moment: 0.6 Nm ±0.05 Nm",
        solvents: "Elektrický kontaktný sprej bez rezíduí (Kontakt 60)",
        safety: "Dotiahnutie vykonávajte len pri odpojenom napájaní (LOTO stav).",
        docRef: "Phoenix Contact M12 Field Cabling Specification • Magna Norma E-04",
        instructions: [
          "Lupou skontrolujte piny 1 až 8 konektora X2, či nie sú ohnuté alebo oxidované.",
          "Zasuňte konektor do vodiacej drážky (zámku) až na doraz.",
          "Momentovým adaptérom dotiahnite poistný krúžok presne na 0.6 Nm.",
          "Jemným ťahom za kábel skontrolujte pevnosť mechanického zaistenia."
        ]
      },
      3: {
        title: "Krok 4: Kalibrácia a test kruhového LED osvetlenia",
        tools: ["Digitálny luxmeter Voltcraft LX-100", "Imbusový kľúč 2.5 mm", "Merací prípravok výšky 250 mm"],
        specs: "Vlnová dĺžka: 630 nm (červené svetlo), Norma intenzity: ≥ 400 lux v pracovnej vzdialenosti 250 mm",
        solvents: "Nevyžaduje sa",
        safety: "Nepozerajte sa priamo do zapnutého LED iluminátora z minimálnej vzdialenosti (ochrana zraku).",
        docRef: "Smart Vision Lights Ring Light R80 Specification • SOP-038",
        instructions: [
          "Umiestните senzor luxmetra na testovacie lôžko paletky #9042 do optickej osi kamery.",
          "Zapnite osvetlenie cez servisné PLC menu a odčítajte hodnotu (musí byť 400 – 480 lux).",
          "Ak je hodnota < 400 lux, skontrolujte polarizačný filter na prítomnosť zahmlenia.",
          "Nastavovacím trimrom na zadnej strane modulu upravte prúd LED na nominálnu hodnotu."
        ]
      },
      4: {
        title: "Krok 5: Skúšobná snímка v In-Sight Explorer & spustenie",
        tools: ["Terminál linky L01 s In-Sight Explorer v6.5", "Kalibračný referenčný dielec Magna e-Drive REV4", "RFID čítačka"],
        specs: "Inšpekčný čas: < 450 ms, Prah zhody (Pattern Match): ≥ 92.0%, Takt stanice: 63s",
        solvents: "Nevyžaduje sa",
        safety: "Pred spustením taktu skontrolujte, či sú všetky bezpečnostné Lexan kryty zatvorené a magnetické zámky aktívne.",
        docRef: "Cognex In-Sight Software Guide • Magna Prebierkový protokol ST-038",
        instructions: [
          "Vložte do hniezda referenčný diel s definovanými rozmermi.",
          "Na HMI termináli spustite testovací cyklus snímky (Soft Event 8).",
          "Overte, že algoritmus hlási zelený výsledok 'PASS' a rozmer tesniacej drážky je v tolerancii ±0.05 mm.",
          "Odstráňte LOTO zámok, zapnite istič QF3 a uvoľnite stanicu do automatického cyklu."
        ]
      }
    },
    customQA: [
      {
        patterns: ["moment", "utiahnut", "uťahov", "skrutk", "nm"],
        answer: "Podľa predpisu výrobcu Cognex a Magna normy E-04 je uťahovací moment konektora M12 presne **0.6 Nm** (tolerancia ±0.05 Nm). Upevňovacie skrutky držiaka kamery Torx T10 sa uťahujú momentom **1.2 Nm**.",
        ref: "Magna Norma E-04 / Cognex 8402P Hardware Doc"
      },
      {
        patterns: ["cistic", "cist", "utierk", "lieh", "alkohol", "rozpustad"],
        answer: "Na čistenie optiky a polarizátora Cognex je predpísaný výhradne **99.8% izopropanol (IPA)** nanesený na bezprašnú utierku **Kimwipes**. Zákaz používať bežný denaturovaný lieh (zanecháva film) alebo acetón (roztaví polarizačný filter!).",
        ref: "Cognex Maintenance Manual, Sekcia 4.2"
      },
      {
        patterns: ["loto", "bezpecn", "odpojit", "istic", "qf3"],
        answer: "Postup LOTO vyžaduje vypnúť istič **QF3** v rozvádzači R03, uzamknúť ho osobným visiacim zámком a multimetrom overiť absenciu 24V DC na pinoch 1 a 2. Tým je zaručený stav nulovej energie (Zero Energy State).",
        ref: "EN ISO 14120 / Bezpečnostná karta LOTO-038"
      },
      {
        patterns: ["svetlo", "led", "lux", "intenzit", "iluminator"],
        answer: "Kruhový LED iluminátor (vlnová dĺžka 630 nm) musí v pracovnej vzdialenosti 250 mm poskytovať intenzitu minimálne **400 lux**. Ak luxmeter nameria menej ako 400 lux, kamera hlási chybu expozície ST-038.",
        ref: "Smart Vision Lights Ring Spec • Magna SOP-038"
      }
    ]
  },

  // OP20: Kistler / TOX Servo-Hydraulic Press
  2: {
    oemDocs: [
      "Kistler maXYmos TL 5877A System Manual",
      "TOX Pressotechnik 120 kN Drive Specification",
      "Magna SOP-L01-ST026: Nalisovanie rotora el. motora"
    ],
    defaultSuggestions: [
      "Aká je maximálna povolená lisovacia sila?",
      "Aká je tolerancia hĺbky vlisovania?",
      "Ako očistiť lisovací tŕň Ø42 od otrepov?",
      "Ako nulovať snímač sily Kistler 9211B?"
    ],
    stepDetails: {
      0: {
        title: "Krok 1: LOTO Zablokovanie servopohonu lisu & aretácia barana",
        tools: ["Aretačný čap barana (Ø 25 mm)", "LOTO bezpečnostný zámok", "Kľúč bezpečnostného modulu Pilz"],
        specs: "Mechanická nosnosť aretačného čapu: 150 kN, Istič QF2 (32A)",
        solvents: "Nevyžaduje sa",
        safety: "Kritické nebezpečenstvo pomliaždenia! Pred vstupom rúk do lisovacieho priestoru MUSÍ byť zasunutý aretačný čap barana lisu.",
        docRef: "TOX Safety Manual EN 692 • Magna LOTO-020",
        instructions: [
          "Aktivujte bezpečnostný stop na paneli stanice OP20.",
          "Otočte bezpečnostný odpojovač QF2 do polohy OFF a uzamknite LOTO visiacim zámkom.",
          "Zasuňte mechanický kalený aretačný klin do vodiacej drážky barana lisu.",
          "Opticky skontrolujte zopnutie bezpečnostného koncového spínača aretácie."
        ]
      },
      1: {
        title: "Krok 2: Inšpekcia lisovacieho tŕňa & vyčistenie sedla rotora",
        tools: ["Diamantový lapovací pilník (jemný zrnitosť 600)", "Priemyselná lupa 10×", "Mosadzná kefa"],
        specs: "Menovitý priemer tŕňa: Ø 42.000 +0.012 mm, Tvrdosť 60 HRC (ocel 1.2379)",
        solvents: "Odmasťovač ložísk Loctite 7063, jemný konzervačný olej ISO VG 32",
        safety: "Zákaz používať brúsny papier (spôsobuje kužeľovitosť tŕňa). Používajte ochranné rukavice odolné voči rezu.",
        docRef: "Magna Výrobný predpis nástrojov T-020 • SOP Nalisovanie",
        instructions: [
          "Lupou skontrolujte nábehový kužeľ tŕňa na prítomnosť zádierov alebo nalepeného hliníka.",
          "Prípadné mikrootrepy jemne zahlaďte diamantovým lapovacím pilníkom.",
          "Očistite sedlo a nalisovaciu dutinu rotora odstraňovačom Loctite 7063.",
          "Naneste tenký film technologického montážneho maziva podľa Magna špecifikácie."
        ]
      },
      2: {
        title: "Krok 3: Kontrola kalibrácie piezo snímača sily (Kistler 50kN)",
        tools: ["Kalibrovaný silomerný etalón Kistler 9301B", "Digitálny merač izolačného odporu (>10^13 Ohm)"],
        specs: "Nominálny rozsah: 0 – 50 kN, Citlivosť snímača: -4.3 pC/N, Linearita: < ±0.5% FSO",
        solvents: "Nevyžaduje sa",
        safety: "Chráňte vysokoizolačný BNC/koaxiálny konektor pred vlhkosťou a dotykom prstov.",
        docRef: "Kistler Type 9211B Quartz Force Sensor Instruction Manual",
        instructions: [
          "Skontrolujte koaxiálny nízkošumový kábel vedúci do zosilňovača maXYmos TL.",
          "V servisnom menu maXYmos zvoľte funkciu 'Reset Drifting / Auto-Zero'.",
          "Vykonajte skúšobné zaťaženie referenčným tlakom a overte linearitu nulového bodu.",
          "Potvrďte kalibračný offset (povolená odchýlка max ±0.15 kN)."
        ]
      },
      3: {
        title: "Krok 4: Overenie optického pravítka hĺbky vlisovania (Limit 42±0.2 mm)",
        tools: ["Digitálny hĺbkomer Mitutoyo (kalibrovaný)", "Čistiaci sprej na optiku Keyence"],
        specs: "Predpísaná konečná hĺbka: 42.0 mm (dolná medza 41.8 mm, horná medza 42.2 mm)",
        solvents: "Optický sprej bez silikónu",
        safety: "Laser triedy II (Keyence LK-G) — nepozerajte sa do lúča.",
        docRef: "Keyence LK-G Series High-Speed Laser Displacement Manual • SOP-020",
        instructions: [
          "Zmerajte koncovú polohu lôžka nezávislým etalónovým hĺbkomerom Mitutoyo.",
          "Porovnajte údaj na obrazovke Keyence s manuálnym meraním (rozdiel musí byť ≤ 0.05 mm).",
          "Vyčistite optické okienko laserového prijímača ofukom.",
          "Uložte nulovací bod referenčnej dráhy do PLC."
        ]
      },
      4: {
        title: "Krok 5: Testovací cyklus lisu & potvrdenie tolerančného okna F/s",
        tools: ["Systém maXYmos TL 5877A", "RFID terminál paletky #9042"],
        specs: "Maximálna sila zalisovania: 38.4 kN (Limitné okno: max 45.0 kN), Čas zalisovania: 2.4s",
        solvents: "Nevyžaduje sa",
        safety: "Pri prvom skúšobnom zalisovaní majte ruku pripravenú na tlačidle núdzového zastavenia.",
        docRef: "Magna Kontrolný plán kvality Q-020 • Kistler Tolerančné krivky",
        instructions: [
          "Odstráňte aretačný čap a uvoľните LOTO zámok na ističi QF2.",
          "Spustite 1 referenčný lisovací cyklus s testovacím rotorom.",
          "Na monitore maXYmos skontrolujte, či celá krivka F/s prešla zeleným tolerančným oknom (bez dotyku prahu 45 kN).",
          "Odošlite signál 'OK Cycle' do nadradeného PLC a uvoľnite stanicu do automatického taktu."
        ]
      }
    },
    customQA: [
      {
        patterns: ["sila", "limit", "kn", "tlak", "maxymos"],
        answer: "Podľa špecifikácie Magna e-Drive je nominálna lisovacia sila **32.0 až 38.4 kN**. Absolútny bezpečnostný limit lisu je nastavený na **45.0 kN**. Ak sila prekročí 45 kN, maXYmos okamžite zastaví baran, aby nepraskol hliníkový obal statora.",
        ref: "Magna Technologická karta lisu OP20 • maXYmos TL"
      },
      {
        patterns: ["hlbka", "draha", "toleranc", "rozmer", "mm", "keyence"],
        answer: "Hĺbka vlisovania rotora je predpísaná na **42.0 mm ±0.2 mm** (merané laserovým pravítkom Keyence LK-G). Ak je rozmer mimo 41.8 – 42.2 mm, dielec je vyradený ako NOK brak (kód Q-020).",
        ref: "SOP-020: Kontrola rozmeru zalisovania"
      },
      {
        patterns: ["trn", "otrep", "ocist", "42", "nastroj"],
        answer: "Lisovací tŕň Ø42 je vyrobený z kalenej ocele 1.2379 (60 HRC). Čistí sa odmasťovačom **Loctite 7063** a mikrootrepy sa zahladzujú jemným **diamantovým lapovacím pilníkom (zrnitosť 600)**. Zákaz brúsneho papiera!",
        ref: "Magna Predpis údržby nástrojov T-020"
      },
      {
        patterns: ["loto", "aretac", "baran", "bezpecn", "poistka"],
        answer: "Pred vstupom do lisovacieho priestoru vypnite istič **QF2** a **vždy zasuňte mechanický aretačný čap** do tela barana. Zabraňuje to gravitačnému pádu nástroja aj pri výpadku hydrauliky.",
        ref: "Bezpečnostný predpis EN 692 / LOTO QF2"
      }
    ]
  }
};

export const StationAIChatCopilot: React.FC<Props> = ({ station, activeStepIdx }) => {
  const [isOpen, setIsOpen] = useState(true);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Station-specific knowledge
  const knowledge = STATION_KNOWLEDGE[station.id] || STATION_KNOWLEDGE[3];
  const activeStep = activeStepIdx !== null ? knowledge.stepDetails[activeStepIdx] : null;

  // Initial welcome message
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'init-1',
      sender: 'ai',
      text: `Dobrý deň, som AI Asistent údržby pre **Stanicu OP${station.id * 10} (${station.name})**. Mám načítanú kompletnú OEM dokumentáciu, normy Magna SOP a tolerančné protokoly. Ako vám môžem pomôcť s postupom opravy?`,
      timestamp: 'Teraz',
      reference: knowledge.oemDocs[0],
      tools: activeStep ? activeStep.tools : undefined,
      safetyNote: activeStep ? activeStep.safety : undefined
    }
  ]);

  // Update initial message when active step changes
  useEffect(() => {
    if (activeStepIdx !== null && knowledge.stepDetails[activeStepIdx]) {
      const step = knowledge.stepDetails[activeStepIdx];
      const stepNotice: Message = {
        id: `step-context-${Date.now()}`,
        sender: 'ai',
        text: `📍 **Zameraný ${step.title}**\n\n` +
          `• **Predpísané náradie:** ${step.tools.join(', ')}\n` +
          `• **Materiály/Čističe:** ${step.solvents}\n` +
          `• **Technická špecifikácia:** ${step.specs}\n\n` +
          `**Postup:**\n${step.instructions.map((ins, i) => `${i + 1}. ${ins}`).join('\n')}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        reference: step.docRef,
        safetyNote: step.safety,
        tools: step.tools
      };
      setMessages(prev => [...prev, stepNotice]);
    }
  }, [activeStepIdx, station.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSendMessage = (userQuery: string) => {
    if (!userQuery.trim()) return;

    const query = userQuery.trim();
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    // AI Response generation using RAG Pattern on Station Knowledge Base
    setTimeout(() => {
      const lower = query.toLowerCase();
      let matchedAnswer: string | null = null;
      let matchedRef: string = knowledge.oemDocs[0];
      let matchedTools: string[] | undefined;
      let matchedSafety: string | undefined;

      // 1. Check custom patterns in knowledge base
      for (const qa of knowledge.customQA) {
        if (qa.patterns.some(p => lower.includes(p))) {
          matchedAnswer = qa.answer;
          matchedRef = qa.ref;
          break;
        }
      }

      // 2. Check if asking about specific step
      if (!matchedAnswer && activeStep) {
        if (lower.includes('ako') || lower.includes('postup') || lower.includes('urobit') || lower.includes('co robit')) {
          matchedAnswer = `Pre **${activeStep.title}** postupujte nasledovne:\n\n` +
            activeStep.instructions.map((ins, i) => `${i + 1}. ${ins}`).join('\n') +
            `\n\n📌 **Upozornenie:** ${activeStep.safety}`;
          matchedRef = activeStep.docRef;
          matchedTools = activeStep.tools;
          matchedSafety = activeStep.safety;
        } else if (lower.includes('naradie') || lower.includes('kluc') || lower.includes('nastroj')) {
          matchedAnswer = `Pre tento úkon potrebujete nasledovné predpísané náradie:\n` +
            activeStep.tools.map(t => `• ${t}`).join('\n');
          matchedRef = activeStep.docRef;
          matchedTools = activeStep.tools;
        }
      }

      // 3. Fallback response with industrial engineering precision
      if (!matchedAnswer) {
        matchedAnswer = `Podľa normy **${knowledge.oemDocs[1]}** a špecifikácie ${station.tech}:\n\n` +
          `Tento úkon vyžaduje dodržanie predpísaného taktu linky (${station.telemetry.cycle_time}s) a overenie Poka-Yoke senzorov. ` +
          `Všetky zásahy do elektroinštalácie a mechaniky musia byť vykonané kvalifikovaným personálom v súlade s normou EN ISO 14120. ` +
          `Ak potrebujete presný uťahovací moment alebo rozpis náhradných dielov, vyberte prosím konkrétny krok vyššie alebo sa spýtajte na konkrétny komponent.`;
        matchedRef = knowledge.oemDocs[1];
      }

      const aiMsg: Message = {
        id: `ai-${Date.now()}`,
        sender: 'ai',
        text: matchedAnswer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        reference: matchedRef,
        tools: matchedTools,
        safetyNote: matchedSafety
      };

      setMessages(prev => [...prev, aiMsg]);
      setIsTyping(false);
    }, 600);
  };

  return (
    <div className="bg-[#090D18] border border-[#1E293B] rounded-2xl overflow-hidden shadow-2xl transition-all duration-300">
      
      {/* 1. Chat Header */}
      <div 
        onClick={() => setIsOpen(!isOpen)}
        className="p-3.5 bg-gradient-to-r from-[#0C1427] via-[#0E1A33] to-[#0C1427] border-b border-[#1E293B] flex items-center justify-between cursor-pointer select-none hover:bg-[#111C38] transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#3B82F6] to-[#06B6D4] p-0.5 flex items-center justify-center shadow-[0_0_12px_rgba(56,189,248,0.4)]">
            <div className="w-full h-full bg-[#090D18] rounded-[10px] flex items-center justify-center">
              <Bot className="w-4 h-4 text-[#38BDF8]" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h5 className="text-sm font-bold text-white tracking-wide flex items-center gap-2">
                <span>Magna AI Asistent údržby</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#38BDF8]/20 text-[#38BDF8] border border-[#38BDF8]/30 font-semibold">
                  Qwen 2.5 3B (OEM RAG)
                </span>
              </h5>
            </div>
            <p className="text-[11px] text-[#94A3B8] leading-tight mt-0.5">
              {activeStep ? (
                <span className="text-[#38BDF8] font-medium">📍 Zaostrené: {activeStep.title.split(':')[0]} • {activeStep.tools[0]}</span>
              ) : (
                <span>Kontext: Stanica OP{station.id * 10} • OEM manuály &amp; SOP predpisy</span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-1.5 text-[10.5px] text-[#94A3B8] bg-white/5 px-2.5 py-1 rounded-lg border border-white/10 font-mono">
            <BookOpen className="w-3.5 h-3.5 text-[#38BDF8]" />
            <span className="truncate max-w-[260px]">{knowledge.oemDocs[0]}</span>
          </div>
          <span className="w-2.5 h-2.5 rounded-full bg-[#10B981] animate-pulse" title="RAG model pripravený v reálnom čase" />
          <button 
            type="button" 
            className="p-1 rounded-lg hover:bg-white/10 text-[#94A3B8]"
            title={isOpen ? "Zbaliť asistent" : "Rozbaliť asistent"}
          >
            {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {isOpen && (
        <div className="flex flex-col h-[280px]">
          
          {/* 2. Messages Scroll Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 text-xs scrollbar-thin scrollbar-thumb-white/10">
            {messages.map((m) => (
              <div 
                key={m.id}
                className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'} max-w-[85%] ${m.sender === 'user' ? 'ml-auto' : 'mr-auto'}`}
              >
                <div 
                  className={`p-3.5 rounded-2xl leading-relaxed text-xs ${
                    m.sender === 'user' 
                      ? 'bg-[#2563EB] text-white rounded-br-xs shadow-md' 
                      : 'bg-[#131D33] border border-[#1E2E4A] text-[#E2E8F0] rounded-bl-xs shadow-lg'
                  }`}
                >
                  {/* Message body with Markdown format */}
                  <div className="whitespace-pre-line leading-relaxed">
                    {m.text}
                  </div>

                  {/* Safety Alert Badge inside AI response */}
                  {m.safetyNote && (
                    <div className="mt-2.5 p-2.5 rounded-xl bg-[#EF4444]/15 border border-[#EF4444]/30 text-[#FCA5A5] text-[11px] flex items-start gap-2">
                      <ShieldAlert className="w-4 h-4 text-[#EF4444] shrink-0 mt-0.5" />
                      <span>{m.safetyNote}</span>
                    </div>
                  )}

                  {/* Tools Badge */}
                  {m.tools && m.tools.length > 0 && (
                    <div className="mt-2.5 pt-2 border-t border-white/10 flex flex-wrap items-center gap-1.5">
                      <span className="text-[10.5px] text-[#94A3B8] flex items-center gap-1 mr-1">
                        <Wrench className="w-3.5 h-3.5 text-[#38BDF8]" /> Predpísané náradie:
                      </span>
                      {m.tools.map((tool, ti) => (
                        <span key={ti} className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 border border-white/10 text-white font-medium">
                          {tool}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* OEM Doc Citation footer */}
                  {m.reference && (
                    <div className="mt-2 pt-2 border-t border-white/5 text-[10px] font-mono text-[#38BDF8] flex items-center gap-1.5 opacity-90">
                      <BookOpen className="w-3.5 h-3.5" />
                      <span>Zdroj: {m.reference}</span>
                    </div>
                  )}
                </div>

                <span className="text-[9.5px] text-[#64748B] mt-0.5 px-1 font-mono">
                  {m.timestamp}
                </span>
              </div>
            ))}

            {isTyping && (
              <div className="flex items-center gap-2 p-2.5 rounded-xl bg-[#131D33] border border-[#1E2E4A] text-xs text-[#38BDF8] w-fit">
                <Sparkles className="w-3.5 h-3.5 animate-spin text-[#38BDF8]" />
                <span className="text-[11px] font-medium animate-pulse">Qwen 2.5 vyhodnocuje OEM manuál...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* 3. Quick Chips (1-Click Suggestions) - Clean wrap with zero horizontal overflow */}
          <div className="px-3.5 py-2 bg-[#0B101E] border-t border-[#1E293B] flex flex-wrap items-center gap-2">
            <span className="text-[10px] text-[#64748B] font-bold shrink-0 flex items-center gap-1">
              <HelpCircle className="w-3.5 h-3.5 text-[#38BDF8]" /> Rýchle otázки:
            </span>
            {knowledge.defaultSuggestions.map((sug, i) => (
              <button
                key={i}
                type="button"
                onClick={() => handleSendMessage(sug)}
                className="px-3 py-1 rounded-full bg-[#131E35] hover:bg-[#1E2D4E] text-[#94A3B8] hover:text-[#38BDF8] text-[10.5px] font-medium border border-[#1E293B] hover:border-[#38BDF8]/40 transition-all active:scale-95 shadow-sm"
              >
                {sug}
              </button>
            ))}
          </div>

          {/* 4. Chat Input Bar */}
          <form 
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage(input);
            }}
            className="p-3 bg-[#0C1222] border-t border-[#1E293B] flex items-center gap-2.5"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Spýtajte sa AI asistenta na detail opravy OP${station.id * 10} (náradie, postupy, momenty zaťahovania)...`}
              className="flex-1 bg-[#070B14] border border-[#1E293B] focus:border-[#38BDF8] rounded-xl px-3.5 py-2 text-xs text-white placeholder-[#64748B] outline-none transition-colors shadow-inner"
            />
            <button
              type="submit"
              disabled={!input.trim()}
              className="px-4 py-2 rounded-xl bg-[#2563EB] hover:bg-[#1D4ED8] disabled:opacity-40 disabled:hover:bg-[#2563EB] text-white text-xs font-bold flex items-center gap-1.5 transition-all active:scale-95 shadow-md shadow-blue-500/20"
              title="Odoslať otázku"
            >
              <span>Odoslať</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>

        </div>
      )}

    </div>
  );
};
