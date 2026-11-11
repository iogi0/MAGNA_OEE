---
name: data-dashboard-design
description: Design effective data dashboards with proper KPI hierarchy, chart type selection, and interactive features. Use this skill when designing industrial dashboards, choosing visualizations, structuring executive vs operational metrics, or evaluating analytical interfaces.
metadata:
  category: "Analytics & UI"
  tags: ["dashboard", "data-visualization", "kpi", "industrial"]
---

# Dashboard Design

## Framework

```text
IRON LAW: One Dashboard, One Audience, One Purpose

A dashboard that tries to serve the CEO, the plant manager, AND the line
operators will serve none of them well. Each audience has different
questions, different metrics, and different time horizons.

Executive (Plant Manager): "Are we meeting monthly targets?" → OEE, volume, key trends
Operational (Shift Leader / Engineer): "Is the line running?" → Hourly OEE, downtimes, micro-stops
Diagnostic (Maintenance): "Why did it fail?" → Root cause ST-xxx/Q-xxx, 5-Why, sensor readings
```

### KPI Hierarchy (Pyramid Structure)

```text
          [North Star Metric: OEE %]
         /                          \
    [L1: 3 Core KPIs: Availability, Performance, Quality]
       /              |                  \
  [L2: Driving Metrics: Run Time, Output pcs, NOK pcs]
     /        |          |          |          \
[L3: Diagnostic / Root Causes: ST-xxx alarms, Q-xxx defects, cycle loss]
```

- **North Star**: ONE metric that best captures line productivity (**OEE %**)
- **L1**: The 3 pillars driving OEE: **Availability**, **Performance**, **Quality**
- **L2**: Operational metrics teams can act on (Run minutes, units per hour, scrap rate)
- **L3**: Diagnostic metrics for line troubleshooting (Specific error codes, sensor alarms, micro-stops)

### Chart Type Selection Matrix

| Question | Chart | Why |
|---|---|---|
| How is the trend over time? | **Line chart** | Shows change over shift hours / weeks |
| How do categories compare? | **Bar chart** (horizontal for Pareto) | Easy comparison of failure causes |
| What's the loss cascade? | **Waterfall chart** | Visualizes step-by-step reduction from 100% Target to Good parts |
| What's the distribution? | **Histogram** or **Box plot** | Shows spread of cycle times and outliers |
| What's the relationship? | **Scatter plot** | Shows correlation between downtimes and defects |
| What's the single number? | **Scorecard / Big number KPI** | At-a-glance status with delta to goal |
| How are we vs target? | **Bullet chart** or **Progress gauge** | Visual comparison against 85% goal |

### Industrial Dashboard Design Principles

1. **5-second rule**: The shift's primary health status (OEE on target or below target) must be obvious within 5 seconds.
2. **Above the fold**: The 4 primary KPIs and current shift trend must be visible without scrolling.
3. **Color with purpose**: Red = Below Target / Failure, Green = On Target / Normal, Amber = Warning / Downtime, Blue = System / AI.
4. **Contextual comparison**: Never show a raw number without comparison context (vs Target 85%, vs yesterday, vs planned).
5. **Progressive disclosure**: Executive summary at top $\rightarrow$ Hourly breakdown in middle $\rightarrow$ Detailed root-cause drill-down at bottom.
