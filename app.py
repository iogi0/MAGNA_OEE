"""
Magna Hackathon - Zadanie 5: AI OEE Improvement Engine
Web application for Production Manager & Shift Engineer.
Designed strictly according to CityCare Dashboard Specification:
- High contrast Light/Dark mode fusion
- Top Section: Light theme (#F3F6F9) with White Cards (#FFFFFF) and Dark Slate text (#111827)
- Bottom Section: Dark theme (#09090B, border-radius: 40px 40px 0 0) with Neon Glow Cards (#18181B)
- Live Demo Pitch: Manual Entry + Auto-completion of remaining hours + Reset button
- Navigation across: Aktuálna zmena (Shift), Týždenný prehľad (7 dní), Mesačný prehľad (30 dní)
- 100% Slovak language in the entire UI.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from constants import (
    HOURLY_SLOTS,
    SHIFT_PLANNED_MIN,
    TARGET_OEE,
    TARGET_PIECES_100,
    DOWNTIME_CATALOG,
    QUALITY_CATALOG
)
from oee_engine import (
    calculate_hourly_kpi,
    calculate_shift_analytics,
    get_demo_shift_slide_11
)
from history_data import MONTH_SHIFTS, WEEKLY_SUMMARIES, MONTH_TOTALS
from ai_engine import analyze_with_qwen

# Page configuration
st.set_page_config(
    page_title="Magna AI OEE Engine",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CityCare Design System CSS Specification
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=JetBrains+Mono:wght@400;600;700;800&display=swap');

    html, body, [class*="css"], .stMarkdown {
        font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Tabular monospace numbers for KPIs */
    .tabular-num {
        font-family: 'JetBrains Mono', monospace !important;
        font-variant-numeric: tabular-nums !important;
    }

    /* --- TOP SECTION (LIGHT THEME #F3F6F9) --- */
    .citycare-top {
        background-color: #F3F6F9;
        padding: 16px 20px 24px 20px;
        border-radius: 24px;
        margin-bottom: 20px;
        border: 1px solid #E5E7EB;
    }

    .white-card {
        background: #FFFFFF !important;
        border-radius: 24px !important;
        padding: 20px 22px !important;
        box-shadow: 0px 4px 24px rgba(0, 0, 0, 0.04) !important;
        border: 1px solid rgba(0, 0, 0, 0.04) !important;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .white-card:hover {
        transform: translateY(-4px);
        box-shadow: 0px 12px 32px rgba(0, 0, 0, 0.08) !important;
    }

    .glass-card {
        border-radius: 28px !important;
        background: linear-gradient(135deg, rgba(255,255,255,0.75) 0%, rgba(255,255,255,0.25) 100%) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255,255,255,0.6) !important;
        box-shadow: 0px 8px 32px rgba(0, 0, 0, 0.04) !important;
        padding: 22px !important;
    }

    .text-dark-slate {
        color: #111827 !important;
    }
    .text-sub {
        color: #6B7280 !important;
    }

    /* Navigation Pills */
    .pill-nav {
        display: inline-flex;
        background: #E5E7EB;
        padding: 4px;
        border-radius: 999px;
        margin-bottom: 16px;
    }
    .pill-btn {
        padding: 8px 20px;
        border-radius: 999px;
        font-size: 0.88rem;
        font-weight: 600;
        text-decoration: none;
        color: #6B7280;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .pill-btn-active {
        background-color: #111827;
        color: #FFFFFF !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }

    /* --- BOTTOM SECTION (DARK THEME #09090B) --- */
    .citycare-bottom {
        background-color: #09090B !important;
        border-radius: 40px 40px 0 0 !important;
        padding: 36px 30px 44px 30px !important;
        margin-top: 24px;
        box-shadow: 0 -10px 40px rgba(0, 0, 0, 0.5) !important;
        color: #F8FAFC !important;
    }

    .dark-card {
        background: #18181B !important;
        border-radius: 20px !important;
        padding: 20px !important;
        border: 1px solid #27272A !important;
        color: #F8FAFC !important;
    }

    /* Neon Glow Cards */
    .glow-green {
        background: #18181B !important;
        border: 1.5px solid #10B981 !important;
        border-radius: 20px !important;
        box-shadow: 0 0 22px rgba(16, 185, 129, 0.22), inset 0 1px 0 rgba(16, 185, 129, 0.3) !important;
        padding: 20px !important;
        margin-bottom: 14px !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        color: #F8FAFC !important;
    }
    .glow-green:hover {
        transform: translateY(-2px);
        box-shadow: 0 0 30px rgba(16, 185, 129, 0.35) !important;
    }

    .glow-orange {
        background: #18181B !important;
        border: 1.5px solid #F59E0B !important;
        border-radius: 20px !important;
        box-shadow: 0 0 22px rgba(245, 158, 11, 0.22), inset 0 1px 0 rgba(245, 158, 11, 0.3) !important;
        padding: 20px !important;
        margin-bottom: 14px !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        color: #F8FAFC !important;
    }
    .glow-orange:hover {
        transform: translateY(-2px);
        box-shadow: 0 0 30px rgba(245, 158, 11, 0.35) !important;
    }

    .glow-blue {
        background: #18181B !important;
        border: 1.5px solid #3B82F6 !important;
        border-radius: 20px !important;
        box-shadow: 0 0 22px rgba(59, 130, 246, 0.22), inset 0 1px 0 rgba(59, 130, 246, 0.3) !important;
        padding: 20px !important;
        margin-bottom: 14px !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        color: #F8FAFC !important;
    }
    .glow-blue:hover {
        transform: translateY(-2px);
        box-shadow: 0 0 30px rgba(59, 130, 246, 0.35) !important;
    }

    .glow-red {
        background: #18181B !important;
        border: 1.5px solid #EF4444 !important;
        border-radius: 20px !important;
        box-shadow: 0 0 22px rgba(239, 68, 68, 0.22), inset 0 1px 0 rgba(239, 68, 68, 0.3) !important;
        padding: 20px !important;
        margin-bottom: 14px !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        color: #F8FAFC !important;
    }
    .glow-red:hover {
        transform: translateY(-2px);
        box-shadow: 0 0 30px rgba(239, 68, 68, 0.35) !important;
    }

    /* Badges */
    .badge-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-pill-green {
        background: rgba(16, 185, 129, 0.15);
        color: #10B981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-pill-red {
        background: rgba(239, 68, 68, 0.15);
        color: #EF4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .badge-pill-orange {
        background: rgba(245, 158, 11, 0.15);
        color: #F59E0B;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .badge-pill-blue {
        background: rgba(59, 130, 246, 0.15);
        color: #3B82F6;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }

    /* AI output container */
    .box-ai-output {
        background: #111420 !important;
        border: 1px solid #4F46E5 !important;
        border-left: 5px solid #818CF8 !important;
        border-radius: 14px;
        padding: 18px;
        margin-top: 14px;
        color: #F8FAFC !important;
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)


# --- SESSION STATE INITIALIZATION ---
if "shift_hours" not in st.session_state:
    st.session_state["shift_hours"] = get_demo_shift_slide_11()

if "manual_hours_entered" not in st.session_state:
    st.session_state["manual_hours_entered"] = set(range(1, 9))

if "show_analytics" not in st.session_state:
    st.session_state["show_analytics"] = True

if "ai_analysis_result" not in st.session_state:
    st.session_state["ai_analysis_result"] = None

if "nav_view" not in st.session_state:
    st.session_state["nav_view"] = "shift"


# --- SIDEBAR: ONLY 2 BUTTONS (SLOVAK) ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Magna_International_logo.svg/320px-Magna_International_logo.svg.png", width=175)
    st.markdown("<h3 style='margin-top:10px; margin-bottom:2px; color:#FFFFFF;'>🛠️ AI OEE Engine</h3>", unsafe_allow_html=True)
    st.caption("Montážna linka elektrických pohonov (L01) • Magna PT")
    st.divider()

    st.markdown("#### ⚡ Prezentácia (Live Demo):")

    # Button 1: Auto-fill remaining hours (Slovak)
    if st.button("🪄 Automaticky doplniť zvyšok zmeny", use_container_width=True, help="Ponechá manuálne zadané hodiny a automaticky doplní zvyšok zmeny etalónovými dátami."):
        slide11 = get_demo_shift_slide_11()
        for h in range(1, 9):
            if h not in st.session_state["manual_hours_entered"]:
                st.session_state["shift_hours"][h - 1] = slide11[h - 1]
                st.session_state["manual_hours_entered"].add(h)
        st.session_state["show_analytics"] = True
        st.session_state["ai_analysis_result"] = None
        st.success("Zvyšok zmeny bol úspešne doplnený!")
        st.rerun()

    # Button 2: Reset shift for fresh live demo (Slovak)
    if st.button("🔄 Resetovať zmenu (Nový Live Demo)", use_container_width=True, help="Vyčistí všetky hodiny na 0, aby ste mohli začať živú prezentáciu od začiatku."):
        st.session_state["shift_hours"] = [
            calculate_hourly_kpi(h, produced_pcs=0, nok_pcs=0, downtime_min=0)
            for h in range(1, 9)
        ]
        st.session_state["manual_hours_entered"] = set()
        st.session_state["show_analytics"] = False
        st.session_state["ai_analysis_result"] = None
        st.rerun()

    st.divider()
    st.markdown("""
    <div style="background:#18181B; border:1px solid #27272A; border-radius:14px; padding:12px; font-size:0.82rem; color:#CBD5E1;">
        <b style="color:#FFFFFF;">ℹ️ Parametre výrobnej linky:</b><br>
        • Ideálny takt: <b style="color:#38BDF8;">60 s / ks</b><br>
        • Plánovaný čas: <b style="color:#38BDF8;">440 min</b> (480 - 40 prestávka)<br>
        • Cieľ OEE: <b style="color:#10B981;">85.0%</b><br>
        • Lokálny AI model: <b style="color:#A855F7;">Qwen 2.5 3B (Ollama)</b>
    </div>
    """, unsafe_allow_html=True)


# --- TOP NAVIGATION PILL BAR (CITYCARE HEADER) ---
col_logo, col_nav = st.columns([1.5, 2.5])
with col_logo:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:12px;">
        <h2 style="margin:0; font-weight:800; color:#111827; letter-spacing:-0.5px;">Magna OEE</h2>
        <span class="badge-pill badge-pill-blue">Line L01</span>
    </div>
    <p style="margin:2px 0 14px 0; font-size:0.88rem; color:#6B7280;">Elektromobilita • Výrobný monitoring a AI Copilot</p>
    """, unsafe_allow_html=True)

with col_nav:
    # 3 Pill View Buttons
    nav_cols = st.columns(3)
    with nav_cols[0]:
        if st.button("⏱️ Aktuálna zmena", use_container_width=True, type="primary" if st.session_state["nav_view"] == "shift" else "secondary"):
            st.session_state["nav_view"] = "shift"
            st.rerun()
    with nav_cols[1]:
        if st.button("📅 Týždenný prehľad (7 dní)", use_container_width=True, type="primary" if st.session_state["nav_view"] == "weekly" else "secondary"):
            st.session_state["nav_view"] = "weekly"
            st.rerun()
    with nav_cols[2]:
        if st.button("📈 Mesačný prehľad (30 dní)", use_container_width=True, type="primary" if st.session_state["nav_view"] == "monthly" else "secondary"):
            st.session_state["nav_view"] = "monthly"
            st.rerun()


# ==============================================================================
# VIEW 1: AKTUÁLNA ZMENA (CURRENT SHIFT MONITORING & DATA ENTRY)
# ==============================================================================
if st.session_state["nav_view"] == "shift":
    analytics = calculate_shift_analytics(st.session_state["shift_hours"])
    kpi = analytics["kpi"]
    totals = analytics["totals"]

    # --- TOP LIGHT SECTION (CITYCARE OVERVIEW #F3F6F9) ---
    st.markdown('<div class="citycare-top">', unsafe_allow_html=True)

    col_overview_left, col_overview_right = st.columns([1.1, 2.9])

    with col_overview_left:
        # Glassmorphism Greeting & Efficiency Card
        oee_pct = kpi["oee"] * 100
        oee_color = "#10B981" if kpi["goal_met"] else "#EF4444"
        badge_status = "CIEĽ SPLNENÝ" if kpi["goal_met"] else "POD CIEĽOM"

        st.markdown(f"""
        <div class="glass-card">
            <span style="font-size:0.75rem; font-weight:700; text-transform:uppercase; color:#6B7280; letter-spacing:0.5px;">Aktuálna 8h Zmena</span>
            <div style="font-size:1.4rem; font-weight:800; color:#111827; margin:4px 0 12px 0;">Výrobná efektivita</div>
            <div style="text-align:center; padding:14px 0;">
                <div style="font-size:3.2rem; font-weight:800; font-family:'JetBrains Mono'; color:{oee_color}; line-height:1;">
                    {oee_pct:.1f}%
                </div>
                <div style="font-size:0.85rem; font-weight:700; color:#111827; margin-top:6px;">
                    CELKOVÉ OEE <span class="badge-pill {'badge-pill-green' if kpi['goal_met'] else 'badge-pill-red'}">{badge_status}</span>
                </div>
                <div style="font-size:0.78rem; color:#6B7280; margin-top:4px;">
                    Cieľ linky: <b>85.0%</b> ({kpi['oee_gap_pp']:+.1f} p.b.)
                </div>
            </div>
            <div style="border-top:1px solid rgba(0,0,0,0.06); padding-top:12px; margin-top:8px; font-size:0.82rem; color:#4B5563;">
                <div>• Vyrobené: <b style="color:#111827;">{totals['produced_pcs']} ks</b> / {totals['good_pcs']} OK</div>
                <div>• Prestoje: <b style="color:#EF4444;">{totals['downtime_min']} min</b> (-{totals['downtime_min']} ks)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_overview_right:
        # 4 Metric Scorecards (White Cards)
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            a_val = kpi["availability"]
            a_col = "#10B981" if a_val >= 0.90 else "#F59E0B"
            st.markdown(f"""
            <div class="white-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Availability</span>
                    <span class="badge-pill {'badge-pill-green' if a_val >= 0.90 else 'badge-pill-orange'}">{'OK' if a_val >= 0.90 else 'POKLES'}</span>
                </div>
                <div style="font-size:2rem; font-weight:800; font-family:'JetBrains Mono'; color:{a_col}; margin:4px 0;">{a_val:.1%}</div>
                <div style="font-size:0.78rem; color:#6B7280;"><span class="tabular-num">{totals['run_min']}</span> / <span class="tabular-num">{totals['planned_min']}</span> min chodu</div>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            p_val = kpi["performance"]
            p_col = "#10B981" if p_val >= 0.90 else "#F59E0B"
            st.markdown(f"""
            <div class="white-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Performance</span>
                    <span class="badge-pill {'badge-pill-green' if p_val >= 0.90 else 'badge-pill-orange'}">{'OK' if p_val >= 0.90 else 'TEMPO'}</span>
                </div>
                <div style="font-size:2rem; font-weight:800; font-family:'JetBrains Mono'; color:{p_col}; margin:4px 0;">{p_val:.1%}</div>
                <div style="font-size:0.78rem; color:#6B7280;"><span class="tabular-num">{totals['produced_pcs']}</span> / <span class="tabular-num">{totals['run_min']}</span> max ks</div>
            </div>
            """, unsafe_allow_html=True)

        with c3:
            q_val = kpi["quality"]
            q_col = "#10B981" if q_val >= 0.98 else "#EF4444"
            st.markdown(f"""
            <div class="white-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Quality</span>
                    <span class="badge-pill {'badge-pill-green' if q_val >= 0.98 else 'badge-pill-red'}">{'VYSOKÁ' if q_val >= 0.98 else 'BRAK'}</span>
                </div>
                <div style="font-size:2rem; font-weight:800; font-family:'JetBrains Mono'; color:{q_col}; margin:4px 0;">{q_val:.1%}</div>
                <div style="font-size:0.78rem; color:#6B7280;"><span class="tabular-num">{totals['good_pcs']}</span> OK / <span class="tabular-num">{totals['nok_pcs']}</span> NOK</div>
            </div>
            """, unsafe_allow_html=True)

        with c4:
            st.markdown(f"""
            <div class="white-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Downtime</span>
                    <span class="badge-pill badge-pill-red">-{totals['downtime_min']} min</span>
                </div>
                <div style="font-size:2rem; font-weight:800; font-family:'JetBrains Mono'; color:#EF4444; margin:4px 0;">{totals['downtime_min']} <span style="font-size:1rem;">min</span></div>
                <div style="font-size:0.78rem; color:#6B7280;">Stratená kapacita ks</div>
            </div>
            """, unsafe_allow_html=True)

        # Charts Area (Line Trend & Hourly Bar)
        st.write("")
        shift_hours = st.session_state["shift_hours"]
        h_nums = [h["hour"] for h in shift_hours]
        h_oee = [h["oee"] * 100 for h in shift_hours]
        h_prod = [h["produced_pcs"] for h in shift_hours]
        h_targets = [h["target_pcs"] for h in shift_hours]

        fig_area = go.Figure()
        fig_area.add_hline(y=85.0, line_dash="dash", line_color="#EF4444", line_width=1.5, annotation_text="Cieľ 85%")
        fig_area.add_trace(go.Scatter(
            x=[f"H{h}" for h in h_nums],
            y=h_oee,
            mode='lines+markers+text',
            name='OEE (%)',
            text=[f"{val:.1f}%" if val > 0 else "0%" for val in h_oee],
            textposition="top center",
            line=dict(color='#3B82F6', width=3),
            fill='tozeroy',
            fillcolor='rgba(59, 130, 246, 0.08)',
            marker=dict(size=8, color=['#10B981' if val >= 85 else '#EF4444' for val in h_oee])
        ))
        fig_area.update_layout(
            title=dict(text="Priebeh OEE (%) po hodinách vs. Cieľ 85%", font=dict(color="#111827", size=13)),
            margin=dict(l=10, r=10, t=30, b=10),
            height=200,
            yaxis=dict(range=[0, 110], gridcolor="#E5E7EB", tickfont=dict(color="#6B7280")),
            xaxis=dict(gridcolor="#E5E7EB", tickfont=dict(color="#111827")),
            plot_bgcolor="rgba(255,255,255,0.8)",
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_area, use_container_width=True)

    # Hourly Data Entry Form (CityCare White Card)
    st.write("")
    col_input_left, col_input_right = st.columns([1.8, 1.2])

    with col_input_left:
        st.markdown("<h4 style='color:#111827; margin:0 0 4px 0;'>⏱️ Po-hodinový report & Alarm (Vstup dát operátora)</h4>", unsafe_allow_html=True)
        st.caption("Manuálne zadajte vyrobené kusy a prestoje, alebo použite tlačidlo automatického doplnenia pre prezentáciu.")

        selected_h = st.selectbox(
            "Vyberte hodinu zmeny:",
            options=range(1, 9),
            format_func=lambda x: f"Hodina {x} ({HOURLY_SLOTS[x]['slot']} | Plán: {HOURLY_SLOTS[x]['target_pcs']} ks)" + ("  ✓ [Zadané]" if x in st.session_state["manual_hours_entered"] else "  ○ [Čaká]")
        )
        curr_h_data = st.session_state["shift_hours"][selected_h - 1]

        with st.form(key=f"citycare_form_{selected_h}"):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                in_produced = st.number_input("Vyrobené kusy (ks):", min_value=0, max_value=80, value=int(curr_h_data["produced_pcs"]))
            with col_f2:
                in_nok = st.number_input("Z toho NOK brak (ks):", min_value=0, max_value=max(1, in_produced), value=int(curr_h_data["nok_pcs"]))

            col_f3, col_f4 = st.columns([1, 1.2])
            with col_f3:
                in_downtime = st.number_input("Trvanie prestoja (min):", min_value=0, max_value=HOURLY_SLOTS[selected_h]["planned_min"], value=int(curr_h_data["downtime_min"]))
            with col_f4:
                in_time_interval = st.text_input("Čas od - do (interval):", value=f"{curr_h_data.get('downtime_from') or ''} - {curr_h_data.get('downtime_to') or ''}".strip(" -"), placeholder="09:10 - 09:35")

            st_options = ["(Žiadny prestoj)"] + list(DOWNTIME_CATALOG.keys())
            st_default_idx = st_options.index(curr_h_data["downtime_code"]) if curr_h_data.get("downtime_code") in DOWNTIME_CATALOG else 0
            in_st_code = st.selectbox(
                "Kód poruchy (Downtime Code):",
                options=st_options,
                index=st_default_idx,
                format_func=lambda x: f"{x} - {DOWNTIME_CATALOG[x]['name_sk']} ({DOWNTIME_CATALOG[x]['station']})" if x in DOWNTIME_CATALOG else x
            )

            q_options = ["(Bez defektu)"] + list(QUALITY_CATALOG.keys())
            q_default_idx = q_options.index(curr_h_data["nok_code"]) if curr_h_data.get("nok_code") in QUALITY_CATALOG else 0
            in_q_code = st.selectbox(
                "Kód chyby kvality (NOK Code):",
                options=q_options,
                index=q_default_idx,
                format_func=lambda x: f"{x} - {QUALITY_CATALOG[x]['name_sk']} ({QUALITY_CATALOG[x]['station']})" if x in QUALITY_CATALOG else x
            )

            submit_hour = st.form_submit_button("💾 Uložiť údaje za túto hodinu", use_container_width=True)
            if submit_hour:
                d_from, d_to = (in_time_interval.split("-")[0].strip(), in_time_interval.split("-")[1].strip()) if "-" in in_time_interval else (None, None)
                st.session_state["shift_hours"][selected_h - 1] = calculate_hourly_kpi(
                    hour=selected_h,
                    produced_pcs=in_produced,
                    nok_pcs=in_nok,
                    downtime_min=in_downtime,
                    downtime_code=in_st_code if in_st_code != "(Žiadny prestoj)" else None,
                    downtime_from=d_from,
                    downtime_to=d_to,
                    nok_code=in_q_code if in_q_code != "(Bez defektu)" else None
                )
                st.session_state["manual_hours_entered"].add(selected_h)
                st.session_state["ai_analysis_result"] = None
                st.success(f"✓ Údaje za Hodinu {selected_h} boli uložené!")
                st.rerun()

    with col_input_right:
        st.markdown("<h4 style='color:#111827; margin:0 0 8px 0;'>⚡ Rýchle akcie prezentácie</h4>", unsafe_allow_html=True)
        st.markdown("""
        <div class="white-card" style="margin-bottom:12px;">
            <div style="font-size:0.85rem; color:#4B5563; margin-bottom:12px;">
                Po manuálnom zadaní 2–3 hodín stlačte <b>Automaticky doplniť</b>, aby ste okamžite získali plnú zmenu a aktivovali AI Copilot.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🪄 Automaticky doplniť zvyšok zmeny", key="btn_autofill_inline", use_container_width=True):
            slide11 = get_demo_shift_slide_11()
            for h in range(1, 9):
                if h not in st.session_state["manual_hours_entered"]:
                    st.session_state["shift_hours"][h - 1] = slide11[h - 1]
                    st.session_state["manual_hours_entered"].add(h)
            st.session_state["show_analytics"] = True
            st.session_state["ai_analysis_result"] = None
            st.rerun()

        if st.button("🚀 Zobraziť analýzu a AI Copilot", key="btn_show_analytics_inline", use_container_width=True, type="primary"):
            st.session_state["show_analytics"] = True
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True) # End of citycare-top


    # --- BOTTOM DARK SECTION (CITYCARE DETAILS #09090B) ---
    st.markdown('<div class="citycare-bottom">', unsafe_allow_html=True)

    if not st.session_state["show_analytics"]:
        st.markdown("""
        <div class="glow-blue" style="text-align:center; padding:30px;">
            <span class="badge-pill badge-pill-blue" style="font-size:0.85rem; padding:4px 14px;">🔒 ČAKÁ NA DOKONČENIE ZMENY</span>
            <h3 style="color:#FFFFFF; margin-top:12px; margin-bottom:8px;">Zadajte hodiny a odomknite hĺbkovú analýzu, Waterfall a AI Copilot</h3>
            <p style="color:#94A3B8; font-size:0.92rem; max-width:650px; margin:0 auto 16px auto;">
                Počas prezentácie zadajte 2–3 hodiny manuálne a kliknite <b>«🪄 Automaticky doplniť zvyšok zmeny»</b>, aby systém vykonal dekompozíciu strát a aktivoval AI Maintenance Copilot.
            </p>
        </div>
        """, unsafe_allow_html=True)

    else:
        st.markdown('<h3 style="color:#FFFFFF; margin:0 0 16px 0; font-weight:800;">📊 Hĺbková analýza strát zmeny & AI Maintenance Copilot</h3>', unsafe_allow_html=True)

        col_d1, col_d2, col_d3 = st.columns(3)

        # 1. TOP 3 Prestoje (Neon Orange Glow)
        with col_d1:
            st.markdown("<h4 style='color:#F59E0B; margin-bottom:12px;'>🚨 TOP 3 Prestoje (Availability)</h4>", unsafe_allow_html=True)
            if analytics["top_3_availability"]:
                for item in analytics["top_3_availability"]:
                    st.markdown(f"""
                    <div class="glow-orange">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <span style="font-family:'JetBrains Mono'; font-weight:800; color:#FDE68A; font-size:1.05rem;">{item['code']}</span>
                            <span class="badge-pill badge-pill-orange">-{item['total_min']} min</span>
                        </div>
                        <div style="color:#FFFFFF; font-weight:700; font-size:0.95rem; margin-bottom:4px;">{item['name']}</div>
                        <div style="color:#CBD5E1; font-size:0.85rem;">📍 <i>{item['station']}</i> • {item['category']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("✅ Počas tejto zmeny neboli zaznamenané žiadne prestoje!")

        # 2. TOP 3 Defekty kvality (Neon Red Glow)
        with col_d2:
            st.markdown("<h4 style='color:#EF4444; margin-bottom:12px;'>🔍 TOP 3 Kvalita (NOK brak)</h4>", unsafe_allow_html=True)
            if analytics["top_3_quality"]:
                for item in analytics["top_3_quality"]:
                    st.markdown(f"""
                    <div class="glow-red">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <span style="font-family:'JetBrains Mono'; font-weight:800; color:#FECACA; font-size:1.05rem;">{item['code']}</span>
                            <span class="badge-pill badge-pill-red">{item['total_nok']} ks brak</span>
                        </div>
                        <div style="color:#FFFFFF; font-weight:700; font-size:0.95rem; margin-bottom:4px;">{item['name']}</div>
                        <div style="color:#CBD5E1; font-size:0.85rem;">📍 <i>{item['station']}</i> • {item['category']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("✅ 100% prvotriedna kvalita! Žiadny chybný kus.")

        # 3. AI Copilot (Neon Green Glow)
        with col_d3:
            st.markdown("<h4 style='color:#10B981; margin-bottom:12px;'>🤖 AI Maintenance Copilot</h4>", unsafe_allow_html=True)
            top_issue = analytics["top_3_availability"][0] if analytics["top_3_availability"] else None
            top_qual = analytics["top_3_quality"][0] if analytics["top_3_quality"] else None

            if top_issue:
                code = top_issue["code"]
                instructions = {
                    "ST-038": ("Stanica 3: Kamera", "Skontrolovať snímač a svetelný modul kamery. Očistiť optickú šošovku od prachu a mastnoty. Preveriť konektor napájania LED modulu 24V.", "Autonomous Maintenance (AM)", "💡 KORELÁCIA: Tento výpadok priamo spôsobuje 80% falošného braku Q-030!"),
                    "ST-046": ("Stanica 9: Leak test", "Preveriť tlakový snímač a pripojenie pneumatickej hadice 6 bar. Resetovať meraciu jednotku v menu ATEQ.", "Preventive Maintenance", "💡 KORELÁCIA: Únik súvisí s defektom Q-031. Preveriť tesnenie ST-047."),
                    "ST-001": ("Stanica 1-2: Vstup", "Privolať logistiku (Andon). Pripraviť zásobu puzdier 10 min pred ukončením pauzy.", "Lean Logistics", "💡 KORELÁCIA: Spôsobuje zníženie tempa linky (Speed Loss)."),
                }
                detail = instructions.get(code, (top_issue['station'], "Skontrolovať mechanické uchytenie, vyčistiť priestor a overiť senzor.", "Poka-Yoke & 5-Why", "💡 KORELÁCIA: Sledovať vplyv na takt linky."))

                st.markdown(f"""
                <div class="glow-green">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="font-weight:700; color:#4ADE80;">{code} — {detail[0]}</span>
                        <span class="badge-pill badge-pill-green">PRIORITA 1</span>
                    </div>
                    <div style="font-size:0.9rem; color:#F8FAFC; margin-bottom:6px;"><b>Zásah:</b> {detail[1]}</div>
                    <div style="font-size:0.85rem; color:#A7F3D0; margin-bottom:8px;"><b>Metodika:</b> {detail[2]}</div>
                    <div style="background:#132219; border-left:3px solid #10B981; padding:8px 10px; border-radius:4px; font-size:0.82rem; color:#BAE6FD;">
                        {detail[3]}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("🧠 Hĺbková analýza cez lokálnu Qwen 3B (Ollama)", use_container_width=True):
                    with st.spinner("Qwen 2.5 3B (lokálny model) generuje inžiniersky postup..."):
                        q_code = top_qual["code"] if top_qual else None
                        q_qty = top_qual["total_nok"] if top_qual else 0
                        ai_res = analyze_with_qwen(downtime_code=code, lost_minutes=top_issue["total_min"], nok_code=q_code, nok_qty=q_qty)
                        st.session_state["ai_analysis_result"] = ai_res

                if st.session_state.get("ai_analysis_result"):
                    res = st.session_state["ai_analysis_result"]
                    st.markdown(f"""
                    <div class="box-ai-output">
                        <span class="badge-pill badge-pill-blue">{res['source']}</span>
                        <div style="margin-top:10px; font-size:0.88rem; line-height:1.6; color:#F8FAFC;">
                            {res['content'].replace(chr(10), '<br>')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("✅ Všetky stanice pracujú optimálne! Žiadny incident.")

        # Full-width Waterfall Loss Bridge (Magna Slide 11)
        st.write("")
        st.markdown("<h4 style='color:#FFFFFF; margin-top:12px;'>📉 Waterfall rozpad výrobných strát (Magna Slide 11)</h4>", unsafe_allow_html=True)
        wf = analytics["waterfall"]

        fig_wf = go.Figure(go.Waterfall(
            name="Straty",
            orientation="v",
            measure=["absolute", "relative", "relative", "total", "relative", "total"],
            x=["Plán (Target)", "Prestoje (Downtime)", "Rýchlosť (Speed Loss)", "Vyrobené spolu", "Brak (NOK)", "Pridaná hodnota (OK)"],
            textposition="outside",
            text=[f"{wf['ideal_target']}", f"-{wf['downtime_loss_pcs']}", f"-{wf['speed_loss_pcs']}", f"{wf['actual_produced']}", f"-{wf['quality_loss_pcs']}", f"{wf['good_pieces']}"],
            textfont=dict(color="#FFFFFF", size=12),
            y=[wf['ideal_target'], -wf['downtime_loss_pcs'], -wf['speed_loss_pcs'], 0, -wf['quality_loss_pcs'], 0],
            connector={"line": {"color": "rgba(255, 255, 255, 0.4)", "width": 1.5}},
            decreasing={"marker": {"color": "#EF4444"}},
            increasing={"marker": {"color": "#10B981"}},
            totals={"marker": {"color": "#3B82F6"}}
        ))
        fig_wf.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=25, b=10),
            yaxis=dict(title="Kusy (ks)", range=[0, 480], gridcolor="#27272A", tickfont=dict(color="#94A3B8")),
            xaxis=dict(gridcolor="#27272A", tickfont=dict(color="#E2E8F0")),
            plot_bgcolor="rgba(24, 24, 27, 0.6)",
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_wf, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True) # End of citycare-bottom


# ==============================================================================
# VIEW 2: TÝŽDENNÝ PREHĽAD (7 DNÍ / WEEKS 45 - 49)
# ==============================================================================
elif st.session_state["nav_view"] == "weekly":
    st.markdown('<div class="citycare-top">', unsafe_allow_html=True)
    st.markdown("<h2 style='color:#111827; margin:0 0 4px 0;'>📅 Týždenný prehľad výroby (7 dní / ISO Týždne 45 – 49)</h2>", unsafe_allow_html=True)
    st.caption("Agregované výrobné výsledky za jednotlivé týždne mesiaca november.")

    df_weeks = pd.DataFrame(WEEKLY_SUMMARIES)

    # 4 Scorecards
    w1, w2, w3, w4 = st.columns(4)
    w1.markdown("""
    <div class="white-card">
        <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Celkový objem</span>
        <div style="font-size:2rem; font-weight:800; color:#111827; font-family:'JetBrains Mono'; margin:4px 0;">8,132 <span style="font-size:1rem;">ks</span></div>
        <div style="font-size:0.78rem; color:#6B7280;">Z plánu 9,240 ks</div>
    </div>
    """, unsafe_allow_html=True)

    w2.markdown("""
    <div class="white-card">
        <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Priemerné OEE</span>
        <div style="font-size:2rem; font-weight:800; color:#10B981; font-family:'JetBrains Mono'; margin:4px 0;">88.0%</div>
        <div style="font-size:0.78rem; color:#6B7280;">+3.0 p.b. nad cieľom 85%</div>
    </div>
    """, unsafe_allow_html=True)

    w3.markdown("""
    <div class="white-card">
        <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Celkový čas prestojov</span>
        <div style="font-size:2rem; font-weight:800; color:#EF4444; font-family:'JetBrains Mono'; margin:4px 0;">410 <span style="font-size:1rem;">min</span></div>
        <div style="font-size:0.78rem; color:#6B7280;">Priemer 19.5 min / zmena</div>
    </div>
    """, unsafe_allow_html=True)

    w4.markdown("""
    <div class="white-card">
        <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Kvalita produkcie</span>
        <div style="font-size:2rem; font-weight:800; color:#10B981; font-family:'JetBrains Mono'; margin:4px 0;">98.6%</div>
        <div style="font-size:0.78rem; color:#6B7280;">119 ks celkový brak</div>
    </div>
    """, unsafe_allow_html=True)

    st.write("")
    fig_w = px.bar(
        df_weeks,
        x="week", y="oee",
        text=df_weeks["oee"].apply(lambda x: f"{x:.1%}"),
        color="oee",
        color_continuous_scale=["#EF4444", "#10B981"],
        range_y=[0.75, 1.0],
        title="OEE podľa týždňov vs. Cieľ 85%"
    )
    fig_w.add_hline(y=0.85, line_dash="dash", line_color="#EF4444", annotation_text="Cieľ 85%")
    fig_w.update_layout(
        margin=dict(l=10, r=10, t=35, b=10),
        height=280,
        plot_bgcolor="rgba(255,255,255,0.8)",
        paper_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig_w, use_container_width=True)

    st.dataframe(
        df_weeks.rename(columns={
            "week": "Týždeň", "shifts": "Zmeny", "target": "Plán (ks)",
            "produced": "Vyrobené (ks)", "good": "OK (ks)", "nok": "NOK (ks)",
            "downtime_min": "Prestoje (min)", "a": "Availability", "p": "Performance",
            "q": "Quality", "oee": "OEE"
        }).style.format({
            "Availability": "{:.1%}", "Performance": "{:.1%}", "Quality": "{:.1%}", "OEE": "{:.1%}"
        }),
        use_container_width=True
    )
    st.markdown('</div>', unsafe_allow_html=True)


# ==============================================================================
# VIEW 3: MESAČNÝ PREHĽAD (30 DNÍ / 21 ZMIEN)
# ==============================================================================
elif st.session_state["nav_view"] == "monthly":
    st.markdown('<div class="citycare-top">', unsafe_allow_html=True)
    st.markdown("<h2 style='color:#111827; margin:0 0 4px 0;'>📈 Mesačný prehľad výroby (30 dní / 21 zmien)</h2>", unsafe_allow_html=True)
    st.caption("Kompletná história: 21 zmien za mesiac november 2026.")

    m = MONTH_TOTALS
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f"""
    <div class="white-card">
        <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Mesačné OEE</span>
        <div style="font-size:2rem; font-weight:800; color:#10B981; font-family:'JetBrains Mono'; margin:4px 0;">{m['oee']:.1%}</div>
        <div style="font-size:0.78rem; color:#6B7280;">+{m['oee_gap_pp']:.1f} p.b. nad cieľom 85%</div>
    </div>
    """, unsafe_allow_html=True)

    m2.markdown(f"""
    <div class="white-card">
        <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Úspešnosť zmien</span>
        <div style="font-size:2rem; font-weight:800; color:#111827; font-family:'JetBrains Mono'; margin:4px 0;">{m['shifts_on_target']} / {m['shifts_count']}</div>
        <div style="font-size:0.78rem; color:#6B7280;">17 na cieli (4 stredy pod cieľom)</div>
    </div>
    """, unsafe_allow_html=True)

    m3.markdown(f"""
    <div class="white-card">
        <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Celkové prestoje</span>
        <div style="font-size:2rem; font-weight:800; color:#F59E0B; font-family:'JetBrains Mono'; margin:4px 0;">{m['downtime_min']} <span style="font-size:1rem;">min</span></div>
        <div style="font-size:0.78rem; color:#6B7280;">33 prestojových udalostí</div>
    </div>
    """, unsafe_allow_html=True)

    m4.markdown(f"""
    <div class="white-card">
        <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Konečný brak (NOK)</span>
        <div style="font-size:2rem; font-weight:800; color:#EF4444; font-family:'JetBrains Mono'; margin:4px 0;">{m['nok']} <span style="font-size:1rem;">ks</span></div>
        <div style="font-size:0.78rem; color:#6B7280;">Kvalita: 98.6%</div>
    </div>
    """, unsafe_allow_html=True)

    st.write("")
    df_month = pd.DataFrame(MONTH_SHIFTS)

    fig_m = go.Figure()
    fig_m.add_hline(y=0.85, line_dash="dash", line_color="#EF4444", annotation_text="Cieľ OEE 85%")
    fig_m.add_trace(go.Scatter(
        x=df_month["date"] + " (" + df_month["day"] + ")",
        y=df_month["oee"],
        mode='lines+markers',
        line=dict(color='#3B82F6', width=2.5),
        marker=dict(size=8, color=['#10B981' if ok else '#EF4444' for ok in df_month["goal_met"]]),
        text=df_month["oee"].apply(lambda x: f"{x:.1%}")
    ))
    fig_m.update_layout(
        title=dict(text="Trend OEE počas všetkých 21 zmien v mesiaci", font=dict(color="#111827", size=13)),
        height=300,
        margin=dict(l=10, r=10, t=35, b=10),
        yaxis=dict(title="OEE", tickformat=".0%", gridcolor="#E5E7EB"),
        xaxis=dict(tickangle=-45, gridcolor="#E5E7EB"),
        plot_bgcolor="rgba(255,255,255,0.8)",
        paper_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig_m, use_container_width=True)

    col_par1, col_par2 = st.columns(2)
    with col_par1:
        st.markdown("#### 🔴 Pareto príčin prestojov (Top 6 ST kódov):")
        pareto_st = pd.DataFrame([
            {"Kód": "ST-038", "Príčina": "Svetelný modul kamery", "Minúty": 100},
            {"Kód": "ST-016", "Príčina": "Kamerové pracovisko", "Minúty": 70},
            {"Kód": "ST-046", "Príčina": "Leak test meracia jednotka", "Minúty": 70},
            {"Kód": "ST-001", "Príčina": "Zásobovanie dielmi", "Minúty": 60},
            {"Kód": "ST-047", "Príčina": "Skúšobné lôžko prepúšťa", "Minúty": 60},
            {"Kód": "ST-017", "Príčina": "Sekvencia nástroja", "Minúty": 50},
        ])
        fig_pst = px.bar(pareto_st, x="Príčina", y="Minúty", color="Minúty", text="Minúty", color_continuous_scale="Reds")
        fig_pst.update_layout(height=280, showlegend=False, plot_bgcolor="rgba(255,255,255,0.8)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_pst, use_container_width=True)

    with col_par2:
        st.markdown("#### 🟠 Pareto príčin braku (Top 4 Q kódy):")
        pareto_q = pd.DataFrame([
            {"Kód": "Q-031", "Defekt": "Únik média (Leak)", "Kusy": 38},
            {"Kód": "Q-020", "Defekt": "Nedosiahnutá poloha (Lis)", "Kusy": 28},
            {"Kód": "Q-026", "Defekt": "Nedotiahnutý skrutkový spoj", "Kusy": 28},
            {"Kód": "Q-030", "Defekt": "Chyba obrazovej kontroly", "Kusy": 25},
        ])
        fig_pq = px.bar(pareto_q, x="Defekt", y="Kusy", color="Kusy", text="Kusy", color_continuous_scale="Oranges")
        fig_pq.update_layout(height=280, showlegend=False, plot_bgcolor="rgba(255,255,255,0.8)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_pq, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)
