"""Streamlit dashboard for Day 13, driven by config/dashboard.yaml.

Run:  streamlit run dashboard/app.py
Data: data/logs.jsonl (structured logs written by the API).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"

# Categorical slots 1-4 (validated reference palette), threshold in muted ink.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
THRESHOLD_COLOR = "#8a8984"

UNIT_LABELS = {
    "ms": "ms",
    "requests_per_minute": "requests/min",
    "percent": "%",
    "usd": "USD",
    "tokens": "tokens",
    "score_0_to_1": "score (0–1)",
}
OPERATOR_SYMBOLS = {"lte": "≤", "gte": "≥"}


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]


def load_logs(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    df = df.dropna(subset=["ts"])
    df["minute"] = df["ts"].dt.floor("1min")
    return df


def threshold_text(panel: dict) -> str:
    th = panel["threshold"]
    unit = UNIT_LABELS.get(panel["unit"], panel["unit"])
    return f"{th['aggregation']} {OPERATOR_SYMBOLS[th['operator']]} {th['value']:g} {unit}"


def base_figure(y_title: str, x_range: tuple[datetime, datetime] | None = None) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        height=300,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
        yaxis_title=y_title,
    )
    if x_range:
        fig.update_xaxes(range=list(x_range), title_text="time (UTC, 1-min buckets)")
    return fig


def add_threshold(fig: go.Figure, panel: dict, *, vertical: bool = False) -> None:
    th = panel["threshold"]
    label = f"threshold: {threshold_text(panel)}"
    kwargs = dict(line_dash="dash", line_color=THRESHOLD_COLOR, line_width=2,
                  annotation_text=label, annotation_font_color=THRESHOLD_COLOR)
    if vertical:
        fig.add_vline(x=th["value"], annotation_position="top left", **kwargs)
    else:
        fig.add_hline(y=th["value"], annotation_position="top left", **kwargs)


def status(value: float | None, panel: dict) -> str:
    if value is None or pd.isna(value):
        return "—"
    th = panel["threshold"]
    ok = value <= th["value"] if th["operator"] == "lte" else value >= th["value"]
    return "✅ within threshold" if ok else "🔴 breaching threshold"


def panel_header(panel: dict, value: float | None = None, fmt: str = "{:,.2f}") -> None:
    unit = UNIT_LABELS.get(panel["unit"], panel["unit"])
    st.subheader(panel["title"])
    shown = "—" if value is None or pd.isna(value) else fmt.format(value)
    st.caption(
        f"Unit: **{unit}** · Threshold: **{threshold_text(panel)}** · "
        f"Current {panel['threshold']['aggregation']}: **{shown}** {status(value, panel)}"
    )


def pct(numerator: float, denominator: float) -> float | None:
    return None if denominator == 0 else numerator / denominator * 100


# ---------------------------------------------------------------- panels


def latency_panel(panel: dict, df: pd.DataFrame, x_range) -> None:
    rs = df[df["event"] == "response_sent"].dropna(subset=["latency_ms"])
    p95 = rs["latency_ms"].quantile(0.95) if len(rs) else None
    panel_header(panel, p95, "{:,.0f}")
    if rs.empty:
        st.info("No `response_sent` events in window.")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("P50", f"{rs['latency_ms'].quantile(0.50):,.0f} ms")
    c2.metric("P95", f"{p95:,.0f} ms")
    c3.metric("P99", f"{rs['latency_ms'].quantile(0.99):,.0f} ms")
    c4.metric("TTFT P95", f"{rs['ttft_ms'].quantile(0.95):,.0f} ms")
    by_min = rs.groupby("minute").agg(
        p50=("latency_ms", lambda s: s.quantile(0.50)),
        p95=("latency_ms", lambda s: s.quantile(0.95)),
        p99=("latency_ms", lambda s: s.quantile(0.99)),
        ttft_p95=("ttft_ms", lambda s: s.quantile(0.95)),
    )
    fig = base_figure("latency (ms)", x_range)
    for (col, name), color in zip(
        [("p50", "P50"), ("p95", "P95"), ("p99", "P99"), ("ttft_p95", "TTFT P95")], SERIES
    ):
        fig.add_scatter(x=by_min.index, y=by_min[col], name=name, mode="lines+markers",
                        line=dict(color=color, width=2), marker=dict(size=8))
    add_threshold(fig, panel)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def traffic_panel(panel: dict, df: pd.DataFrame, x_range, minutes: int) -> None:
    rq = df[df["event"] == "request_received"]
    rate = len(rq) / minutes
    panel_header(panel, rate, "{:,.2f}")
    c1, c2 = st.columns(2)
    c1.metric("Requests (60 min)", f"{len(rq):,}")
    c2.metric("Avg rate", f"{rate:,.2f} req/min")
    by_min = rq.groupby("minute").size()
    fig = base_figure("requests / min", x_range)
    fig.add_bar(x=by_min.index, y=by_min.values, name="requests/min",
                marker_color=SERIES[0])
    add_threshold(fig, panel)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def errors_panel(panel: dict, df: pd.DataFrame, x_range) -> None:
    rq = df[df["event"] == "request_received"]
    failed = df[df["event"] == "request_failed"]
    tool = df[df["tool_success"].notna()] if "tool_success" in df else df.iloc[0:0]
    error_rate = pct(len(failed), len(rq))
    retrieval = pct(int((tool["tool_success"] == True).sum()), len(tool))  # noqa: E712
    panel_header(panel, error_rate, "{:,.2f}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Error rate", "—" if error_rate is None else f"{error_rate:.2f} %")
    c2.metric("Failed requests", f"{len(failed):,}")
    c3.metric("Retrieval success", "—" if retrieval is None else f"{retrieval:.1f} %")

    minutes = rq.groupby("minute").size().rename("total").to_frame()
    minutes["failed"] = failed.groupby("minute").size()
    minutes["tool_total"] = tool.groupby("minute").size()
    minutes["tool_ok"] = tool[tool["tool_success"] == True].groupby("minute").size()  # noqa: E712
    minutes = minutes.fillna(0)
    minutes["error_rate"] = minutes["failed"] / minutes["total"].where(minutes["total"] > 0) * 100
    minutes["retrieval"] = minutes["tool_ok"] / minutes["tool_total"].where(minutes["tool_total"] > 0) * 100

    fig = base_figure("percent (%)", x_range)
    fig.add_scatter(x=minutes.index, y=minutes["error_rate"], name="error rate %",
                    mode="lines+markers", line=dict(color=SERIES[1], width=2), marker=dict(size=8))
    fig.add_scatter(x=minutes.index, y=minutes["retrieval"], name="retrieval success %",
                    mode="lines+markers", line=dict(color=SERIES[2], width=2), marker=dict(size=8))
    fig.update_yaxes(range=[0, 105])
    add_threshold(fig, panel)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.markdown("**Breakdown by `error_type`**")
    if failed.empty or "error_type" not in failed:
        st.caption("No failed requests in window.")
    else:
        breakdown = failed["error_type"].fillna("unknown").value_counts().rename("count")
        st.dataframe(breakdown, width="stretch")


def cost_panel(panel: dict, df: pd.DataFrame, x_range) -> None:
    rs = df[df["event"] == "response_sent"].dropna(subset=["cost_usd"])
    total = rs["cost_usd"].sum() if len(rs) else 0.0
    panel_header(panel, total, "${:,.4f}")
    c1, c2 = st.columns(2)
    c1.metric("Total (60 min)", f"${total:,.4f}")
    c2.metric("Avg per request", f"${(total / len(rs)) if len(rs) else 0:,.6f}")
    by_min = rs.groupby("minute")["cost_usd"].sum()
    fig = base_figure("USD", x_range)
    fig.add_bar(x=by_min.index, y=by_min.values, name="cost per minute", marker_color=SERIES[0])
    fig.add_scatter(x=by_min.index, y=by_min.cumsum().values, name="cumulative total",
                    mode="lines+markers", line=dict(color=SERIES[1], width=2), marker=dict(size=8))
    add_threshold(fig, panel)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def tokens_panel(panel: dict, df: pd.DataFrame) -> None:
    rs = df[df["event"] == "response_sent"]
    tin = rs["tokens_in"].sum() if "tokens_in" in rs else 0
    tout = rs["tokens_out"].sum() if "tokens_out" in rs else 0
    panel_header(panel, max(tin, tout), "{:,.0f}")
    c1, c2 = st.columns(2)
    c1.metric("Input tokens", f"{tin:,.0f}")
    c2.metric("Output tokens", f"{tout:,.0f}")
    fig = base_figure("")
    fig.add_bar(y=["tokens_in", "tokens_out"], x=[tin, tout], orientation="h",
                marker_color=[SERIES[0], SERIES[1]], text=[f"{tin:,.0f}", f"{tout:,.0f}"],
                textposition="outside", name="sum over 60 min", showlegend=False)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(title_text="tokens (sum over 60 min)",
                     range=[0, max(panel["threshold"]["value"], tin, tout) * 1.15])
    add_threshold(fig, panel, vertical=True)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def quality_panel(panel: dict, df: pd.DataFrame, x_range) -> None:
    rs = df[df["event"] == "response_sent"].dropna(subset=["quality_score"])
    mean = rs["quality_score"].mean() if len(rs) else None
    panel_header(panel, mean, "{:.3f}")
    st.metric("Mean quality score", "—" if mean is None else f"{mean:.3f}")
    by_min = rs.groupby("minute")["quality_score"].mean()
    fig = base_figure("score (0–1)", x_range)
    fig.add_scatter(x=by_min.index, y=by_min.values, name="mean quality",
                    mode="lines+markers", line=dict(color=SERIES[2], width=2), marker=dict(size=8))
    fig.update_yaxes(range=[0, 1.05])
    add_threshold(fig, panel)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# ---------------------------------------------------------------- page

config = load_config()
panels = {p["id"]: p for p in config["panels"]}
minutes = config["time_range_minutes"]
log_path = REPO_ROOT / panels["latency"]["source"]

st.set_page_config(page_title=config["title"], page_icon="📈", layout="wide")

with st.sidebar:
    st.header("Settings")
    anchor = st.radio(
        "Window ends at",
        ["now", "latest log event"],
        help="'latest log event' is useful to review a past run; the window is still "
        f"{minutes} minutes.",
    )
    st.caption(f"Source: `{panels['latency']['source']}`")
    st.caption(f"Contract: `config/dashboard.yaml` · refresh {config['refresh_seconds']}s")


@st.fragment(run_every=f"{config['refresh_seconds']}s")
def render() -> None:
    df_all = load_logs(log_path)
    if df_all.empty:
        st.warning(f"No logs found at `{log_path}`. Run the API and `scripts/load_test.py` first.")
        return
    end = datetime.now(timezone.utc) if anchor == "now" else df_all["ts"].max().to_pydatetime()
    start = end - timedelta(minutes=minutes)
    df = df_all[(df_all["ts"] >= start) & (df_all["ts"] <= end)]
    x_range = (start, end)

    st.title(config["title"])
    st.markdown(
        f"**Time range: last {minutes} minutes** "
        f"({start:%Y-%m-%d %H:%M} → {end:%H:%M} UTC) · auto-refresh every "
        f"{config['refresh_seconds']}s · last refresh {datetime.now(timezone.utc):%H:%M:%S} UTC · "
        f"{len(df):,} log records in window"
    )
    if df.empty:
        st.warning("No log records in the selected window. Run `python scripts/load_test.py` "
                   "or switch the window to end at the latest log event.")
        return

    row1 = st.columns(2, border=True)
    with row1[0]:
        latency_panel(panels["latency"], df, x_range)
    with row1[1]:
        traffic_panel(panels["traffic"], df, x_range, minutes)
    row2 = st.columns(2, border=True)
    with row2[0]:
        errors_panel(panels["errors"], df, x_range)
    with row2[1]:
        cost_panel(panels["cost"], df, x_range)
    row3 = st.columns(2, border=True)
    with row3[0]:
        tokens_panel(panels["tokens"], df)
    with row3[1]:
        quality_panel(panels["quality"], df, x_range)


render()
