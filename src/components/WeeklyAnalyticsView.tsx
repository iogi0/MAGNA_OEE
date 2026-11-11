import React, { useState } from 'react';
import { CURRENT_WEEK_DAYS } from '../data/constants';
import { Calendar, TrendingUp, Clock, CheckCircle2, ChevronRight, BarChart3, Info } from 'lucide-react';

export const WeeklyAnalyticsView: React.FC = () => {
  // Default selection to Wednesday ("Streda", which is today's shift)
  const [selectedDay, setSelectedDay] = useState<string | null>('Streda');
  const [hoveredDay, setHoveredDay] = useState<string | null>(null);

  const activeDayName = hoveredDay || selectedDay;
  const activeDay = CURRENT_WEEK_DAYS.find(d => d.day === activeDayName) || null;

  // Weekly aggregated statistics (Week 47: 16.11 – 20.11.2026)
  const totalProduced = CURRENT_WEEK_DAYS.reduce((sum, d) => sum + d.produced, 0); // 1,987 ks
  const totalGood = CURRENT_WEEK_DAYS.reduce((sum, d) => sum + d.good, 0); // 1,957 ks
  const totalNok = CURRENT_WEEK_DAYS.reduce((sum, d) => sum + d.nok, 0); // 30 ks
  const totalPlan = CURRENT_WEEK_DAYS.reduce((sum, d) => sum + d.target, 0); // 2,200 ks
  const totalDowntime = CURRENT_WEEK_DAYS.reduce((sum, d) => sum + d.downtime_min, 0); // 73 min
  const avgOee = (totalGood / totalPlan) * 100; // 88.95% -> 89.0% or weighted
  const qualityRate = (totalGood / totalProduced) * 100; // 98.49% -> 98.5%

  return (
    <div className="max-w-[1440px] w-full mx-auto px-6 mb-8 select-none">
      <div className="space-y-6">
        
        {/* Header */}
        <div className="bg-white p-6 rounded-[28px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-[#3B82F6]/10 text-[#3B82F6] flex items-center justify-center">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold tracking-tight text-[#111827]">
                  Týždenný prehľad výroby (Týždeň 47: 16.11 – 20.11.2026)
                </h2>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#3B82F6]/10 text-[#3B82F6]">
                  7 dní / 5 pracovných dní
                </span>
              </div>
              <p className="text-xs text-[#6B7280]">
                Konsolidované denné výsledky montážnej linky L01 za 5 pracovných zmien aktuálneho týždňa.
              </p>
            </div>
          </div>
          <span className="text-xs font-semibold px-3 py-1.5 rounded-full bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30">
            Priemer týždňa: 88.9% OEE
          </span>
        </div>

        {/* 4 Clean White Scorecards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          
          <div className="bg-white p-5 rounded-[24px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100 citycare-card-hover">
            <span className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wider">
              Vyrobené spolu
            </span>
            <div className="text-3xl font-extrabold tracking-tight text-[#111827] mt-2">
              {totalProduced.toLocaleString()} <span className="text-sm font-normal text-[#6B7280]">ks</span>
            </div>
            <div className="text-xs text-[#10B981] font-semibold mt-1">
              {totalGood.toLocaleString()} OK (88.9% OEE) / {totalPlan.toLocaleString()} plán
            </div>
          </div>

          <div className="bg-white p-5 rounded-[24px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100 citycare-card-hover">
            <span className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wider">
              Priemerné OEE
            </span>
            <div className="text-3xl font-extrabold tracking-tight text-[#10B981] mt-2">
              88.9%
            </div>
            <div className="text-xs text-[#10B981] font-semibold mt-1">
              +3.9 p.b. nad cieľom 85%
            </div>
          </div>

          <div className="bg-white p-5 rounded-[24px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100 citycare-card-hover">
            <span className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wider">
              Downtime prestoje
            </span>
            <div className="text-3xl font-extrabold tracking-tight text-[#F59E0B] mt-2">
              {totalDowntime} <span className="text-sm font-normal text-[#6B7280]">min</span>
            </div>
            <div className="text-xs text-[#6B7280] font-semibold mt-1">
              Priemer {(totalDowntime / CURRENT_WEEK_DAYS.length).toFixed(1)} min / deň
            </div>
          </div>

          <div className="bg-white p-5 rounded-[24px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100 citycare-card-hover">
            <span className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wider">
              Kvalita výroby
            </span>
            <div className="text-3xl font-extrabold tracking-tight text-[#10B981] mt-2">
              {qualityRate.toFixed(1)}%
            </div>
            <div className="text-xs text-[#6B7280] font-semibold mt-1">
              {totalNok} ks celkový brak ({(100 - qualityRate).toFixed(1)}% NOK)
            </div>
          </div>

        </div>

        {/* 5-Day Weekly Bar Chart */}
        <div className="bg-white p-6 rounded-[28px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-4">
            <div>
              <h3 className="text-base font-bold text-[#111827]">
                Denný vývoj OEE (Týždeň 47: Po – Pi) vs. Cieľová hodnota 85%
              </h3>
              <p className="text-xs text-[#6B7280]">
                {activeDay ? (
                  <span>
                    Zvolený deň: <b className="text-[#3B82F6]">{activeDay.day} ({activeDay.date})</b>
                    {activeDay.note && <span className="text-[#F59E0B] font-medium ml-1">({activeDay.note})</span>} • Pre podrobnosti A/P/Q kliknite alebo prejdite myškou
                  </span>
                ) : (
                  <span>Jednotlivé stĺpce reprezentujú 5 pracovných dní týždňa • Prejdite myšou pre rozpad A/P/Q</span>
                )}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {selectedDay && (
                <button
                  type="button"
                  onClick={() => { setSelectedDay(null); setHoveredDay(null); }}
                  className="text-[11px] font-semibold text-[#6B7280] hover:text-[#111827] px-2.5 py-1 rounded-full bg-gray-100 hover:bg-gray-200 transition-colors"
                >
                  Zrušiť výber ✕
                </button>
              )}
              <span className="text-xs font-semibold px-3 py-1 rounded-full bg-[#EF4444]/10 text-[#EF4444]">
                Cieľ: 85.0%
              </span>
            </div>
          </div>

          <div className="h-72 w-full relative">
            <svg className="w-full h-full overflow-visible" viewBox="0 0 740 250">
              {/* Baseline Y=200 */}
              <line x1="38" y1="200" x2="702" y2="200" stroke="#E5E7EB" strokeWidth="1" />

              {/* Target 85% line (200 - 0.85 * 90 = 123.5) */}
              <line x1="38" y1="123.5" x2="702" y2="123.5" stroke="#EF4444" strokeWidth="1.5" strokeDasharray="4 4" opacity="0.8" />
              <text x="32" y="127" fill="#EF4444" fontSize="10" fontWeight="bold" textAnchor="end">85%</text>

              {CURRENT_WEEK_DAYS.map((d, idx) => {
                // 5 evenly spaced bars with ample headroom above
                const barWidth = 66;
                const x = 75 + idx * 135;
                const barCenter = x + barWidth / 2;
                const baseY = 200;
                const barH = d.oee * 90;
                const y = baseY - barH;
                const isOver = d.oee >= 0.85;
                const isActive = activeDayName === d.day;

                // Tooltip positioned cleanly in the dedicated headroom above bars
                const tooltipW = 230;
                const tooltipH = 80;
                const tooltipY = 14;
                const tooltipX = Math.max(15, Math.min(740 - tooltipW - 15, barCenter - tooltipW / 2));

                return (
                  <g 
                    key={d.day}
                    className="cursor-pointer"
                    onClick={() => setSelectedDay(selectedDay === d.day ? null : d.day)}
                    onMouseEnter={() => setHoveredDay(d.day)}
                    onMouseLeave={() => setHoveredDay(null)}
                  >
                    {/* Hover hit target spanning from top to bottom */}
                    <rect
                      x={x - 12}
                      y={10}
                      width={barWidth + 24}
                      height="230"
                      fill="transparent"
                    />

                    {/* Active highlight glow backdrop */}
                    {isActive && (
                      <rect
                        x={x - 6}
                        y={y - 6}
                        width={barWidth + 12}
                        height={barH + 10}
                        rx="14"
                        fill="#3B82F6"
                        opacity="0.16"
                      />
                    )}

                    {/* Bar */}
                    <rect
                      x={x}
                      y={y}
                      width={barWidth}
                      height={barH}
                      rx="10"
                      fill={isOver ? "#10B981" : "#F59E0B"}
                      stroke={isActive ? "#3B82F6" : "transparent"}
                      strokeWidth={isActive ? "2.5" : "0"}
                      className="transition-all duration-200"
                      opacity={isActive ? 1 : 0.88}
                    />

                    {/* Percentage text above bar */}
                    <text
                      x={barCenter}
                      y={y - 7}
                      fill={isActive ? "#3B82F6" : (isOver ? "#111827" : "#D97706")}
                      fontSize={isActive ? "13" : "11.5"}
                      fontWeight="bold"
                      textAnchor="middle"
                    >
                      {(d.oee * 100).toFixed(1)}%
                    </text>

                    {/* Day & Date label below baseline */}
                    <text
                      x={barCenter}
                      y={baseY + 19}
                      fill={isActive ? "#111827" : "#4B5563"}
                      fontSize="12"
                      fontWeight={isActive ? "bold" : "600"}
                      textAnchor="middle"
                    >
                      {d.day}
                    </text>
                    <text
                      x={barCenter}
                      y={baseY + 34}
                      fill={isActive ? "#3B82F6" : (d.note ? "#F59E0B" : "#9CA3AF")}
                      fontSize="10.5"
                      fontWeight={isActive || d.note ? "bold" : "normal"}
                      textAnchor="middle"
                    >
                      {d.date.slice(0, 5)} {d.note ? `• Dnes` : ''}
                    </text>

                    {/* Interactive Tooltip with Full A / P / Q Breakdown (never covers bars) */}
                    {isActive && (
                      <g className="pointer-events-none animate-fadeIn">
                        {/* Tooltip Card Body */}
                        <rect
                          x={tooltipX}
                          y={tooltipY}
                          width={tooltipW}
                          height={tooltipH}
                          rx="14"
                          fill="#111827"
                          stroke="#3B82F6"
                          strokeWidth="1.5"
                          className="shadow-2xl"
                        />
                        {/* Downward triangle pointer pointing directly at the bar */}
                        <polygon
                          points={`${barCenter},${tooltipY + tooltipH + 8} ${barCenter - 7},${tooltipY + tooltipH} ${barCenter + 7},${tooltipY + tooltipH}`}
                          fill="#111827"
                        />

                        {/* Tooltip Title & OEE Percentage */}
                        <text x={tooltipX + 12} y={tooltipY + 17} fill="#F8FAFC" fontSize="11" fontWeight="bold">
                          {d.day} ({d.date.slice(0, 5)}){d.note ? ' • Dnes' : ''}
                        </text>
                        <text x={tooltipX + tooltipW - 12} y={tooltipY + 17} fill={isOver ? "#10B981" : "#F59E0B"} fontSize="11.5" fontWeight="extrabold" textAnchor="end">
                          {(d.oee * 100).toFixed(1)}% OEE
                        </text>

                        {/* Divider */}
                        <line x1={tooltipX + 10} y1={tooltipY + 24} x2={tooltipX + tooltipW - 10} y2={tooltipY + 24} stroke="#374151" strokeWidth="0.8" />

                        {/* Metrics Breakdown Rows */}
                        <text x={tooltipX + 12} y={tooltipY + 39} fill="#94A3B8" fontSize="9.5">
                          <tspan fill="#10B981" fontWeight="bold">A (Dostupnosť):</tspan> {(d.a * 100).toFixed(1)}% (-{d.downtime_min} min)
                        </text>
                        <text x={tooltipX + 12} y={tooltipY + 54} fill="#94A3B8" fontSize="9.5">
                          <tspan fill="#F59E0B" fontWeight="bold">P (Výkon):</tspan> {(d.p * 100).toFixed(1)}% ({d.produced} / {d.target} ks)
                        </text>
                        <text x={tooltipX + 12} y={tooltipY + 69} fill="#94A3B8" fontSize="9.5">
                          <tspan fill="#38BDF8" fontWeight="bold">Q (Kvalita):</tspan> {(d.q * 100).toFixed(1)}% ({d.good} OK, {d.nok} NOK)
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}
            </svg>
          </div>
        </div>

        {/* Detailed 5-Day Weekly Table with Synchronized Row Highlight */}
        <div className="bg-white rounded-[28px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100 overflow-hidden">
          <div className="p-5 border-b border-gray-100 flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-[#111827]">
                Detailné ukazovatele po pracovných dňoch týždňa (Po – Pi)
              </h3>
              <p className="text-xs text-[#6B7280]">
                Kliknutím na riadok zvýrazníte príslušný deň na grafe
              </p>
            </div>
            {selectedDay && (
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-[#3B82F6]/10 text-[#3B82F6]">
                Zvolený riadok: {selectedDay}
              </span>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-[#F8FAFC] text-[#6B7280] font-semibold border-b border-gray-100">
                <tr>
                  <th className="py-3 px-6">Deň v týždni</th>
                  <th className="py-3 px-4">Dátum</th>
                  <th className="py-3 px-4">Vyrobené / Plán</th>
                  <th className="py-3 px-4">Downtime (min)</th>
                  <th className="py-3 px-4">Dostupnosť (A)</th>
                  <th className="py-3 px-4">Výkon (P)</th>
                  <th className="py-3 px-4">Kvalita (Q)</th>
                  <th className="py-3 px-4">OEE</th>
                  <th className="py-3 px-4">Stav cieľa</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-[#111827]">
                {CURRENT_WEEK_DAYS.map((d) => {
                  const isActive = activeDayName === d.day;
                  const isOver = d.oee >= 0.85;

                  return (
                    <tr 
                      key={d.day} 
                      onClick={() => setSelectedDay(selectedDay === d.day ? null : d.day)}
                      onMouseEnter={() => setHoveredDay(d.day)}
                      onMouseLeave={() => setHoveredDay(null)}
                      className={`cursor-pointer transition-all duration-200 ${
                        isActive 
                          ? 'bg-[#3B82F6]/10 font-bold border-l-4 border-[#3B82F6]' 
                          : 'hover:bg-gray-50'
                      }`}
                    >
                      <td className="py-3.5 px-6 font-bold flex items-center gap-2">
                        {isActive && <span className="w-2 h-2 rounded-full bg-[#3B82F6]" />}
                        <span>{d.day}</span>
                        {d.note && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#F59E0B]/15 text-[#D97706]">
                            {d.note}
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-[#6B7280]">{d.date}</td>
                      <td className="py-3.5 px-4 font-mono">{d.produced} / {d.target} ks</td>
                      <td className="py-3.5 px-4 font-mono text-[#F59E0B] font-semibold">{d.downtime_min} min</td>
                      <td className="py-3.5 px-4 font-semibold">{(d.a * 100).toFixed(1)}%</td>
                      <td className="py-3.5 px-4 font-semibold">{(d.p * 100).toFixed(1)}%</td>
                      <td className="py-3.5 px-4 font-semibold">{(d.q * 100).toFixed(1)}%</td>
                      <td className={`py-3.5 px-4 font-bold ${isOver ? 'text-[#10B981]' : 'text-[#D97706]'}`}>
                        {(d.oee * 100).toFixed(1)}%
                      </td>
                      <td className="py-3.5 px-4">
                        {isOver ? (
                          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#10B981]/15 text-[#10B981]">
                            Splnené
                          </span>
                        ) : (
                          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#F59E0B]/15 text-[#D97706]">
                            Pod cieľom (84.1%)
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
};
