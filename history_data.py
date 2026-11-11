"""
Historical and monthly data from Magna Hackathon dataset (21 shifts, November 2026).
Powers the Manager View (Weekly / Monthly summary & trend analysis).
"""

from typing import Dict, List, Any

# 21 Daily shifts
MONTH_SHIFTS: List[Dict[str, Any]] = [
    {"date": "2026-11-02", "day": "Po", "plan_min": 440, "downtime_min": 23, "produced": 393, "ok": 384, "nok": 9, "a": 0.9477, "p": 0.9424, "q": 0.9771, "oee": 0.8727, "goal_met": True},
    {"date": "2026-11-03", "day": "Ut", "plan_min": 440, "downtime_min": 17, "produced": 403, "ok": 396, "nok": 7, "a": 0.9614, "p": 0.9527, "q": 0.9826, "oee": 0.9000, "goal_met": True},
    {"date": "2026-11-04", "day": "St", "plan_min": 440, "downtime_min": 35, "produced": 366, "ok": 359, "nok": 7, "a": 0.9205, "p": 0.9037, "q": 0.9809, "oee": 0.8159, "goal_met": False},
    {"date": "2026-11-05", "day": "Št", "plan_min": 440, "downtime_min": 28, "produced": 391, "ok": 388, "nok": 3, "a": 0.9364, "p": 0.9490, "q": 0.9923, "oee": 0.8818, "goal_met": True},
    {"date": "2026-11-06", "day": "Pi", "plan_min": 440, "downtime_min": 9,  "produced": 407, "ok": 402, "nok": 5, "a": 0.9795, "p": 0.9443, "q": 0.9877, "oee": 0.9136, "goal_met": True},
    
    {"date": "2026-11-09", "day": "Po", "plan_min": 440, "downtime_min": 11, "produced": 403, "ok": 397, "nok": 6, "a": 0.9750, "p": 0.9394, "q": 0.9851, "oee": 0.9023, "goal_met": True},
    {"date": "2026-11-10", "day": "Ut", "plan_min": 440, "downtime_min": 15, "produced": 400, "ok": 394, "nok": 6, "a": 0.9659, "p": 0.9412, "q": 0.9850, "oee": 0.8955, "goal_met": True},
    {"date": "2026-11-11", "day": "St", "plan_min": 440, "downtime_min": 36, "produced": 368, "ok": 362, "nok": 6, "a": 0.9182, "p": 0.9109, "q": 0.9837, "oee": 0.8227, "goal_met": False},
    {"date": "2026-11-12", "day": "Št", "plan_min": 440, "downtime_min": 15, "produced": 397, "ok": 392, "nok": 5, "a": 0.9659, "p": 0.9341, "q": 0.9874, "oee": 0.8909, "goal_met": True},
    {"date": "2026-11-13", "day": "Pi", "plan_min": 440, "downtime_min": 15, "produced": 394, "ok": 391, "nok": 3, "a": 0.9659, "p": 0.9271, "q": 0.9924, "oee": 0.8886, "goal_met": True},

    {"date": "2026-11-16", "day": "Po", "plan_min": 440, "downtime_min": 9,  "produced": 407, "ok": 398, "nok": 9, "a": 0.9795, "p": 0.9443, "q": 0.9779, "oee": 0.9045, "goal_met": True},
    {"date": "2026-11-17", "day": "Ut", "plan_min": 440, "downtime_min": 15, "produced": 399, "ok": 393, "nok": 6, "a": 0.9659, "p": 0.9388, "q": 0.9850, "oee": 0.8932, "goal_met": True},
    {"date": "2026-11-18", "day": "St", "plan_min": 440, "downtime_min": 25, "produced": 377, "ok": 370, "nok": 7, "a": 0.9432, "p": 0.9084, "q": 0.9814, "oee": 0.8409, "goal_met": False},
    {"date": "2026-11-19", "day": "Št", "plan_min": 440, "downtime_min": 15, "produced": 396, "ok": 392, "nok": 4, "a": 0.9659, "p": 0.9318, "q": 0.9899, "oee": 0.8909, "goal_met": True},
    {"date": "2026-11-20", "day": "Pi", "plan_min": 440, "downtime_min": 9,  "produced": 408, "ok": 404, "nok": 4, "a": 0.9795, "p": 0.9466, "q": 0.9902, "oee": 0.9182, "goal_met": True},

    {"date": "2026-11-23", "day": "Po", "plan_min": 440, "downtime_min": 23, "produced": 394, "ok": 390, "nok": 4, "a": 0.9477, "p": 0.9448, "q": 0.9898, "oee": 0.8864, "goal_met": True},
    {"date": "2026-11-24", "day": "Ut", "plan_min": 440, "downtime_min": 16, "produced": 399, "ok": 394, "nok": 5, "a": 0.9636, "p": 0.9410, "q": 0.9875, "oee": 0.8955, "goal_met": True},
    {"date": "2026-11-25", "day": "St", "plan_min": 440, "downtime_min": 48, "produced": 350, "ok": 344, "nok": 6, "a": 0.8909, "p": 0.8929, "q": 0.9829, "oee": 0.7818, "goal_met": False},
    {"date": "2026-11-26", "day": "Št", "plan_min": 440, "downtime_min": 15, "produced": 400, "ok": 393, "nok": 7, "a": 0.9659, "p": 0.9412, "q": 0.9825, "oee": 0.8932, "goal_met": True},
    {"date": "2026-11-27", "day": "Pi", "plan_min": 440, "downtime_min": 18, "produced": 397, "ok": 395, "nok": 2, "a": 0.9591, "p": 0.9408, "q": 0.9950, "oee": 0.8977, "goal_met": True},

    {"date": "2026-11-30", "day": "Po", "plan_min": 440, "downtime_min": 13, "produced": 402, "ok": 394, "nok": 8, "a": 0.9705, "p": 0.9415, "q": 0.9801, "oee": 0.8955, "goal_met": True},
]

# Weekly summaries
WEEKLY_SUMMARIES = [
    {"week": "Týždeň 45 (02-06.11)", "shifts": 5, "target": 2200, "produced": 1960, "good": 1929, "nok": 31, "downtime_min": 112, "a": 0.9491, "p": 0.9387, "q": 0.9842, "oee": 0.8768, "goal_met": True},
    {"week": "Týždeň 46 (09-13.11)", "shifts": 5, "target": 2200, "produced": 1962, "good": 1936, "nok": 26, "downtime_min": 92,  "a": 0.9582, "p": 0.9307, "q": 0.9867, "oee": 0.8800, "goal_met": True},
    {"week": "Týždeň 47 (16-20.11)", "shifts": 5, "target": 2200, "produced": 1987, "good": 1957, "nok": 30, "downtime_min": 73,  "a": 0.9668, "p": 0.9342, "q": 0.9849, "oee": 0.8895, "goal_met": True},
    {"week": "Týždeň 48 (23-27.11)", "shifts": 5, "target": 2200, "produced": 1940, "good": 1916, "nok": 24, "downtime_min": 120, "a": 0.9455, "p": 0.9327, "q": 0.9876, "oee": 0.8709, "goal_met": True},
    {"week": "Týždeň 49 (30.11)",    "shifts": 1, "target": 440,  "produced": 402,  "good": 394,  "nok": 8,  "downtime_min": 13,  "a": 0.9705, "p": 0.9415, "q": 0.9801, "oee": 0.8955, "goal_met": True},
]

# Month Total
MONTH_TOTALS = {
    "shifts_count": 21,
    "shifts_on_target": 17,
    "planned_min": 9240,
    "target_pcs": 9240,
    "downtime_min": 410,
    "run_min": 8830,
    "produced": 8251,
    "ok": 8132,
    "nok": 119,
    "speed_loss_pcs": 579,
    "availability": 0.9556,
    "performance": 0.9344,
    "quality": 0.9856,
    "oee": 0.8801,
    "target_oee": 0.8500,
    "oee_gap_pp": 3.01
}
