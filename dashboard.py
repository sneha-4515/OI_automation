"""
dashboard.py

Streamlit dashboard for the NSE MWPL tracker.

Run with:
    streamlit run scripts/dashboard.py
"""

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(BASE_DIR, "data", "processed", "mwpl_history.csv")
INTRADAY_OI_PATH = os.path.join(BASE_DIR, "data", "processed", "intraday_oi.csv")

st.set_page_config(page_title="NSE MWPL Tracker", layout="wide")


@st.cache_data(ttl=3600)
def load_history() -> pd.DataFrame:
    if not os.path.exists(HISTORY_PATH):
        return pd.DataFrame()
    df = pd.read_csv(HISTORY_PATH, parse_dates=["Date"])
    return df


df = load_history()

st.title("📊 NSE Market-Wide Position Limit (MWPL) Tracker")

if df.empty:
    st.warning(
        "No processed data found yet. Run `fetch_nse_data.py` then "
        "`process_data.py` to populate `data/processed/mwpl_history.csv`."
    )
    st.stop()

latest_date = df["Date"].max()
latest_df = df[df["Date"] == latest_date].copy()

# --- Top metrics -------------------------------------------------------
col1, col2, col3 = st.columns(3)
col1.metric("Latest data date", latest_date.strftime("%d-%b-%Y"))
col2.metric("Symbols tracked (latest day)", len(latest_df))
col3.metric(
    "Symbols in ban zone (>=95% MWPL)",
    int(latest_df["Ban_Flag"].sum()) if "Ban_Flag" in latest_df else 0,
)

st.divider()

# --- Overview table ------------------------------------------------------
st.subheader(f"Overview — {latest_date.strftime('%d-%b-%Y')}")
sort_col = st.selectbox(
    "Sort by", ["OI_pct_MWPL", "FutOI_pct_MWPL"], index=0
)
display_df = latest_df.sort_values(sort_col, ascending=False)


def highlight_ban(row):
    color = "background-color: #ffcccc" if row.get("Ban_Flag") else ""
    return [color] * len(row)


st.dataframe(
    display_df[
        [
            "NSE_Symbol",
            "MWPL",
            "Open_Interest",
            "Future_Equivalent_OI",
            "OI_pct_MWPL",
            "FutOI_pct_MWPL",
            "Ban_Flag",
        ]
    ].style.apply(highlight_ban, axis=1),
    use_container_width=True,
    height=400,
)

st.divider()

# --- Ban-watch panel -------------------------------------------------
st.subheader("🚨 Top symbols closest to / over the MWPL ban threshold")
top_n = st.slider("Number of symbols to show", 5, 30, 15)
ban_watch = display_df.head(top_n)

fig_ban = px.bar(
    ban_watch,
    x="NSE_Symbol",
    y="OI_pct_MWPL",
    color="Ban_Flag",
    color_discrete_map={True: "crimson", False: "steelblue"},
    title=f"Top {top_n} symbols by % of MWPL utilized ({latest_date.strftime('%d-%b-%Y')})",
    labels={"OI_pct_MWPL": "% of MWPL"},
)
fig_ban.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="95% ban threshold")
st.plotly_chart(fig_ban, use_container_width=True)

st.divider()

# --- Day-wise comparison: search a symbol, see table + chart together ----
st.subheader("🔍 Day-wise comparison for a symbol")
symbols = sorted(df["NSE_Symbol"].unique())
selected_symbol = st.selectbox(
    "Search / select a symbol", symbols, key="symbol_search"
)

symbol_df = df[df["NSE_Symbol"] == selected_symbol].sort_values("Date").copy()
# Day label with no time component — every day the pipeline has processed
# for this symbol shows up as its own row/tick, never interpolated by hour.
symbol_df["Day"] = symbol_df["Date"].dt.strftime("%d-%b-%Y")

st.markdown(f"**{selected_symbol} — day-wise values**")
table_cols = [
    "Day",
    "MWPL",
    "Open_Interest",
    "Future_Equivalent_OI",
    "OI_pct_MWPL",
    "FutOI_pct_MWPL",
    "Ban_Flag",
]
st.dataframe(
    symbol_df[table_cols].style.apply(highlight_ban, axis=1),
    use_container_width=True,
    height=min(400, 45 + 35 * len(symbol_df)),
)

# Let the user narrow the date range directly instead of relying on
# Plotly's built-in range slider (which renders as an empty strip when
# there are only a couple of points, and gets fiddly on mobile anyway).
min_date, max_date = symbol_df["Date"].min().date(), symbol_df["Date"].max().date()
if min_date != max_date:
    date_range = st.slider(
        "Zoom into a date range",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
        format="DD-MMM-YYYY",
        key="date_range_slider",
    )
    chart_df = symbol_df[
        (symbol_df["Date"].dt.date >= date_range[0])
        & (symbol_df["Date"].dt.date <= date_range[1])
    ]
else:
    chart_df = symbol_df

COLOR_OI = "#2563EB"      # deep blue
COLOR_FUTOI = "#F59E0B"   # amber — clearly distinct from blue, colorblind-friendlier than blue/light-blue
COLOR_BAN = "#DC2626"     # red

fig_trend = go.Figure()

# Shade the danger zone instead of just a thin dashed line, so "close to
# the ban" reads instantly rather than requiring the legend to be checked.
fig_trend.add_hrect(
    y0=95, y1=100,
    fillcolor=COLOR_BAN, opacity=0.08, line_width=0,
)
fig_trend.add_hline(
    y=95, line_dash="dash", line_color=COLOR_BAN, line_width=1.5,
    annotation_text="95% ban threshold", annotation_position="top left",
    annotation_font_color=COLOR_BAN, annotation_font_size=12,
)

def hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


for col, color, label in [
    ("OI_pct_MWPL", COLOR_OI, "OI % of MWPL"),
    ("FutOI_pct_MWPL", COLOR_FUTOI, "Future-equivalent OI % of MWPL"),
]:
    fig_trend.add_trace(
        go.Scatter(
            x=chart_df["Date"],
            y=chart_df[col],
            name=label,
            mode="lines+markers",
            line=dict(color=color, width=3, shape="spline", smoothing=0.3),
            marker=dict(size=8, color=color, line=dict(width=1.5, color="white")),
            fill="tozeroy",
            fillcolor=hex_to_rgba(color, 0.07),
            hovertemplate=f"<b>%{{x|%d-%b-%Y}}</b><br>{label}: %{{y:.2f}}%<extra></extra>",
        )
    )
    # Label the most recent point directly on the chart
    last_row = chart_df.iloc[-1]
    fig_trend.add_annotation(
        x=last_row["Date"], y=last_row[col],
        text=f"{last_row[col]:.1f}%",
        showarrow=False, xshift=38, font=dict(color=color, size=12, family="Arial"),
    )

fig_trend.update_layout(
    title=dict(
        text=f"<b>{selected_symbol}</b> — % of MWPL, day-wise",
        font=dict(size=18, family="Arial"),
    ),
    template="plotly_white",
    font=dict(family="Arial", size=13, color="#374151"),
    legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        font=dict(size=12),
    ),
    margin=dict(l=60, r=60, t=70, b=60),
    hovermode="x unified",
    plot_bgcolor="white",
    yaxis=dict(
        title="% of MWPL", range=[0, 105], ticksuffix="%",
        gridcolor="#F1F5F9", zeroline=False,
    ),
    xaxis=dict(
        title=None,
        type="date",
        dtick=86400000 if (chart_df["Date"].max() - chart_df["Date"].min()).days <= 21 else None,
        tickformat="%d-%b-%Y",
        tickangle=-30,
        gridcolor="#F8FAFC",
        showline=True, linecolor="#E5E7EB",
    ),
)
st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# --- Historical ban frequency (stretch feature) -------------------------
st.subheader("📅 Historical ban-period frequency")
ban_counts = (
    df[df["Ban_Flag"]]
    .groupby("NSE_Symbol")
    .size()
    .reset_index(name="Days_in_ban")
    .sort_values("Days_in_ban", ascending=False)
    .head(20)
)
if not ban_counts.empty:
    fig_freq = px.bar(
        ban_counts,
        x="NSE_Symbol",
        y="Days_in_ban",
        title="Symbols most frequently in the MWPL ban period (all history stored)",
    )
    st.plotly_chart(fig_freq, use_container_width=True)
else:
    st.info("No symbols have crossed the ban threshold yet in stored history.")

st.divider()

# --- Live intraday OI (Fyers, supplement to the official NSE EOD number) --
st.subheader("⚡ Live intraday futures OI (Fyers watchlist)")
st.caption(
    "Per-contract futures OI polled live during the trading day — a "
    "supplement to the official NSE end-of-day combined OI/MWPL figures "
    "above, not a replacement. Populated by `fyers_intraday_oi.py`."
)

if os.path.exists(INTRADAY_OI_PATH):
    intraday_df = pd.read_csv(INTRADAY_OI_PATH, parse_dates=["Timestamp"])
    intraday_symbols = sorted(intraday_df["NSE_Symbol"].unique())
    selected_intraday_symbol = st.selectbox(
        "Choose a watchlist symbol", intraday_symbols, key="intraday_symbol"
    )
    sym_df = intraday_df[
        intraday_df["NSE_Symbol"] == selected_intraday_symbol
    ].sort_values("Timestamp")

    fig_intraday = px.line(
        sym_df,
        x="Timestamp",
        y="Futures_OI",
        markers=True,
        title=f"{selected_intraday_symbol} — live futures OI today",
    )
    st.plotly_chart(fig_intraday, use_container_width=True)
else:
    st.info(
        "No intraday data yet. Run `python scripts/fyers_intraday_oi.py` "
        "during market hours to start logging."
    )
