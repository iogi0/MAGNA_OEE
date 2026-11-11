"""
OEE Engine: Core mathematical and analytical module for Magna Assembly Line L01.
Implements exact formulas and loss cascade according to Magna standards.
"""

from typing import Dict, List, Any, Optional
from constants import (
    HOURLY_SLOTS,
    SHIFT_PLANNED_MIN,
    TARGET_OEE,
    TARGET_PIECES_100,
    DOWNTIME_CATALOG,
    QUALITY_CATALOG
)


def calculate_hourly_kpi(
    hour: int,
    produced_pcs: int,
    nok_pcs: int = 0,
    downtime_min: int = 0,
    downtime_code: Optional[str] = None,
    downtime_from: Optional[str] = None,
    downtime_to: Optional[str] = None,
    nok_code: Optional[str] = None,
    comment: str = ""
) -> Dict[str, Any]:
    """Calculate KPIs and loss breakdown for a single hour (1 to 8)."""
    slot_info = HOURLY_SLOTS.get(hour, HOURLY_SLOTS[1])
    planned_min = slot_info["planned_min"]
    target_pcs = slot_info["target_pcs"]
    
    # Run time
    downtime_min = max(0, min(downtime_min, planned_min))
    run_min = max(0, planned_min - downtime_min)
    
    # Output and scrap
    produced_pcs = max(0, produced_pcs)
    nok_pcs = max(0, min(nok_pcs, produced_pcs))
    good_pcs = produced_pcs - nok_pcs
    
    # Losses
    possible_in_run = run_min  # 1 min = 1 pc at 60s ideal cycle
    speed_loss_pcs = max(0, possible_in_run - produced_pcs)
    
    # KPIs
    availability = (run_min / planned_min) if planned_min > 0 else 0.0
    performance = (produced_pcs / run_min) if run_min > 0 else 0.0
    quality = (good_pcs / produced_pcs) if produced_pcs > 0 else 1.0
    oee = availability * performance * quality
    
    return {
        "hour": hour,
        "slot": slot_info["slot"],
        "planned_min": planned_min,
        "target_pcs": target_pcs,
        "downtime_min": downtime_min,
        "run_min": run_min,
        "produced_pcs": produced_pcs,
        "nok_pcs": nok_pcs,
        "good_pcs": good_pcs,
        "speed_loss_pcs": speed_loss_pcs,
        "downtime_code": downtime_code,
        "downtime_from": downtime_from,
        "downtime_to": downtime_to,
        "nok_code": nok_code,
        "comment": comment,
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "oee": oee,
        "goal_met": oee >= TARGET_OEE
    }


def calculate_shift_analytics(hours_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate all submitted hours for the shift and calculate cumulative KPIs.
    All aggregations are strictly computed from primary sums, never averaged percentages.
    """
    tot_planned_min = sum(h["planned_min"] for h in hours_data)
    tot_downtime_min = sum(h["downtime_min"] for h in hours_data)
    tot_run_min = sum(h["run_min"] for h in hours_data)
    tot_produced = sum(h["produced_pcs"] for h in hours_data)
    tot_nok = sum(h["nok_pcs"] for h in hours_data)
    tot_good = sum(h["good_pcs"] for h in hours_data)
    tot_speed_loss = sum(h["speed_loss_pcs"] for h in hours_data)
    
    # 4 Core Shift KPIs
    availability = (tot_run_min / tot_planned_min) if tot_planned_min > 0 else 0.0
    performance = (tot_produced / tot_run_min) if tot_run_min > 0 else 0.0
    quality = (tot_good / tot_produced) if tot_produced > 0 else 1.0
    oee = availability * performance * quality
    
    # Gap analysis
    oee_gap_pp = (oee - TARGET_OEE) * 100.0
    ideal_target = tot_planned_min  # for full shift: 440
    pieces_gap = tot_good - int(ideal_target * TARGET_OEE)  # vs 374 good pieces
    
    # Top 3 Downtime Issues
    downtime_summary = {}
    for h in hours_data:
        code = h.get("downtime_code")
        d_min = h.get("downtime_min", 0)
        if code and d_min > 0:
            if code not in downtime_summary:
                info = DOWNTIME_CATALOG.get(code, {})
                downtime_summary[code] = {
                    "code": code,
                    "station": info.get("station", "Stanica ?"),
                    "name": info.get("name_sk", code),
                    "category": info.get("category", "General"),
                    "total_min": 0,
                    "count": 0
                }
            downtime_summary[code]["total_min"] += d_min
            downtime_summary[code]["count"] += 1
            
    top_3_availability = sorted(
        downtime_summary.values(),
        key=lambda x: x["total_min"],
        reverse=True
    )[:3]
    
    # Top 3 Quality Issues
    quality_summary = {}
    for h in hours_data:
        code = h.get("nok_code")
        nok_qty = h.get("nok_pcs", 0)
        if code and nok_qty > 0:
            if code not in quality_summary:
                info = QUALITY_CATALOG.get(code, {})
                quality_summary[code] = {
                    "code": code,
                    "station": info.get("station", "Stanica ?"),
                    "name": info.get("name_sk", code),
                    "category": info.get("category", "General"),
                    "total_nok": 0,
                    "count": 0
                }
            quality_summary[code]["total_nok"] += nok_qty
            quality_summary[code]["count"] += 1
            
    top_3_quality = sorted(
        quality_summary.values(),
        key=lambda x: x["total_nok"],
        reverse=True
    )[:3]
    
    # Loss Cascade / Waterfall Breakdown:
    # 440 ideal -> -Downtime -> -Speed loss -> Produced -> -NOK -> Good
    waterfall = {
        "ideal_target": ideal_target,
        "downtime_loss_pcs": tot_downtime_min,
        "possible_in_run": ideal_target - tot_downtime_min,
        "speed_loss_pcs": tot_speed_loss,
        "actual_produced": tot_produced,
        "quality_loss_pcs": tot_nok,
        "good_pieces": tot_good
    }
    
    return {
        "totals": {
            "planned_min": tot_planned_min,
            "downtime_min": tot_downtime_min,
            "run_min": tot_run_min,
            "produced_pcs": tot_produced,
            "nok_pcs": tot_nok,
            "good_pcs": tot_good,
            "speed_loss_pcs": tot_speed_loss,
        },
        "kpi": {
            "availability": availability,
            "performance": performance,
            "quality": quality,
            "oee": oee,
            "target_oee": TARGET_OEE,
            "oee_gap_pp": oee_gap_pp,
            "pieces_gap": pieces_gap,
            "goal_met": oee >= TARGET_OEE
        },
        "top_3_availability": top_3_availability,
        "top_3_quality": top_3_quality,
        "waterfall": waterfall,
        "hourly_series": hours_data
    }


def get_demo_shift_slide_11() -> List[Dict[str, Any]]:
    """
    Returns the real reference shift from Magna Slide 11:
    OEE: 79.3% (A=89.8%, P=89.4%, Q=98.9%)
    Downtime: 45 min (30 min Camera ST-038 in 4th hour, 15 min Leak test ST-046 in 3rd hour)
    Produced: 353 pcs, NOK: 4 pcs (2 pressing Q-020, 2 screw torque Q-026) -> 349 Good pcs.
    Hourly output: 48, 57, 40, 20, 25, 52, 55, 56.
    """
    shift = [
        # Hour 1: 06:00-07:00 (50 min planned), 48 produced, slow ramp-up
        calculate_hourly_kpi(1, produced_pcs=48, nok_pcs=0, downtime_min=0),
        # Hour 2: 07:00-08:00 (60 min planned), 57 produced
        calculate_hourly_kpi(2, produced_pcs=57, nok_pcs=1, downtime_min=0, nok_code="Q-020"),
        # Hour 3: 08:00-09:00 (60 min planned), 15 min Leak test stop (ST-046), 40 produced
        calculate_hourly_kpi(3, produced_pcs=40, nok_pcs=0, downtime_min=15, downtime_code="ST-046", downtime_from="08:15", downtime_to="08:30"),
        # Hour 4: 09:00-10:00 (60 min planned), 30 min Camera stop (ST-038), 20 produced
        calculate_hourly_kpi(4, produced_pcs=20, nok_pcs=1, downtime_min=30, downtime_code="ST-038", downtime_from="09:10", downtime_to="09:40", nok_code="Q-030"),
        # Hour 5: 10:00-11:00 (30 min planned, 30 min lunch), 25 produced
        calculate_hourly_kpi(5, produced_pcs=25, nok_pcs=0, downtime_min=0),
        # Hour 6: 11:00-12:00 (60 min planned), 52 produced
        calculate_hourly_kpi(6, produced_pcs=52, nok_pcs=1, downtime_min=0, nok_code="Q-026"),
        # Hour 7: 12:00-13:00 (60 min planned), 55 produced
        calculate_hourly_kpi(7, produced_pcs=55, nok_pcs=1, downtime_min=0, nok_code="Q-020"),
        # Hour 8: 13:00-14:00 (60 min planned), 56 produced
        calculate_hourly_kpi(8, produced_pcs=56, nok_pcs=0, downtime_min=0),
    ]
    return shift


def get_demo_shift_worst_wednesday() -> List[Dict[str, Any]]:
    """
    Returns Shift 2026-11-25 (Worst shift from Magna Excel, OEE 78.18%):
    48 min downtime, 350 produced, 6 NOK -> 344 good.
    """
    shift = [
        calculate_hourly_kpi(1, produced_pcs=42, nok_pcs=0, downtime_min=0),
        calculate_hourly_kpi(2, produced_pcs=44, nok_pcs=1, downtime_min=13, downtime_code="ST-046", downtime_from="07:08", downtime_to="07:21", nok_code="Q-030"),
        calculate_hourly_kpi(3, produced_pcs=54, nok_pcs=1, downtime_min=0, nok_code="Q-031"),
        calculate_hourly_kpi(4, produced_pcs=31, nok_pcs=0, downtime_min=25, downtime_code="ST-038", downtime_from="09:08", downtime_to="09:33"),
        calculate_hourly_kpi(5, produced_pcs=25, nok_pcs=1, downtime_min=0, nok_code="Q-030"),
        calculate_hourly_kpi(6, produced_pcs=46, nok_pcs=2, downtime_min=10, downtime_code="ST-046", downtime_from="11:08", downtime_to="11:18", nok_code="Q-020"),
        calculate_hourly_kpi(7, produced_pcs=54, nok_pcs=1, downtime_min=0, nok_code="Q-020"),
        calculate_hourly_kpi(8, produced_pcs=54, nok_pcs=0, downtime_min=0),
    ]
    return shift
