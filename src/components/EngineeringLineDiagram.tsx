import React, { useState } from 'react';
import { 
  AlertTriangle, 
  ArrowLeft, 
  Crosshair, 
  ShieldAlert,
  Gauge,
  Sparkles,
  Zap,
  Activity,
  Layers,
  Wrench,
  CheckCircle2
} from 'lucide-react';
import { LINE_STATIONS } from '../data/constants';

interface Props {
  selectedStationId: number | null;
  activeStepIdx: number | null;
  hoveredStepIdx?: number | null;
  onSelectStation: (stationId: number | null) => void;
  onSelectStep: (stepIdx: number) => void;
  isAlarm: boolean;
  onResolveStation?: () => void;
  resolvedStations?: Set<number>;
}

export const EngineeringLineDiagram: React.FC<Props> = ({
  selectedStationId,
  activeStepIdx,
  hoveredStepIdx = null,
  onSelectStation,
  onSelectStep,
  isAlarm,
  resolvedStations = new Set(),
}) => {
  // If selectedStationId is 2 or 3, show deep-dive technical X-Ray cutaway
  const isDetailView = selectedStationId === 2 || selectedStationId === 3;
  const isStation2 = selectedStationId === 2;
  const isStation3 = selectedStationId === 3;

  // Local hover state on SVG pins
  const [internalHoverStep, setInternalHoverStep] = useState<number | null>(null);

  // Effective highlighted step (either hovered from panel, hovered from SVG, or actively selected)
  const effectiveStep = internalHoverStep !== null 
    ? internalHoverStep 
    : hoveredStepIdx !== null && hoveredStepIdx !== undefined
    ? hoveredStepIdx
    : activeStepIdx;

  // ========================================================================
  // CAMERA ZOOM & PAN TRANSFORMS (Smooth Vector Zoom to Component on Hover)
  // ========================================================================
  const getCameraZoomTransform = () => {
    if (effectiveStep === null) {
      return {
        transform: 'scale(1)',
        transformOrigin: '450px 260px'
      };
    }

    if (isStation3) {
      // OP30 Cognex Camera Station Zoom Targets
      switch (effectiveStep) {
        case 0: // Step 1: LOTO Switch on left cabinet
          return { transform: 'scale(1.85)', transformOrigin: '167px 225px' };
        case 1: // Step 2: Cognex Optical Lens & Polarizer
          return { transform: 'scale(1.9)', transformOrigin: '450px 195px' };
        case 2: // Step 3: Connector X2 & M12 Cable
          return { transform: 'scale(1.9)', transformOrigin: '515px 145px' };
        case 3: // Step 4: Circular LED Illuminator Ring
          return { transform: 'scale(1.85)', transformOrigin: '460px 220px' };
        case 4: // Step 5: Pallet Nest & Test Bed
          return { transform: 'scale(1.7)', transformOrigin: '450px 345px' };
        default:
          return { transform: 'scale(1)', transformOrigin: '450px 260px' };
      }
    }

    if (isStation2) {
      // OP20 Hydraulic / Servo Press Station Zoom Targets
      switch (effectiveStep) {
        case 0: // Step 1: LOTO Switch QF2 & Ram Lock on left cabinet
          return { transform: 'scale(1.85)', transformOrigin: '167px 225px' };
        case 1: // Step 2: Hardened Press Ram Tool & Stator Seat
          return { transform: 'scale(1.85)', transformOrigin: '450px 270px' };
        case 2: // Step 3: Kistler Piezo Quartz Force Sensor Ring
          return { transform: 'scale(1.9)', transformOrigin: '450px 175px' };
        case 3: // Step 4: Keyence Laser Optical Displacement Gauge
          return { transform: 'scale(1.9)', transformOrigin: '525px 235px' };
        case 4: // Step 5: Kistler maXYmos HMI Screen & F/s Curve
          return { transform: 'scale(1.8)', transformOrigin: '725px 210px' };
        default:
          return { transform: 'scale(1)', transformOrigin: '450px 260px' };
      }
    }

    return { transform: 'scale(1)', transformOrigin: '450px 260px' };
  };

  const { transform, transformOrigin } = getCameraZoomTransform();

  return (
    <div className="relative w-full bg-[#070B14] rounded-[32px] overflow-hidden border border-[#1E293B] shadow-[0px_8px_32px_rgba(0,0,0,0.6)]">
      
      {/* Top Header Bar: Mode Switcher, Status & Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 border-b border-[#1E293B] bg-[#0A0F1D]/80 backdrop-blur-md">
        <div className="flex items-center gap-2">
          {isDetailView ? (
            <button
              onClick={() => {
                onSelectStation(null);
                onSelectStep(-1);
              }}
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#1E293B] hover:bg-[#334155] text-white text-xs font-bold border border-white/10 shadow-lg transition-all active:scale-95"
            >
              <ArrowLeft className="w-4 h-4 text-[#38BDF8]" />
              <span>‹ Späť na celú linku (10 staníc)</span>
            </button>
          ) : (
            <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#0F172A] border border-white/10 text-white text-xs font-semibold">
              <span className="w-2.5 h-2.5 rounded-full bg-[#10B981] animate-pulse" />
              <span>Pohľad: <b>Linka L01 — Tok výroby Magna e-Drive (10 staníc)</b></span>
            </div>
          )}

          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-[11px] text-[#94A3B8]">
            <span>Režim:</span>
            <b className="text-[#38BDF8]">
              {isStation3 ? 'Technický rez OP30 (Kamera Cognex)' : isStation2 ? 'Technický rez OP20 (Lis Kistler 50kN)' : 'Sekvenčný proces (10 staníc)'}
            </b>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs">
          {isDetailView ? (
            <div className="flex items-center gap-2">
              {isStation3 ? (
                <span className="px-3 py-1 rounded-full bg-[#EF4444]/20 border border-[#EF4444]/40 text-[#EF4444] font-bold text-[11px] flex items-center gap-1.5 animate-pulse">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Stanica OP30: ALARM ST-038</span>
                </span>
              ) : (
                <span className="px-3 py-1 rounded-full bg-[#F59E0B]/20 border border-[#F59E0B]/40 text-[#F59E0B] font-bold text-[11px] flex items-center gap-1.5">
                  <Gauge className="w-3.5 h-3.5" />
                  <span>Stanica OP20: POZOR Q-020 (Sila lisu)</span>
                </span>
              )}
              <button
                onClick={() => {
                  onSelectStation(null);
                  onSelectStep(-1);
                }}
                className="px-3 py-1 rounded-full bg-[#1E293B] hover:bg-[#334155] text-[#94A3B8] hover:text-white border border-white/10 text-[11px] font-medium transition-all"
              >
                Prepnúť na prehľad linky
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => onSelectStation(2)}
                className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#F59E0B]/20 hover:bg-[#F59E0B]/30 border border-[#F59E0B]/50 text-[#FCD34D] font-bold text-[11px] transition-all"
              >
                <Gauge className="w-3.5 h-3.5 text-[#F59E0B]" />
                <span>Detail OP20 (Lis)</span>
              </button>
              <button
                onClick={() => onSelectStation(3)}
                className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#EF4444]/20 hover:bg-[#EF4444]/30 border border-[#EF4444]/50 text-[#FCA5A5] font-bold text-[11px] transition-all"
              >
                <Crosshair className="w-3.5 h-3.5 text-[#EF4444]" />
                <span>Detail OP30 (Cognex)</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Visual Display Area */}
      {!isDetailView ? (
        // ====================================================================
        // VIEW 1: FULL 10-STATION HORIZONTAL FLOW DIAGRAM (IMAGE 1 STYLE)
        // High-definition technical vector illustration of all 10 operations!
        // ====================================================================
        <div className="p-4 sm:p-6 overflow-x-auto">
          {/* Infeed Header */}
          <div className="flex items-center justify-between mb-3 text-xs text-[#94A3B8]">
            <div className="flex items-center gap-2 font-mono">
              <span className="w-2 h-2 rounded-full bg-[#38BDF8]" />
              <span>VSTUP: Odlitok skrine z predchádzajúceho procesu</span>
            </div>
            <div className="flex items-center gap-2 font-mono">
              <span>VÝSTUP: Dokončený e-Drive pohon na EOL test</span>
              <span className="w-2 h-2 rounded-full bg-[#10B981]" />
            </div>
          </div>

          {/* 10 Stations Grid / Pipeline */}
          <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-3 min-w-[980px]">
            {LINE_STATIONS.map((st) => {
              const isStResolved = resolvedStations.has(st.id);
              const isStAlarm = st.id === 3 && isAlarm && !isStResolved;
              const isStWarning = st.id === 2 && !isStResolved;

              return (
                <div
                  key={st.id}
                  onClick={() => onSelectStation(st.id)}
                  className={`group relative rounded-2xl p-3 border transition-all duration-300 cursor-pointer flex flex-col justify-between h-[340px] select-none ${
                    isStAlarm
                      ? 'bg-gradient-to-b from-[#1C0E14] to-[#0A0710] border-[#EF4444] shadow-[0_0_24px_rgba(239,68,68,0.25)] ring-2 ring-[#EF4444]/50 hover:scale-[1.02]'
                      : isStWarning
                      ? 'bg-gradient-to-b from-[#1C160E] to-[#0A0D18] border-[#F59E0B] shadow-[0_0_20px_rgba(245,158,11,0.2)] hover:scale-[1.02]'
                      : 'bg-gradient-to-b from-[#0D1527] to-[#070B16] border-[#1E293B] hover:border-[#38BDF8]/60 hover:shadow-[0_0_20px_rgba(56,189,248,0.15)] hover:scale-[1.02]'
                  }`}
                >
                  {/* Top: Station Number Badge & Tooling Header */}
                  <div>
                    <div className="flex items-center justify-between">
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center font-mono font-extrabold text-xs text-white shadow-md border ${
                        isStAlarm 
                          ? 'bg-[#EF4444] border-white/40 ring-2 ring-[#EF4444]/40' 
                          : isStWarning 
                          ? 'bg-[#F59E0B] border-white/40' 
                          : isStResolved
                          ? 'bg-[#10B981] border-white/30 text-white'
                          : 'bg-[#1E293B] border-white/20 text-[#38BDF8]'
                      }`}>
                        {st.id < 10 ? `0${st.id}` : st.id}
                      </div>

                      <span className={`text-[9.5px] font-mono px-2 py-0.5 rounded-full font-bold ${
                        isStAlarm 
                          ? 'bg-[#EF4444]/20 text-[#EF4444] border border-[#EF4444]/40 animate-pulse' 
                          : isStWarning 
                          ? 'bg-[#F59E0B]/20 text-[#F59E0B] border border-[#F59E0B]/40' 
                          : isStResolved
                          ? 'bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/30 font-bold'
                          : 'bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/30'
                      }`}>
                        {isStAlarm ? 'ALARM' : isStWarning ? 'POZOR' : isStResolved ? '✓ OK' : 'OK'}
                      </span>
                    </div>

                    <div className="mt-2">
                      <div className="text-[10px] font-mono uppercase text-[#94A3B8] font-semibold tracking-wider">
                        OP{st.id * 10}
                      </div>
                      <h4 className="text-xs font-bold text-white line-clamp-2 mt-0.5 leading-snug">
                        {st.name}
                      </h4>
                    </div>
                  </div>

                  {/* Center: Detailed Technical Industrial Graphic */}
                  <div className="my-auto py-2 flex items-center justify-center relative">
                    <div className="w-full h-32 flex items-center justify-center">
                      {st.id === 1 && (
                        // Robot Arm Loading Graphic
                        <svg viewBox="0 0 100 100" className="w-24 h-24">
                          <rect x="25" y="80" width="50" height="12" rx="3" fill="#1E293B" stroke="#475569" strokeWidth="1.5" />
                          <circle cx="50" cy="74" r="10" fill="#F59E0B" stroke="#B45309" strokeWidth="1.5" />
                          <path d="M 50 74 L 38 42 L 58 24" fill="none" stroke="#F59E0B" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
                          <circle cx="38" cy="42" r="5" fill="#1E293B" stroke="#B45309" strokeWidth="1.5" />
                          <circle cx="58" cy="24" r="4" fill="#1E293B" stroke="#B45309" strokeWidth="1.5" />
                          <path d="M 54 22 L 72 20 M 56 26 L 74 30" stroke="#94A3B8" strokeWidth="3" strokeLinecap="round" />
                          <rect x="68" y="16" width="22" height="18" rx="2" fill="#64748B" stroke="#94A3B8" strokeWidth="1" />
                        </svg>
                      )}

                      {st.id === 2 && (
                        // Hydraulic Press Ram inserting motor (POZOR)
                        <svg viewBox="0 0 100 100" className="w-24 h-24">
                          <rect x="15" y="10" width="70" height="8" rx="2" fill="#1E293B" stroke="#F59E0B" strokeWidth="1.5" />
                          <rect x="20" y="18" width="6" height="66" fill="#1E293B" />
                          <rect x="74" y="18" width="6" height="66" fill="#1E293B" />
                          <rect x="42" y="18" width="16" height="24" rx="2" fill="#334155" stroke="#64748B" strokeWidth="1" />
                          <rect x="46" y="42" width="8" height="26" fill="#E2E8F0" stroke="#94A3B8" strokeWidth="1" />
                          <rect x="36" y="68" width="28" height="6" rx="1" fill="#F59E0B" />
                          <rect x="32" y="75" width="36" height="16" rx="2" fill="#64748B" stroke="#CBD5E1" strokeWidth="1" />
                        </svg>
                      )}

                      {st.id === 3 && (
                        // Cognex In-Sight Vision Camera (ALARM)
                        <svg viewBox="0 0 100 100" className="w-24 h-24">
                          <rect x="12" y="8" width="76" height="84" rx="4" fill="none" stroke="#EF4444" strokeWidth="2" strokeDasharray="6 3" className="animate-pulse" />
                          <rect x="36" y="14" width="28" height="22" rx="3" fill="#0F172A" stroke="#EF4444" strokeWidth="1.5" />
                          <rect x="38" y="18" width="24" height="4" fill="#FACC15" />
                          <rect x="42" y="36" width="16" height="14" rx="2" fill="#1E293B" stroke="#64748B" strokeWidth="1" />
                          <circle cx="50" cy="50" r="7" fill="#38BDF8" opacity="0.8" />
                          <circle cx="50" cy="50" r="10" fill="none" stroke="#EF4444" strokeWidth="2.5" className="animate-ping" style={{ transformOrigin: '50px 50px' }} />
                          <polygon points="50,52 24,80 76,80" fill="#EF4444" opacity="0.25" />
                          <rect x="30" y="76" width="40" height="14" rx="2" fill="#475569" stroke="#94A3B8" strokeWidth="1" />
                          <circle cx="50" cy="83" r="5" fill="#C26330" />
                        </svg>
                      )}

                      {(st.id === 4 || st.id === 5) && (
                        // Screwdriver Spindles
                        <svg viewBox="0 0 100 100" className="w-24 h-24">
                          <rect x="25" y="10" width="50" height="8" rx="2" fill="#1E293B" stroke="#475569" strokeWidth="1" />
                          <rect x="42" y="18" width="16" height="28" rx="2" fill="#1E293B" stroke="#38BDF8" strokeWidth="1.2" />
                          <line x1="50" y1="46" x2="50" y2="74" stroke="#E2E8F0" strokeWidth="3" strokeLinecap="round" />
                          <polygon points="46,74 54,74 50,80" fill="#94A3B8" />
                          <rect x="30" y="78" width="40" height="14" rx="2" fill="#475569" stroke="#94A3B8" strokeWidth="1" />
                          {st.id === 5 && (
                            <rect x="70" y="32" width="18" height="14" rx="2" fill="#090D16" stroke="#10B981" strokeWidth="1" />
                          )}
                        </svg>
                      )}

                      {st.id === 6 && (
                        // 90° Rotator Cradle
                        <svg viewBox="0 0 100 100" className="w-24 h-24">
                          <rect x="20" y="78" width="60" height="8" fill="#1E293B" stroke="#475569" strokeWidth="1" />
                          <circle cx="50" cy="50" r="28" fill="none" stroke="#94A3B8" strokeWidth="4" />
                          <circle cx="50" cy="50" r="22" fill="none" stroke="#38BDF8" strokeWidth="1.5" strokeDasharray="8 4" />
                          <path d="M 74 50 A 24 24 0 0 0 50 26" fill="none" stroke="#10B981" strokeWidth="2.5" />
                          <rect x="40" y="40" width="20" height="20" rx="2" fill="#475569" stroke="#E2E8F0" strokeWidth="1" transform="rotate(45 50 50)" />
                        </svg>
                      )}

                      {st.id === 7 && (
                        // Inverter Insertion Unit
                        <svg viewBox="0 0 100 100" className="w-24 h-24">
                          <rect x="20" y="10" width="60" height="8" fill="#1E293B" stroke="#475569" strokeWidth="1" />
                          <rect x="46" y="18" width="8" height="30" fill="#E2E8F0" />
                          <rect x="34" y="48" width="32" height="18" rx="2" fill="#E2E8F0" stroke="#38BDF8" strokeWidth="1.5" />
                          <rect x="40" y="66" width="6" height="8" fill="#F59E0B" />
                          <rect x="54" y="66" width="6" height="8" fill="#F59E0B" />
                          <rect x="26" y="76" width="48" height="14" rx="2" fill="#475569" stroke="#94A3B8" strokeWidth="1" />
                        </svg>
                      )}

                      {st.id === 8 && (
                        // 4-Spindle Tightening Unit
                        <svg viewBox="0 0 100 100" className="w-24 h-24">
                          <rect x="25" y="16" width="50" height="14" rx="2" fill="#1E293B" stroke="#38BDF8" strokeWidth="1.2" />
                          <line x1="33" y1="30" x2="33" y2="72" stroke="#E2E8F0" strokeWidth="2.5" />
                          <line x1="44" y1="30" x2="44" y2="72" stroke="#E2E8F0" strokeWidth="2.5" />
                          <line x1="56" y1="30" x2="56" y2="72" stroke="#E2E8F0" strokeWidth="2.5" />
                          <line x1="67" y1="30" x2="67" y2="72" stroke="#E2E8F0" strokeWidth="2.5" />
                          <rect x="24" y="74" width="52" height="16" rx="2" fill="#475569" stroke="#94A3B8" strokeWidth="1" />
                        </svg>
                      )}

                      {st.id === 9 && (
                        // Ateq Leak Tester Chamber
                        <svg viewBox="0 0 100 100" className="w-24 h-24">
                          <rect x="18" y="16" width="64" height="68" rx="3" fill="#0F172A" stroke="#38BDF8" strokeWidth="1.5" />
                          <rect x="24" y="22" width="52" height="42" fill="#38BDF8" opacity="0.12" stroke="#38BDF8" strokeWidth="0.8" />
                          <rect x="42" y="24" width="16" height="24" fill="#E2E8F0" />
                          <circle cx="50" cy="32" r="8" fill="#1E293B" stroke="#10B981" strokeWidth="1.2" />
                          <line x1="50" y1="32" x2="54" y2="28" stroke="#10B981" strokeWidth="1.5" />
                          <rect x="30" y="52" width="40" height="24" rx="2" fill="#475569" stroke="#94A3B8" strokeWidth="1" />
                        </svg>
                      )}

                      {st.id === 10 && (
                        // EOL Transfer Robot
                        <svg viewBox="0 0 100 100" className="w-24 h-24">
                          <rect x="25" y="80" width="50" height="12" rx="3" fill="#1E293B" stroke="#475569" strokeWidth="1.5" />
                          <circle cx="50" cy="74" r="10" fill="#F59E0B" stroke="#B45309" strokeWidth="1.5" />
                          <path d="M 50 74 L 62 44 L 46 22" fill="none" stroke="#F59E0B" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
                          <circle cx="62" cy="44" r="5" fill="#1E293B" />
                          <rect x="18" y="20" width="26" height="22" rx="2" fill="#64748B" stroke="#10B981" strokeWidth="1.5" />
                          <path d="M 28 42 L 28 70" stroke="#10B981" strokeWidth="2" strokeDasharray="3 3" />
                        </svg>
                      )}
                    </div>
                  </div>

                  {/* Bottom: Conveyor Segment & Metric Card */}
                  <div className="pt-2 border-t border-white/10">
                    <div className="flex items-center justify-between text-[10px] font-mono text-[#94A3B8]">
                      <span>Takt:</span>
                      <b className="text-white">{st.telemetry.cycle_time} s</b>
                    </div>
                    <div className="text-[10px] text-[#6B7280] truncate mt-0.5">
                      {st.critical_part}
                    </div>

                    <button 
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectStation(st.id);
                      }}
                      className={`w-full mt-2 py-1.5 rounded-lg text-[10.5px] font-bold text-center transition-all flex items-center justify-center gap-1 ${
                        isStAlarm 
                          ? 'bg-[#EF4444] text-white hover:bg-[#DC2626] shadow-lg animate-pulse' 
                          : isStWarning
                          ? 'bg-[#F59E0B] text-[#090D16] hover:bg-[#D97706] shadow-md font-extrabold'
                          : 'bg-white/10 hover:bg-[#38BDF8] hover:text-[#090D16] text-[#E2E8F0]'
                      }`}
                    >
                      {isStAlarm ? (
                        <>
                          <Crosshair className="w-3.5 h-3.5" />
                          <span>Riešiť v 3D/X-Ray</span>
                        </>
                      ) : isStWarning ? (
                        <>
                          <Gauge className="w-3.5 h-3.5" />
                          <span>Otvoriť X-Ray (Lis)</span>
                        </>
                      ) : (
                        <span>Otvoriť X-Ray</span>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Continuous Conveyor Line Visual Representation at Base */}
          <div className="mt-4 pt-3 border-t border-[#1E293B] flex items-center justify-between text-[11px] text-[#6B7280]">
            <div className="flex items-center gap-2">
              <span className="w-3 h-1 bg-[#38BDF8] rounded-full animate-pulse" />
              <span>Dvojdrážkový pásový dopravník s RFID trackingom paliet • Rýchlosť posuvu: <b>14 m/min</b></span>
            </div>
            <div className="text-[#38BDF8] font-mono">
              Linka L01 • Magna Powertrain Ilava
            </div>
          </div>
        </div>
      ) : (
        // ====================================================================
        // VIEW 2: ULTRA-DETAILED 2.5D TECHNICAL X-RAY OF SELECTED STATION
        // Dynamic Cinematic Vector Zoom & Pan on Hover of AI Copilot Steps!
        // ====================================================================
        <div className="p-4 sm:p-6 lg:p-8 flex flex-col items-center">
          
          {/* Machine Header Banner */}
          <div className="w-full flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-4 border-b border-[#1E293B] mb-6">
            <div>
              <div className="flex items-center gap-2">
                <span className={`px-2.5 py-0.5 rounded-md font-mono font-bold text-xs uppercase tracking-wider border ${
                  isStation3 
                    ? 'bg-[#EF4444]/20 border-[#EF4444]/40 text-[#EF4444]' 
                    : 'bg-[#F59E0B]/20 border-[#F59E0B]/40 text-[#F59E0B]'
                }`}>
                  {isStation3 ? 'STANICA OP30 • KAMEROVÁ KONTROLA' : 'STANICA OP20 • NALISOVANIE EL. MOTORA'}
                </span>
                <span className="px-2.5 py-0.5 rounded-md bg-[#38BDF8]/20 border border-[#38BDF8]/40 text-[#38BDF8] font-mono font-bold text-xs">
                  {isStation3 ? 'COGNEX IN-SIGHT 8402P' : 'KISTLER 50 kN / TOX PRESSOTECHNIK'}
                </span>
              </div>
              <h3 className="text-xl font-bold text-white mt-1">
                {isStation3 
                  ? 'Technický X-Ray Rez Stanice & 5-Krokový Akčný Plán AI Copilot' 
                  : 'Technický X-Ray Rez Servolisu & TPM Kalibračný Plán'}
              </h3>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-[#94A3B8]">Zameraný komponent:</span>
              {effectiveStep !== null ? (
                <button
                  type="button"
                  onClick={() => onSelectStep(-1)}
                  className="px-3 py-1 rounded-xl bg-[#090D16] border border-[#38BDF8] text-[#38BDF8] shadow-[0_0_15px_rgba(56,189,248,0.35)] font-mono font-bold text-xs hover:bg-[#38BDF8]/15 transition-all flex items-center gap-1.5 active:scale-95 cursor-pointer group"
                  title="Kliknite pre oddialenie na celú stanicu"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] animate-pulse" />
                  <span>Krok {effectiveStep + 1} (Zaostrené 🔍)</span>
                  <span className="text-[10px] bg-[#38BDF8] text-[#090D16] px-1.5 py-0.2 rounded-full font-bold ml-1 group-hover:bg-white">✕ Oddialiť</span>
                </button>
              ) : (
                <span className="px-3 py-1 rounded-xl bg-[#090D16] border border-[#1E293B] text-[#94A3B8] font-mono font-bold text-xs">
                  Celý stanok (Prehľad 1.0×)
                </span>
              )}
            </div>
          </div>

          {/* Interactive Detailed Engineering Machine Blueprint SVG with Smooth CSS Zoom */}
          <div className="relative w-full max-w-[1080px] bg-[#0A0E1A] rounded-2xl border border-[#1E293B] p-4 sm:p-8 shadow-2xl overflow-hidden">
            
            {/* Background Engineering Tech Grid */}
            <div 
              className="absolute inset-0 opacity-15 pointer-events-none"
              style={{
                backgroundImage: 'linear-gradient(#38BDF8 1px, transparent 1px), linear-gradient(90deg, #38BDF8 1px, transparent 1px)',
                backgroundSize: '32px 32px'
              }}
            />

            {/* SVG Engineering Cutaway with Smooth Hardware-Accelerated Camera Zoom */}
            <div className="w-full h-auto overflow-hidden rounded-xl">
              <svg viewBox="0 0 900 520" className="w-full h-auto drop-shadow-2xl select-none">
                <defs>
                  {/* Glow filters */}
                  <filter id="red-glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="6" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                  </filter>
                  <filter id="amber-glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="5" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                  </filter>
                  <filter id="cyan-glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="5" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                  </filter>
                  {/* Linear Gradients */}
                  <linearGradient id="alum-frame" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#475569" />
                    <stop offset="50%" stopColor="#94A3B8" />
                    <stop offset="100%" stopColor="#334155" />
                  </linearGradient>
                  <linearGradient id="laser-beam" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#EF4444" stopOpacity="0.85" />
                    <stop offset="100%" stopColor="#EF4444" stopOpacity="0.12" />
                  </linearGradient>
                </defs>

                {/* DYNAMIC ZOOM GROUP — Animated smoothly on hover of each AI Copilot step! */}
                <g 
                  style={{
                    transform,
                    transformOrigin,
                    transition: 'transform 0.55s cubic-bezier(0.2, 0.8, 0.25, 1)',
                  }}
                >
                  {/* 1. SHOP FLOOR & MOUNTING BASE */}
                  <rect x="40" y="490" width="820" height="12" rx="3" fill="#0F172A" stroke="#334155" strokeWidth="1.5" />
                  <line x1="40" y1="490" x2="860" y2="490" stroke="#38BDF8" strokeWidth="1" strokeDasharray="8 6" opacity="0.6" />

                  {/* Vibration Damped Leveling Machine Feet */}
                  <rect x="90" y="475" width="36" height="16" rx="2" fill="#475569" stroke="#94A3B8" strokeWidth="1" />
                  <rect x="774" y="475" width="36" height="16" rx="2" fill="#475569" stroke="#94A3B8" strokeWidth="1" />
                  <circle cx="108" cy="483" r="4" fill="#E2E8F0" />
                  <circle cx="792" cy="483" r="4" fill="#E2E8F0" />

                  {/* 2. ALUMINUM EXTRUDED STRUCTURE (Rexroth Profile 45x45 / 90x90) */}
                  <rect x="96" y="70" width="24" height="405" fill="url(#alum-frame)" stroke="#1E293B" strokeWidth="1.5" />
                  <line x1="108" y1="70" x2="108" y2="475" stroke="#1E293B" strokeWidth="2" />
                  <rect x="780" y="70" width="24" height="405" fill="url(#alum-frame)" stroke="#1E293B" strokeWidth="1.5" />
                  <line x1="792" y1="70" x2="792" y2="475" stroke="#1E293B" strokeWidth="2" />
                  <rect x="96" y="56" width="708" height="24" fill="url(#alum-frame)" stroke="#1E293B" strokeWidth="1.5" />
                  <line x1="96" y1="68" x2="804" y2="68" stroke="#1E293B" strokeWidth="2" />
                  <rect x="96" y="320" width="708" height="18" fill="url(#alum-frame)" stroke="#1E293B" strokeWidth="1" />

                  {/* Corner Gusset Brackets */}
                  <polygon points="120,80 150,80 120,110" fill="#64748B" stroke="#334155" strokeWidth="1" />
                  <polygon points="780,80 750,80 780,110" fill="#64748B" stroke="#334155" strokeWidth="1" />

                  {/* Lexan Safety Enclosure Panels */}
                  <rect x="124" y="84" width="652" height="232" rx="4" fill="#0F172A" opacity="0.35" stroke="#38BDF8" strokeWidth="1" strokeDasharray="6 4" />
                  <text x="750" y="105" fill="#94A3B8" fontSize="10" fontFamily="monospace" textAnchor="end">LEXAN® ENCLOSURE • EN ISO 14120</text>

                  {/* 3. ROOF ANDON TOWER LIGHT */}
                  <g transform="translate(450, 20)">
                    <rect x="-4" y="16" width="8" height="20" fill="#334155" />
                    {isStation3 ? (
                      <rect x="-10" y="4" width="20" height="14" rx="2" fill="#EF4444" filter="url(#red-glow)" className="animate-pulse" />
                    ) : (
                      <rect x="-10" y="-8" width="20" height="12" rx="2" fill="#F59E0B" filter="url(#amber-glow)" className="animate-pulse" />
                    )}
                    <rect x="-10" y="4" width="20" height="14" rx="2" fill={isStation3 ? '#EF4444' : '#EF4444'} opacity={isStation3 ? 1 : 0.2} />
                    <rect x="-10" y="-8" width="20" height="12" rx="2" fill="#F59E0B" opacity={isStation2 ? 1 : 0.2} />
                    <rect x="-10" y="-20" width="20" height="12" rx="2" fill="#10B981" opacity="0.2" />
                    <polygon points="0,-24 -12,-20 12,-20" fill="#1E293B" />
                    <text x="22" y="15" fill={isStation3 ? '#EF4444' : '#F59E0B'} fontSize="11" fontWeight="bold" fontFamily="monospace">
                      {isStation3 ? 'ANDON: CRITICAL STOP' : 'ANDON: SILOVÝ LIMIT (POZOR)'}
                    </text>
                  </g>

                  {/* 4. CONVEYOR ASSEMBLY & CARRIER PALLET */}
                  <rect x="50" y="380" width="800" height="16" rx="2" fill="#1E293B" stroke="#475569" strokeWidth="1.5" />
                  <rect x="50" y="396" width="800" height="8" fill="#090D16" />
                  {[120, 180, 240, 300, 360, 420, 480, 540, 600, 660, 720, 780].map((rx) => (
                    <circle key={rx} cx={rx} cy="388" r="5" fill="#94A3B8" stroke="#334155" strokeWidth="1" />
                  ))}
                  <rect x="50" y="374" width="800" height="4" fill="#38BDF8" opacity="0.9" filter="url(#cyan-glow)" />

                  {/* Pneumatic Stop Cylinder */}
                  <rect x="442" y="405" width="16" height="34" rx="2" fill="#334155" stroke="#64748B" strokeWidth="1" />
                  <line x1="450" y1="390" x2="450" y2="405" stroke="#E2E8F0" strokeWidth="4" />

                  {/* CARRIER PALLET */}
                  <g transform="translate(340, 350)">
                    <rect x="0" y="10" width="220" height="16" rx="3" fill="#1E293B" stroke="#3B82F6" strokeWidth="2" />
                    <circle cx="30" cy="18" r="6" fill="#F59E0B" />
                    <text x="42" y="21" fill="#94A3B8" fontSize="8" fontFamily="monospace">RFID #9042</text>
                    <rect x="25" y="0" width="170" height="10" rx="1" fill="#475569" stroke="#94A3B8" strokeWidth="1" />
                  </g>

                  {/* MAGNA E-DRIVE CAST ALUMINUM HOUSING ON PALLET */}
                  <g transform="translate(365, 270)">
                    <rect x="0" y="10" width="170" height="70" rx="4" fill="#64748B" stroke="#CBD5E1" strokeWidth="2" />
                    {[18, 28, 38, 48, 58].map((fy) => (
                      <line key={fy} x1="-6" y1={fy} x2="0" y2={fy} stroke="#94A3B8" strokeWidth="2.5" />
                    ))}
                    {[18, 28, 38, 48, 58].map((fy) => (
                      <line key={fy} x1="170" y1={fy} x2="176" y2={fy} stroke="#94A3B8" strokeWidth="2.5" />
                    ))}
                    <rect x="20" y="20" width="130" height="50" rx="3" fill="#1E293B" stroke="#334155" strokeWidth="1.5" />
                    <rect x="30" y="25" width="22" height="40" rx="2" fill="#C26330" stroke="#EA580C" strokeWidth="1" />
                    <rect x="118" y="25" width="22" height="40" rx="2" fill="#C26330" stroke="#EA580C" strokeWidth="1" />
                    <circle cx="85" cy="45" r="14" fill="#334155" stroke="#94A3B8" strokeWidth="1.5" />
                    <circle cx="85" cy="45" r="7" fill="#090D16" />
                    <text x="85" y="78" fill="#E2E8F0" fontSize="9" fontFamily="monospace" textAnchor="middle" fontWeight="bold">MAGNA e-DRIVE L01</text>
                  </g>

                  {/* ============================================================ */}
                  {/* SPECIFIC MACHINE TOOLING: OP30 (COGNEX) vs OP20 (SERVO LIS)  */}
                  {/* ============================================================ */}

                  {isStation3 ? (
                    // ------------------------------------------------------------
                    // OP30 TOOLING: COGNEX VISION CAMERA & OPTICAL SYSTEM
                    // ------------------------------------------------------------
                    <>
                      {/* Overhead Heavy Gantry Bracket */}
                      <rect x="400" y="80" width="100" height="20" rx="2" fill="#334155" stroke="#64748B" strokeWidth="1.5" />
                      <rect x="440" y="100" width="20" height="30" fill="#1E293B" stroke="#475569" strokeWidth="1" />

                      {/* COGNEX IN-SIGHT 8402P MAIN HOUSING */}
                      <g transform="translate(415, 130)">
                        <rect x="0" y="0" width="70" height="55" rx="4" fill="#0F172A" stroke="#EF4444" strokeWidth="2" filter="url(#red-glow)" />
                        <rect x="0" y="10" width="70" height="8" fill="#FACC15" />
                        <text x="35" y="16.5" fill="#090D16" fontSize="7" fontWeight="bold" fontFamily="sans-serif" textAnchor="middle">COGNEX</text>
                        <circle cx="12" cy="28" r="2.5" fill="#10B981" />
                        <circle cx="20" cy="28" r="2.5" fill="#38BDF8" />
                        <circle cx="28" cy="28" r="2.5" fill="#EF4444" className="animate-ping" style={{ transformOrigin: '28px 28px' }} />
                        <text x="36" y="31" fill="#EF4444" fontSize="7" fontFamily="monospace" fontWeight="bold">ERR: ST-038</text>
                        <text x="35" y="46" fill="#94A3B8" fontSize="7.5" fontFamily="monospace" textAnchor="middle">In-Sight 8402P</text>
                      </g>

                      {/* OPTICAL LENS BARREL */}
                      <g transform="translate(433, 185)">
                        <rect x="0" y="0" width="34" height="30" rx="2" fill="#1E293B" stroke="#64748B" strokeWidth="1.5" />
                        <line x1="0" y1="8" x2="34" y2="8" stroke="#94A3B8" strokeWidth="1.5" strokeDasharray="3 2" />
                        <line x1="0" y1="18" x2="34" y2="18" stroke="#94A3B8" strokeWidth="1.5" strokeDasharray="3 2" />
                        <ellipse cx="17" cy="30" rx="14" ry="4" fill="#38BDF8" opacity="0.9" />
                      </g>

                      {/* CIRCULAR LED ILLUMINATOR RING */}
                      <g transform="translate(425, 212)">
                        <ellipse cx="25" cy="5" rx="28" ry="8" fill="none" stroke="#EF4444" strokeWidth="4" filter="url(#red-glow)" className="animate-pulse" />
                        <ellipse cx="25" cy="5" rx="20" ry="5" fill="none" stroke="#DC2626" strokeWidth="2" />
                      </g>

                      {/* VOLUMETRIC SCANNING CONE BEAM */}
                      <polygon points="450,220 375,290 525,290" fill="url(#laser-beam)" />
                      <ellipse cx="450" cy="290" rx="75" ry="14" fill="#EF4444" opacity="0.3" filter="url(#red-glow)" />

                      {/* M12 CONNECTOR X2 & CABLE ROUTING */}
                      <g transform="translate(485, 142)">
                        <rect x="0" y="0" width="18" height="14" rx="2" fill="#F59E0B" stroke="#D97706" strokeWidth="1.2" />
                        <rect x="-4" y="3" width="4" height="8" fill="#FACC15" />
                        <path d="M 18 7 Q 60 7 70 -30 T 120 -50" fill="none" stroke="#EA580C" strokeWidth="5" strokeLinecap="round" />
                        <text x="24" y="24" fill="#F59E0B" fontSize="8" fontFamily="monospace" fontWeight="bold">X2 (24V DC / ETH)</text>
                      </g>

                      {/* ELECTRICAL SAFETY CABINET (LOTO) */}
                      <g transform="translate(130, 160)">
                        <rect x="0" y="0" width="75" height="120" rx="4" fill="#1E293B" stroke="#475569" strokeWidth="2" />
                        <rect x="4" y="4" width="67" height="112" rx="2" fill="#0F172A" stroke="#334155" strokeWidth="1" />
                        <rect x="-2" y="15" width="4" height="10" fill="#94A3B8" />
                        <rect x="-2" y="95" width="4" height="10" fill="#94A3B8" />
                        <polygon points="37,20 27,36 47,36" fill="#FACC15" stroke="#090D16" strokeWidth="1" />
                        <text x="37" y="34" fill="#090D16" fontSize="10" fontWeight="bold" textAnchor="middle">⚡</text>
                        <circle cx="37.5" cy="65" r="18" fill="#FACC15" stroke="#B45309" strokeWidth="1.5" />
                        <rect x="22" y="60" width="31" height="10" rx="3" fill="#EF4444" stroke="#DC2626" strokeWidth="1.5" filter="url(#red-glow)" />
                        <circle cx="37.5" cy="65" r="4" fill="#090D16" />
                        <circle cx="48" cy="65" r="2.5" fill="#090D16" />
                        <text x="37.5" y="98" fill="#EF4444" fontSize="8.5" fontFamily="monospace" textAnchor="middle" fontWeight="bold">LOTO: QF3 (24V)</text>
                      </g>
                    </>
                  ) : (
                    // ------------------------------------------------------------
                    // OP20 TOOLING: KISTLER 50kN / TOX SERVO-HYDRAULIC PRESS
                    // ------------------------------------------------------------
                    <>
                      {/* Heavy C-Frame Upper Press Yoke */}
                      <rect x="360" y="80" width="180" height="28" rx="4" fill="#1E293B" stroke="#F59E0B" strokeWidth="1.8" filter="url(#amber-glow)" />
                      <text x="450" y="98" fill="#F59E0B" fontSize="9" fontWeight="bold" fontFamily="monospace" textAnchor="middle">TOX PRESSOTECHNIK 120 kN</text>

                      {/* Servo Actuator Cylinder Body */}
                      <rect x="415" y="108" width="70" height="50" rx="3" fill="#334155" stroke="#64748B" strokeWidth="1.5" />
                      {/* High Pressure Hydraulic Fluid Hose */}
                      <path d="M 485 125 Q 530 120 560 90 T 600 65" fill="none" stroke="#F59E0B" strokeWidth="4" strokeLinecap="round" />

                      {/* PIEZOELECTRIC QUARTZ FORCE SENSOR RING (KISTLER 9211B) */}
                      <g transform="translate(425, 160)">
                        <rect x="0" y="0" width="50" height="18" rx="2" fill="#F59E0B" stroke="#D97706" strokeWidth="1.5" filter="url(#amber-glow)" />
                        <text x="25" y="12" fill="#090D16" fontSize="7.5" fontWeight="bold" fontFamily="monospace" textAnchor="middle">KISTLER 50kN</text>
                        {/* Coaxial BNC signal cable */}
                        <path d="M 50 9 Q 80 12 110 -10" fill="none" stroke="#38BDF8" strokeWidth="2.5" />
                      </g>

                      {/* POLISHED CHROME PRESS RAM / QUILL SPINDLE */}
                      <rect x="438" y="180" width="24" height="65" fill="#E2E8F0" stroke="#94A3B8" strokeWidth="1.5" />
                      <line x1="442" y1="180" x2="442" y2="245" stroke="#FFFFFF" strokeWidth="2" /> {/* Chrome reflection */}

                      {/* HARDENED PRESS PUNCH TOOL HEAD (Ø 42.0 mm) */}
                      <g transform="translate(420, 245)">
                        <polygon points="10,0 50,0 55,20 5,20" fill="#475569" stroke="#E2E8F0" strokeWidth="1.2" />
                        <rect x="12" y="20" width="36" height="15" rx="1" fill="#F59E0B" stroke="#B45309" strokeWidth="1.2" />
                        <text x="30" y="31" fill="#090D16" fontSize="7.5" fontWeight="extrabold" fontFamily="monospace" textAnchor="middle">TŘŇ Ø42</text>
                      </g>

                      {/* KEYENCE LASER DISPLACEMENT GAUGE (Stroke Measurement) */}
                      <g transform="translate(510, 210)">
                        <rect x="0" y="0" width="32" height="42" rx="2" fill="#090D16" stroke="#38BDF8" strokeWidth="1.2" />
                        <circle cx="16" cy="12" r="3" fill="#10B981" />
                        <text x="16" y="28" fill="#38BDF8" fontSize="6.5" fontFamily="monospace" textAnchor="middle">LK-G</text>
                        {/* Red Laser Measuring Beam */}
                        <line x1="0" y1="36" x2="-35" y2="40" stroke="#EF4444" strokeWidth="1.5" strokeDasharray="3 2" filter="url(#red-glow)" />
                      </g>

                      {/* STATOR CORE INSERTION PRESSURE EFFECT */}
                      <rect x="400" y="278" width="100" height="24" rx="2" fill="#F59E0B" opacity="0.25" filter="url(#amber-glow)" />
                      <text x="450" y="294" fill="#F59E0B" fontSize="9" fontWeight="bold" fontFamily="monospace" textAnchor="middle">F = 38.4 kN (LIMIT 45 kN)</text>

                      {/* KISTLER MAXYMOS HMI TOUCH SCREEN (Right Column) */}
                      <g transform="translate(685, 140)">
                        <rect x="0" y="0" width="90" height="95" rx="4" fill="#0F172A" stroke="#38BDF8" strokeWidth="1.8" />
                        <rect x="5" y="5" width="80" height="15" fill="#1E293B" />
                        <text x="45" y="16" fill="#38BDF8" fontSize="7" fontWeight="bold" fontFamily="monospace" textAnchor="middle">maXYmos TL 5877</text>
                        {/* F/s Force-Displacement Real-Time Curve */}
                        <rect x="8" y="24" width="74" height="62" fill="#060913" stroke="#334155" strokeWidth="1" />
                        {/* Tolerance Envelope Box */}
                        <rect x="42" y="35" width="30" height="25" fill="#10B981" opacity="0.15" stroke="#10B981" strokeWidth="1" strokeDasharray="2 2" />
                        {/* Force Curve Path */}
                        <path d="M 12 80 Q 25 78 40 58 T 65 42" fill="none" stroke="#F59E0B" strokeWidth="2.5" filter="url(#amber-glow)" />
                        <circle cx="65" cy="42" r="3" fill="#F59E0B" />
                        <text x="45" y="82" fill="#F59E0B" fontSize="6.5" fontFamily="monospace" textAnchor="middle">POZOR: +12% sily</text>
                      </g>

                      {/* LOTO SAFETY CABINET QF2 (Left Side) */}
                      <g transform="translate(130, 160)">
                        <rect x="0" y="0" width="75" height="120" rx="4" fill="#1E293B" stroke="#475569" strokeWidth="2" />
                        <rect x="4" y="4" width="67" height="112" rx="2" fill="#0F172A" stroke="#334155" strokeWidth="1" />
                        <polygon points="37,20 27,36 47,36" fill="#FACC15" stroke="#090D16" strokeWidth="1" />
                        <text x="37" y="34" fill="#090D16" fontSize="10" fontWeight="bold" textAnchor="middle">⚡</text>
                        <circle cx="37.5" cy="65" r="18" fill="#FACC15" stroke="#B45309" strokeWidth="1.5" />
                        <rect x="22" y="60" width="31" height="10" rx="3" fill="#F59E0B" stroke="#D97706" strokeWidth="1.5" filter="url(#amber-glow)" />
                        <circle cx="37.5" cy="65" r="4" fill="#090D16" />
                        <text x="37.5" y="98" fill="#F59E0B" fontSize="8.5" fontFamily="monospace" textAnchor="middle" fontWeight="bold">LOTO: QF2 (LIS)</text>
                      </g>
                    </>
                  )}

                  {/* ============================================================ */}
                  {/* INTERACTIVE 5 PINS (FOR OP30 OR OP20)                        */}
                  {/* ============================================================ */}

                  {isStation3 ? (
                    // ------------------------------------------------------------
                    // OP30 COGNEX PINS (1 TO 5)
                    // ------------------------------------------------------------
                    <>
                      {/* PIN 1: LOTO Switch QF3 (x: 167, y: 225) */}
                      <g 
                        onClick={() => onSelectStep(0)}
                        onMouseEnter={() => setInternalHoverStep(0)}
                        onMouseLeave={() => setInternalHoverStep(null)}
                        className="cursor-pointer group"
                        transform="translate(167, 225)"
                      >
                        <line x1="0" y1="0" x2="35" y2="-35" stroke="#EF4444" strokeWidth="1.5" strokeDasharray="3 2" />
                        <circle cx="0" cy="0" r="14" fill="#EF4444" opacity="0.3" className="animate-ping" />
                        <circle cx="0" cy="0" r="11" fill="#EF4444" stroke="#FFFFFF" strokeWidth="2" filter="url(#red-glow)" />
                        <text x="0" y="4" fill="#FFFFFF" fontSize="11" fontWeight="extrabold" fontFamily="sans-serif" textAnchor="middle">1</text>
                        <g transform="translate(40, -55)">
                          <rect x="0" y="0" width="135" height="34" rx="6" fill="#090D16" stroke={effectiveStep === 0 ? '#38BDF8' : '#EF4444'} strokeWidth={effectiveStep === 0 ? 2.5 : 1} filter={effectiveStep === 0 ? 'url(#cyan-glow)' : undefined} />
                          <text x="8" y="14" fill="#FFFFFF" fontSize="9.5" fontWeight="bold">Krok 1: LOTO Istič QF3</text>
                          <text x="8" y="26" fill="#94A3B8" fontSize="8">Odpojenie napájania 24V</text>
                        </g>
                      </g>

                      {/* PIN 2: Cognex Optical Lens & Polarizer (x: 450, y: 200) */}
                      <g 
                        onClick={() => onSelectStep(1)}
                        onMouseEnter={() => setInternalHoverStep(1)}
                        onMouseLeave={() => setInternalHoverStep(null)}
                        className="cursor-pointer group"
                        transform="translate(450, 200)"
                      >
                        <line x1="0" y1="0" x2="-60" y2="-40" stroke="#38BDF8" strokeWidth="1.5" strokeDasharray="3 2" />
                        <circle cx="0" cy="0" r="14" fill="#38BDF8" opacity="0.3" className="animate-ping" />
                        <circle cx="0" cy="0" r="11" fill="#38BDF8" stroke="#FFFFFF" strokeWidth="2" filter="url(#cyan-glow)" />
                        <text x="0" y="4" fill="#FFFFFF" fontSize="11" fontWeight="extrabold" fontFamily="sans-serif" textAnchor="middle">2</text>
                        <g transform="translate(-190, -65)">
                          <rect x="0" y="0" width="125" height="34" rx="6" fill="#090D16" stroke={effectiveStep === 1 ? '#38BDF8' : '#38BDF8'} strokeWidth={effectiveStep === 1 ? 2.5 : 1} filter={effectiveStep === 1 ? 'url(#cyan-glow)' : undefined} />
                          <text x="8" y="14" fill="#FFFFFF" fontSize="9.5" fontWeight="bold">Krok 2: Optika Cognex</text>
                          <text x="8" y="26" fill="#94A3B8" fontSize="8">Čistenie šošovky 8402P</text>
                        </g>
                      </g>

                      {/* PIN 3: Connector X2 & M12 Cable (x: 505, y: 150) */}
                      <g 
                        onClick={() => onSelectStep(2)}
                        onMouseEnter={() => setInternalHoverStep(2)}
                        onMouseLeave={() => setInternalHoverStep(null)}
                        className="cursor-pointer group"
                        transform="translate(505, 150)"
                      >
                        <line x1="0" y1="0" x2="50" y2="-35" stroke="#F59E0B" strokeWidth="1.5" strokeDasharray="3 2" />
                        <circle cx="0" cy="0" r="14" fill="#F59E0B" opacity="0.3" className="animate-ping" />
                        <circle cx="0" cy="0" r="11" fill="#F59E0B" stroke="#FFFFFF" strokeWidth="2" />
                        <text x="0" y="4" fill="#FFFFFF" fontSize="11" fontWeight="extrabold" fontFamily="sans-serif" textAnchor="middle">3</text>
                        <g transform="translate(55, -55)">
                          <rect x="0" y="0" width="125" height="34" rx="6" fill="#090D16" stroke={effectiveStep === 2 ? '#38BDF8' : '#F59E0B'} strokeWidth={effectiveStep === 2 ? 2.5 : 1} filter={effectiveStep === 2 ? 'url(#cyan-glow)' : undefined} />
                          <text x="8" y="14" fill="#FFFFFF" fontSize="9.5" fontWeight="bold">Krok 3: Kábel X2 (M12)</text>
                          <text x="8" y="26" fill="#94A3B8" fontSize="8">Dotiahnutie momentom 0.6Nm</text>
                        </g>
                      </g>

                      {/* PIN 4: Circular LED Illuminator (x: 485, y: 220) */}
                      <g 
                        onClick={() => onSelectStep(3)}
                        onMouseEnter={() => setInternalHoverStep(3)}
                        onMouseLeave={() => setInternalHoverStep(null)}
                        className="cursor-pointer group"
                        transform="translate(485, 220)"
                      >
                        <line x1="0" y1="0" x2="65" y2="20" stroke="#38BDF8" strokeWidth="1.5" strokeDasharray="3 2" />
                        <circle cx="0" cy="0" r="14" fill="#38BDF8" opacity="0.3" className="animate-ping" />
                        <circle cx="0" cy="0" r="11" fill="#38BDF8" stroke="#FFFFFF" strokeWidth="2" />
                        <text x="0" y="4" fill="#FFFFFF" fontSize="11" fontWeight="extrabold" fontFamily="sans-serif" textAnchor="middle">4</text>
                        <g transform="translate(70, 5)">
                          <rect x="0" y="0" width="125" height="34" rx="6" fill="#090D16" stroke={effectiveStep === 3 ? '#38BDF8' : '#38BDF8'} strokeWidth={effectiveStep === 3 ? 2.5 : 1} filter={effectiveStep === 3 ? 'url(#cyan-glow)' : undefined} />
                          <text x="8" y="14" fill="#FFFFFF" fontSize="9.5" fontWeight="bold">Krok 4: LED lúč (&gt;400 lx)</text>
                          <text x="8" y="26" fill="#94A3B8" fontSize="8">Kalibrácia kruhového svetla</text>
                        </g>
                      </g>

                      {/* PIN 5: Calibration Target & Test Bed on Pallet (x: 450, y: 345) */}
                      <g 
                        onClick={() => onSelectStep(4)}
                        onMouseEnter={() => setInternalHoverStep(4)}
                        onMouseLeave={() => setInternalHoverStep(null)}
                        className="cursor-pointer group"
                        transform="translate(450, 345)"
                      >
                        <line x1="0" y1="0" x2="70" y2="40" stroke="#10B981" strokeWidth="1.5" strokeDasharray="3 2" />
                        <circle cx="0" cy="0" r="14" fill="#10B981" opacity="0.3" className="animate-ping" />
                        <circle cx="0" cy="0" r="11" fill="#10B981" stroke="#FFFFFF" strokeWidth="2" />
                        <text x="0" y="4" fill="#FFFFFF" fontSize="11" fontWeight="extrabold" fontFamily="sans-serif" textAnchor="middle">5</text>
                        <g transform="translate(75, 25)">
                          <rect x="0" y="0" width="130" height="34" rx="6" fill="#090D16" stroke={effectiveStep === 4 ? '#38BDF8' : '#10B981'} strokeWidth={effectiveStep === 4 ? 2.5 : 1} filter={effectiveStep === 4 ? 'url(#cyan-glow)' : undefined} />
                          <text x="8" y="14" fill="#FFFFFF" fontSize="9.5" fontWeight="bold">Krok 5: In-Sight Test</text>
                          <text x="8" y="26" fill="#94A3B8" fontSize="8">Overovacia snímka &amp; PLC takt</text>
                        </g>
                      </g>
                    </>
                  ) : (
                    // ------------------------------------------------------------
                    // OP20 SERVO-HYDRAULIC PRESS PINS (1 TO 5)
                    // ------------------------------------------------------------
                    <>
                      {/* PIN 1: LOTO Switch QF2 & Ram Lock Pin (x: 167, y: 225) */}
                      <g 
                        onClick={() => onSelectStep(0)}
                        onMouseEnter={() => setInternalHoverStep(0)}
                        onMouseLeave={() => setInternalHoverStep(null)}
                        className="cursor-pointer group"
                        transform="translate(167, 225)"
                      >
                        <line x1="0" y1="0" x2="35" y2="-35" stroke="#F59E0B" strokeWidth="1.5" strokeDasharray="3 2" />
                        <circle cx="0" cy="0" r="14" fill="#F59E0B" opacity="0.3" className="animate-ping" />
                        <circle cx="0" cy="0" r="11" fill="#F59E0B" stroke="#FFFFFF" strokeWidth="2" filter="url(#amber-glow)" />
                        <text x="0" y="4" fill="#090D16" fontSize="11" fontWeight="extrabold" fontFamily="sans-serif" textAnchor="middle">1</text>
                        <g transform="translate(40, -55)">
                          <rect x="0" y="0" width="135" height="34" rx="6" fill="#090D16" stroke={effectiveStep === 0 ? '#38BDF8' : '#F59E0B'} strokeWidth={effectiveStep === 0 ? 2.5 : 1} filter={effectiveStep === 0 ? 'url(#cyan-glow)' : undefined} />
                          <text x="8" y="14" fill="#FFFFFF" fontSize="9.5" fontWeight="bold">Krok 1: LOTO Istič QF2</text>
                          <text x="8" y="26" fill="#94A3B8" fontSize="8">Aretácia barana lisu</text>
                        </g>
                      </g>

                      {/* PIN 2: Hardened Press Ram Punch Tool (x: 450, y: 260) */}
                      <g 
                        onClick={() => onSelectStep(1)}
                        onMouseEnter={() => setInternalHoverStep(1)}
                        onMouseLeave={() => setInternalHoverStep(null)}
                        className="cursor-pointer group"
                        transform="translate(450, 260)"
                      >
                        <line x1="0" y1="0" x2="-65" y2="-35" stroke="#F59E0B" strokeWidth="1.5" strokeDasharray="3 2" />
                        <circle cx="0" cy="0" r="14" fill="#F59E0B" opacity="0.3" className="animate-ping" />
                        <circle cx="0" cy="0" r="11" fill="#F59E0B" stroke="#FFFFFF" strokeWidth="2" filter="url(#amber-glow)" />
                        <text x="0" y="4" fill="#090D16" fontSize="11" fontWeight="extrabold" fontFamily="sans-serif" textAnchor="middle">2</text>
                        <g transform="translate(-195, -60)">
                          <rect x="0" y="0" width="125" height="34" rx="6" fill="#090D16" stroke={effectiveStep === 1 ? '#38BDF8' : '#F59E0B'} strokeWidth={effectiveStep === 1 ? 2.5 : 1} filter={effectiveStep === 1 ? 'url(#cyan-glow)' : undefined} />
                          <text x="8" y="14" fill="#FFFFFF" fontSize="9.5" fontWeight="bold">Krok 2: Lisovací tŕň</text>
                          <text x="8" y="26" fill="#94A3B8" fontSize="8">Inšpekcia a očistenie otrepov</text>
                        </g>
                      </g>

                      {/* PIN 3: Kistler Piezo Quartz Force Sensor (x: 450, y: 170) */}
                      <g 
                        onClick={() => onSelectStep(2)}
                        onMouseEnter={() => setInternalHoverStep(2)}
                        onMouseLeave={() => setInternalHoverStep(null)}
                        className="cursor-pointer group"
                        transform="translate(450, 170)"
                      >
                        <line x1="0" y1="0" x2="-55" y2="-35" stroke="#38BDF8" strokeWidth="1.5" strokeDasharray="3 2" />
                        <circle cx="0" cy="0" r="14" fill="#38BDF8" opacity="0.3" className="animate-ping" />
                        <circle cx="0" cy="0" r="11" fill="#38BDF8" stroke="#FFFFFF" strokeWidth="2" filter="url(#cyan-glow)" />
                        <text x="0" y="4" fill="#FFFFFF" fontSize="11" fontWeight="extrabold" fontFamily="sans-serif" textAnchor="middle">3</text>
                        <g transform="translate(-185, -60)">
                          <rect x="0" y="0" width="125" height="34" rx="6" fill="#090D16" stroke={effectiveStep === 2 ? '#38BDF8' : '#38BDF8'} strokeWidth={effectiveStep === 2 ? 2.5 : 1} filter={effectiveStep === 2 ? 'url(#cyan-glow)' : undefined} />
                          <text x="8" y="14" fill="#FFFFFF" fontSize="9.5" fontWeight="bold">Krok 3: Piezo Kistler</text>
                          <text x="8" y="26" fill="#94A3B8" fontSize="8">Kalibrácia nulového bodu sily</text>
                        </g>
                      </g>

                      {/* PIN 4: Keyence Laser Optical Displacement Gauge (x: 525, y: 230) */}
                      <g 
                        onClick={() => onSelectStep(3)}
                        onMouseEnter={() => setInternalHoverStep(3)}
                        onMouseLeave={() => setInternalHoverStep(null)}
                        className="cursor-pointer group"
                        transform="translate(525, 230)"
                      >
                        <line x1="0" y1="0" x2="55" y2="-20" stroke="#38BDF8" strokeWidth="1.5" strokeDasharray="3 2" />
                        <circle cx="0" cy="0" r="14" fill="#38BDF8" opacity="0.3" className="animate-ping" />
                        <circle cx="0" cy="0" r="11" fill="#38BDF8" stroke="#FFFFFF" strokeWidth="2" />
                        <text x="0" y="4" fill="#FFFFFF" fontSize="11" fontWeight="extrabold" fontFamily="sans-serif" textAnchor="middle">4</text>
                        <g transform="translate(60, -35)">
                          <rect x="0" y="0" width="130" height="34" rx="6" fill="#090D16" stroke={effectiveStep === 3 ? '#38BDF8' : '#38BDF8'} strokeWidth={effectiveStep === 3 ? 2.5 : 1} filter={effectiveStep === 3 ? 'url(#cyan-glow)' : undefined} />
                          <text x="8" y="14" fill="#FFFFFF" fontSize="9.5" fontWeight="bold">Krok 4: Pravítko dráhy</text>
                          <text x="8" y="26" fill="#94A3B8" fontSize="8">Hĺbka 42±0.2 mm (Keyence)</text>
                        </g>
                      </g>

                      {/* PIN 5: Kistler maXYmos HMI Screen & F/s Curve (x: 725, y: 200) */}
                      <g 
                        onClick={() => onSelectStep(4)}
                        onMouseEnter={() => setInternalHoverStep(4)}
                        onMouseLeave={() => setInternalHoverStep(null)}
                        className="cursor-pointer group"
                        transform="translate(725, 200)"
                      >
                        <line x1="0" y1="0" x2="35" y2="45" stroke="#10B981" strokeWidth="1.5" strokeDasharray="3 2" />
                        <circle cx="0" cy="0" r="14" fill="#10B981" opacity="0.3" className="animate-ping" />
                        <circle cx="0" cy="0" r="11" fill="#10B981" stroke="#FFFFFF" strokeWidth="2" />
                        <text x="0" y="4" fill="#FFFFFF" fontSize="11" fontWeight="extrabold" fontFamily="sans-serif" textAnchor="middle">5</text>
                        <g transform="translate(40, 30)">
                          <rect x="0" y="0" width="130" height="34" rx="6" fill="#090D16" stroke={effectiveStep === 4 ? '#38BDF8' : '#10B981'} strokeWidth={effectiveStep === 4 ? 2.5 : 1} filter={effectiveStep === 4 ? 'url(#cyan-glow)' : undefined} />
                          <text x="8" y="14" fill="#FFFFFF" fontSize="9.5" fontWeight="bold">Krok 5: F/s Verifikácia</text>
                          <text x="8" y="26" fill="#94A3B8" fontSize="8">maXYmos TL &amp; uvoľnenie linky</text>
                        </g>
                      </g>
                    </>
                  )}

                </g>
              </svg>
            </div>

            {/* Bottom Diagnostic Spec Strip */}
            <div className="mt-4 pt-3 border-t border-[#1E293B] flex flex-wrap items-center justify-between gap-3 text-xs text-[#94A3B8]">
              {isStation3 ? (
                <>
                  <div className="flex items-center gap-4">
                    <span>Výrobca: <b className="text-white">Cognex Corp.</b></span>
                    <span>Optika: <b className="text-white">C-Mount 16mm F1.4</b></span>
                    <span>Osvetlenie: <b className="text-white">LED Ring Red 630nm</b></span>
                    <span>Rozhranie: <b className="text-white">Profinet / 24V DC</b></span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#EF4444] animate-ping" />
                    <span className="text-[#EF4444] font-bold">ST-038: Zlyhanie snímania obrazu</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-4">
                    <span>Lisovacia jednotka: <b className="text-white">TOX Pressotechnik / Kistler</b></span>
                    <span>Nominálna sila: <b className="text-white">120 kN (Nastavené: 50 kN)</b></span>
                    <span>Meranie dráhy: <b className="text-white">Keyence LK-G laser (0.1 µm)</b></span>
                    <span>Vyhodnotenie: <b className="text-white">maXYmos TL 5877A</b></span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#F59E0B] animate-pulse" />
                    <span className="text-[#F59E0B] font-bold">Q-020: Sila prekročila limit (38.4 kN)</span>
                  </div>
                </>
              )}
            </div>

          </div>

        </div>
      )}

    </div>
  );
};