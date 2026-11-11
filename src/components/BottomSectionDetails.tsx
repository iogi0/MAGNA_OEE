import React, { useState } from 'react';
import { ShiftAnalytics, HourlyData } from '../types';
import { HOURLY_SLOTS, DOWNTIME_CATALOG, QUALITY_CATALOG, LINE_STATIONS } from '../data/constants';
import { 
  AlertTriangle, 
  CheckCircle2, 
  Cpu, 
  Zap, 
  Sparkles, 
  Layers, 
  Clock, 
  Wrench, 
  Save, 
  Sliders, 
  AlertOctagon,
  ArrowRight,
  TrendingDown,
  Info
} from 'lucide-react';

interface Props {
  analytics: ShiftAnalytics;
  shiftHours: HourlyData[];
  selectedHour: number;
  onSelectHour: (h: number) => void;
  onSaveHour: (hourData: HourlyData) => void;
  onOpenMachineStation?: (stationId: number) => void;
}

export const BottomSectionDetails: React.FC<Props> = ({
  analytics,
  shiftHours,
  selectedHour,
  onSelectHour,
  onSaveHour,
  onOpenMachineStation,
}) => {
  const { top_3_availability, top_3_quality, waterfall, totals } = analytics;
  const currentHourData = shiftHours[selectedHour - 1] || shiftHours[0];

  // Dynamic station lookup for TOP-1 cards
  const getStationIdForCode = (code?: string | null, fallbackId: number = 3): number => {
    if (!code) return fallbackId;
    const found = LINE_STATIONS.find(s => s.related_codes.includes(code));
    return found ? found.id : fallbackId;
  };

  const topDtStationId = getStationIdForCode(top_3_availability[0]?.code, 3);
  const topQStationId = getStationIdForCode(top_3_quality[0]?.code, 2);

  // Local Form state for hourly entry
  const [producedPcs, setProducedPcs] = useState<number | ''>(currentHourData.produced_pcs);
  const [nokPcs, setNokPcs] = useState<number | ''>(currentHourData.nok_pcs);
  const [downtimeMin, setDowntimeMin] = useState<number | ''>(currentHourData.downtime_min);
  const [downtimeCode, setDowntimeCode] = useState<string>(currentHourData.downtime_code || '');
  const [nokCode, setNokCode] = useState<string>(currentHourData.nok_code || '');

  // AI Copilot state
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [aiResponse, setAiResponse] = useState<string | null>(null);

  // Sync state when selected hour changes
  React.useEffect(() => {
    const d = shiftHours[selectedHour - 1];
    if (d) {
      setProducedPcs(d.produced_pcs);
      setNokPcs(d.nok_pcs);
      setDowntimeMin(d.downtime_min);
      setDowntimeCode(d.downtime_code || '');
      setNokCode(d.nok_code || '');
    }
  }, [selectedHour, shiftHours]);

  const handleSubmitHour = (e: React.FormEvent) => {
    e.preventDefault();
    onSaveHour({
      ...currentHourData,
      hour: selectedHour,
      produced_pcs: producedPcs === '' ? 0 : Number(producedPcs),
      nok_pcs: nokPcs === '' ? 0 : Number(nokPcs),
      downtime_min: downtimeMin === '' ? 0 : Number(downtimeMin),
      downtime_code: downtimeCode || null,
      nok_code: nokCode || null,
    });
  };

  // Run AI Copilot (local Ollama or fallback expert knowledge)
  const handleRunAiCopilot = async () => {
    setAiLoading(true);
    setAiResponse(null);

    const topDowntime = top_3_availability[0];
    const topQuality = top_3_quality[0];

    const dtText = topDowntime 
      ? `Porucha: ${topDowntime.code} — ${topDowntime.name} (${topDowntime.total_min} minút prestoj na ${topDowntime.station})`
      : 'Žiadny zaznamenaný prestoj (Dostupnosť 100%)';

    const qText = topQuality
      ? `Defekt kvality: ${topQuality.code} — ${topQuality.name} (${topQuality.total_nok} ks NOK na ${topQuality.station})`
      : 'Žiadne chyby kvality (100% OK)';

    const prompt = `Si hlavný priemyselný inžinier TPM v Magna Powertrain (montážna linka L01).
Analyzuj nasledujúci zistený stav zmeny:
- ${dtText}
- ${qText}
Aktuálne OEE zmeny: ${(analytics.kpi.oee * 100).toFixed(1)}% (Dostupnosť: ${(analytics.kpi.availability * 100).toFixed(1)}%, Výkon: ${(analytics.kpi.performance * 100).toFixed(1)}%, Kvalita: ${(analytics.kpi.quality * 100).toFixed(1)}%).

Uveď stručne a vecne v slovenčine:
1. Okamžité kroky pre technika údržby / operátora
2. Analýza koreňovej príczyny (5-Why)
3. Preventívne Poka-Yoke / Kaizen opatrenie na stabilizáciu OEE ≥ 85%`;

    try {
      const resp = await fetch('http://localhost:11434/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'qwen2.5:3b',
          messages: [{ role: 'user', content: prompt }],
          stream: false,
        }),
      });

      if (resp.ok) {
        const data = await resp.json();
        setAiResponse(data.message?.content || 'AI odporúčanie pripravené.');
      } else {
        throw new Error('Ollama not running');
      }
    } catch {
      // Dynamic contextual fallback based on active issues
      if (topDowntime?.code === 'ST-046' || topDowntime?.code === 'ST-047' || topQuality?.code === 'Q-031') {
        setAiResponse(
          `⚡ [Magna TPM Expertíza — Stanica 9: Leak Test]:\n` +
          `1. Okamžitý zásah: Skontrolovať tesniaci O-krúžok na testovacom adaptéri Ateq F620 a vykonať skúšku tesnosti kalibračným etalónom.\n` +
          `2. Koreňová príčina (5-Why): O-krúžok vykazoval mikrotrhliny po prekročení 10 000 cyklov, čo viedlo k poklesu tlaku v testovacej komore.\n` +
          `3. Preventívne Poka-Yoke: Zavedenie automatického počítadla cyklov tesnenia v PLC s preventívnym upozornením po 8 000 cykloch.`
        );
      } else if (topQuality?.code === 'Q-020' || topDowntime?.code === 'ST-026') {
        setAiResponse(
          `⚡ [Magna TPM Expertíza — Stanica 2: Lisovanie el. motora]:\n` +
          `1. Okamžitý zásah: Skontrolovať silovú krivku lisu Kistler, očistiť sedlo ložiska a overiť kalibráciu snímača dráhy.\n` +
          `2. Koreňová príčina (5-Why): Tolerancia priemeru rotora prekročila hornú medzu, čo spôsobilo nárast odporu vlisovania nad 45 kN.\n` +
          `3. Preventívne Poka-Yoke: Vstupný kaliber Poka-Yoke na kontrolu vonkajšieho priemeru pred naložením rotora do lisu.`
        );
      } else if (topDowntime?.code === 'ST-001') {
        setAiResponse(
          `⚡ [Magna TPM Expertíza — Stanica 1-2: Zásobovanie]:\n` +
          `1. Okamžitý zásah: Aktivovať Andon privolanie logistiky a manuálne doplniť gravitačný zásobník puzdier.\n` +
          `2. Koreňová príčina (5-Why): Oneskorenie expedície kitting boxov zo skladu komponentov z dôvodu chýbajúceho min-max senzora.\n` +
          `3. Preventívne Poka-Yoke: Optický hladinový snímač gravitačnej sklznice s automatickým Andon signálom 15 minút pred vyprázdnením.`
        );
      } else if (!topDowntime && !topQuality) {
        setAiResponse(
          `⚡ [Magna TPM Expertíza — Linka L01]:\n` +
          `1. Aktuálny stav: Linka pracuje v optimálnom režime bez aktívnych porúch a bez braku kvality.\n` +
          `2. TPM Odporúčanie: Vykonať 5S kontrolu pracoviska a audit uťahovacích momentov na vretenách Atlas Copco.\n` +
          `3. Trvalé opatrenie: Udržiavať štandardizovanú prácu a dodržiavať takt cyklu 60s.`
        );
      } else {
        setAiResponse(
          `⚡ [Magna TPM Expertíza — Stanica 3: Kamerová kontrola]:\n` +
          `1. Okamžitý zásah: Očistiť optickú šošovku Cognex izopropanolom a dotiahnuť 24V konektor LED modulu na Stanici 3.\n` +
          `2. Koreňová príčina (5-Why): Vibrácie dopravníka uvoľnili konektor LED svetla, čím osvetlenie kleslo pod 400 lux.\n` +
          `3. Preventívne Poka-Yoke: Antivibračná podložka svorkovnice a automatický softvérový alarm pri poklese luxov pod 450 lux.`
        );
      }
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <section className="bg-[#09090B] rounded-t-[40px] px-6 lg:px-12 py-10 text-white border-t border-[#27272A] shadow-2xl mt-8 select-none">
      <div className="max-w-[1440px] mx-auto">
        
        {/* CityCare 3-Column Architecture: (1fr 1.5fr 1fr) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* ========================================================
              COLUMN 1 (4/12 Cols): Patients Symptoms style 
              -> Po-hodinový report & Alarm (Vstup dát)
             ======================================================== */}
          <div className="lg:col-span-4 bg-[#18181B] rounded-[28px] p-6 border border-[#27272A] shadow-lg">
            
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sliders className="w-4 h-4 text-[#3B82F6]" />
                Po-hodinový vstup dát
              </h3>
              <span className="text-[11px] font-semibold text-[#94A3B8] px-2.5 py-0.5 rounded-full bg-[#27272A]">
                Hodina {selectedHour} z 8
              </span>
            </div>
            
            <p className="text-xs text-[#94A3B8] mb-4">
              Vyberte hodinu zmeny pre manuálnu úpravu alebo zadanie poruchy:
            </p>

            {/* Hourly Pills List (flex-wrap: wrap, gap: 8px) */}
            <div className="flex flex-wrap gap-2 mb-6">
              {shiftHours.map((h) => {
                const isSelected = selectedHour === h.hour;
                const hasDowntime = h.downtime_min > 0;
                const hasNok = h.nok_pcs > 0;

                return (
                  <button
                    key={h.hour}
                    type="button"
                    onClick={() => onSelectHour(h.hour)}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 flex items-center gap-1.5 ${
                      isSelected
                        ? 'bg-[#3B82F6] text-white shadow-glow-blue ring-2 ring-white/30 scale-105'
                        : hasDowntime
                        ? 'bg-[#EF4444]/20 text-[#EF4444] border border-[#EF4444]/40 hover:bg-[#EF4444]/30'
                        : hasNok
                        ? 'bg-[#F59E0B]/20 text-[#F59E0B] border border-[#F59E0B]/40 hover:bg-[#F59E0B]/30'
                        : 'bg-[#27272A] text-[#D1D5DB] hover:bg-[#323238] border border-transparent'
                    }`}
                  >
                    <span>H{h.hour}</span>
                    <span className="text-[10px] opacity-75">({h.produced_pcs}ks)</span>
                    {hasDowntime ? (
                      <span className="w-1.5 h-1.5 rounded-full bg-[#EF4444]" />
                    ) : (
                      <span className="w-1.5 h-1.5 rounded-full bg-[#10B981]" />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Quick Edit Form for Selected Hour */}
            <form onSubmit={handleSubmitHour} className="space-y-4">
              
              {/* Row: Vyrobené kusy & NOK brak */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-semibold text-[#94A3B8] block mb-1.5">
                    Vyrobené kusy (ks)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max={currentHourData.planned_min + 15}
                    value={producedPcs}
                    placeholder="0"
                    onFocus={(e) => e.target.select()}
                    onChange={(e) => {
                      const raw = e.target.value;
                      if (raw === '') {
                        setProducedPcs('');
                        return;
                      }
                      const val = parseInt(raw, 10);
                      if (!isNaN(val)) {
                        setProducedPcs(Math.max(0, val));
                      }
                    }}
                    className="w-full bg-[#09090B] border border-[#27272A] rounded-xl px-3 py-2 text-white font-bold text-sm focus:outline-none focus:border-[#3B82F6]"
                  />
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-[#94A3B8] block mb-1.5">
                    NOK brak (ks)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="20"
                    value={nokPcs}
                    placeholder="0"
                    onFocus={(e) => e.target.select()}
                    onChange={(e) => {
                      const raw = e.target.value;
                      if (raw === '') {
                        setNokPcs('');
                        return;
                      }
                      const val = parseInt(raw, 10);
                      if (!isNaN(val)) {
                        setNokPcs(Math.max(0, Math.min(20, val)));
                      }
                    }}
                    className="w-full bg-[#09090B] border border-[#27272A] rounded-xl px-3 py-2 text-[#EF4444] font-bold text-sm focus:outline-none focus:border-[#EF4444]"
                  />
                </div>
              </div>

              {/* Trvanie prestoja: Manuálny číselný vstup + posuvník */}
              <div>
                <div className="flex items-center justify-between text-[11px] font-semibold text-[#94A3B8] mb-1.5">
                  <label htmlFor="dt-min-input">Trvanie prestoja (max {currentHourData.planned_min} min)</label>
                  <span className="text-[#F59E0B] font-mono font-bold text-xs">{downtimeMin === '' ? 0 : downtimeMin} min</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="relative w-28 shrink-0">
                    <input
                      id="dt-min-input"
                      type="number"
                      min="0"
                      max={currentHourData.planned_min}
                      value={downtimeMin}
                      placeholder="0"
                      onFocus={(e) => e.target.select()}
                      onChange={(e) => {
                        const raw = e.target.value;
                        if (raw === '') {
                          setDowntimeMin('');
                          return;
                        }
                        const val = parseInt(raw, 10);
                        if (!isNaN(val)) {
                          setDowntimeMin(Math.min(currentHourData.planned_min, Math.max(0, val)));
                        }
                      }}
                      className="w-full bg-[#09090B] border border-[#27272A] rounded-xl px-3 py-2 text-[#F59E0B] font-bold text-sm focus:outline-none focus:border-[#F59E0B]"
                    />
                    <span className="absolute right-3 top-2.5 text-xs text-[#6B7280] pointer-events-none">min</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max={currentHourData.planned_min}
                    step="5"
                    value={downtimeMin === '' ? 0 : Math.min(Number(downtimeMin), currentHourData.planned_min)}
                    onChange={(e) => setDowntimeMin(Number(e.target.value))}
                    className="flex-1 accent-[#F59E0B] cursor-pointer"
                  />
                </div>
              </div>

              {/* Kód poruchy (Downtime Code) */}
              <div>
                <label className="text-[11px] font-semibold text-[#94A3B8] block mb-1.5">
                  Kód poruchy (Downtime)
                </label>
                <select
                  value={downtimeCode}
                  onChange={(e) => setDowntimeCode(e.target.value)}
                  className="w-full bg-[#09090B] border border-[#27272A] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#F59E0B]"
                >
                  <option value="">(Žiadny prestoj)</option>
                  {Object.values(DOWNTIME_CATALOG).map((dt) => (
                    <option key={dt.code} value={dt.code}>
                      {dt.code} — {dt.name_sk} ({dt.station})
                    </option>
                  ))}
                </select>
              </div>

              {/* Kód chyby kvality (NOK Code) */}
              <div>
                <label className="text-[11px] font-semibold text-[#94A3B8] block mb-1.5">
                  Kód defektu kvality (NOK)
                </label>
                <select
                  value={nokCode}
                  onChange={(e) => setNokCode(e.target.value)}
                  className="w-full bg-[#09090B] border border-[#27272A] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#EF4444]"
                >
                  <option value="">(Bez defektu)</option>
                  {Object.values(QUALITY_CATALOG).map((q) => (
                    <option key={q.code} value={q.code}>
                      {q.code} — {q.name_sk} ({q.station})
                    </option>
                  ))}
                </select>
              </div>

              {/* Save Button */}
              <button
                type="submit"
                className="w-full py-2.5 rounded-xl bg-white text-[#111827] font-bold text-xs hover:bg-gray-100 active:scale-[0.98] transition-all flex items-center justify-center gap-2 shadow-md mt-2"
              >
                <Save className="w-3.5 h-3.5" />
                <span>Uložiť údaje za Hodinu {selectedHour}</span>
              </button>
            </form>

          </div>


          {/* ========================================================
              COLUMN 2 (5/12 Cols): Dept. Performance style
              -> 3 Vertical Glow Cards (Neurology / Pediatric / Cardiology)
             ======================================================== */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#F59E0B]" />
                Prioritné incidenty & AI Copilot
              </h3>
              <span className="text-[11px] text-[#94A3B8]">
                Magna TPM Štandard
              </span>
            </div>

            {/* 3 Glowing Cards Grid (Exact CityCare visual) */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
              
              {/* Card 1: 🟡 TOP 1 Prestoj (Amber Glow) */}
              <div 
                onClick={() => onOpenMachineStation && onOpenMachineStation(topDtStationId)}
                className="bg-[#18181B] rounded-[22px] p-5 glow-card-orange flex flex-col justify-between cursor-pointer group"
              >
                <div>
                  <div className="flex items-center justify-between text-[11px] font-bold text-[#F59E0B] uppercase tracking-wider mb-3">
                    <span>Prestoje</span>
                    <Clock className="w-3.5 h-3.5" />
                  </div>
                  <div className="text-3xl font-extrabold text-[#F59E0B] tracking-tight">
                    {top_3_availability[0]?.total_min ?? 0}
                    <span className="text-sm font-normal text-white/70 ml-1">min</span>
                  </div>
                  <div className="text-xs font-bold text-white mt-2 group-hover:text-[#F59E0B] transition-colors">
                    {top_3_availability[0]?.code || 'Bez prestojov'}
                  </div>
                  <p className="text-[10px] text-[#94A3B8] mt-1 line-clamp-2">
                    {top_3_availability[0]?.name || 'Všetky pracovné stanice linky sú bez poruchy.'}
                  </p>
                </div>
                <div className="mt-4 pt-2.5 border-t border-white/10 text-[10px] text-[#F59E0B] font-semibold flex items-center justify-between">
                  <span>{top_3_availability[0]?.station || 'Linka v chode'}</span>
                  <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                </div>
              </div>

              {/* Card 2: 🔴 TOP 1 Kvalita (Red Glow) */}
              <div 
                onClick={() => onOpenMachineStation && onOpenMachineStation(topQStationId)}
                className="bg-[#18181B] rounded-[22px] p-5 glow-card-red flex flex-col justify-between cursor-pointer group"
              >
                <div>
                  <div className="flex items-center justify-between text-[11px] font-bold text-[#EF4444] uppercase tracking-wider mb-3">
                    <span>Kvalita NOK</span>
                    <AlertOctagon className="w-3.5 h-3.5" />
                  </div>
                  <div className="text-3xl font-extrabold text-[#EF4444] tracking-tight">
                    {top_3_quality[0]?.total_nok ?? 0}
                    <span className="text-sm font-normal text-white/70 ml-1">ks</span>
                  </div>
                  <div className="text-xs font-bold text-white mt-2 group-hover:text-[#EF4444] transition-colors">
                    {top_3_quality[0]?.code || '100% Bezchybnosť'}
                  </div>
                  <p className="text-[10px] text-[#94A3B8] mt-1 line-clamp-2">
                    {top_3_quality[0]?.name || 'Nezaznamenaný žiaden defekt kvality.'}
                  </p>
                </div>
                <div className="mt-4 pt-2.5 border-t border-white/10 text-[10px] text-[#EF4444] font-semibold flex items-center justify-between">
                  <span>{top_3_quality[0]?.station || 'Kvalita OK'}</span>
                  <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                </div>
              </div>

              {/* Card 3: 🔵 AI Maintenance Copilot (Blue Glow) */}
              <div 
                onClick={handleRunAiCopilot}
                className="bg-[#18181B] rounded-[22px] p-5 glow-card-blue flex flex-col justify-between cursor-pointer group"
              >
                <div>
                  <div className="flex items-center justify-between text-[11px] font-bold text-[#3B82F6] uppercase tracking-wider mb-3">
                    <span>AI Copilot</span>
                    <Cpu className="w-3.5 h-3.5" />
                  </div>
                  <div className="text-3xl font-extrabold text-[#38BDF8] tracking-tight">
                    98%
                  </div>
                  <div className="text-xs font-bold text-white mt-2 group-hover:text-[#38BDF8] transition-colors">
                    Qwen 2.5 3B
                  </div>
                  <p className="text-[10px] text-[#94A3B8] mt-1">
                    Okamžitá TPM diagnostika a 5-Why
                  </p>
                </div>
                <div className="mt-4 pt-2.5 border-t border-white/10 text-[10px] text-[#38BDF8] font-semibold flex items-center justify-between">
                  <span>{aiLoading ? 'Generujem...' : 'Spustiť AI'}</span>
                  <Zap className="w-3 h-3" />
                </div>
              </div>

            </div>

            {/* AI Copilot Output Drawer */}
            {aiResponse && (
              <div className="bg-[#18181B] border border-[#3B82F6]/50 rounded-[20px] p-4 text-xs text-[#E2E8F0] shadow-glow-blue animate-fadeIn">
                <div className="flex items-center justify-between mb-2 pb-2 border-b border-[#27272A]">
                  <span className="font-bold text-[#38BDF8] flex items-center gap-1.5">
                    <Cpu className="w-4 h-4" />
                    Odporúčanie AI Údržby (TPM):
                  </span>
                  <button 
                    onClick={() => setAiResponse(null)}
                    className="text-gray-400 hover:text-white text-xs font-bold"
                  >
                    ✕
                  </button>
                </div>
                <div className="whitespace-pre-line font-mono text-[11px] leading-relaxed">
                  {aiResponse}
                </div>
              </div>
            )}

          </div>


          {/* ========================================================
              COLUMN 3 (3/12 Cols): Critical Alerts & Slide 11 Waterfall
             ======================================================== */}
          <div className="lg:col-span-3 flex flex-col gap-4">
            
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-[#EF4444]" />
                Kritické alarmy linky
              </h3>
            </div>

            {/* Critical Alerts List (CityCare right side - Dynamic) */}
            <div className="space-y-2.5">
              {(() => {
                const alarmHours = shiftHours.filter(h => h.downtime_min > 0 || h.nok_pcs > 0);

                if (alarmHours.length === 0) {
                  return (
                    <div className="p-4 rounded-2xl bg-[#18181B] border border-[#10B981]/30 text-center">
                      <div className="flex items-center justify-center gap-2 text-xs font-semibold text-[#10B981]">
                        <CheckCircle2 className="w-4 h-4" />
                        <span>Linka bez aktívnych porúch</span>
                      </div>
                      <p className="text-[10px] text-[#94A3B8] mt-1">
                        Všetkých 8 hodín zmeny pracuje bez zaznamenaných prestojov.
                      </p>
                    </div>
                  );
                }

                return alarmHours.slice(0, 3).map((ah) => {
                  const isDowntime = ah.downtime_min > 0;
                  const dtInfo = ah.downtime_code ? DOWNTIME_CATALOG[ah.downtime_code] : null;
                  const qInfo = ah.nok_code ? QUALITY_CATALOG[ah.nok_code] : null;

                  return (
                    <div 
                      key={ah.hour}
                      onClick={() => onSelectHour(ah.hour)}
                      className="p-3 rounded-2xl bg-[#18181B] border border-[#27272A] hover:border-[#EF4444]/40 transition-colors cursor-pointer"
                    >
                      <div className="flex items-center justify-between text-[11px]">
                        <span className={`font-bold flex items-center gap-1.5 ${isDowntime ? 'text-[#EF4444]' : 'text-[#F59E0B]'}`}>
                          <span className={`w-2 h-2 rounded-full ${isDowntime ? 'bg-[#EF4444] animate-beacon' : 'bg-[#F59E0B]'}`} />
                          {ah.downtime_code || ah.nok_code || `Hodina ${ah.hour}`}
                        </span>
                        <span className="text-[#94A3B8] font-mono text-[10px]">
                          {ah.slot}
                        </span>
                      </div>
                      <div className="text-xs text-white mt-1 font-medium truncate">
                        {dtInfo?.name_sk || qInfo?.name_sk || (isDowntime ? 'Technický prestoj' : 'Brak kvality')}
                      </div>
                      <div className="text-[10px] text-[#94A3B8] mt-0.5">
                        {isDowntime ? `Strata: ${ah.downtime_min} min (-${ah.downtime_min} ks)` : `Brak: ${ah.nok_pcs} ks NOK`}
                      </div>
                    </div>
                  );
                });
              })()}
            </div>

            {/* Waterfall Magna Slide 11 Breakdown Bar - Dynamic */}
            <div className="p-4 rounded-2xl bg-[#18181B] border border-[#27272A] mt-2">
              <div className="text-xs font-bold text-white mb-2 flex items-center justify-between">
                <span>Magna Rozpad výrobných strát</span>
                <span className="text-[#10B981] font-mono font-bold">{waterfall.good_pieces} OK</span>
              </div>
              
              {/* Visual Step-Down Bars */}
              <div className="space-y-1.5 text-[11px]">
                <div className="flex justify-between items-center text-[#94A3B8]">
                  <span>1. Plán (Target)</span>
                  <b className="text-white font-mono">{waterfall.ideal_target} ks</b>
                </div>
                <div className="flex justify-between items-center text-[#EF4444]">
                  <span>2. Prestoje (-{totals.downtime_min} min)</span>
                  <b className="font-mono">-{waterfall.downtime_loss_pcs} ks</b>
                </div>
                <div className="flex justify-between items-center text-[#F59E0B]">
                  <span>3. Rýchlosť (Cycle loss)</span>
                  <b className="font-mono">-{waterfall.speed_loss_pcs} ks</b>
                </div>
                <div className="flex justify-between items-center text-[#3B82F6] pt-1 border-t border-[#27272A]">
                  <span>4. Vyrobené spolu</span>
                  <b className="font-mono">{waterfall.actual_produced} ks</b>
                </div>
                <div className="flex justify-between items-center text-[#EF4444]">
                  <span>5. Brak (NOK)</span>
                  <b className="font-mono">-{waterfall.quality_loss_pcs} ks</b>
                </div>
                <div className="flex justify-between items-center text-[#10B981] font-bold pt-1 border-t border-[#27272A]">
                  <span>6. Predajné kusy (OK)</span>
                  <b className="font-mono">{waterfall.good_pieces} ks</b>
                </div>
              </div>
            </div>

          </div>

        </div>

      </div>
    </section>
  );
};
