export interface HourlySlot {
  hour: number;
  slot: string;
  am_min: number;
  break_min: number;
  planned_min: number;
  target_pcs: number;
}

export interface HourlyData {
  hour: number;
  slot: string;
  planned_min: number;
  target_pcs: number;
  produced_pcs: number;
  nok_pcs: number;
  good_pcs: number;
  downtime_min: number;
  downtime_code?: string | null;
  downtime_from?: string | null;
  downtime_to?: string | null;
  nok_code?: string | null;
  run_min: number;
  speed_loss_pcs: number;
  availability: number;
  performance: number;
  quality: number;
  oee: number;
}

export interface ShiftKPI {
  availability: number;
  performance: number;
  quality: number;
  oee: number;
  target_oee: number;
  oee_gap_pp: number;
  goal_met: boolean;
}

export interface ShiftTotals {
  planned_min: number;
  downtime_min: number;
  run_min: number;
  produced_pcs: number;
  nok_pcs: number;
  good_pcs: number;
  target_pcs: number;
  speed_loss_pcs: number;
}

export interface TopIssue {
  code: string;
  name: string;
  station: string;
  category: string;
  total_min?: number;
  total_nok?: number;
}

export interface WaterfallData {
  ideal_target: number;
  downtime_loss_pcs: number;
  speed_loss_pcs: number;
  actual_produced: number;
  quality_loss_pcs: number;
  good_pieces: number;
}

export interface ShiftAnalytics {
  kpi: ShiftKPI;
  totals: ShiftTotals;
  waterfall: WaterfallData;
  top_3_availability: TopIssue[];
  top_3_quality: TopIssue[];
}

export interface StationSensor {
  name: string;
  value: string;
  status: 'ok' | 'warning' | 'alarm';
}

export interface StationTelemetry {
  temp_c: number;
  pressure_bar: number;
  vibration_mm_s: number;
  cycle_time: number;
}

export interface StationTechInfo {
  id: number;
  name: string;
  name_en: string;
  tech: string;
  type: string;
  critical_part: string;
  related_codes: string[];
  sensors: StationSensor[];
  telemetry: StationTelemetry;
  description: string;
  five_why: string[];
  cause: string;
  remedy_steps: string[];
  lean_tool: string;
  lean_desc: string;
}
