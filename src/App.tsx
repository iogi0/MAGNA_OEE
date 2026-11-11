import React, { useState } from 'react';
import { HourlyData } from './types';
import { getSlide11ShiftData, calculateShiftAnalytics, calculateHourlyKPI } from './utils/oeeCalculator';
import { LINE_STATIONS } from './data/constants';
import { HeaderNav } from './components/HeaderNav';
import { TopSectionOverview } from './components/TopSectionOverview';
import { BottomSectionDetails } from './components/BottomSectionDetails';
import { InteractiveStationDiagram } from './components/InteractiveStationDiagram';
import { WeeklyAnalyticsView } from './components/WeeklyAnalyticsView';
import { MonthlyAnalyticsView } from './components/MonthlyAnalyticsView';

export function App() {
  const [shiftHours, setShiftHours] = useState<HourlyData[]>(() => getSlide11ShiftData());
  const [manualHoursEntered, setManualHoursEntered] = useState<Set<number>>(new Set([1, 2, 3, 4, 5, 6, 7, 8]));
  const [activeTab, setActiveTab] = useState<'shift' | 'weekly' | 'monthly' | 'machine'>(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const tab = params.get('tab');
      if (tab === 'machine' || tab === 'weekly' || tab === 'monthly' || tab === 'shift') return tab;
    }
    return 'machine'; // Default to Factory X-Ray so user immediately sees the 3D twin!
  });
  const [selectedHour, setSelectedHour] = useState<number>(1);
  const [selectedStationId, setSelectedStationId] = useState<number | null>(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const st = params.get('station');
      if (st) return parseInt(st, 10);
    }
    return null; // Default null: Signature Isometric Digital Twin Overview (Image 2)
  });
  const [resolvedStations, setResolvedStations] = useState<Set<number>>(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const res = params.get('resolved');
      if (res) {
        return new Set(res.split(',').map(n => parseInt(n.trim(), 10)));
      }
    }
    return new Set();
  });
  const [completedSteps, setCompletedSteps] = useState<Record<string, boolean>>(() => {
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

  const analytics = calculateShiftAnalytics(shiftHours);

  // Active fault codes for machine diagram:
  // - ST-038 is the live critical downtime breakdown on Station 3.
  // - Once Station 3 is resolved, there are NO active downtime breakdowns on the line (past shift history does not trigger false alarms).
  const activeDowntimeCode = resolvedStations.has(3)
    ? null
    : (analytics.top_3_availability.find(item => item.code === 'ST-038')?.code || null);

  // - Q-020 is the quality warning on Station 2 (Nalisovanie motora).
  // - Once Station 2 is resolved, there are NO active quality warnings.
  const activeNokCode = resolvedStations.has(2)
    ? null
    : (analytics.top_3_quality.find(item => item.code === 'Q-020')?.code || null);

  // Handlers
  const handleSaveHour = (updatedHour: HourlyData) => {
    const recalculated = calculateHourlyKPI(
      updatedHour.hour,
      updatedHour.produced_pcs,
      updatedHour.nok_pcs,
      updatedHour.downtime_min,
      updatedHour.downtime_code,
      updatedHour.downtime_from,
      updatedHour.downtime_to,
      updatedHour.nok_code
    );
    setShiftHours(prev => {
      const next = [...prev];
      next[updatedHour.hour - 1] = recalculated;
      return next;
    });
    setManualHoursEntered(prev => new Set([...prev, updatedHour.hour]));

    // If saving a new fault on a station, re-arm that station
    if (updatedHour.downtime_code || updatedHour.nok_code) {
      const stationWithFault = LINE_STATIONS.find(s => 
        (updatedHour.downtime_code && s.related_codes.includes(updatedHour.downtime_code)) ||
        (updatedHour.nok_code && s.related_codes.includes(updatedHour.nok_code))
      );
      if (stationWithFault) {
        setResolvedStations(prev => {
          const next = new Set(prev);
          next.delete(stationWithFault.id);
          return next;
        });
      }
    }
  };

  const handleAutofillRest = () => {
    const slide11 = getSlide11ShiftData();
    setShiftHours(prev => {
      return prev.map((curr, idx) => {
        if (manualHoursEntered.has(curr.hour)) {
          return curr;
        }
        return slide11[idx];
      });
    });
    setManualHoursEntered(new Set([1, 2, 3, 4, 5, 6, 7, 8]));
  };

  const handleResetShift = () => {
    const emptyHours = Array.from({ length: 8 }, (_, i) => 
      calculateHourlyKPI(i + 1, 0, 0, 0)
    );
    setShiftHours(emptyHours);
    setManualHoursEntered(new Set());
    setSelectedHour(1);
    setResolvedStations(new Set());
    setCompletedSteps({});
  };

  const handleResolveStation = (stationId: number) => {
    const station = LINE_STATIONS.find(s => s.id === stationId);
    const relatedCodes = station?.related_codes || [];

    setResolvedStations(prev => new Set([...prev, stationId]));

    setShiftHours(prev => 
      prev.map(h => {
        let downtimeToClear = false;
        let nokToClear = false;

        if (h.downtime_code && relatedCodes.includes(h.downtime_code)) {
          downtimeToClear = true;
        }
        if (h.nok_code && relatedCodes.includes(h.nok_code)) {
          nokToClear = true;
        }

        if (downtimeToClear || nokToClear) {
          const recoveredPcs = downtimeToClear ? h.produced_pcs + h.downtime_min : h.produced_pcs;
          const newDowntimeMin = downtimeToClear ? 0 : h.downtime_min;
          const newDowntimeCode = downtimeToClear ? null : h.downtime_code;
          const newDowntimeFrom = downtimeToClear ? null : h.downtime_from;
          const newDowntimeTo = downtimeToClear ? null : h.downtime_to;
          const newNokPcs = nokToClear ? 0 : h.nok_pcs;
          const newNokCode = nokToClear ? null : h.nok_code;

          return calculateHourlyKPI(
            h.hour,
            recoveredPcs,
            newNokPcs,
            newDowntimeMin,
            newDowntimeCode,
            newDowntimeFrom,
            newDowntimeTo,
            newNokCode
          );
        }
        return h;
      })
    );
  };

  const handleOpenMachineStation = (stationId: number) => {
    setSelectedStationId(stationId);
    setActiveTab('machine');
  };

  return (
    <div className="min-h-screen bg-[#F3F6F9] text-[#111827] flex flex-col font-sans selection:bg-[#E53935] selection:text-white">
      
      {/* 1. CityCare Navigation Header */}
      <HeaderNav
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        hasAlarms={Boolean(activeDowntimeCode || activeNokCode)}
      />

      {/* 2. Main Content Body according to Active Tab */}
      <main className="flex-1">
        {activeTab === 'shift' && (
          <>
            {/* Top Light Section (Overview, Glass Card & Area Chart) */}
            <TopSectionOverview
              analytics={analytics}
              shiftHours={shiftHours}
              manualHoursEntered={manualHoursEntered}
              onAutofillRest={handleAutofillRest}
              onResetShift={handleResetShift}
              onSelectHourForEdit={(h) => setSelectedHour(h)}
              onNavigateTab={(tab) => setActiveTab(tab)}
            />

            {/* Bottom Dark Obsidian Dock (Po-hodinový report, 3 Glowing Neon Cards, Alerts & Waterfall) */}
            <BottomSectionDetails
              analytics={analytics}
              shiftHours={shiftHours}
              selectedHour={selectedHour}
              onSelectHour={(h) => setSelectedHour(h)}
              onSaveHour={handleSaveHour}
              onOpenMachineStation={handleOpenMachineStation}
            />
          </>
        )}

        {activeTab === 'machine' && (
          <div className="py-2">
            <InteractiveStationDiagram
              activeDowntimeCode={activeDowntimeCode}
              activeNokCode={activeNokCode}
              onResolveStation={handleResolveStation}
              selectedStationId={selectedStationId}
              onSelectStation={(id) => setSelectedStationId(id)}
              resolvedStations={resolvedStations}
              completedSteps={completedSteps}
              onToggleStep={(stationId, stepIdx) => {
                const key = `${stationId}_${stepIdx}`;
                setCompletedSteps(prev => ({ ...prev, [key]: !prev[key] }));
              }}
            />
          </div>
        )}

        {activeTab === 'weekly' && (
          <div className="py-2">
            <WeeklyAnalyticsView />
          </div>
        )}

        {activeTab === 'monthly' && (
          <div className="py-2">
            <MonthlyAnalyticsView />
          </div>
        )}
      </main>

      {/* 3. Footer with Magna & CityCare Design System Info */}
      <footer className="w-full bg-[#09090B] border-t border-[#27272A] py-6 px-6 text-center text-xs text-[#6B7280]">
        <div className="max-w-[1440px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <div>
            <span className="font-bold text-[#E2E8F0]">Magna International Powertrain</span> • Systém riadenia OEE Linky L01
          </div>
          <div className="flex items-center gap-4 text-[11px]">
            <span>Norma CT = 60s (50 ks/h)</span>
            <span>•</span>
            <span>Cieľové OEE: 85.0%</span>
            <span>•</span>
            <span className="text-[#10B981]">CityCare Fusion UI</span>
          </div>
        </div>
      </footer>

    </div>
  );
}

export default App;
