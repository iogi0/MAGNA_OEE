import React, { useState } from 'react';
import { MONTH_SHIFTS_DATA, PARETO_DOWNTIME, PARETO_DEFECTS } from '../data/constants';
import { TrendingUp, BarChart3, PieChart, AlertTriangle } from 'lucide-react';

export const MonthlyAnalyticsView: React.FC = () => {
  const [activeShiftIndex, setActiveShiftIndex] = useState<number>(17); // Default to index 17 (25.11 worst shift)

  return (
    <div className="max-w-[1440px] w-full mx-auto px-6 mb-8 select-none">
      <div className="space-y-6">
        
        {/* Header */}
        <div className="bg-white p-6 rounded-[28px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-[#3B82F6]/10 text-[#3B82F6] flex items-center justify-center">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold tracking-tight text-[#111827]">
                Mesačný prehľad výroby (30 dní / 21 pracovných zmien)
              </h2>
              <p className="text-xs text-[#6B7280]">
                Celkový prehľad za november 2026 s Pareto analýzou prestojov a chýb kvality 80/20.
              </p>
            </div>
          </div>
          <span className="text-xs font-semibold px-3 py-1.5 rounded-full bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30">
            Mesačný OEE priemer: 88.0%
          </span>
        </div>

        {/* 21 Shifts Trend Chart */}
        {(() => {
          const padLeft = 45;
          const padRight = 45;
          const plotW = 740 - padLeft - padRight; // 650
          const padTop = 30;
          const plotH = 125; // y from 30 to 155

          const getShiftX = (idx: number) => padLeft + (idx / (MONTH_SHIFTS_DATA.length - 1)) * plotW;
          const getShiftY = (oee: number) => {
            const clamped = Math.max(0.70, Math.min(0.98, oee));
            return padTop + (1 - (clamped - 0.70) / 0.28) * plotH;
          };

          const points = MONTH_SHIFTS_DATA.map((s, idx) => ({
            x: getShiftX(idx),
            y: getShiftY(s.oee),
            data: s,
          }));

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
          const areaPath = `${linePath} L ${points[points.length - 1].x} 160 L ${points[0].x} 160 Z`;
          const targetY = getShiftY(0.85);
          const y90 = getShiftY(0.90);
          const y80 = getShiftY(0.80);

          return (
            <div className="bg-white p-6 rounded-[28px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100">
              <div className="flex justify-between items-center mb-4">
                <div>
                  <h3 className="text-base font-bold text-[#111827]">
                    Trend OEE počas 21 pracovných zmien mesiaca
                  </h3>
                  <p className="text-xs text-[#6B7280]">
                    Rozpätie efektivity 70% – 98% • Zelené body = splnený cieľ (≥ 85%), Červené body = pod limitom
                  </p>
                </div>
                <span className="text-xs font-semibold px-3 py-1 rounded-full bg-[#EF4444]/10 text-[#EF4444]">
                  Cieľ: 85.0%
                </span>
              </div>

              <div className="w-full">
                <svg className="w-full h-64 overflow-visible" viewBox="0 0 740 200">
                  <defs>
                    <linearGradient id="monthlyBlueGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.22" />
                      <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  {/* Horizontal Guideline: 90% */}
                  <line x1={padLeft} y1={y90} x2={740 - padRight} y2={y90} stroke="#E2E8F0" strokeWidth="1" strokeDasharray="3 3" />
                  <text x={padLeft - 8} y={y90 + 3} fill="#94A3B8" fontSize="10" fontWeight="600" textAnchor="end">90%</text>

                  {/* Horizontal Guideline: 80% */}
                  <line x1={padLeft} y1={y80} x2={740 - padRight} y2={y80} stroke="#E2E8F0" strokeWidth="1" strokeDasharray="3 3" />
                  <text x={padLeft - 8} y={y80 + 3} fill="#94A3B8" fontSize="10" fontWeight="600" textAnchor="end">80%</text>

                  {/* Target 85% Line */}
                  <line x1={padLeft} y1={targetY} x2={740 - padRight} y2={targetY} stroke="#EF4444" strokeWidth="1.5" strokeDasharray="4 4" />
                  <text x={padLeft - 8} y={targetY + 3} fill="#EF4444" fontSize="10" fontWeight="bold" textAnchor="end">85%</text>
                  <text x={740 - padRight} y={targetY - 6} fill="#EF4444" fontSize="11" fontWeight="bold" textAnchor="end">Cieľ OEE: 85.0%</text>

                  {/* Gradient Area & Smooth Line */}
                  <path d={areaPath} fill="url(#monthlyBlueGrad)" />
                  <path d={linePath} fill="none" stroke="#3B82F6" strokeWidth="2.5" strokeLinecap="round" />

                  {/* 21 Interactive Shift Points */}
                  {points.map((pt, idx) => {
                    const isUnder = pt.data.oee < 0.85;
                    const isSelected = activeShiftIndex === idx;

                    return (
                      <g 
                        key={pt.data.date}
                        className="cursor-pointer"
                        onMouseEnter={() => setActiveShiftIndex(idx)}
                        onClick={() => setActiveShiftIndex(idx)}
                      >
                        {/* Invisible larger hover hit target */}
                        <circle
                          cx={pt.x}
                          cy={pt.y}
                          r="16"
                          fill="transparent"
                        />

                        {/* Subtle vertical indicator line for selected shift */}
                        {isSelected && (
                          <line
                            x1={pt.x}
                            y1={30}
                            x2={pt.x}
                            y2={160}
                            stroke="#3B82F6"
                            strokeWidth="1.5"
                            strokeDasharray="2 2"
                            opacity="0.4"
                          />
                        )}

                        {/* Outer halo when selected */}
                        {isSelected && (
                          <circle
                            cx={pt.x}
                            cy={pt.y}
                            r="10"
                            fill={isUnder ? "#EF4444" : "#10B981"}
                            opacity="0.25"
                          />
                        )}

                        {/* Main Point Circle */}
                        <circle
                          cx={pt.x}
                          cy={pt.y}
                          r={isSelected ? 6 : 4}
                          fill={isUnder ? "#EF4444" : "#10B981"}
                          stroke="#FFFFFF"
                          strokeWidth="2"
                        />

                        {/* Floating tooltip pill for active shift */}
                        {isSelected && (
                          <g className="pointer-events-none">
                            <rect
                              x={Math.max(10, Math.min(740 - 95, pt.x - 45))}
                              y={Math.max(5, pt.y - 28)}
                              width="90"
                              height="20"
                              rx="10"
                              fill="#111827"
                            />
                            <text
                              x={Math.max(10, Math.min(740 - 95, pt.x - 45)) + 45}
                              y={Math.max(5, pt.y - 28) + 14}
                              fill="#FFFFFF"
                              fontSize="10"
                              fontWeight="bold"
                              textAnchor="middle"
                            >
                              {pt.data.date.slice(8, 10)}.{pt.data.date.slice(5, 7)}: {(pt.data.oee * 100).toFixed(1)}%
                            </text>
                          </g>
                        )}
                      </g>
                    );
                  })}

                  {/* Week Milestone Labels at Bottom */}
                  <g fontSize="10" fontWeight="600" fill="#6B7280">
                    <text x={getShiftX(0)} y="185" textAnchor="start">02.11 (W45)</text>
                    <text x={getShiftX(5)} y="185" textAnchor="middle">09.11 (W46)</text>
                    <text x={getShiftX(10)} y="185" textAnchor="middle">16.11 (W47)</text>
                    <text x={getShiftX(15)} y="185" textAnchor="middle">23.11 (W48)</text>
                    <text x={getShiftX(20)} y="185" textAnchor="end">30.11 (W49)</text>
                  </g>
                </svg>
              </div>
            </div>
          );
        })()}

        {/* 2 Pareto Charts Side-by-Side: Downtime & Quality NOK */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Pareto 1: Downtimes */}
          <div className="bg-white p-6 rounded-[28px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold text-[#111827] flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-[#F59E0B]" />
                  Pareto analýza prestojov (Downtime 80/20)
                </h3>
                <p className="text-xs text-[#6B7280]">
                  TOP kategórie porúch spôsobujúce 80% všetkých strát zmeny
                </p>
              </div>
              <span className="text-xs font-bold text-[#F59E0B]">410 min spolu</span>
            </div>

            <div className="space-y-3">
              {PARETO_DOWNTIME.map((item, idx) => (
                <div key={item.code} className="space-y-1">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-[#111827]">{idx + 1}. {item.code} — {item.name}</span>
                    <span className="font-mono text-[#6B7280]">
                      {item.minutes} min ({item.percent}%) • Kumulatívne: <b className="text-[#F59E0B]">{item.cum_pct}%</b>
                    </span>
                  </div>
                  <div className="w-full bg-gray-100 h-2.5 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-[#F59E0B] to-[#EF4444] rounded-full"
                      style={{ width: `${item.percent}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Pareto 2: Quality NOK Defects */}
          <div className="bg-white p-6 rounded-[28px] shadow-[0px_4px_24px_rgba(0,0,0,0.03)] border border-gray-100">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold text-[#111827] flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-[#EF4444]" />
                  Pareto analýza kvality (Brak NOK 80/20)
                </h3>
                <p className="text-xs text-[#6B7280]">
                  Najčastejšie defekty spôsobujúce vyradenie dielov
                </p>
              </div>
              <span className="text-xs font-bold text-[#EF4444]">119 ks braku</span>
            </div>

            <div className="space-y-3">
              {PARETO_DEFECTS.map((item, idx) => (
                <div key={item.code} className="space-y-1">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-[#111827]">{idx + 1}. {item.code} — {item.name}</span>
                    <span className="font-mono text-[#6B7280]">
                      {item.pcs} ks ({item.percent}%) • Kumulatívne: <b className="text-[#EF4444]">{item.cum_pct}%</b>
                    </span>
                  </div>
                  <div className="w-full bg-gray-100 h-2.5 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-[#EF4444] to-[#B91C1C] rounded-full"
                      style={{ width: `${item.percent}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};
