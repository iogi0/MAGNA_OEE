import React, { useState } from 'react';
import { ShiftAnalytics, HourlyData } from '../types';
import { 
  Sparkles, 
  RotateCcw, 
  Clock, 
  TrendingUp, 
  CheckCircle, 
  AlertOctagon, 
  Activity, 
  ChevronRight,
  MoreHorizontal
} from 'lucide-react';

interface Props {
  analytics: ShiftAnalytics;
  shiftHours: HourlyData[];
  manualHoursEntered: Set<number>;
  onAutofillRest: () => void;
  onResetShift: () => void;
  onSelectHourForEdit?: (hour: number) => void;
  onNavigateTab?: (tab: 'shift' | 'weekly' | 'monthly' | 'machine') => void;
}

export const TopSectionOverview: React.FC<Props> = ({
  analytics,
  shiftHours,
  manualHoursEntered,
  onAutofillRest,
  onResetShift,
  onSelectHourForEdit,
  onNavigateTab,
}) => {
  const { kpi, totals } = analytics;
  const [selectedChartPoint, setSelectedChartPoint] = useState<number>(4); // Default to H4 with downtime

  // Dynamic values
  const oeePercent = (kpi.oee * 100).toFixed(1);
  const aPercent = (kpi.availability * 100).toFixed(1);
  const pPercent = (kpi.performance * 100).toFixed(1);
  const qPercent = (kpi.quality * 100).toFixed(1);

  // SVG Area Chart points calculation
  // SVG Dimensions: 720 x 220, padding: x: 40..680, y: 30..180
  const chartW = 700;
  const chartH = 200;
  const padX = 40;
  const padY = 30;
  const plotW = chartW - padX * 2;
  const plotH = chartH - padY * 2;

  const points = shiftHours.map((h, i) => {
    const x = padX + (i / 7) * plotW;
    // Map OEE (0.0 to 1.0) to y (chartH - padY down to padY)
    const clampedOee = Math.max(0, Math.min(1.0, h.oee));
    const y = chartH - padY - clampedOee * plotH;
    return { x, y, hour: h.hour, oee: (h.oee * 100).toFixed(1), data: h };
  });

  // Construct SVG cubic Bezier smooth path
  const createSmoothPath = (pts: { x: number; y: number }[]) => {
    if (pts.length === 0) return '';
    let d = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i];
      const p1 = pts[i + 1];
      const cpX = (p0.x + p1.x) / 2;
      d += ` C ${cpX} ${p0.y}, ${cpX} ${p1.y}, ${p1.x} ${p1.y}`;
    }
    return d;
  };

  const linePath = createSmoothPath(points);
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${chartH - padY} L ${points[0].x} ${chartH - padY} Z`;
  const targetY = chartH - padY - 0.85 * plotH;

  return (
    <section className="max-w-[1440px] w-full mx-auto px-6 mb-8 select-none">
      
      {/* 12-Column CityCare Top Grid (5/12 Left, 7/12 Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        
        {/* ========================================================
            LEFT COLUMN (5 Cols): Personalized Hero + Glass Efficiency Card
           ======================================================== */}
        <div className="lg:col-span-5 flex flex-col justify-between p-8 rounded-[32px] bg-gradient-to-br from-white via-[#F8FAFC] to-[#F1F5F9] border border-white/80 shadow-[0px_4px_24px_rgba(0,0,0,0.03)] relative overflow-hidden">
          
          {/* Subtle Ambient Background Gradients */}
          <div className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-bl from-[#3B82F6]/10 via-[#10B981]/5 to-transparent rounded-full blur-3xl pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-[#F59E0B]/5 rounded-full blur-2xl pointer-events-none" />

          {/* Top Greeting & Subtitle */}
          <div className="relative z-10">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h2 className="text-3xl font-bold tracking-tight text-[#111827]">
                Prehľad Linky L01
              </h2>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-white text-[#4B5563] font-semibold border border-gray-200 shadow-sm">
                18.11.2026 • Ranná zmena
              </span>
            </div>
            <p className="text-sm text-[#6B7280]">
              Monitoring 8-hodinovej zmeny • Norma CT = 60s (50 ks/h) • Magna Powertrain
            </p>

            {/* 2 Mini Indicator Arcs (Patient Recovery & Bed Utilization style) */}
            <div className="grid grid-cols-2 gap-4 mt-6">
              {/* Availability Arc */}
              <div className="bg-white/80 backdrop-blur-sm p-4 rounded-2xl border border-white shadow-sm">
                <div className="flex items-center justify-between text-xs text-[#6B7280] mb-1 font-medium">
                  <span>Dostupnosť</span>
                  <span className="text-[#10B981] font-bold">Cieľ: 90%</span>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-bold text-[#111827]">{aPercent}</span>
                  <span className="text-xs text-[#6B7280] font-semibold">%</span>
                </div>
                {/* Mini SVG Arch Bar */}
                <div className="w-full bg-gray-100 h-2 rounded-full mt-2.5 overflow-hidden">
                  <div 
                    className="h-full bg-gradient-to-r from-[#10B981] to-[#3B82F6] rounded-full transition-all duration-500" 
                    style={{ width: `${Math.min(100, Math.max(0, kpi.availability * 100))}%` }}
                  />
                </div>
              </div>

              {/* Performance Arc */}
              <div className="bg-white/80 backdrop-blur-sm p-4 rounded-2xl border border-white shadow-sm">
                <div className="flex items-center justify-between text-xs text-[#6B7280] mb-1 font-medium">
                  <span>Výkon linky</span>
                  <span className="text-[#F59E0B] font-bold">CT: 60s</span>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-bold text-[#111827]">{pPercent}</span>
                  <span className="text-xs text-[#6B7280] font-semibold">%</span>
                </div>
                <div className="w-full bg-gray-100 h-2 rounded-full mt-2.5 overflow-hidden">
                  <div 
                    className="h-full bg-gradient-to-r from-[#F59E0B] to-[#EF4444] rounded-full transition-all duration-500" 
                    style={{ width: `${Math.min(100, Math.max(0, kpi.performance * 100))}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Frosted Glassmorphism Central Card (CityCare "92% Care Efficiency" Card) */}
          <div className="relative z-10 my-6 p-6 rounded-[28px] citycare-glass shadow-[0_8px_32px_rgba(0,0,0,0.06)] border border-white/70">
            <div className="flex items-center gap-5">
              
              {/* Circular Gauge Ring */}
              <div className="relative w-24 h-24 flex items-center justify-center shrink-0">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                  <circle
                    cx="50"
                    cy="50"
                    r="40"
                    fill="transparent"
                    stroke="#E2E8F0"
                    strokeWidth="8"
                  />
                  <circle
                    cx="50"
                    cy="50"
                    r="40"
                    fill="transparent"
                    stroke={kpi.goal_met ? "#10B981" : "#EF4444"}
                    strokeWidth="8"
                    strokeDasharray={251.2}
                    strokeDashoffset={251.2 * (1 - Math.min(1, Math.max(0, kpi.oee)))}
                    strokeLinecap="round"
                    className="transition-all duration-1000 ease-out"
                  />
                </svg>
                <div className="absolute flex flex-col items-center justify-center text-center">
                  <span className="text-xl font-extrabold text-[#111827] tracking-tight">
                    {oeePercent}%
                  </span>
                  <span className="text-[9px] uppercase font-bold text-[#6B7280] tracking-wider">
                    OEE
                  </span>
                </div>
              </div>

              {/* Text & Micro Breakdown Details */}
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-[#111827]">
                    Celková výrobná efektivita
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    totals.produced_pcs === 0
                      ? 'bg-gray-100 text-[#6B7280]'
                      : kpi.goal_met 
                      ? 'bg-[#10B981]/15 text-[#10B981]' 
                      : 'bg-[#EF4444]/15 text-[#EF4444]'
                  }`}>
                    {totals.produced_pcs === 0 ? 'Pripravené na zadanie' : kpi.goal_met ? 'Cieľ splnený' : 'Pod cieľom (85%)'}
                  </span>
                </div>
                <p className="text-xs text-[#6B7280] mt-1">
                  Straty zmeny: <b className="text-[#EF4444]">-{totals.downtime_min} min</b> prestoje, <b className="text-[#EF4444]">-{totals.nok_pcs} ks</b> brak, <b className="text-[#F59E0B]">-{totals.speed_loss_pcs} ks</b> tempo.
                </p>

                {/* Sub-Bar Breakdown (Equalizer effect) */}
                <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-gray-200/50 text-[11px]">
                  <div>
                    <span className="text-[#6B7280] block text-[10px]">Dostupnosť</span>
                    <b className="text-[#111827]">{aPercent}%</b>
                  </div>
                  <div>
                    <span className="text-[#6B7280] block text-[10px]">Výkon</span>
                    <b className="text-[#111827]">{pPercent}%</b>
                  </div>
                  <div>
                    <span className="text-[#6B7280] block text-[10px]">Kvalita</span>
                    <b className="text-[#111827]">{qPercent}%</b>
                  </div>
                </div>
              </div>

            </div>
          </div>

          {/* Quick Action Pill Buttons for 3-minute Presentation */}
          <div className="relative z-10 pt-2 flex flex-col sm:flex-row items-center gap-3">
            <button
              onClick={onAutofillRest}
              className="w-full sm:w-auto flex-1 flex items-center justify-center gap-2 px-5 py-3 rounded-full bg-[#111827] text-white text-xs font-semibold hover:bg-black active:scale-[0.98] shadow-md transition-all duration-200"
            >
              <Sparkles className="w-4 h-4 text-[#F59E0B]" />
              <span>Automaticky doplniť zvyšok zmeny</span>
            </button>

            <button
              onClick={onResetShift}
              className="w-full sm:w-auto px-4 py-3 rounded-full bg-white text-[#4B5563] text-xs font-semibold border border-gray-200 hover:bg-gray-50 active:scale-[0.98] shadow-sm transition-all duration-200 flex items-center justify-center gap-1.5"
              title="Vyčistiť zmenu pre čistý začiatok live demo"
            >
              <RotateCcw className="w-3.5 h-3.5 text-[#6B7280]" />
              <span>Reset</span>
            </button>
          </div>

        </div>


        {/* ========================================================
            RIGHT COLUMN (7 Cols): 4 Stat Cards + Large Area Chart
           ======================================================== */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          
          {/* Top Row: 4 Clean White Statistic Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            
            {/* 1. Vyrobené kusy */}
            <div className="bg-white p-5 rounded-[24px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100/80 citycare-card-hover flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs text-[#6B7280] font-medium">
                <span>Vyrobené spolu</span>
                <MoreHorizontal className="w-4 h-4 text-gray-300" />
              </div>
              <div className="my-2">
                <div className="text-3xl font-extrabold tracking-tight text-[#111827]">
                  {totals.produced_pcs}
                </div>
                <div className="flex items-center gap-1 mt-1 text-[11px] font-semibold text-[#10B981]">
                  <span>{totals.good_pcs} OK</span>
                  <span className="text-[#6B7280]">/ 440 plán</span>
                </div>
              </div>
              {/* Mini Sparkline SVG */}
              <div className="w-full h-4">
                <svg className="w-full h-full" viewBox="0 0 100 20" preserveAspectRatio="none">
                  <path d="M 0 15 Q 25 5, 50 12 T 100 8" fill="none" stroke="#10B981" strokeWidth="2" strokeLinecap="round" />
                  <circle cx="100" cy="8" r="2.5" fill="#10B981" />
                </svg>
              </div>
            </div>

            {/* 2. Prestoje (Downtime) */}
            <div className="bg-white p-5 rounded-[24px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100/80 citycare-card-hover flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs text-[#6B7280] font-medium">
                <span>Downtime strata</span>
                <MoreHorizontal className="w-4 h-4 text-gray-300" />
              </div>
              <div className="my-2">
                <div className="text-3xl font-extrabold tracking-tight text-[#F59E0B]">
                  {totals.downtime_min}
                  <span className="text-base font-semibold text-[#6B7280] ml-1">min</span>
                </div>
                <div className="text-[11px] font-semibold text-[#F59E0B] mt-1">
                  -{totals.downtime_min} ks kapacity
                </div>
              </div>
              <div className="w-full h-4">
                <svg className="w-full h-full" viewBox="0 0 100 20" preserveAspectRatio="none">
                  <path d="M 0 18 Q 30 18, 50 4 T 100 16" fill="none" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" />
                  <circle cx="50" cy="4" r="2.5" fill="#F59E0B" />
                </svg>
              </div>
            </div>

            {/* 3. Rýchlostná strata */}
            <div className="bg-white p-5 rounded-[24px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100/80 citycare-card-hover flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs text-[#6B7280] font-medium">
                <span>Rýchlostná strata</span>
                <MoreHorizontal className="w-4 h-4 text-gray-300" />
              </div>
              <div className="my-2">
                <div className="text-3xl font-extrabold tracking-tight text-[#111827]">
                  {totals.speed_loss_pcs}
                  <span className="text-base font-semibold text-[#6B7280] ml-1">ks</span>
                </div>
                <div className="text-[11px] font-semibold text-[#6B7280] mt-1">
                  Spomalenie cyklu
                </div>
              </div>
              <div className="w-full h-4">
                <svg className="w-full h-full" viewBox="0 0 100 20" preserveAspectRatio="none">
                  <path d="M 0 10 Q 30 15, 60 8 T 100 12" fill="none" stroke="#3B82F6" strokeWidth="2" strokeLinecap="round" />
                  <circle cx="100" cy="12" r="2.5" fill="#3B82F6" />
                </svg>
              </div>
            </div>

            {/* 4. Kvalita (NOK brak) */}
            <div className="bg-white p-5 rounded-[24px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100/80 citycare-card-hover flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs text-[#6B7280] font-medium">
                <span>Brak (NOK kusy)</span>
                <MoreHorizontal className="w-4 h-4 text-gray-300" />
              </div>
              <div className="my-2">
                <div className="text-3xl font-extrabold tracking-tight text-[#EF4444]">
                  {totals.nok_pcs}
                  <span className="text-base font-semibold text-[#6B7280] ml-1">ks</span>
                </div>
                <div className="text-[11px] font-semibold text-[#EF4444] mt-1">
                  {totals.produced_pcs > 0 ? ((totals.nok_pcs / totals.produced_pcs) * 100).toFixed(1) : '0.0'}% chybovosť
                </div>
              </div>
              <div className="w-full h-4">
                <svg className="w-full h-full" viewBox="0 0 100 20" preserveAspectRatio="none">
                  <path d="M 0 16 Q 40 16, 70 6 T 100 14" fill="none" stroke="#EF4444" strokeWidth="2" strokeLinecap="round" />
                  <circle cx="70" cy="6" r="2.5" fill="#EF4444" />
                </svg>
              </div>
            </div>

          </div>


          {/* Bottom Card: Smooth Curved Area Chart (CityCare "Patient Admission Trend" style) */}
          <div className="bg-white p-6 rounded-[28px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100/80 flex-1 flex flex-col justify-between">
            
            {/* Header with Title and Timeframe Filters */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="flex items-center gap-2.5">
                  <h3 className="text-base font-bold text-[#111827]">
                    Priebeh OEE počas 8 hodín zmeny
                  </h3>
                  <span className="flex items-center gap-1.5 text-[10.5px] font-bold text-[#EF4444] bg-[#EF4444]/10 px-2.5 py-0.5 rounded-full border border-[#EF4444]/20">
                    <span className="w-2.5 h-0 border-b-2 border-dashed border-[#EF4444]" />
                    Cieľ: 85% OEE
                  </span>
                </div>
                <p className="text-xs text-[#6B7280] mt-0.5">
                  Hodinový vývoj efektivity oproti cieľovej hodnote 85%
                </p>
              </div>

              {/* Pill Selectors */}
              <div className="flex items-center p-1 bg-gray-100/80 rounded-full text-xs font-semibold text-[#6B7280]">
                <button
                  type="button"
                  onClick={() => onNavigateTab && onNavigateTab('shift')}
                  className="px-3 py-1 rounded-full bg-white text-[#111827] shadow-sm transition-all"
                >
                  Dnes (8h)
                </button>
                <button
                  type="button"
                  onClick={() => onNavigateTab && onNavigateTab('weekly')}
                  className="px-3 py-1 hover:text-[#111827] transition-all"
                >
                  Týždeň
                </button>
                <button
                  type="button"
                  onClick={() => onNavigateTab && onNavigateTab('monthly')}
                  className="px-3 py-1 hover:text-[#111827] transition-all"
                >
                  Mesiac
                </button>
              </div>
            </div>

            {/* SVG Interactive Area Chart Container */}
            <div className="w-full flex flex-col">
              <div className="relative w-full h-44">
                <svg 
                  className="w-full h-full overflow-visible" 
                  viewBox={`0 0 ${chartW} ${chartH}`}
                  preserveAspectRatio="none"
                >
                  <defs>
                    {/* Blue Gradient Fill */}
                    <linearGradient id="citycareBlueGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.28" />
                      <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  {/* Target Line (85% Goal) */}
                  <line
                    x1={padX}
                    y1={targetY}
                    x2={chartW - padX}
                    y2={targetY}
                    stroke="#EF4444"
                    strokeWidth="1.5"
                    strokeDasharray="4 4"
                    opacity="0.6"
                  />

                  {/* Smooth Area & Line Path */}
                  <path d={areaPath} fill="url(#citycareBlueGrad)" />
                  <path d={linePath} fill="none" stroke="#3B82F6" strokeWidth="3" strokeLinecap="round" />

                  {/* Target Badge on Left with White Protective Background Pill */}
                  <g transform={`translate(${padX + 6}, ${targetY - 15})`}>
                    <rect x="0" y="0" width="80" height="15" rx="4" fill="#FFFFFF" fillOpacity="0.95" stroke="#EF4444" strokeWidth="0.8" strokeOpacity="0.4" />
                    <text
                      x="40"
                      y="11"
                      fill="#EF4444"
                      fontSize="9.5"
                      fontWeight="bold"
                      textAnchor="middle"
                    >
                      Cieľ OEE: 85%
                    </text>
                  </g>

                  {/* Data Points on the line */}
                  {points.map((pt) => {
                    const isLow = Number(pt.oee) < 85 && pt.data.produced_pcs > 0;
                    const isAlarmPoint = pt.data.downtime_min > 0;
                    const isSelected = selectedChartPoint === pt.hour;

                    return (
                      <g key={pt.hour} className="cursor-pointer" onClick={() => setSelectedChartPoint(pt.hour)}>
                        {/* Soft stationary halo for actual downtime alarm */}
                        {isAlarmPoint && (
                          <>
                            <circle
                              cx={pt.x}
                              cy={pt.y}
                              r="11"
                              fill="#EF4444"
                              opacity="0.18"
                            />
                            <circle
                              cx={pt.x}
                              cy={pt.y}
                              r="8"
                              fill="none"
                              stroke="#EF4444"
                              strokeWidth="2"
                              opacity="0.5"
                            />
                          </>
                        )}

                        {/* Main point circle */}
                        <circle
                          cx={pt.x}
                          cy={pt.y}
                          r={isSelected ? 6 : 4}
                          fill={isAlarmPoint ? "#EF4444" : isLow ? "#F59E0B" : pt.data.produced_pcs === 0 ? "#94A3B8" : "#10B981"}
                          stroke="#FFFFFF"
                          strokeWidth="2.5"
                        />

                        {/* Floating Tooltip Pill (like "215" on Tuesday in CityCare) */}
                        {isSelected && (
                          <g>
                            <rect
                              x={pt.x - 36}
                              y={pt.y - 32}
                              width="72"
                              height="24"
                              rx="12"
                              fill="#111827"
                            />
                            <text
                              x={pt.x}
                              y={pt.y - 16}
                              fill="#FFFFFF"
                              fontSize="11"
                              fontWeight="bold"
                              textAnchor="middle"
                            >
                              {pt.oee}%
                            </text>
                          </g>
                        )}
                      </g>
                    );
                  })}
                </svg>
              </div>

              {/* X-Axis Labels - cleanly separated in document flow with no collision */}
              <div className="flex justify-between items-center px-4 mt-3 text-xs font-semibold text-[#6B7280]">
                {shiftHours.map((h) => (
                  <button
                    key={h.hour}
                    onClick={() => {
                      setSelectedChartPoint(h.hour);
                      if (onSelectHourForEdit) onSelectHourForEdit(h.hour);
                    }}
                    className={`transition-colors py-1 px-2 rounded-lg ${
                      selectedChartPoint === h.hour 
                        ? 'text-[#111827] font-bold bg-gray-100 shadow-xs' 
                        : 'hover:text-[#111827]'
                    }`}
                  >
                    H{h.hour}
                  </button>
                ))}
              </div>
            </div>

            {/* Chart Subtitle Note with generous separation */}
            <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-[11px] text-[#6B7280]">
              {(() => {
                const problematic = [...shiftHours].filter(h => h.downtime_min > 0 || (h.oee < 0.85 && h.produced_pcs > 0));
                const worst = problematic.sort((a, b) => a.oee - b.oee)[0];

                if (worst) {
                  return (
                    <span className="flex items-center gap-1.5 text-[#EF4444]">
                      <span className="w-2 h-2 rounded-full bg-[#EF4444] animate-beacon" />
                      Kritický pokles: <b>Hodina {worst.hour} ({(worst.oee * 100).toFixed(1)}% OEE)</b>
                      {worst.downtime_code ? ` — Porucha ${worst.downtime_code} (-${worst.downtime_min} min)` : ''}
                    </span>
                  );
                }

                if (totals.produced_pcs === 0) {
                  return (
                    <span className="flex items-center gap-1.5 text-gray-400">
                      <span className="w-2 h-2 rounded-full bg-gray-400" />
                      Zmena je vyčistená (Zadajte hodiny manuálne alebo kliknite «Automaticky doplniť»)
                    </span>
                  );
                }

                return (
                  <span className="flex items-center gap-1.5 text-[#10B981] font-semibold">
                    <span className="w-2 h-2 rounded-full bg-[#10B981]" />
                    Optimálna zmena: Všetky hodiny dosahujú cieľové OEE ≥ 85%
                  </span>
                );
              })()}
              <span className="font-semibold text-[#3B82F6]">
                Kliknutím na hodinu zobrazíte detail
              </span>
            </div>

          </div>

        </div>

      </div>

    </section>
  );
};
