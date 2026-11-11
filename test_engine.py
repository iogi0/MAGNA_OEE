"""
Unit tests for oee_engine.py against Magna Slide 11 Golden Values.
"""

from oee_engine import (
    calculate_hourly_kpi,
    calculate_shift_analytics,
    get_demo_shift_slide_11,
    get_demo_shift_worst_wednesday
)

def test_slide_11():
    shift_hours = get_demo_shift_slide_11()
    assert len(shift_hours) == 8, f"Expected 8 hours, got {len(shift_hours)}"
    
    res = calculate_shift_analytics(shift_hours)
    totals = res["totals"]
    kpi = res["kpi"]
    
    print("\n--- TEST: MAGNA SLIDE 11 SHIFT ---")
    print(f"Planned min: {totals['planned_min']} (expected 440)")
    print(f"Downtime min: {totals['downtime_min']} (expected 45)")
    print(f"Run min: {totals['run_min']} (expected 395)")
    print(f"Produced pcs: {totals['produced_pcs']} (expected 353)")
    print(f"NOK pcs: {totals['nok_pcs']} (expected 4)")
    print(f"Good pcs: {totals['good_pcs']} (expected 349)")
    print(f"Speed loss pcs: {totals['speed_loss_pcs']} (expected 42)")
    
    print(f"\nAvailability: {kpi['availability']:.3%} (expected 89.8%)")
    print(f"Performance:  {kpi['performance']:.3%} (expected 89.4%)")
    print(f"Quality:      {kpi['quality']:.3%} (expected 98.9%)")
    print(f"OEE:          {kpi['oee']:.3%} (expected 79.3%)")
    print(f"OEE Gap:      {kpi['oee_gap_pp']:.1f} pp (expected -5.7 pp)")
    
    assert totals['planned_min'] == 440
    assert totals['downtime_min'] == 45
    assert totals['run_min'] == 395
    assert totals['produced_pcs'] == 353
    assert totals['nok_pcs'] == 4
    assert totals['good_pcs'] == 349
    assert totals['speed_loss_pcs'] == 42
    
    assert abs(kpi['availability'] - 0.8977) < 0.002
    assert abs(kpi['performance'] - 0.8936) < 0.002
    assert abs(kpi['quality'] - 0.9886) < 0.002
    assert abs(kpi['oee'] - 0.7931) < 0.002
    
    # Waterfall identity check
    wf = res["waterfall"]
    calc_good = wf["ideal_target"] - wf["downtime_loss_pcs"] - wf["speed_loss_pcs"] - wf["quality_loss_pcs"]
    assert calc_good == wf["good_pieces"], f"Waterfall identity failed: {calc_good} != {wf['good_pieces']}"
    print("\n[OK] Waterfall identity: 440 - 45 (downtime) - 42 (speed) - 4 (NOK) = 349 (good)")
    
    # Check Top 3 Availability
    top3_a = res["top_3_availability"]
    print(f"[OK] Top Downtime: {[item['code'] + ' (' + str(item['total_min']) + ' min)' for item in top3_a]}")
    assert len(top3_a) == 2  # ST-038 (30 min), ST-046 (15 min)
    
    # Check Top 3 Quality
    top3_q = res["top_3_quality"]
    print(f"[OK] Top Quality: {[item['code'] + ' (' + str(item['total_nok']) + ' pcs)' for item in top3_q]}")
    
    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<\n")

if __name__ == "__main__":
    test_slide_11()
