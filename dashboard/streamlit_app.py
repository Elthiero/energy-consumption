import sys
from pathlib import Path
from datetime import datetime
import zoneinfo
import time

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px
import plotly.graph_objects as go
from config.config import config

# ─── Constants ────────────────────────────────────────────────────────────────
KIGALI_TZ = zoneinfo.ZoneInfo("Africa/Kigali")
DATA_DIR = project_root / "data"

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Energy Grid Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

  :root {
    --bg:        #0b0f1a;
    --surface:   #111827;
    --border:    #1f2d45;
    --accent:    #00d4ff;
    --accent2:   #7c3aed;
    --success:   #10b981;
    --warning:   #f59e0b;
    --danger:    #ef4444;
    --text:      #e2e8f0;
    --muted:     #64748b;
  }

  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: var(--bg);
    color: var(--text);
  }

  h1, h2, h3 { font-family: 'Space Mono', monospace; }

  /* Metric cards */
  .metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 12px;
  }
  .metric-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }
  .metric-value { font-family: 'Space Mono', monospace; font-size: 22px; font-weight: 700; color: var(--accent); }
  .metric-sub   { font-size: 12px; color: var(--muted); margin-top: 4px; }

  /* Badge */
  .badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    font-family: 'Space Mono', monospace;
  }
  .badge-ok      { background: #064e3b; color: var(--success); }
  .badge-warn    { background: #451a03; color: var(--warning); }
  .badge-danger  { background: #450a0a; color: var(--danger); }

  /* Section header */
  .section-header {
    font-family: 'Space Mono', monospace;
    font-size: 13px;
    color: var(--accent);
    letter-spacing: 2px;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
    margin: 20px 0 14px;
  }

  /* Tab styling override */
  .stTabs [data-baseweb="tab-list"] { gap: 4px; }
  .stTabs [data-baseweb="tab"] {
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px 6px 0 0;
    color: var(--muted);
    padding: 8px 18px;
  }
  .stTabs [aria-selected="true"] {
    background: var(--border) !important;
    color: var(--accent) !important;
    border-bottom-color: var(--bg) !important;
  }

  .stButton > button {
    background: transparent;
    border: 1px solid var(--accent);
    color: var(--accent);
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    border-radius: 6px;
    padding: 6px 18px;
    transition: all 0.2s;
  }
  .stButton > button:hover {
    background: var(--accent);
    color: var(--bg);
  }

  /* Sidebar */
  [data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--border);
  }

  /* Plotly chart background match */
  .js-plotly-plot { border-radius: 8px; }
</style>
""",
    unsafe_allow_html=True,
)

# ─── Plotly theme ─────────────────────────────────────────────────────────────
# margin is intentionally excluded so callers can override it without conflict.
PLOT_THEME = dict(
    paper_bgcolor="#111827",
    plot_bgcolor="#0b0f1a",
    font=dict(family="DM Sans", color="#e2e8f0", size=12),
    xaxis=dict(gridcolor="#1f2d45", linecolor="#1f2d45", zerolinecolor="#1f2d45"),
    yaxis=dict(gridcolor="#1f2d45", linecolor="#1f2d45", zerolinecolor="#1f2d45"),
    legend=dict(bgcolor="#111827", bordercolor="#1f2d45", borderwidth=1),
    colorway=[
        "#00d4ff",
        "#7c3aed",
        "#10b981",
        "#f59e0b",
        "#ef4444",
        "#06b6d4",
        "#a855f7",
        "#34d399",
        "#fbbf24",
        "#f87171",
    ],
)

DEFAULT_MARGIN = dict(l=40, r=20, t=40, b=40)
COMPACT_MARGIN = dict(l=20, r=10, t=30, b=20)


def apply_theme(fig, **overrides):
    """Apply base theme then merge any per-chart overrides (including margin)."""
    layout = {**PLOT_THEME, "margin": DEFAULT_MARGIN, **overrides}
    fig.update_layout(**layout)
    return fig


# ─── DB engine ────────────────────────────────────────────────────────────────
@st.cache_resource
def get_engine():
    return create_engine(
        config.db_url,
        connect_args={"options": "-c timezone=Africa/Kigali"},
        pool_pre_ping=True,
    )


def run_query(sql: str, params: dict = None) -> tuple[pd.DataFrame, float]:
    """Run query and return (DataFrame, elapsed_ms)."""
    engine = get_engine()
    t0 = time.perf_counter()
    df = pd.read_sql(text(sql), engine, params=params)
    elapsed = (time.perf_counter() - t0) * 1000
    return df, elapsed


# ─── Header ───────────────────────────────────────────────────────────────────
now_kigali = datetime.now(KIGALI_TZ)

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("# ⚡ Smart Energy Grid")
    st.markdown(
        f"<span style='color:#64748b;font-family:Space Mono,monospace;font-size:13px;'>"
        f"KIGALI • {now_kigali.strftime('%A %d %B %Y  %H:%M:%S')} CAT</span>",
        unsafe_allow_html=True,
    )
with col_h2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⟳  Refresh"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Performance Metrics Panel
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📊 Performance Metrics")

    # ── 1. Live query timing: raw vs aggregated ──────────────────────────────
    st.markdown(
        '<div class="section-header">Query Execution Time</div>', unsafe_allow_html=True
    )

    RAW_SQL = """
        SELECT DATE_TRUNC('day', timestamp AT TIME ZONE 'Africa/Kigali') AS day,
               SUM(energy) AS total_energy
        FROM energy_readings
        WHERE timestamp >= NOW() - INTERVAL '7 days'
        GROUP BY day ORDER BY day
    """
    AGG_SQL = """
        SELECT bucket::date AS day, SUM(total_energy) AS total_energy
        FROM energy_readings_daily
        WHERE bucket >= NOW() - INTERVAL '7 days'
        GROUP BY day ORDER BY day
    """

    with st.spinner("Benchmarking queries…"):
        _, raw_ms = run_query(RAW_SQL)
        _, agg_ms = run_query(AGG_SQL)

    speedup = raw_ms / agg_ms if agg_ms > 0 else 0

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"""<div class="metric-card">
            <div class="metric-label">Raw Table</div>
            <div class="metric-value" style="color:#ef4444">{raw_ms:.0f}<span style="font-size:13px"> ms</span></div>
            <div class="metric-sub">energy_readings</div>
        </div>""",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""<div class="metric-card">
            <div class="metric-label">Aggregated</div>
            <div class="metric-value" style="color:#10b981">{agg_ms:.1f}<span style="font-size:13px"> ms</span></div>
            <div class="metric-sub">energy_readings_daily</div>
        </div>""",
            unsafe_allow_html=True,
        )

    badge_class = (
        "badge-ok"
        if speedup >= 5
        else ("badge-warn" if speedup >= 2 else "badge-danger")
    )
    st.markdown(
        f'<div style="text-align:center;margin-bottom:12px">'
        f'<span class="badge {badge_class}">⚡ {speedup:.1f}× faster with aggregates</span></div>',
        unsafe_allow_html=True,
    )

    # Bar chart
    fig_perf = go.Figure(
        go.Bar(
            x=["Raw (energy_readings)", "Hourly agg", "Daily agg"],
            y=[raw_ms, None, agg_ms],
            marker_color=["#ef4444", "#f59e0b", "#10b981"],
            text=[f"{raw_ms:.0f} ms", "—", f"{agg_ms:.1f} ms"],
            textposition="auto",
        )
    )
    # Also benchmark hourly
    _, hourly_ms = run_query("""
        SELECT bucket::date AS day, SUM(total_energy) AS total_energy
        FROM energy_readings_hourly
        WHERE bucket >= NOW() - INTERVAL '7 days'
        GROUP BY day ORDER BY day
    """)
    fig_perf = go.Figure(
        go.Bar(
            x=["Raw", "Hourly agg", "Daily agg"],
            y=[raw_ms, hourly_ms, agg_ms],
            marker_color=["#ef4444", "#f59e0b", "#10b981"],
            text=[f"{raw_ms:.0f} ms", f"{hourly_ms:.1f} ms", f"{agg_ms:.1f} ms"],
            textposition="auto",
        )
    )
    apply_theme(
        fig_perf,
        height=200,
        title=dict(text="Query Time (ms)", font=dict(size=12)),
        showlegend=False,
        margin=COMPACT_MARGIN,
    )
    st.plotly_chart(fig_perf, use_container_width=True)

    # ── 2. Storage / Compression ─────────────────────────────────────────────
    st.markdown(
        '<div class="section-header">Storage Efficiency</div>', unsafe_allow_html=True
    )

    storage_csv = DATA_DIR / "storage_efficiency.csv"
    if storage_csv.exists():
        s_df = pd.read_csv(storage_csv)
        st.dataframe(s_df, use_container_width=True, hide_index=True)
    else:
        # Live fallback: hypertable size vs continuous aggregates
        size_sql = """
            SELECT
                h.hypertable_name AS "Table",
                pg_size_pretty(h.total_bytes) AS "Total Size",
                h.num_chunks AS "Chunks",
                h.compression_enabled AS "Compressed"
            FROM timescaledb_information.hypertable_detailed_size(NULL) s
            RIGHT JOIN timescaledb_information.hypertables h
                ON s.hypertable_name = h.hypertable_name
            ORDER BY h.hypertable_name
        """
        try:
            size_df, _ = run_query("""
                SELECT hypertable_name AS "Table",
                       num_chunks AS "Chunks",
                       compression_enabled AS "Compressed"
                FROM timescaledb_information.hypertables
            """)
            st.dataframe(size_df, use_container_width=True, hide_index=True)
        except Exception:
            st.info("Run compression impact script to see storage gains.")

    # ── 3. Chunk Strategy Comparison ─────────────────────────────────────────
    st.markdown(
        '<div class="section-header">Chunk Strategy (Query 4)</div>',
        unsafe_allow_html=True,
    )

    chunk_files = {
        "3h": DATA_DIR / "compressed_3h.csv",
        "1day": DATA_DIR / "compressed_1day.csv",
        "1week": DATA_DIR / "compressed_1week.csv",
    }
    chunk_times = {}
    for label, path in chunk_files.items():
        if path.exists():
            df_c = pd.read_csv(path)
            row = df_c[df_c["query_name"].str.contains("Query 4", na=False)]
            if not row.empty:
                chunk_times[label] = row["execution_time_ms"].values[0]

    if chunk_times:
        fig_chunk = go.Figure(
            go.Bar(
                x=[f"Chunk\n{k}" for k in chunk_times],
                y=list(chunk_times.values()),
                marker_color=["#00d4ff", "#7c3aed", "#10b981"],
                text=[f"{v:.1f} ms" for v in chunk_times.values()],
                textposition="auto",
            )
        )
        apply_theme(
            fig_chunk,
            height=200,
            title=dict(text="Full Scan by Chunk Size", font=dict(size=12)),
            showlegend=False,
            margin=COMPACT_MARGIN,
        )
        st.plotly_chart(fig_chunk, use_container_width=True)
    else:
        # Show side-by-side chunk strategy info text
        st.markdown(
            """
        <div style='background:#0b0f1a;border:1px solid #1f2d45;border-radius:6px;padding:12px;font-size:12px;'>
            <b style='color:#00d4ff'>3h chunks</b> → Best for real-time / last-hour queries<br>
            <b style='color:#7c3aed'>1day chunks</b> → Balanced for daily aggregations<br>
            <b style='color:#10b981'>1week chunks</b> → Best compression ratio for historical scans<br>
            <span style='color:#64748b'>Run compressed_Xh/1day/1week benchmark CSVs to compare.</span>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # ── 4. Aggregate freshness check ─────────────────────────────────────────
    st.markdown(
        '<div class="section-header">Aggregate Freshness</div>', unsafe_allow_html=True
    )
    try:
        fresh_df, _ = run_query("""
            SELECT 
                'energy_readings_hourly' AS view,
                MAX(bucket) AS last_bucket,
                ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(bucket)))/3600, 1) AS lag_hours
            FROM energy_readings_hourly
            UNION ALL
            SELECT 
                'energy_readings_daily',
                MAX(bucket),
                ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(bucket)))/3600, 1)
            FROM energy_readings_daily
        """)
        for _, row in fresh_df.iterrows():
            lag = float(row["lag_hours"])
            badge = (
                "badge-ok" if lag < 2 else ("badge-warn" if lag < 6 else "badge-danger")
            )
            short_name = row["view"].replace("energy_readings_", "")
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:6px 0;border-bottom:1px solid #1f2d45;">'
                f'<span style="font-size:12px;font-family:Space Mono,monospace;">{short_name}</span>'
                f'<span class="badge {badge}">{lag}h lag</span></div>',
                unsafe_allow_html=True,
            )
    except Exception as e:
        st.error(f"Freshness check failed: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN TABS
# ═══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "⚡  Real-time (Last Hour)",
        "📅  Daily Patterns",
        "📈  Weekly Trends",
        "🗺️  Monthly by Region",
    ]
)

# ─── Tab 1: Real-time ─────────────────────────────────────────────────────────
with tab1:
    st.markdown(
        '<div class="section-header">Power Readings — Last 60 Minutes</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    # KPI: how many meters active in last hour
    kpi_sql = """
        SELECT COUNT(DISTINCT meter_id) AS active_meters,
               ROUND(AVG(power)::numeric, 2) AS avg_power,
               ROUND(MAX(power)::numeric, 2) AS peak_power
        FROM energy_readings
        WHERE timestamp >= NOW() - INTERVAL '1 hour'
    """
    kpi_df, _ = run_query(kpi_sql)
    if not kpi_df.empty:
        row = kpi_df.iloc[0]
        with c1:
            st.markdown(
                f"""<div class="metric-card">
                <div class="metric-label">Active Meters</div>
                <div class="metric-value">{int(row['active_meters']):,}</div>
                <div class="metric-sub">in last 60 min</div>
            </div>""",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"""<div class="metric-card">
                <div class="metric-label">Avg Power</div>
                <div class="metric-value">{row['avg_power']} <span style="font-size:13px">W</span></div>
                <div class="metric-sub">across active meters</div>
            </div>""",
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f"""<div class="metric-card">
                <div class="metric-label">Peak Power</div>
                <div class="metric-value" style="color:#f59e0b">{row['peak_power']} <span style="font-size:13px">W</span></div>
                <div class="metric-sub">single meter max</div>
            </div>""",
                unsafe_allow_html=True,
            )

    # Pick 5 representative meters and show their full 1-hour trace
    rt_sql = """
        WITH sampled_meters AS (
            SELECT DISTINCT meter_id
            FROM energy_readings
            WHERE timestamp >= NOW() - INTERVAL '1 hour'
            ORDER BY meter_id
            LIMIT 5
        )
        SELECT e.timestamp, e.meter_id, e.power, e.voltage, e.energy
        FROM energy_readings e
        JOIN sampled_meters s ON e.meter_id = s.meter_id
        WHERE e.timestamp >= NOW() - INTERVAL '1 hour'
        ORDER BY e.timestamp ASC
    """
    df_rt, rt_ms = run_query(rt_sql)

    st.caption(
        f"Query: {rt_ms:.1f} ms  •  "
        f"Last refresh: {datetime.now(KIGALI_TZ).strftime('%H:%M:%S')} CAT"
    )

    if not df_rt.empty:
        col_l, col_r = st.columns([2, 1])
        with col_l:
            fig_rt = px.line(
                df_rt,
                x="timestamp",
                y="power",
                color="meter_id",
                title="Real-time Power (W) — 5 Sample Meters",
                labels={"power": "Power (W)", "timestamp": "Time", "meter_id": "Meter"},
            )
            apply_theme(fig_rt)
            fig_rt.update_traces(line=dict(width=2))
            st.plotly_chart(fig_rt, use_container_width=True)

        with col_r:
            fig_volt = px.line(
                df_rt,
                x="timestamp",
                y="voltage",
                color="meter_id",
                title="Voltage (V)",
                labels={"voltage": "Voltage (V)", "timestamp": "Time"},
            )
            apply_theme(fig_volt)
            fig_volt.update_traces(line=dict(width=1.5))
            fig_volt.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig_volt, use_container_width=True)

        # Latest snapshot table
        latest = (
            df_rt.sort_values("timestamp")
            .groupby("meter_id")
            .last()
            .reset_index()[["meter_id", "timestamp", "power", "voltage", "energy"]]
        )
        latest.columns = [
            "Meter ID",
            "Last Reading",
            "Power (W)",
            "Voltage (V)",
            "Energy (Wh)",
        ]
        st.dataframe(latest, use_container_width=True, hide_index=True)
    else:
        st.warning(
            "No readings found in the last hour. Check that data ingestion is running."
        )

# ─── Tab 2: Daily patterns ────────────────────────────────────────────────────
with tab2:
    st.markdown(
        '<div class="section-header">Hourly Consumption — Today vs Yesterday</div>',
        unsafe_allow_html=True,
    )

    daily_sql = """
        WITH today AS (
            SELECT
                EXTRACT(HOUR FROM bucket AT TIME ZONE 'Africa/Kigali')::int AS hour,
                SUM(total_energy) AS energy
            FROM energy_readings_hourly
            WHERE bucket >= DATE_TRUNC('day', NOW() AT TIME ZONE 'Africa/Kigali')
                              AT TIME ZONE 'Africa/Kigali'
              AND bucket <  (DATE_TRUNC('day', NOW() AT TIME ZONE 'Africa/Kigali')
                              AT TIME ZONE 'Africa/Kigali') + INTERVAL '1 day'
              AND bucket <= NOW()
            GROUP BY hour
        ),
        yesterday AS (
            SELECT
                EXTRACT(HOUR FROM bucket AT TIME ZONE 'Africa/Kigali')::int AS hour,
                SUM(total_energy) AS energy
            FROM energy_readings_hourly
            WHERE bucket >= (DATE_TRUNC('day', NOW() AT TIME ZONE 'Africa/Kigali')
                              AT TIME ZONE 'Africa/Kigali') - INTERVAL '1 day'
              AND bucket <   DATE_TRUNC('day', NOW() AT TIME ZONE 'Africa/Kigali')
                              AT TIME ZONE 'Africa/Kigali'
            GROUP BY hour
        )
        SELECT
            COALESCE(t.hour, y.hour)      AS hour,
            COALESCE(t.energy, 0)         AS today_energy,
            COALESCE(y.energy, 0)         AS yesterday_energy
        FROM today t
        FULL OUTER JOIN yesterday y ON t.hour = y.hour
        ORDER BY hour
    """
    df_daily, d_ms = run_query(daily_sql)
    st.caption(f"Source: energy_readings_hourly  •  Query: {d_ms:.1f} ms")

    if not df_daily.empty:
        # Summary KPIs
        today_total = df_daily["today_energy"].sum() / 1000  # kWh
        yest_total = df_daily["yesterday_energy"].sum() / 1000
        delta_pct = ((today_total - yest_total) / yest_total * 100) if yest_total else 0

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(
                f"""<div class="metric-card">
                <div class="metric-label">Today So Far</div>
                <div class="metric-value">{today_total:.1f} <span style="font-size:13px">kWh</span></div>
            </div>""",
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                f"""<div class="metric-card">
                <div class="metric-label">Yesterday Total</div>
                <div class="metric-value" style="color:#7c3aed">{yest_total:.1f} <span style="font-size:13px">kWh</span></div>
            </div>""",
                unsafe_allow_html=True,
            )
        with k3:
            delta_color = "#ef4444" if delta_pct > 0 else "#10b981"
            delta_sign = "+" if delta_pct > 0 else ""
            st.markdown(
                f"""<div class="metric-card">
                <div class="metric-label">vs Yesterday</div>
                <div class="metric-value" style="color:{delta_color}">{delta_sign}{delta_pct:.1f}<span style="font-size:13px">%</span></div>
                <div class="metric-sub">same hours comparison</div>
            </div>""",
                unsafe_allow_html=True,
            )

        # Grouped bar chart
        fig_daily = go.Figure()
        fig_daily.add_trace(
            go.Bar(
                x=df_daily["hour"],
                y=df_daily["yesterday_energy"] / 1000,
                name="Yesterday",
                marker_color="#7c3aed",
                opacity=0.75,
            )
        )
        fig_daily.add_trace(
            go.Bar(
                x=df_daily["hour"],
                y=df_daily["today_energy"] / 1000,
                name="Today",
                marker_color="#00d4ff",
            )
        )
        apply_theme(
            fig_daily,
            barmode="group",
            title="Hourly Energy Consumption (kWh)",
            xaxis=dict(
                title="Hour of Day (Kigali CAT)",
                tickmode="linear",
                dtick=1,
                gridcolor="#1f2d45",
                linecolor="#1f2d45",
            ),
            yaxis=dict(title="Energy (kWh)", gridcolor="#1f2d45", linecolor="#1f2d45"),
        )
        st.plotly_chart(fig_daily, use_container_width=True)

        # Area chart overlay
        fig_area = go.Figure()
        fig_area.add_trace(
            go.Scatter(
                x=df_daily["hour"],
                y=df_daily["yesterday_energy"] / 1000,
                name="Yesterday",
                fill="tozeroy",
                line=dict(color="#7c3aed", width=2),
                fillcolor="rgba(124,58,237,0.15)",
            )
        )
        fig_area.add_trace(
            go.Scatter(
                x=df_daily["hour"],
                y=df_daily["today_energy"] / 1000,
                name="Today",
                fill="tozeroy",
                line=dict(color="#00d4ff", width=2),
                fillcolor="rgba(0,212,255,0.15)",
            )
        )
        apply_theme(
            fig_area,
            title="Consumption Profile Overlay",
            xaxis=dict(title="Hour", gridcolor="#1f2d45", linecolor="#1f2d45"),
            yaxis=dict(title="Energy (kWh)", gridcolor="#1f2d45", linecolor="#1f2d45"),
        )
        st.plotly_chart(fig_area, use_container_width=True)
    else:
        st.warning(
            "No hourly aggregate data found for today/yesterday. "
            "Run: CALL refresh_continuous_aggregate('energy_readings_hourly', NULL, NULL);"
        )

# ─── Tab 3: Weekly trends ─────────────────────────────────────────────────────
with tab3:
    st.markdown(
        '<div class="section-header">Daily Energy — Last 7 Days</div>',
        unsafe_allow_html=True,
    )

    weekly_sql = """
        SELECT
            (bucket AT TIME ZONE 'Africa/Kigali')::date AS day,
            SUM(total_energy)  / 1000  AS total_kwh,
            AVG(avg_power)             AS avg_power_w,
            MAX(max_power)             AS peak_power_w
        FROM energy_readings_daily
        WHERE bucket >= NOW() - INTERVAL '7 days'
        GROUP BY day
        ORDER BY day
    """
    df_wk, w_ms = run_query(weekly_sql)
    st.caption(f"Source: energy_readings_daily  •  Query: {w_ms:.1f} ms")

    if not df_wk.empty:
        col_l, col_r = st.columns([3, 2])

        with col_l:
            fig_wk = go.Figure()
            fig_wk.add_trace(
                go.Scatter(
                    x=df_wk["day"],
                    y=df_wk["total_kwh"],
                    mode="lines+markers",
                    name="Total Energy",
                    line=dict(color="#00d4ff", width=3),
                    marker=dict(
                        size=8, color="#00d4ff", line=dict(color="#0b0f1a", width=2)
                    ),
                    fill="tozeroy",
                    fillcolor="rgba(0,212,255,0.08)",
                )
            )
            apply_theme(
                fig_wk,
                title="Daily Total Energy (kWh)",
                xaxis=dict(
                    title="Date",
                    gridcolor="#1f2d45",
                    linecolor="#1f2d45",
                    tickformat="%a %d %b",
                ),
                yaxis=dict(
                    title="Energy (kWh)", gridcolor="#1f2d45", linecolor="#1f2d45"
                ),
            )
            st.plotly_chart(fig_wk, use_container_width=True)

        with col_r:
            fig_pwr = go.Figure()
            fig_pwr.add_trace(
                go.Bar(
                    x=df_wk["day"],
                    y=df_wk["avg_power_w"],
                    name="Avg Power",
                    marker_color="#10b981",
                )
            )
            fig_pwr.add_trace(
                go.Scatter(
                    x=df_wk["day"],
                    y=df_wk["peak_power_w"],
                    name="Peak Power",
                    mode="lines+markers",
                    line=dict(color="#f59e0b", width=2, dash="dot"),
                    marker=dict(size=6),
                )
            )
            apply_theme(
                fig_pwr,
                title="Avg vs Peak Power (W)",
                xaxis=dict(
                    tickformat="%a %d", gridcolor="#1f2d45", linecolor="#1f2d45"
                ),
                yaxis=dict(title="Power (W)", gridcolor="#1f2d45", linecolor="#1f2d45"),
                height=340,
            )
            st.plotly_chart(fig_pwr, use_container_width=True)

        # Stats table
        df_wk_display = df_wk.copy()
        df_wk_display.columns = [
            "Date",
            "Total (kWh)",
            "Avg Power (W)",
            "Peak Power (W)",
        ]
        df_wk_display["Total (kWh)"] = df_wk_display["Total (kWh)"].round(1)
        df_wk_display["Avg Power (W)"] = df_wk_display["Avg Power (W)"].round(1)
        df_wk_display["Peak Power (W)"] = df_wk_display["Peak Power (W)"].round(1)
        st.dataframe(df_wk_display, use_container_width=True, hide_index=True)
    else:
        st.warning("No daily aggregate data for the last 7 days.")

# ─── Tab 4: Monthly by Region ──────────────────────────────────────────────────
with tab4:
    st.markdown(
        '<div class="section-header">Monthly Energy by Region — Current Month</div>',
        unsafe_allow_html=True,
    )

    # Region = first significant digit of meter_id
    # All meters start with "1", so we use position 2 (0-indexed char 1) which varies
    # e.g. 10xxxxxxxx → Region 1, 11xxxxxxxx → Region 1, etc.
    region_sql = """
        SELECT
            SUBSTRING(meter_id, 1, 1)          AS region,
            COUNT(DISTINCT meter_id)            AS meter_count,
            SUM(total_energy)  / 1000           AS total_kwh,
            AVG(avg_power)                      AS avg_power_w,
            MAX(max_power)                      AS peak_power_w
        FROM energy_readings_daily
        WHERE bucket >= DATE_TRUNC('month', NOW() AT TIME ZONE 'Africa/Kigali')
                          AT TIME ZONE 'Africa/Kigali'
          AND bucket <   (DATE_TRUNC('month', NOW() AT TIME ZONE 'Africa/Kigali')
                          AT TIME ZONE 'Africa/Kigali') + INTERVAL '1 month'
        GROUP BY region
        ORDER BY region
    """
    df_reg, r_ms = run_query(region_sql)
    st.caption(
        f"Source: energy_readings_daily  •  Query: {r_ms:.1f} ms  •  "
        f"Region derived from 1st digit of meter ID (e.g. **1**xxxxxxxx)"
    )

    if not df_reg.empty:
        df_reg["region_label"] = "Region " + df_reg["region"].astype(str)

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(
                f"""<div class="metric-card">
                <div class="metric-label">Total Regions</div>
                <div class="metric-value">{len(df_reg)}</div>
                <div class="metric-sub">active this month</div>
            </div>""",
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                f"""<div class="metric-card">
                <div class="metric-label">Total Consumption</div>
                <div class="metric-value">{df_reg['total_kwh'].sum()/1000:.1f} <span style="font-size:13px">MWh</span></div>
                <div class="metric-sub">current month</div>
            </div>""",
                unsafe_allow_html=True,
            )
        with k3:
            top_region = df_reg.loc[df_reg["total_kwh"].idxmax(), "region_label"]
            st.markdown(
                f"""<div class="metric-card">
                <div class="metric-label">Highest Consuming</div>
                <div class="metric-value" style="font-size:17px">{top_region}</div>
                <div class="metric-sub">this month</div>
            </div>""",
                unsafe_allow_html=True,
            )

        col_l, col_r = st.columns([2, 1])

        with col_l:
            fig_reg = go.Figure()
            fig_reg.add_trace(
                go.Bar(
                    x=df_reg["region_label"],
                    y=df_reg["total_kwh"],
                    marker=dict(
                        color=df_reg["total_kwh"],
                        colorscale=[[0, "#1f2d45"], [0.5, "#7c3aed"], [1, "#00d4ff"]],
                        showscale=True,
                        colorbar=dict(title="kWh", tickfont=dict(color="#e2e8f0")),
                    ),
                    text=df_reg["total_kwh"].apply(lambda x: f"{x/1000:.1f} MWh"),
                    textposition="outside",
                    textfont=dict(color="#e2e8f0", size=11),
                )
            )
            apply_theme(
                fig_reg,
                title="Monthly Energy Consumption by Region (kWh)",
                xaxis=dict(title="Region", gridcolor="#1f2d45", linecolor="#1f2d45"),
                yaxis=dict(
                    title="Total Energy (kWh)", gridcolor="#1f2d45", linecolor="#1f2d45"
                ),
                height=420,
            )
            st.plotly_chart(fig_reg, use_container_width=True)

        with col_r:
            fig_pie = px.pie(
                df_reg,
                values="total_kwh",
                names="region_label",
                title="Share of Total Consumption",
                hole=0.55,
                color_discrete_sequence=[
                    "#00d4ff",
                    "#7c3aed",
                    "#10b981",
                    "#f59e0b",
                    "#ef4444",
                    "#06b6d4",
                    "#a855f7",
                    "#34d399",
                    "#fbbf24",
                    "#f87171",
                ],
            )
            apply_theme(fig_pie, height=420)
            fig_pie.update_traces(textfont_color="#e2e8f0")
            st.plotly_chart(fig_pie, use_container_width=True)

        # Detailed table
        df_display = df_reg[
            ["region_label", "meter_count", "total_kwh", "avg_power_w", "peak_power_w"]
        ].copy()
        df_display.columns = [
            "Region",
            "Meters",
            "Total (kWh)",
            "Avg Power (W)",
            "Peak Power (W)",
        ]
        df_display["Total (kWh)"] = df_display["Total (kWh)"].round(1)
        df_display["Avg Power (W)"] = df_display["Avg Power (W)"].round(1)
        df_display["Peak Power (W)"] = df_display["Peak Power (W)"].round(1)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning("No daily aggregate data for the current month.")
