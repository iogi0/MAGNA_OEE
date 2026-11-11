# Dashboard Wireframe Templates

## Framework

### Template 1 — Executive Dashboard (C-suite / Plant Manager)
5-second rule: Answers "Are we on track?"

```
┌──────────────────────────────────────────────────────────────────────┐
│  ROW 1 (Height: 1.5x)                                                │
│  [Scorecard: North Star OEE]  [Scorecard: Volume]  [Scorecard: Scrap]│
├──────────────────────────────────────────────────────────────────────┤
│  ROW 2 (Height: 2.5x)                                                │
│  [Line Chart: OEE 12-Month / Daily Trend]   [Bar: 4 KPI Breakdown]   │
├──────────────────────────────────────────────────────────────────────┤
│  ROW 3 (Height: 2x)                                                  │
│  [Waterfall Loss Cascade: 440 -> 349]       [Top 3 Systemic Alerts]  │
└──────────────────────────────────────────────────────────────────────┘
```

### Template 2 — Operational / Shift Dashboard (Shift Leader / Engineer)
Answers: "What requires attention on this shift right now?"

```
┌──────────────────────────────────────────────────────────────────────┐
│  ROW 1: Shift Header & Global Filters                                │
│  [Shift Date] [Line L01] [Planned Min: 440] [Target: 85%]            │
├──────────────────────────────────────────────────────────────────────┤
│  ROW 2: Real-time 4 KPI Scorecards                                   │
│  [Availability %] [Performance %] [Quality %] [Shift OEE %]          │
├──────────────────────────────────────────────────────────────────────┤
│  ROW 3: Hourly Progress & Tactical Input                             │
│  [Line: 8-Hour OEE Trend]        [Hourly Alarm & Production Input]   │
│  [Bar: Output vs Target per Hour] [Downtime ST-xxx / Scrap Q-xxx]    │
├──────────────────────────────────────────────────────────────────────┤
│  ROW 4: Action Center                                                │
│  [Top 3 Downtime Issues]         [Top 3 Quality Defects]             │
│  [Engineer Action Plan (Postup)] [AI Correlation & Root Cause]       │
└──────────────────────────────────────────────────────────────────────┘
```

### Template 3 — Diagnostic / Root Cause (Maintenance & Process Engineering)
Answers: "Why did Station X fail and how do we prevent recurrence?"

- Component health metrics
- MTBF (Mean Time Between Failures) & MTTR (Mean Time To Repair)
- 5-Why root cause drill-down
- SPC (Statistical Process Control) alarm logs
