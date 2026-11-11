import React, { useState } from 'react';
import { StationTechInfo } from '../types';
import { LINE_STATIONS } from '../data/constants';
import { ThreeFactoryScene } from './ThreeFactoryScene';
import { EngineeringLineDiagram } from './EngineeringLineDiagram';
import { StationAIChatCopilot } from './StationAIChatCopilot';
import { 
  AlertTriangle, 
  CheckCircle2, 
  Settings, 
  Eye, 
  Activity, 
  Wrench, 
  ShieldCheck, 
  Zap, 
  Cpu, 
  RotateCw, 
  Gauge, 
  Box,
  CheckSquare,
  Square,
  Sparkles,
  Info,
  Layers,
  ArrowRight
} from 'lucide-react';

interface Props {
  activeDowntimeCode?: string | null;
  activeNokCode?: string | null;
  onResolveStation?: (stationId: number) => void;
  selectedStationId?: number | null;
  onSelectStation?: (stationId: number | null) => void;
  resolvedStations?: Set<number>;
  completedSteps?: Record<string, boolean>;
  onToggleStep?: (stationId: number, stepIdx: number) => void;
}

// 5 Specific TPM Action Plan Steps for Station 3 (Camera Inspection ST-038)
const OP30_REMEDY_STEPS_5 = [
  {
    step: 1,
    title: "LOTO: Bezpečné odpojenie napájania 24V DC",
    desc: "Vypnúť hlavný istič QF3 na rozvádzači a odpojiť prívodný konektor X2.",
    component: "Konektor X2 (24V DC)",
    badge: "LOTO Zásah"
  },
  {
    step: 2,
    title: "Očistenie optickej šošovky Cognex & polarizátora",
    desc: "Zotrieť optický prach mikrovláknovou utierkou napustenou izopropanolom.",
    component: "Optická šošovka & LED kruh",
    badge: "Optika"
  },
  {
    step: 3,
    title: "Kontrola a dotiahnutie uvoľneného konektora X2",
    desc: "Skontrolovať piny konektora, dotiahnuť montážnu poistku momentom 0.6 Nm.",
    component: "Svorkovnica X2",
    badge: "Elektro"
  },
  {
    step: 4,
    title: "Kalibrácia a test kruhového LED osvetlenia",
    desc: "Zmerať intenzitu osvetlenia (norma >400 lux), skontrolovať polarizačný filter.",
    component: "Kruhový LED iluminátor",
    badge: "Svetlo"
  },
  {
    step: 5,
    title: "Skúšobná snímka v In-Sight Explorer & spustenie",
    desc: "Spustiť overovací kontrolný cyklus snímania, potvrdiť detekciu a spustiť takt 56s.",
    component: "Testovacie lôžko & PLC",
    badge: "Verifikácia"
  }
];

// 5 Specific TPM / Quality Action Plan Steps for Station 2 (Nalisovanie el. motora - Kistler 50kN / TOX Press)
const OP20_REMEDY_STEPS_5 = [
  {
    step: 1,
    title: "LOTO: Zablokovanie servopohonu lisu & aretácia barana",
    desc: "Aktivovať bezpečnostný zámok lisu QF2, zaistiť mechanický aretačný klin barana.",
    component: "Bezpečnostný istič QF2 & aretačný čap",
    badge: "LOTO Bezpečnosť"
  },
  {
    step: 2,
    title: "Inšpekcia lisovacieho tŕňa & vyčistenie sedla rotora",
    desc: "Skontrolovať povrch tŕňa na prítomnosť otrepov a nečistôt, zotrieť kovový prach.",
    component: "Lisovací tŕň (Ø 42.0 mm)",
    badge: "Mechanika"
  },
  {
    step: 3,
    title: "Kontrola kalibrácie piezo snímača sily (Kistler 50kN)",
    desc: "Overiť nulový bod snímača sily a pripojenie nízkošumového koaxiálneho kábla.",
    component: "Piezo snímač sily Kistler",
    badge: "Kalibrácia"
  },
  {
    step: 4,
    title: "Overenie optického pravítka hĺbky vlisovania (Limit 42±0.2 mm)",
    desc: "Zmerať koncový doraz servolôžka kalibrovaným hĺbkomerom, očistiť optickú stupnicu.",
    component: "Optické pravítko dráhy (Keyence)",
    badge: "Senzor dráhy"
  },
  {
    step: 5,
    title: "Testovací cyklus lisu & potvrdenie tolerančného okna F/s",
    desc: "Vykonať 1 referenčné zalisovanie, overiť silovú krivku (max 38.4 kN) a uvoľniť linku.",
    component: "Riadiaci systém Kistler maXYmos & PLC",
    badge: "Verifikácia"
  }
];

export const InteractiveStationDiagram: React.FC<Props> = ({
  activeDowntimeCode,
  activeNokCode,
  onResolveStation,
  selectedStationId: externalSelectedId,
  onSelectStation,
  resolvedStations: externalResolvedStations,
  completedSteps: externalCompletedSteps,
  onToggleStep: externalOnToggleStep,
}) => {
  const [internalSelectedId, setInternalSelectedId] = useState<number | null>(null); // Null = Full Isometric line overview
  const [internalCompletedSteps, setInternalCompletedSteps] = useState<Record<string, boolean>>(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const doneParam = params.get('done');
      if (doneParam) {
        const stn = params.get('station') || '3';
        const res: Record<string, boolean> = {};
        if (doneParam === 'all') {
          for (let i = 0; i < 5; i++) res[`${stn}_${i}`] = true;
        } else {
          doneParam.split(',').forEach(idx => {
            res[`${stn}_${idx.trim()}`] = true;
          });
        }
        return res;
      }
    }
    return {};
  });
  const [internalResolvedStations, setInternalResolvedStations] = useState<Set<number>>(new Set());

  // View mode: '2d' (High-Detail Industrial Vector & Blueprint) vs '3d' (Three.js WebGL)
  const [diagramMode, setDiagramMode] = useState<'2d' | '3d'>('2d');

  // Interactive Step Focus State
  const [activeStepIdx, setActiveStepIdx] = useState<number | null>(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const stp = params.get('step');
      if (stp !== null) return parseInt(stp, 10);
    }
    return null;
  });

  // Hover state from AI Copilot steps to trigger smooth vector zoom on diagram
  const [hoveredStepIdx, setHoveredStepIdx] = useState<number | null>(null);

  const resolvedStations = externalResolvedStations ?? internalResolvedStations;
  const completedSteps = externalCompletedSteps ?? internalCompletedSteps;

  const selectedStationId = externalSelectedId !== undefined ? externalSelectedId : internalSelectedId;
  const setSelectedStationId = (id: number | null) => {
    if (onSelectStation) onSelectStation(id);
    setInternalSelectedId(id);
    setActiveStepIdx(null); // Reset step when changing station
  };

  const selectedStation = (selectedStationId ? LINE_STATIONS.find(s => s.id === selectedStationId) : null) || LINE_STATIONS[2];

  // Icons for stations
  const getStationIcon = (id: number) => {
    switch (id) {
      case 1: return <Box className="w-4 h-4" />;
      case 2: return <Gauge className="w-4 h-4" />;
      case 3: return <Eye className="w-4 h-4" />;
      case 4:
      case 5: return <Wrench className="w-4 h-4" />;
      case 6: return <RotateCw className="w-4 h-4" />;
      case 7: return <Cpu className="w-4 h-4" />;
      case 8: return <Wrench className="w-4 h-4" />;
      case 9: return <Activity className="w-4 h-4" />;
      case 10: return <Zap className="w-4 h-4" />;
      default: return <Settings className="w-4 h-4" />;
    }
  };

  const isAlarm = (st: StationTechInfo) => {
    if (resolvedStations.has(st.id)) return false;
    return Boolean(activeDowntimeCode && st.related_codes.includes(activeDowntimeCode));
  };

  const isWarning = (st: StationTechInfo) => {
    if (resolvedStations.has(st.id)) return false;
    return Boolean(activeNokCode && st.related_codes.includes(activeNokCode));
  };

  const toggleStep = (idx: number) => {
    if (externalOnToggleStep) {
      externalOnToggleStep(selectedStation.id, idx);
    } else {
      const key = `${selectedStation.id}_${idx}`;
      setInternalCompletedSteps(prev => ({ ...prev, [key]: !prev[key] }));
    }
  };

  const handleFixStation = () => {
    setInternalResolvedStations(prev => new Set([...prev, selectedStation.id]));
    if (onResolveStation) {
      onResolveStation(selectedStation.id);
    }
  };

  const stationHasAlarm = isAlarm(selectedStation);
  const stationHasWarning = isWarning(selectedStation);
  const isResolved = resolvedStations.has(selectedStation.id);
  const needsRepair = (stationHasAlarm || stationHasWarning) && !isResolved;

  // Active steps calculation (Specific 5 steps for OP30 and OP20)
  const stepsList = selectedStation.id === 3 
    ? OP30_REMEDY_STEPS_5 
    : selectedStation.id === 2 
    ? OP20_REMEDY_STEPS_5 
    : selectedStation.remedy_steps.map((r, i) => ({
        step: i + 1,
        title: r,
        desc: "Štandardný predpísaný zásah údržby linky L01.",
        component: selectedStation.critical_part,
        badge: "TPM Zásah"
      }));

  const checkedStepsCount = stepsList.filter((_, idx) => !!completedSteps[`${selectedStation.id}_${idx}`]).length;
  const progressPercent = Math.round((checkedStepsCount / stepsList.length) * 100);

  return (
    <div className="max-w-[1440px] w-full mx-auto px-6 mb-8 select-none">
      <div className="bg-[#18181B] border border-[#27272A] rounded-[32px] p-6 lg:p-8 shadow-2xl text-white space-y-6">
        
        {/* 1. Header with Live Status */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-[#27272A]">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-[#3B82F6]/20 border border-[#3B82F6]/40 flex items-center justify-center text-[#38BDF8] shadow-glow-blue">
                <Layers className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2.5">
                  <h3 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                    Factory X-Ray — Linka L01 (3D Digital Twin)
                  </h3>
                  <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-[#3B82F6]/20 text-[#38BDF8] border border-[#3B82F6]/30 uppercase tracking-wider">
                    Three.js WebGL & AI Copilot
                  </span>
                </div>
                <p className="text-xs text-[#94A3B8] mt-0.5">
                  Plne interaktívny 3D model linky s voľným otáčaním. Kliknite na krok v AI Copilot a 3D kamera plynule poletí priamo k danému komponentu!
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 text-xs">
            {/* View Mode Switcher: 2D Ultra-Detail Engineering vs 3D WebGL */}
            <div className="flex items-center p-1 rounded-xl bg-[#090D16] border border-[#27272A]">
              <button
                onClick={() => setDiagramMode('2d')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                  diagramMode === '2d'
                    ? 'bg-[#3B82F6] text-white shadow-glow-blue'
                    : 'text-[#94A3B8] hover:text-white'
                }`}
              >
                <span>📐 2D Inžiniersky X-Ray</span>
              </button>
              <button
                onClick={() => setDiagramMode('3d')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                  diagramMode === '3d'
                    ? 'bg-[#3B82F6] text-white shadow-glow-blue'
                    : 'text-[#94A3B8] hover:text-white'
                }`}
              >
                <span>🎲 3D Model</span>
              </button>
            </div>

            {/* Alarm indicator */}
            {!resolvedStations.has(3) && activeDowntimeCode ? (
              <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#EF4444]/15 text-[#EF4444] border border-[#EF4444]/30 font-semibold">
                <span className="w-2 h-2 rounded-full bg-[#EF4444] animate-ping" />
                1 ALARM (OP30 • ST-038)
              </span>
            ) : (
              <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30 font-semibold">
                <span className="w-2 h-2 rounded-full bg-[#10B981]" />
                Všetky stanice OK (100% v norme)
              </span>
            )}
          </div>
        </div>

        {/* 2. View Switcher & 10 Stations Horizontal Sequence Selector Bar */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSelectedStationId(null)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all duration-300 flex items-center gap-2 border ${
                  selectedStationId === null
                    ? 'bg-[#3B82F6] text-white border-[#38BDF8] shadow-glow-blue'
                    : 'bg-[#18181B] text-[#94A3B8] border-[#27272A] hover:text-white hover:border-[#38BDF8]'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>🌐 Celá linka L01 (Izometrický prehľad)</span>
              </button>
              <span className="text-[11px] text-[#6B7280] hidden sm:inline">
                Kliknite na stanicu pre detailný 3D náhľad:
              </span>
            </div>

            {selectedStationId !== null && (
              <span className="text-[11px] font-mono text-[#38BDF8] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#38BDF8] animate-pulse" />
                Zaostrené na: <b>OP{selectedStationId * 10}</b>
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-2">
            {LINE_STATIONS.map((st) => {
              const hasAlarm = isAlarm(st);
              const hasWarning = isWarning(st);
              const isSelected = st.id === selectedStationId;
              const isStationResolved = resolvedStations.has(st.id);

              return (
                <button
                  key={st.id}
                  onClick={() => setSelectedStationId(isSelected ? null : st.id)}
                  className={`p-2.5 rounded-2xl text-left transition-all duration-300 relative flex flex-col justify-between h-24 border ${
                    isSelected
                      ? 'bg-[#27272A] border-[#3B82F6] ring-2 ring-[#3B82F6]/50 shadow-glow-blue scale-[1.03] z-10'
                      : hasAlarm
                      ? 'bg-[#18181B] border-[#EF4444] glow-card-red'
                      : hasWarning
                      ? 'bg-[#18181B] border-[#F59E0B] glow-card-orange'
                      : 'bg-[#18181B] border-[#27272A] hover:border-gray-500 hover:bg-[#202024]'
                  }`}
                >
                  <div className="flex items-center justify-between w-full">
                    <span className="text-[10px] font-mono font-bold text-[#94A3B8]">
                      OP{st.id * 10}
                    </span>
                    <div className={`p-1 rounded-lg ${
                      hasAlarm ? 'text-[#EF4444] bg-[#EF4444]/10' : hasWarning ? 'text-[#F59E0B] bg-[#F59E0B]/10' : 'text-[#3B82F6] bg-[#3B82F6]/10'
                    }`}>
                      {getStationIcon(st.id)}
                    </div>
                  </div>

                  <div className="text-[10.5px] font-bold text-white truncate mt-1">
                    {st.name}
                  </div>

                  <div className="mt-auto flex items-center justify-between text-[9px]">
                    {hasAlarm ? (
                      <span className="text-[#EF4444] font-bold flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#EF4444] animate-ping" />
                        ALARM
                      </span>
                    ) : hasWarning ? (
                      <span className="text-[#F59E0B] font-bold">POZOR</span>
                    ) : isStationResolved ? (
                      <span className="text-[#10B981] font-bold">✓ OK</span>
                    ) : (
                      <span className="text-[#10B981] font-semibold">OK</span>
                    )}
                    <span className="text-[#6B7280] font-mono">{st.telemetry.cycle_time}s</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* 3. Main Digital Twin View: 2D Ultra-Detailed Engineering Cutaway OR 3D WebGL Scene */}
        {diagramMode === '2d' ? (
          <EngineeringLineDiagram
            selectedStationId={selectedStationId}
            activeStepIdx={activeStepIdx}
            hoveredStepIdx={hoveredStepIdx}
            onSelectStation={(id) => setSelectedStationId(id)}
            onSelectStep={(idx) => {
              if (idx === -1 || activeStepIdx === idx) {
                setActiveStepIdx(null);
              } else {
                setActiveStepIdx(idx);
              }
            }}
            isAlarm={!resolvedStations.has(3) && Boolean(activeDowntimeCode)}
            onResolveStation={handleFixStation}
            resolvedStations={resolvedStations}
          />
        ) : (
          <ThreeFactoryScene
            selectedStationId={selectedStationId}
            activeStepIdx={activeStepIdx}
            onSelectStation={(id) => setSelectedStationId(id)}
            onSelectStep={(idx) => {
              if (idx === -1 || activeStepIdx === idx) {
                setActiveStepIdx(null);
              } else {
                setActiveStepIdx(idx);
              }
            }}
            isAlarm={!resolvedStations.has(3) && Boolean(activeDowntimeCode)}
            onResolveStation={handleFixStation}
          />
        )}

        {/* 4. Bottom Diagnostic, Root Cause 5-Why & AI Copilot 5-Step Action Plan */}
        <div className="bg-[#09090B] border border-[#27272A] rounded-[24px] p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* Left Block (8 Cols): Row 1 (Telemetry + 5-Why) & Row 2 (AI Maintenance Chat Copilot) */}
          <div className="lg:col-span-8 flex flex-col gap-6">
            
            {/* Row 1: Telemetry Card & 5-Why Root Cause Card */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-stretch">
              
              {/* Column 1: Station Telemetry & Live Sensors */}
              <div className="bg-[#18181B] p-5 rounded-2xl border border-[#27272A] flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between pb-3 border-b border-[#27272A]">
                    <div>
                      <span className="text-[10px] font-mono font-bold uppercase text-[#3B82F6]">
                        Stanica OP{selectedStation.id * 10} • {selectedStation.type}
                      </span>
                      <h4 className="text-base font-bold text-white mt-0.5">
                        {selectedStation.name}
                      </h4>
                    </div>
                    <div className="p-2 rounded-xl bg-[#3B82F6]/10 text-[#38BDF8]">
                      {getStationIcon(selectedStation.id)}
                    </div>
                  </div>

                  {/* Live Sensors Grid */}
                  <div className="grid grid-cols-2 gap-2.5 mt-4 text-xs">
                    <div className="p-2.5 bg-[#09090B] rounded-xl border border-[#27272A]">
                      <span className="text-[10px] text-[#94A3B8] block">Teplota pohonu</span>
                      <b className="text-white font-mono text-sm">{selectedStation.telemetry.temp_c}°C</b>
                    </div>
                    <div className="p-2.5 bg-[#09090B] rounded-xl border border-[#27272A]">
                      <span className="text-[10px] text-[#94A3B8] block">Pracovný tlak / moment</span>
                      <b className="text-white font-mono text-sm">{selectedStation.telemetry.pressure_bar} bar</b>
                    </div>
                    <div className="p-2.5 bg-[#09090B] rounded-xl border border-[#27272A]">
                      <span className="text-[10px] text-[#94A3B8] block">Vibračný index</span>
                      <b className={`font-mono text-sm ${stationHasAlarm ? 'text-[#EF4444]' : 'text-[#10B981]'}`}>
                        {stationHasAlarm ? selectedStation.telemetry.vibration_mm_s : Math.min(1.4, selectedStation.telemetry.vibration_mm_s)} mm/s
                      </b>
                    </div>
                    <div className="p-2.5 bg-[#09090B] rounded-xl border border-[#27272A]">
                      <span className="text-[10px] text-[#94A3B8] block">Čas cyklu (CT)</span>
                      <b className={`font-mono text-sm ${stationHasAlarm ? 'text-[#EF4444]' : 'text-white'}`}>
                        {selectedStation.telemetry.cycle_time} s
                      </b>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[#27272A] text-[11px] text-[#94A3B8] space-y-1.5">
                  <div>
                    <span className="text-[#6B7280]">Zariadenie:</span> <span className="text-white font-medium">{selectedStation.tech}</span>
                  </div>
                  <div>
                    <span className="text-[#6B7280]">Kritický komponent:</span> <span className="text-white font-medium">{selectedStation.critical_part}</span>
                  </div>
                  <p className="pt-1 text-[#94A3B8] leading-relaxed">
                    {selectedStation.description}
                  </p>
                </div>
              </div>

              {/* Column 2: 5-Why Root Cause Chain / SOP Standard */}
              <div className="bg-[#18181B] p-5 rounded-2xl border border-[#27272A] flex flex-col justify-between">
                {needsRepair ? (
                  <>
                    <div>
                      <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#27272A]">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-[#EF4444]" />
                          <h4 className="text-xs font-bold text-[#EF4444] uppercase tracking-wider">
                            Analýza koreňovej príčiny (5-Why)
                          </h4>
                        </div>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#EF4444]/20 text-[#EF4444] font-bold">
                          AKTÍVNY INCIDENT
                        </span>
                      </div>

                      <div className="space-y-2 text-xs">
                        {selectedStation.five_why.map((why, idx) => (
                          <div key={idx} className="p-2 rounded-xl bg-[#09090B] border border-[#27272A] flex items-start gap-2">
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#3B82F6]/20 text-[#38BDF8] shrink-0">
                              W{idx + 1}
                            </span>
                            <span className="text-[#D1D5DB] text-[11px] leading-tight">
                              {why}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="mt-3 p-2.5 rounded-xl bg-[#EF4444]/10 border border-[#EF4444]/30 text-[11px] text-[#FCA5A5]">
                      <b className="text-white block mb-0.5">Identifikovaná príčina:</b>
                      {selectedStation.cause}
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#27272A]">
                        <div className="flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4 text-[#10B981]" />
                          <h4 className="text-xs font-bold text-[#10B981] uppercase tracking-wider">
                            Štandardná prevádzka (SOP)
                          </h4>
                        </div>
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-[#10B981]/15 text-[#10B981]">
                          100% V NORME
                        </span>
                      </div>

                      <div className="space-y-2.5 text-xs text-[#94A3B8]">
                        <div className="p-3 rounded-xl bg-[#09090B] border border-[#27272A]">
                          <span className="text-[11px] text-white font-semibold block mb-1">
                            Predpísaný Lean štandard:
                          </span>
                          <div className="text-xs text-[#38BDF8] font-bold">
                            {selectedStation.lean_tool}
                          </div>
                          <div className="text-[11px] text-[#D1D5DB] mt-1">
                            {selectedStation.lean_desc}
                          </div>
                        </div>

                        <div className="p-3 rounded-xl bg-[#09090B] border border-[#27272A]">
                          <span className="text-[11px] text-white font-semibold block mb-1">
                            FMEA Preventívna ochrana:
                          </span>
                          <p className="text-[11px] leading-relaxed">
                            Pracovisko má zavedené Poka-Yoke bariéry zabraňujúce vzniku defektov. Všetky tolerancie senzorov sú v zelenom poli.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="mt-3 p-2.5 rounded-xl bg-[#10B981]/10 border border-[#10B981]/30 text-[11px] text-[#10B981] flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-[#10B981]" />
                      <span>Stanica beží v nominálnom takte {selectedStation.telemetry.cycle_time}s.</span>
                    </div>
                  </>
                )}
              </div>

            </div>

            {/* Row 2: AI Assistant Maintenance Chat Copilot (Qwen 2.5 3B with OEM SOP manuals) */}
            <StationAIChatCopilot 
              station={selectedStation} 
              activeStepIdx={activeStepIdx} 
            />

          </div>

          {/* Right Column (4 Cols): AI Copilot 5-Step Action Plan with Camera Fly-To */}
          <div className="lg:col-span-4 bg-[#18181B] p-5 rounded-2xl border border-[#27272A] flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2 pb-2 border-b border-[#27272A]">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#F59E0B]" />
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                    {needsRepair ? 'AI Copilot — 5-Krokový plán opravy' : 'Preventívna autonómna údržba'}
                  </h4>
                </div>
                <span className="text-[10px] text-[#38BDF8] font-mono font-bold">
                  {checkedStepsCount}/{stepsList.length} Hotovo ({progressPercent}%)
                </span>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-[#09090B] h-1.5 rounded-full overflow-hidden mb-3 border border-white/5">
                <div 
                  className="h-full bg-gradient-to-r from-[#3B82F6] to-[#10B981] transition-all duration-300"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>

              <p className="text-[10.5px] text-[#94A3B8] mb-3">
                {needsRepair ? (
                  <span>💡 <b>Kliknite na krok</b> pre trvalé zaostrenie (zoom ostane uzamknutý). Pre potvrdenie splnenia kliknite na štvorček <b>[✓]</b>.</span>
                ) : (
                  <span>Pravidelný kontrolný zoznam autonómnej údržby pre operátora zmeny.</span>
                )}
              </p>

              {/* Step Action Cards with Dynamic Zoom on Hover & Click */}
              <div className="space-y-2">
                {stepsList.map((item, idx) => {
                  const key = `${selectedStation.id}_${idx}`;
                  const isChecked = !!completedSteps[key];
                  const isActive = activeStepIdx === idx;
                  const isHovered = hoveredStepIdx === idx;

                  return (
                    <div
                      key={idx}
                      onClick={() => {
                        // Clicking card body toggles camera lock/focus on this component
                        if (activeStepIdx === idx) {
                          setActiveStepIdx(null);
                        } else {
                          setActiveStepIdx(idx);
                        }
                      }}
                      onMouseEnter={() => setHoveredStepIdx(idx)}
                      onMouseLeave={() => setHoveredStepIdx(null)}
                      className={`group p-3 rounded-xl border cursor-pointer transition-all duration-200 flex flex-col gap-1.5 text-xs ${
                        isActive
                          ? 'bg-[#3B82F6]/20 border-[#38BDF8] text-white shadow-[0_0_20px_rgba(56,189,248,0.25)] ring-2 ring-[#38BDF8]/50'
                          : isChecked 
                          ? 'bg-[#10B981]/10 border-[#10B981]/30 text-[#D1D5DB] hover:border-[#10B981]/50' 
                          : isHovered
                          ? 'bg-[#182338] border-[#38BDF8]/60 text-white shadow-md'
                          : 'bg-[#09090B] border-[#27272A] text-[#D1D5DB] hover:border-gray-500 hover:bg-[#18181B]'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {/* Dedicated Checkbox Button - toggles completion independently from zoom */}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleStep(idx);
                            }}
                            className="p-0.5 rounded transition-transform active:scale-90"
                            title={isChecked ? 'Kliknite pre zrušenie označenia' : 'Kliknite pre označenie kroku za hotový'}
                          >
                            {isChecked ? (
                              <CheckSquare className="w-4 h-4 text-[#10B981] fill-[#10B981]/20" />
                            ) : (
                              <Square className="w-4 h-4 text-gray-500 group-hover:text-gray-300" />
                            )}
                          </button>

                          <span className={`text-[10px] font-bold font-mono px-1.5 py-0.5 rounded ${
                            isActive ? 'bg-[#38BDF8] text-[#090D16]' : 'bg-white/10 text-white'
                          }`}>
                            Krok {item.step}
                          </span>
                          <span className="text-[9.5px] font-semibold text-[#94A3B8]">
                            {item.badge}
                          </span>
                        </div>

                        {/* Status Tag on right */}
                        <div>
                          {isActive ? (
                            <span className="text-[10px] font-bold text-[#38BDF8] bg-[#38BDF8]/15 px-2 py-0.5 rounded-full border border-[#38BDF8]/30 flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] animate-pulse" />
                              <span>🔍 Zaostrené</span>
                            </span>
                          ) : isChecked ? (
                            <span className="text-[9.5px] font-bold text-[#10B981] bg-[#10B981]/15 px-2 py-0.5 rounded-full border border-[#10B981]/30">
                              ✓ Hotovo
                            </span>
                          ) : isHovered ? (
                            <span className="text-[9.5px] font-semibold text-[#38BDF8]">
                              Náhľad 🔍
                            </span>
                          ) : (
                            <span className="text-[9.5px] text-[#6B7280] group-hover:text-[#94A3B8]">
                              Kliknite pre zoom
                            </span>
                          )}
                        </div>
                      </div>

                      <div className={`text-[11.5px] font-bold leading-tight pl-6 ${
                        isChecked ? 'line-through text-[#94A3B8]' : 'text-white'
                      }`}>
                        {item.title}
                      </div>
                      <div className="text-[10px] text-[#94A3B8] pl-6 leading-tight">
                        {item.desc}
                      </div>

                      {/* When Step is actively locked, show inline Quick-Action Bar */}
                      {isActive && (
                        <div className="mt-2 pt-2 border-t border-[#38BDF8]/20 flex items-center justify-between gap-2 pl-6">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleStep(idx);
                            }}
                            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all flex items-center gap-1.5 active:scale-95 ${
                              isChecked 
                                ? 'bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/40 hover:bg-[#10B981]/30' 
                                : 'bg-[#10B981] hover:bg-[#059669] text-white shadow-md'
                            }`}
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>{isChecked ? 'Krok hotový ✓' : 'Označiť ako hotové ✓'}</span>
                          </button>

                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveStepIdx(null);
                            }}
                            className="px-2 py-1 rounded-lg text-[10.5px] text-[#94A3B8] hover:text-white bg-white/5 hover:bg-white/10 transition-colors"
                            title="Vrátiť sa na celý prehľad stanice"
                          >
                            Oddialiť ✕
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Resolve button (if alarm) OR Status Banner (if normal) */}
            <div className="mt-5 pt-3 border-t border-[#27272A]">
              {needsRepair ? (
                <button
                  onClick={handleFixStation}
                  className={`w-full py-3 rounded-xl text-white font-bold text-xs active:scale-[0.98] transition-all flex items-center justify-center gap-2 shadow-lg ${
                    checkedStepsCount === stepsList.length
                      ? 'bg-gradient-to-r from-[#10B981] to-[#059669] hover:from-[#059669] hover:to-[#047857] shadow-[0_0_20px_rgba(16,185,129,0.4)] animate-pulse'
                      : 'bg-gradient-to-r from-[#EF4444] to-[#DC2626] hover:from-[#10B981] hover:to-[#059669]'
                  }`}
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>
                    {checkedStepsCount === stepsList.length
                      ? `✓ Všetkých 5 krokov splnených — Potvrdiť opravu OP${selectedStation.id * 10}`
                      : `Potvrdiť opravu a spustiť stanicu OP${selectedStation.id * 10} (${checkedStepsCount}/${stepsList.length} hotovo)`}
                  </span>
                </button>
              ) : (
                <div className="p-3 rounded-xl bg-[#10B981]/10 border border-[#10B981]/30 flex items-center gap-3">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#10B981] shrink-0" />
                  <div>
                    <div className="text-xs font-bold text-[#10B981]">
                      Stanica v prevádzke • Zásah nie je potrebný
                    </div>
                    <div className="text-[10px] text-[#94A3B8]">
                      Takt cyklu {selectedStation.telemetry.cycle_time}s je stabilný v norme Magna L01.
                    </div>
                  </div>
                </div>
              )}
            </div>

          </div>

        </div>

      </div>
    </div>
  );
};
