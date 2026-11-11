import { HourlyData, ShiftAnalytics, TopIssue } from '../types';
import { HOURLY_SLOTS, DOWNTIME_CATALOG, QUALITY_CATALOG, SLIDE_11_RAW, SHIFT_PLANNED_MIN, TARGET_OEE } from '../data/constants';

export function calculateHourlyKPI(
  hour: number,
  produced_pcs: number,
  nok_pcs: number,
  downtime_min: number,
  downtime_code: string | null = null,
  downtime_from: string | null = null,
  downtime_to: string | null = null,
  nok_code: string | null = null
): HourlyData {
  const slotInfo = HOURLY_SLOTS[hour];
  const planned_min = slotInfo.planned_min;
  const target_pcs = slotInfo.target_pcs;

  const valid_downtime = Math.min(downtime_min, planned_min);
  const run_min = Math.max(0, planned_min - valid_downtime);

  const good_pcs = Math.max(0, produced_pcs - nok_pcs);
  const speed_loss_pcs = Math.max(0, run_min - produced_pcs);

  const availability = planned_min > 0 ? run_min / planned_min : 0;
  const performance = run_min > 0 ? Math.min(1.0, produced_pcs / run_min) : 0;
  const quality = produced_pcs > 0 ? good_pcs / produced_pcs : 1.0;
  const oee = availability * performance * quality;

  return {
    hour,
    slot: slotInfo.slot,
    planned_min,
    target_pcs,
    produced_pcs,
    nok_pcs,
    good_pcs,
    downtime_min: valid_downtime,
    downtime_code,
    downtime_from,
    downtime_to,
    nok_code,
    run_min,
    speed_loss_pcs,
    availability,
    performance,
    quality,
    oee,
  };
}

export function calculateShiftAnalytics(hours: HourlyData[]): ShiftAnalytics {
  let planned_min = 0;
  let downtime_min = 0;
  let run_min = 0;
  let produced_pcs = 0;
  let nok_pcs = 0;
  let good_pcs = 0;
  let target_pcs = 0;

  const downtime_agg: Record<string, { total_min: number; station: string; name: string; category: string }> = {};
  const quality_agg: Record<string, { total_nok: number; station: string; name: string; category: string }> = {};

  for (const h of hours) {
    planned_min += h.planned_min;
    downtime_min += h.downtime_min;
    run_min += h.run_min;
    produced_pcs += h.produced_pcs;
    nok_pcs += h.nok_pcs;
    good_pcs += h.good_pcs;
    target_pcs += h.target_pcs;

    if (h.downtime_code && h.downtime_min > 0) {
      const code = h.downtime_code;
      const cat = DOWNTIME_CATALOG[code] || { name_sk: code, station: "Neznáma", category: "Všeobecné" };
      if (!downtime_agg[code]) {
        downtime_agg[code] = { total_min: 0, station: cat.station, name: cat.name_sk, category: cat.category };
      }
      downtime_agg[code].total_min += h.downtime_min;
    }

    if (h.nok_code && h.nok_pcs > 0) {
      const code = h.nok_code;
      const cat = QUALITY_CATALOG[code] || { name_sk: code, station: "Neznáma", category: "Kvalita" };
      if (!quality_agg[code]) {
        quality_agg[code] = { total_nok: 0, station: cat.station, name: cat.name_sk, category: cat.category };
      }
      quality_agg[code].total_nok += h.nok_pcs;
    }
  }

  const speed_loss_pcs = Math.max(0, run_min - produced_pcs);

  const availability = planned_min > 0 ? run_min / planned_min : 0;
  const performance = run_min > 0 ? Math.min(1.0, produced_pcs / run_min) : 0;
  const quality = produced_pcs > 0 ? good_pcs / produced_pcs : 1.0;
  const oee = availability * performance * quality;
  const oee_gap_pp = (oee - TARGET_OEE) * 100;
  const goal_met = oee >= TARGET_OEE;

  // Top 3 Availability Issues
  const top_3_availability: TopIssue[] = Object.entries(downtime_agg)
    .sort((a, b) => b[1].total_min - a[1].total_min)
    .slice(0, 3)
    .map(([code, item]) => ({
      code,
      name: item.name,
      station: item.station,
      category: item.category,
      total_min: item.total_min,
    }));

  // Top 3 Quality Issues
  const top_3_quality: TopIssue[] = Object.entries(quality_agg)
    .sort((a, b) => b[1].total_nok - a[1].total_nok)
    .slice(0, 3)
    .map(([code, item]) => ({
      code,
      name: item.name,
      station: item.station,
      category: item.category,
      total_nok: item.total_nok,
    }));

  const waterfall = {
    ideal_target: planned_min,
    downtime_loss_pcs: downtime_min,
    speed_loss_pcs: speed_loss_pcs,
    actual_produced: produced_pcs,
    quality_loss_pcs: nok_pcs,
    good_pieces: good_pcs,
  };

  return {
    kpi: {
      availability,
      performance,
      quality,
      oee,
      target_oee: TARGET_OEE,
      oee_gap_pp,
      goal_met,
    },
    totals: {
      planned_min,
      downtime_min,
      run_min,
      produced_pcs,
      nok_pcs,
      good_pcs,
      target_pcs,
      speed_loss_pcs,
    },
    waterfall,
    top_3_availability,
    top_3_quality,
  };
}

export function getSlide11ShiftData(): HourlyData[] {
  return SLIDE_11_RAW.map((h) =>
    calculateHourlyKPI(
      h.hour,
      h.produced_pcs,
      h.nok_pcs,
      h.downtime_min,
      h.downtime_code,
      (h as any).downtime_from || null,
      (h as any).downtime_to || null,
      h.nok_code
    )
  );
}
