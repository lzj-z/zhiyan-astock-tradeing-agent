


### 核心改造

| 维度 | 原版 | 本 Fork |
|------|------|---------|
| **数据源** | Yahoo Finance / Alpha Vantage | mootdx + 东财 + 新浪 + 同花顺（全免费直连） |
| **Analyst 角色** | 4 个（市场/情绪/新闻/基本面） | **7 个**（+政策分析师/游资追踪/解禁监控） |
| **交易规则** | 美股（T+0、无涨跌停） | A 股（T+1、涨跌停、最小手数、交易时段） |
| **输出语言** | 英文 | 中文报告（内部辩论保持英文以保证推理质量） |
| **Alpha 基准** | SPY | 沪深 300（CSI 300） |

---

## 与上游对比

| 特性 | 原版 TradingAgents | **本 Fork** |
|------|-------------------|-------------|
| 许可证 | Apache 2.0 | **全 Apache 2.0** |
| 部署依赖 | pip install | **开箱即用** |
| A 股数据 | ❌ | **mootdx + 东财 + 新浪 + 同花顺（直连 HTTP）** |
| A 股特化角色 | ❌ | **政策/游资/解禁 3 个深度角色** |
| A 股交易约束 | ❌ | **T+1/涨跌停/手数/ST 全覆盖** |

---

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    7 Analyst 研报生成                      │
│  Market → Social → News → Fundamentals                   │
│  → Policy → Hot Money → Lockup                           │
│         （每个 Analyst 带工具循环）                          │
├─────────────────────────────────────────────────────────┤
│               Bull vs Bear 投研辩论                       │
│         Bull Researcher ←→ Bear Researcher               │
│               （最多 N 轮辩论）                             │
├─────────────────────────────────────────────────────────┤
│              Research Manager 综合研判                     │
│         （深度思考 LLM，输出投资计划）                       │
├─────────────────────────────────────────────────────────┤
│                  Trader 交易方案                          │
│         （A 股约束：T+1/涨跌停/手数）                       │
├─────────────────────────────────────────────────────────┤
│        Aggressive ←→ Conservative ←→ Neutral             │
│               三方风险辩论                                 │
├─────────────────────────────────────────────────────────┤
│            Portfolio Manager 最终决策                      │
│     （深度思考 LLM，输出评级 + 理由）                       │
└─────────────────────────────────────────────────────────┘
```

**双 LLM 设计**：
- `quick_think_llm`：所有 Analyst、Researcher、Trader、Risk Debater
- `deep_think_llm`：Research Manager 和 Portfolio Manager（需要综合全局信息做决策）

---

## 7 个 Analyst 角色

### 原版 4 角色（A 股适配）

| 角色 | 职责 | 数据工具 |
|------|------|---------|
| 🏪 市场分析师 | K 线形态、技术指标、量价分析 | `get_stock_data`, `get_indicators` |
| 💬 舆情分析师 | 社交媒体情绪、散户讨论热度 | `get_news` |
| 📰 新闻分析师 | 行业新闻、公告、宏观事件 | `get_news`, `get_global_news`, `get_insider_transactions` |
| 📊 基本面分析师 | 财报三表、盈利能力、估值 | `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement` |

### A 股特化 3 角色（新增）

| 角色 | 职责 | 数据工具 | 为什么需要 |
|------|------|---------|-----------|
| 🏛️ 政策分析师 | 监管政策、产业政策、窗口指导 | `get_news`, `get_global_news` | A 股是政策市，政策变化直接影响板块轮动 |
| 🔥 游资追踪师 | 龙虎榜、大单流向、主力资金动态 | `get_stock_data`, `get_news`, `get_insider_transactions` | 游资是 A 股短线定价的核心力量 |
| 🔓 解禁监控师 | 限售股解禁、大股东减持、股权质押 | `get_insider_transactions`, `get_news`, `get_fundamentals` | 解禁是 A 股特有的重大供给冲击因素 |

所有 7 个 Analyst 的报告会流入后续的 Bull/Bear 辩论和三方风险辩论，确保 A 股特色因素贯穿整条决策链。

---

## 数据源

全部免费，无需 API Key，无积分墙：

| 来源 | 协议 | 提供内容 |
|------|------|---------|
| **mootdx** | TCP 7709 | OHLCV K 线、财务快照、F10 文本 |
| **腾讯财经** | HTTP (`qt.gtimg.cn`) | PE / PB / 市值 / 换手率（实时） |
| **东方财富** | HTTP (datacenter / push2) | 龙虎榜、限售解禁、板块行情、个股信息 |
| **新浪财经** | HTTP | K 线历史、财报三表 |
| **同花顺** | HTTP (10jqka) | EPS 一致预期 |
| **财联社** | HTTP (cls.cn) | 全球财经快讯 |
| **百度股市通** | HTTP (finance.pae.baidu) | 概念板块分类、资金流向 |

> 完全不依赖 Tushare（积分墙）、Alpha Vantage（海外 API）、Yahoo Finance（不支持 A 股）。

---

> **数据源优先级 & 东财防封（v0.2.11）**：行情 / K线 / 市值 / 财务能从 mootdx（通达信 TCP，不封 IP）或腾讯拿到的，一律走它们；东财只用于它独有的数据（龙虎榜 / 解禁 / 资金流 / 板块 / 个股新闻等）。所有东财请求统一走内置节流入口 `_em_get()`：串行限流（默认间隔 ≥1s + 0.1~0.5s 随机抖动）+ 复用 Keep-Alive 会话，多 Agent 跑批量分析不再触发临时封 IP（东财风控实测：每秒 >5 / 并发 ≥10 / 1 分钟 ≥200 触发封禁）。批量场景可设环境变量 `EM_MIN_INTERVAL=1.5~2` 进一步降速。**仅东财限流，mootdx / 腾讯 / 新浪 / 同花顺 / 财联社 / 百度 不受影响。**

## 快速开始

### 1. 环境准备

```bash
# Python >= 3.10
git clone https://github.com/simonlin1212/tradingagents-astock.git
cd tradingagents-astock
pip install -e .

# 如需使用 Google Gemini 模型（无 [google] extra，需显式装，见下方 FAQ）：
pip install --no-deps "langchain-google-genai>=4.0.0"
pip install "google-genai>=1.53.0" "httpx>=0.28.1"

# 如需让节点走你个人 Claude Pro/Max 订阅额度而非 API 计费（可选）：
pip install -e ".[agentsdk]"
```

> **装完即可用，无需 Docker。** 安装后直接跑 `streamlit run web/app.py`（Web UI）或 `tradingagents`（CLI）即可，详见下方「Web UI」「CLI 方式」两节。Docker 仅是可选的部署方式，本地开发不需要。

### 2. 配置 LLM

> **默认走 API Key 计费**。每次分析需 30-50 次 LLM 调用。
>
> **例外（v0.4.0 新增）**：装 `[agentsdk]` 后可让部分或全部节点经 Claude Agent SDK 走你**个人 Claude Pro/Max 订阅额度**，不产生 API 账单。见下方「用个人 Claude 订阅额度」。

在项目根目录创建 `.env` 文件，按你选择的供应商配置：

```bash
# ── 方案 A：MiniMax（推荐，国内直连，性价比高）──────────
MINIMAX_API_KEY=sk-xxx
# 申请地址：https://platform.minimaxi.com/

# ── 方案 B：DeepSeek ─────────────────────────────────
DEEPSEEK_API_KEY=sk-xxx
# 申请地址：https://platform.deepseek.com/

# ── 方案 C：智谱 GLM ─────────────────────────────────
ZHIPU_API_KEY=xxx
# 申请地址：https://open.bigmodel.cn/

# ── 方案 D：通义千问 Qwen ────────────────────────────
DASHSCOPE_API_KEY=sk-xxx
# 申请地址：https://dashscope.console.aliyun.com/

# ── 方案 E：OpenAI ───────────────────────────────────
OPENAI_API_KEY=sk-xxx

# ── 方案 F：Anthropic ────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-xxx

# ── 方案 G：Kimi（Anthropic 兼容 API）────────────────
ANTHROPIC_API_KEY=your-kimi-token
ANTHROPIC_BASE_URL=https://api.kimi.com/coding/
# ⚠️ 两个都要设。只给 key 不给端点，请求会发到 Anthropic 官方并报
#    「401 invalid x-api-key」。端点也可以写在 config 的 backend_url 里（见下）。
# ⚠️ 别用 ANTHROPIC_AUTH_TOKEN——那是 Claude Code CLI 的写法，本项目走 langchain，
#    只认 ANTHROPIC_API_KEY。

# ── 方案 H：任意 OpenAI 兼容网关（9Router / AI Router / 自建代理）──
OPENAI_COMPATIBLE_API_KEY=sk-xxx     # 也接受 OPENAI_API_KEY
BACKEND_URL=https://your-relay.example/v1   # 你的网关地址（也可在 Web 侧栏「API Base URL」填）
```

### 3. 运行分析

新建一个 Python 文件（比如项目根目录下的 `run.py`），把下面这段粘进去，按你选的供应商改 `config` 后运行 `uv run python run.py`。根目录自带的 `main.py` 就是这个示例的可运行版本，直接 `uv run python main.py` 也行。

> `config` 不是仓库里的某个配置文件，而是传给 `TradingAgentsGraph(config=...)` 的一个字典：只写你要覆盖的项，其余项自动取 `tradingagents/default_config.py` 里的默认值（完整可选项见下文「配置说明」一节）。

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph

# ── 双 LLM 示例：quick 走千问，deep 走 DeepSeek ──────
config = {
    "quick_think_provider": "qwen",
    "quick_think_llm": "qwen3.8-flash",
    "quick_think_max_tokens": 131072,
    "deep_think_provider": "deepseek",
    "deep_think_llm": "deepseek-flash",
    "deep_think_max_tokens": 393216,
    "output_language": "Chinese",
}

# ── Anthropic + Kimi 示例 ───────────────────────────
# config = {
#     "llm_provider": "anthropic",
#     "deep_think_llm": "claude-sonnet-4-6",
#     "quick_think_llm": "claude-sonnet-4-6",
#     "backend_url": "https://api.kimi.com/coding/",
#     "output_language": "Chinese",
# }

ta = TradingAgentsGraph(debug=True, config=config)
final_state, decision = ta.propagate("688017", "2026-05-12")
print(decision)
```

### 4. CLI 方式

```bash
tradingagents                 # 交互式 CLI
tradingagents analyze         # 同上（默认命令）
tradingagents performance     # 决策绩效统计（见下）
tradingagents --help          # 查看所有选项
```

### 5. 决策绩效统计（v0.5.2 新增）

想知道**这套流程过往的判断准不准**，跑：

```bash
tradingagents performance            # 人读的报告
tradingagents performance --json     # 机器读的 JSON
```

数据来自记忆日志：每次分析会落一条决策，下次分析同一只股票时自动拉真实行情回填收益与 alpha（对沪深 300）。**统计本身零 LLM 调用**，只读已经落盘的结果。

输出的核心指标是 **`direction_accuracy`（方向正确率）**——**只有它衡量判断准不准**：看多要跑赢、看空要跑输才算对，Hold 不表态不计入。另外给出 `up_rate`（标的上涨占比）与 `outperform_rate`（跑赢沪深300占比），这两个只描述标的怎么走，**与判断对错无关**：给出卖出评级后股价下跌是判断正确，但它不会计入「上涨占比」。

还有按评级、按标的分组，以及一项**评级区分度检验**——五档评级从 Buy 到 Sell，平均 alpha 是否真的单调递减。评级不单调，说明这套流程的评级没有实际区分能力。

几点务必注意：

- **这不是回测，也不是策略业绩。** 每条记录是「某天做出的判断在固定持有期后的表现」：持有窗口互相重叠、没有仓位管理、未计交易成本与冲击成本，样本还可能有选择偏差。
- **A 股 beta 很强**，跟着大盘涨不代表判断对，所以方向正确率用 alpha 口径判定，看绝对收益容易高估判断力。
- **样本量分开算**：方向正确率只统计有方向的评级，已结算总数够、但有方向的不足 20 条时，报告会单独提示这个指标仍是噪音。
- **样本少于 20 条时报告会自己标注「这些比率基本是噪音」**，不要拿三五条记录下结论。
- 收益解析不出来的记录会被**跳过**而不是当成 0%——后者会把统计悄悄拉向中性。

---

## Web UI

内置 Streamlit 可视化界面，支持在侧边栏选择 LLM 供应商和模型，输入股票代码即可一键分析，适合不写代码的用户。

### 启动

```bash
# 方式一：命令行启动（推荐）
tradingagents-web

# 方式二：直接运行
streamlit run web/app.py
```

打开浏览器访问 `http://localhost:8501`。

### 功能

- **配置记住**：侧栏选的供应商 / 模型 / Base URL / 订阅覆盖写入 `~/.tradingagents/llm_config.json`，重开标签页或重启后自动恢复（v0.5.17）
- **模型自选**：快速与深度两档模型可分别选择供应商和模型（MiniMax/DeepSeek/Qwen/GLM/OpenAI/Anthropic/Google/xAI/OpenRouter/Ollama），外加 **「OpenAI 兼容（自定义 base_url）」** 一档可接任意 OpenAI 兼容网关（9Router / AI Router / 自建代理）
- **一键分析**：输入 6 位 A 股代码 + 分析日期 +「数据起始日期」（默认本月第一天，可自定义技术分析回溯区间，支持按月/自定义时段分析），点击「开始分析」
- **实时进度**：12 阶段 pipeline 实时显示（7 分析师 → 质量门控 → 辩论 → 风控 → 决策），所有已完成阶段的报告均可展开查看
- **完整报告**：信号卡片（Buy/Hold/Sell）、7 份分析师报告、多空辩论、风控评估
- **报告导出**：一键下载 **Markdown**（零依赖，永远可用）或 **PDF** 完整分析报告（PDF 自动适配 Windows/macOS/Linux 中文字体）
- **历史记录**：自动保存并展示所有历史分析



## 配置说明

所有配置通过 `config` 字典传入，完整选项：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `llm_provider` | `"qwen"` | 兼容旧配置的默认 provider；未设置下方分档 provider 时两档都沿用它 |
| `quick_think_provider` | `"qwen"` | 所有 Analyst / Researcher / Trader / Risk Debater 的 provider |
| `quick_think_llm` | `"qwen3.8-flash"` | quick 档模型 |
| `quick_think_max_tokens` | `131072` | quick 档单次回复最大输出 token；设置时优先于 `max_tokens` |
| `deep_think_provider` | `"deepseek"` | Research Manager + Portfolio Manager 的 provider |
| `deep_think_llm` | `"deepseek-flash"` | deep 档模型 |
| `deep_think_max_tokens` | `393216` | deep 档单次回复最大输出 token；设置时优先于 `max_tokens` |
| `backend_url` | `None` | 自定义 API 端点 / 第三方中转网关。可在 Web UI 侧边栏填写，或用 `.env` 的 `BACKEND_URL`；方便国内通过代理访问 Claude / OpenAI |
| `role_llms` | `{}` | **可选**：给单个角色指定另一家模型（如多空辩手用不同厂商），留空 = 全部沿用 quick/deep 两档，行为不变。见下方「分角色模型」 #39 |
| `max_tokens` | `None` | 两档都未设置分档上限时的通用单次回复最大输出 token 数。**报告写到一半就断，先调这里**（不是上下文超长）；也可用环境变量 `TRADINGAGENTS_MAX_TOKENS`。#91 |
| `output_language` | `"Chinese"` | 报告输出语言（内部辩论始终英文） |
| `market_lookback_days` | `None` | 技术分析回溯天数（分析区间 = 起始日期 → 分析日期）。Web/CLI 由「数据起始日期」自动算出；`None` = 模型自选（约 30 天）。#16 |
| `max_debate_rounds` | `1` | Bull vs Bear 辩论轮数 |
| `max_risk_discuss_rounds` | `1` | 风险三方辩论轮数 |
| `data_vendors` | 全部 `"a_stock"` | 数据供应商路由 |
| `checkpoint_enabled` | `False` | 启用 SQLite 断点续跑 |
| `memory_log_max_entries` | `None` | 交易记忆最大条目数 |

---

### 分角色模型（可选，v0.5.0 新增）

默认所有角色共用 `quick_think_llm` / `deep_think_llm` 两档——**大多数人只有一家模型，不需要碰这一项**。

如果你手上有多家模型，可以给单个角色单独指定。最典型的用法是**让多空辩手用不同厂商的模型**：同一个模型分饰多角时倾向于互相附和，换成不同底座才会真的出现反驳。

```python
config = {
    "llm_provider": "deepseek",          # 未单独配置的角色仍走这里
    "deep_think_llm": "deepseek-chat",
    "quick_think_llm": "deepseek-chat",
    "role_llms": {
        "bull": {"provider": "qwen",    "model": "qwen-plus"},
        "bear": {"provider": "glm",     "model": "glm-4.6"},
        # provider 省略则沿用 llm_provider，只换模型：
        "portfolio_manager": {"model": "deepseek-reasoner"},
    },
}
```

合法角色名（其余角色自动沿用两档默认）：

| 分组 | 角色名 |
|------|--------|
| 7 个分析师 | `market` `social` `news` `fundamentals` `policy` `hot_money` `lockup` |
| 辩论与决策 | `bull` `bear` `research_manager` `trader` |
| 风险三方 | `risk_aggressive` `risk_neutral` `risk_conservative` |
| 其他 | `quality_gate` `portfolio_manager` |

几点说明：

- **角色名写错会直接报错**，不会静默忽略——否则你会以为配置生效了，实际没有。
- **相同的 provider + model 只建一个实例**，写 7 个角色不会开 7 条连接。
- 每家 provider 用**自己的** API Key 环境变量（`DEEPSEEK_API_KEY` / `DASHSCOPE_API_KEY` / `ZHIPU_API_KEY` …），缺哪个会指名报出来。
- 换了 provider 时**不会**把 `backend_url` 带过去（那是给主 provider 配的端点），需要的话在该角色里单独写 `backend_url`。
- 同时开着 `claude_agent_sdk` 订阅覆盖时，`role_llms` 里配的角色会**绕开订阅按 token 计费**，启动时会点名警告是哪几个。

---



## 项目结构

```
TradingAgents-Astock/
├── tradingagents/
│   ├── agents/
│   │   ├── analysts/          # 7 个分析师
│   │   │   ├── market_analyst.py
│   │   │   ├── social_media_analyst.py
│   │   │   ├── news_analyst.py
│   │   │   ├── fundamentals_analyst.py
│   │   │   ├── policy_analyst.py        # A 股特化
│   │   │   ├── hot_money_tracker.py     # A 股特化
│   │   │   └── lockup_watcher.py        # A 股特化
│   │   ├── researchers/       # Bull / Bear 研究员
│   │   ├── risk_mgmt/         # 激进 / 保守 / 中立 辩手
│   │   ├── managers/          # Research Manager + Portfolio Manager
│   │   ├── trader/            # Trader（A 股交易约束）
│   │   └── utils/             # 状态定义、工具函数
│   ├── dataflows/
│   │   ├── a_stock.py         # A 股数据 vendor（直连 HTTP API，零第三方库）
│   │   ├── interface.py       # 数据接口抽象层
│   │   └── ...
│   └── graph/
│       ├── trading_graph.py   # 主入口：TradingAgentsGraph
│       ├── setup.py           # LangGraph 拓扑定义
│       ├── propagation.py     # 状态初始化与传播
│       ├── reflection.py      # 交易反思（CSI 300 基准）
│       └── conditional_logic.py
├── web/
│   ├── app.py                 # Streamlit 主入口
│   ├── runner.py              # 后台线程运行分析
│   ├── progress.py            # 线程安全进度追踪
│   ├── history.py             # 历史记录扫描
│   ├── pdf_export.py          # PDF 报告生成
│   ├── launch.py              # CLI 启动器
│   └── components/            # UI 组件
│       ├── sidebar.py         # 侧边栏（输入 + 历史）
│       ├── progress_panel.py  # 实时进度面板
│       └── report_viewer.py   # 报告展示
├── test_astock.py             # E2E 集成测试
├── CHANGES_FROM_UPSTREAM.md   # 与上游的完整改动记录
├── NOTICE                     # Apache 2.0 归属声明
├── LICENSE                    # Apache 2.0 许可证
└── pyproject.toml             # 包定义与依赖
```

---

## 致谢

本项目基于 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 开源项目进行 A 股特化改造。感谢原作者的出色工作和 Apache 2.0 开源精神。

**原始论文**：[TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/abs/2412.20138)

---

## 项目定位

**这是一个框架的工程实现，不是一个投资产品。**

- **它是什么**：[TradingAgents 论文](https://arxiv.org/abs/2412.20138)（TauricResearch）多 Agent 架构的 A 股工程实现，用于研究与教学——研究多 Agent 辩论在金融文本上的行为、A 股数据源如何接入、结构化输出如何落地。
- **它不是什么**：不是投资顾问、不是荐股软件、不提供任何投资服务。本仓库不发布针对具体证券的分析报告、评级或买卖建议；`examples/` 下只有可自行运行的脚本，没有任何预生成的个股结论。
- **模型和数据都是你自己的**：你配置自己的 LLM API key，在自己的机器上运行，产出的内容归你所有、由你判断、由你负责。项目本身不托管服务、不代为分析、不接触你的运行结果。
- **不产出可执行价位**：框架内**没有**建仓价 / 止损位 / 仓位 / 目标价这类输出——不是默认关闭，是代码里就没有。Trader 与 Portfolio Manager 只给方向、评级与理由。需要这类能力的使用者可以自行 fork 添加（Apache-2.0 允许），并自行承担相应责任、自行确认所在司法辖区的资质要求。

> **⚠️ 免责声明**
>
> - 本系统产出的所有内容均由 AI 自动生成，可能存在错误或偏差
> - 本项目不构成任何投资建议；投资决策请咨询持有中国证监会颁发资质的专业机构
> - 作者不对使用本工具产生的任何投资损失承担责任
> - 股市有风险，投资需谨慎


`[agentsdk]` 的依赖链是 `claude-agent-sdk → mcp → httpx2`，**不碰 httpx**，与 mootdx 的 `httpx<0.26` 无冲突（已 `uv lock` 实测）——和 #87 里被移除的 `[google]` 情况不同，不需要单开 venv。


