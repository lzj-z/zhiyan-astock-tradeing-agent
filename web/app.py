"""TradingAgents A股分析 — Streamlit Web UI."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# override=True：让 .env 的值优先于进程里可能残留的空/旧环境变量（#66）。
# 注意：load_dotenv 仅在进程启动时执行一次，启动后修改 .env 仍需重启 Web 服务才生效。
load_dotenv(_PROJECT_ROOT / ".env", override=True)

from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402

from web.components.progress_panel import render_progress  # noqa: E402
from web.components.report_viewer import render_report  # noqa: E402
from web.components.sidebar import render_sidebar  # noqa: E402
from web.history import clear_incomplete_task, extract_signal, load_analysis  # noqa: E402
from web.progress import ProgressTracker  # noqa: E402
from web.runner import run_analysis_in_thread  # noqa: E402

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="TradingAgents-Astock A股分析",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');

    /* Hide Streamlit chrome for clean video recording.
       IMPORTANT: do NOT `display:none` the whole header OR the whole toolbar.
       In Streamlit >= 1.36 the "expand sidebar" button lives *inside* the
       toolbar (header > stToolbar > stExpandSidebarButton), so hiding either
       one makes a collapsed sidebar impossible to reopen (issue #36). Instead
       keep the header/toolbar in the DOM, make the header transparent, and
       hide only the individual chrome widgets we don't want on camera. */
    #MainMenu,
    footer,
    div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"],
    div[data-testid="stToolbarActions"],
    div[data-testid="stAppDeployButton"],
    span[data-testid="stMainMenu"] { display: none !important; }
    header[data-testid="stHeader"] {
        background: transparent !important;
        box-shadow: none !important;
    }
    /* Keep the sidebar collapse / expand controls always visible & clickable.
       Selector list spans multiple Streamlit versions. */
    button[data-testid="stExpandSidebarButton"],
    button[data-testid="stSidebarCollapseButton"],
    button[data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    }
    .stApp {
        background: #ffffff;
        color: #111925;
    }
    section[data-testid="stSidebar"] {
        background: #f7f9fc;
        border-right: 1px solid #dbe2ec;
    }
    .stMetric label { color: #657184 !important; font-size: 0.8rem !important; }
    .stMetric [data-testid="stMetricValue"] {
        color: #166ff7 !important;
        font-weight: 700 !important;
    }
    .stProgress > div > div > div {
        background: #166ff7 !important;
    }
    button[kind="primary"] {
        background: #111925 !important;
        border: 1px solid #111925 !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        box-shadow: 0 8px 20px rgba(17, 25, 37, 0.14) !important;
        transition: all 0.2s ease !important;
    }
    button[kind="primary"]:hover {
        background: #166ff7 !important;
        border-color: #166ff7 !important;
        box-shadow: 0 10px 24px rgba(22, 111, 247, 0.2) !important;
        transform: translateY(-1px) !important;
    }
    button[kind="primary"]:disabled {
        background: #a7b1bf !important;
        border-color: #a7b1bf !important;
        box-shadow: none !important;
        opacity: 0.65 !important;
    }
    /* Secondary buttons (history items) */
    button[kind="secondary"] {
        background: #ffffff !important;
        border: 1px solid #dbe2ec !important;
        color: #2d3848 !important;
        transition: all 0.2s ease !important;
    }
    button[kind="secondary"]:hover {
        background: #edf5ff !important;
        border-color: #166ff7 !important;
        color: #166ff7 !important;
    }
    .stExpander {
        background: #ffffff !important;
        border: 1px solid #dbe2ec !important;
        border-radius: 8px !important;
    }
    .stTabs [data-baseweb="tab"] {
        color: #657184 !important;
    }
    .stTabs [aria-selected="true"] {
        color: #166ff7 !important;
        border-bottom-color: #166ff7 !important;
    }
    div[data-testid="stDownloadButton"] button {
        background: #ffffff !important;
        border: 1px solid #166ff7 !important;
        color: #166ff7 !important;
    }
    /* Text input styling */
    input[data-testid="stTextInputRootElement"] input,
    .stTextInput input {
        background: #ffffff !important;
        border-color: #dbe2ec !important;
        color: #111925 !important;
    }
    .stTextInput input:focus {
        border-color: #166ff7 !important;
        box-shadow: 0 0 0 1px #166ff7 !important;
    }
    /* Date input styling */
    .stDateInput input {
        background: #ffffff !important;
        border-color: #dbe2ec !important;
        color: #111925 !important;
    }
    .welcome-hero {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 60vh;
        margin: 0 -3rem;
        padding: 3rem 2rem;
        text-align: center;
        background:
            radial-gradient(circle at 18% 30%, rgba(224, 248, 255, 0.84), transparent 38%),
            radial-gradient(circle at 78% 24%, rgba(179, 200, 255, 0.72), transparent 40%),
            radial-gradient(circle at 58% 78%, rgba(240, 240, 255, 0.9), transparent 42%),
            #f6f9fe;
    }
    .welcome-brand {
        color: #111925;
        font-size: 2.5rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    .welcome-brand span { color: #166ff7; }
    .welcome-copy {
        color: #455166;
        font-size: 1.1rem;
        max-width: 540px;
        line-height: 1.7;
    }
    .welcome-prompt {
        margin-top: 2rem;
        padding: 1rem 2rem;
        background: #111925;
        border-radius: 999px;
        color: #ffffff;
        font-size: 0.9rem;
        font-weight: 700;
        box-shadow: 0 12px 24px rgba(17, 25, 37, 0.14);
    }
    .welcome-note {
        margin-top: 2.5rem;
        color: #657184;
        font-size: 0.75rem;
        max-width: 520px;
        line-height: 1.6;
    }
    @media (max-width: 700px) {
        .welcome-hero { margin: 0 -1rem; padding: 2.5rem 1.25rem; }
        .welcome-brand { font-size: 2.15rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Build config ─────────────────────────────────────────────────────────────

def _build_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    config["quick_think_provider"] = st.session_state.get(
        "quick_think_provider", config["quick_think_provider"]
    )
    config["deep_think_provider"] = st.session_state.get(
        "deep_think_provider", config["deep_think_provider"]
    )
    # llm_provider remains the legacy fallback for callers that only set one provider.
    config["llm_provider"] = config["quick_think_provider"]
    config["quick_think_llm"] = st.session_state.get(
        "quick_think_llm", config["quick_think_llm"]
    )
    config["deep_think_llm"] = st.session_state.get(
        "deep_think_llm", config["deep_think_llm"]
    )
    # Optional third-party / proxy endpoint. Sidebar input wins, else .env BACKEND_URL.
    backend_url = (st.session_state.get("llm_base_url") or os.getenv("BACKEND_URL") or "").strip()
    config["backend_url"] = backend_url or None
    config["data_vendors"] = {
        "core_stock_apis": "a_stock",
        "technical_indicators": "a_stock",
        "fundamental_data": "a_stock",
        "news_data": "a_stock",
        "signal_data": "a_stock",
    }
    # Analysis window (#16): start-date input in the sidebar → look-back days.
    config["market_lookback_days"] = st.session_state.get("market_lookback_days")
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["checkpoint_enabled"] = True
    config["output_language"] = "Chinese"
    # Optional: route nodes through a personal Claude Pro/Max subscription (Agent
    # SDK). Scope: "deep" = Research/Portfolio only; "all" = + the 7 analysts.
    # Leaving the fallback keys None makes the graph fall back to the
    # sidebar-selected llm_provider + models on quota/failure.
    scope = st.session_state.get("subscription_scope", "off")
    # 侧栏那个输入框只配**深度节点**的模型。不要把它同时赋给 quick——
    # quick 节点有 7 个分析师 + 多空/交易员/风险辩手，把深度节点的 opus 复制过去
    # 会让订阅额度烧得极快，也与 README / 侧栏提示所说的「quick 默认 sonnet」矛盾。
    # quick 的模型交给 DEFAULT_CONFIG（默认 sonnet），需要时在 config 层单独覆盖。
    sub_model = st.session_state.get("agent_sdk_model")
    if scope in ("deep", "all"):
        config["deep_think_provider_override"] = "claude_agent_sdk"
        if sub_model:
            config["agent_sdk_model"] = sub_model
    if scope == "all":
        config["quick_think_provider_override"] = "claude_agent_sdk"
    return config


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    render_sidebar()


# ── Handle "Start Analysis" trigger ──────────────────────────────────────────

start_req = st.session_state.pop("start_analysis", None)
if start_req:
    if start_req.get("fresh"):
        from tradingagents.graph.checkpointer import clear_checkpoint

        clear_incomplete_task(start_req["ticker"], start_req["trade_date"])
        clear_checkpoint(
            DEFAULT_CONFIG["data_cache_dir"],
            start_req["ticker"],
            start_req["trade_date"],
        )

    tracker = ProgressTracker(
        ticker=start_req["ticker"],
        trade_date=start_req["trade_date"],
    )
    st.session_state["tracker"] = tracker
    st.session_state["viewing_history"] = None
    run_analysis_in_thread(
        ticker=start_req["ticker"],
        trade_date=start_req["trade_date"],
        config=_build_config(),
        tracker=tracker,
    )


# ── Main area state machine ─────────────────────────────────────────────────

tracker: ProgressTracker | None = st.session_state.get("tracker")
viewing_history: str | None = st.session_state.get("viewing_history")

# State 1: Viewing a historical analysis
if viewing_history:
    try:
        state = load_analysis(viewing_history)
        signal = extract_signal(state)
        ticker = Path(viewing_history).parent.parent.name
        trade_date = Path(viewing_history).stem.replace("full_states_log_", "")
        render_report(state, ticker, trade_date, signal)
    except Exception as exc:
        st.error(f"加载失败: {exc}")

# State 2: Analysis running
elif tracker and tracker.is_running:
    render_progress(tracker)
    time.sleep(2)
    st.rerun()

# State 3: Analysis complete
elif tracker and tracker.is_complete:
    render_report(
        tracker.final_state,
        tracker.ticker,
        tracker.trade_date,
        tracker.signal,
        elapsed=tracker.elapsed,
    )

# State 4: Analysis errored
elif tracker and tracker.error:
    st.error(f"分析失败: {tracker.error}")
    st.caption("已完成阶段会保存在本地断点中；修复模型额度或配置后，可以继续未完成的部分。")
    if st.button("继续未完成任务", type="primary"):
        st.session_state["start_analysis"] = {
            "ticker": tracker.ticker,
            "trade_date": tracker.trade_date,
        }
        st.session_state["viewing_history"] = None
        st.rerun()

# State 0: Idle — welcome screen
else:
    st.markdown(
        """
        <div class="welcome-hero">
            <div style="font-size: 4rem; margin-bottom: 1rem;">📈</div>
            <div class="welcome-brand">
                <span>智研</span>A股
            </div>
            <div class="welcome-copy">
                A股多Agent投研分析系统<br>
                7位AI分析师 → 质量门控 → 多空辩论 → 风控评估 → 最终决策
            </div>
            <div class="welcome-prompt">
                ← 在左侧输入股票代码，开始分析
            </div>
            <div class="welcome-note">
                ⚠️ 本项目仅供学习研究与技术演示，不构成任何投资建议。<br>
                投资决策请咨询持牌专业机构。作者不对使用本工具产生的任何损失承担责任。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
