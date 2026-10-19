# Commodity Calendar Spread Research

MTH 9897 · Project 7 · Baruch MFE 2026

用 1986–2026 的 Bloomberg 商品期货数据，研究同一商品不同到期月之间的 **calendar spread**：曲线形状、roll、carry、价差的可预测性与可交易性。

> 这个 repo 是**数据层 + 研究脚手架**。数据层、A baseline、A 负结果诊断、
> B 预测试、C baseline、C rolling-OLS hedge-ratio 和 C Kalman variant
> 已完成；A/B/C 都是负结果或 mixed-negative。C 已 closed，在独立 branch
> 上（未合入 main）；D/H 是下一阶段。
>
> A/B 的负结果在 **0 bps（不考虑 transaction cost）** 下已经成立；
> C 的 1:1、rolling OLS 和 Kalman variant 也都不是稳健正的。5 bps/leg
> 只是放大亏损，不改变符号。

---

## 当前状态

- [x] 原始数据审计：24 commodities × 4 nearby ranks，1986–2026
- [x] Repo scaffold、agent collaboration protocol、decision/log 体系
- [x] Rank / contract / return / spread panels + QA
- [x] Liquidity diagnostics（threshold 由你看完图后决定）
- [x] A baseline：K=5 panel + carry signal + return-based event-loop backtest
- [x] A 负结果诊断：side × sector × era、K=5 vs K=10、成本敏感性
- [x] B 预测试：adjacent-carry rank；负结果，skip B
- [x] C baseline：continuous index + weekly mean-reversion；负结果
- [x] C hedge-ratio variant：60-day rolling OLS；负结果
- [x] C Kalman variant：rolling-likelihood DLM；mixed/negative，C closed
- [ ] D/H（C 在 `feat/idea-c-mean-reversion`，未合入 main）

`notebooks/00_data_audit.ipynb`、`01_panel_build.ipynb`、`02_carry.ipynb`、
`03_mean_reversion.ipynb`、`04_a_diagnose.ipynb` 和
`05_b_pretest.ipynb` 已可从头运行；01 生成 `data/processed/*.parquet`，
02 生成 `output/carry_*`，03 生成 `output/mean_reversion_*`，04/05 生成
诊断和 B 预测试输出（都不提交）。

**新对话 / 队友先读：** `docs/HANDOFF.md` → `AGENTS.md` → `docs/decisions.md` → `docs/logs/INDEX.md`。

---

## Quick start

1. 把 raw CSV 放到：

   ```text
   data/raw/bloomberg_commodity_bulk_tickers_1986_2026.csv
   ```

   文件名、checksum、获取方式见 `data/raw/README.md`。

2. 安装依赖：

   ```bash
   python -m pip install -r requirements.txt
   ```

3. 启动 Jupyter：

   ```bash
   jupyter lab
   ```

4. 依次运行：

   ```text
   notebooks/00_data_audit.ipynb
   notebooks/01_panel_build.ipynb
   notebooks/02_carry.ipynb
   notebooks/03_mean_reversion.ipynb
   notebooks/04_a_diagnose.ipynb   # 依赖 02 的 output/carry_full_*
   notebooks/05_b_pretest.ipynb
   ```

   第二个 notebook 会生成 `data/processed/*.parquet`（不提交到 repo）；
   第三个跑 A baseline，03 跑 C baseline + hedge-ratio，04 跑 A 诊断，
   05 跑 B 预测试；结果写到 `output/`（不提交）。

---

## Repo map

```text
README.md                 # 本文件：简洁入口
AGENTS.md                 # 通用 coding agent 入口与硬规则
CLAUDE.md                 # Claude Code 专用入口

docs/
  project_brief.md        # 详细项目背景、五个 idea、数据说明
  HANDOFF.md              # 当前状态、关键数字、open questions、下一步
  PROGRESS.md             # 实时进度（给另一个 agent / 队友）
  backtest_framework.md   # 回测框架一页：五层、接口、扩展方式
  research_notes.md       # roll / spread 的论文与业界惯例、为什么这样选
  data_dictionary.md      # raw + derived fields + panel schemas
  decisions.md            # 已锁定的研究/数据决定
  onboarding.md           # 队友 1 页上手
  logs/                   # agent 操作日志（谁、做了什么、为什么、怎么验证）

src/                      # 所有数据处理逻辑（notebook 只调用）
  continuous.py           # roll-chained leg indices + rolling OLS hedge ratio
  kalman.py               # Kalman-filter hedge ratio (rolling-likelihood DLM)
  signals.py              # signal functions（A carry; C mean reversion）
  backtest.py             # target legs + event-loop engine
  metrics.py              # summary / conditional mean / sector / plot
  a_diagnostics.py        # A 负结果诊断
  b_pre_test.py           # cheap adjacent-carry B 预测试
notebooks/                # 00, 01, 02, 03, 04, 05
tests/                    # synthetic fixtures + parser/roll/spread/backtest tests
scripts/run_all.sh        # 一键复现：依赖 + tests + A/B/C notebook

data/raw/                  # 原始数据（本地；public repo 不提交）
data/metadata/             # 24 商品元数据 + checksum（提交）
data/processed/            # 生成的 parquet（本地；gitignored）

paper/README.md            # 论文引用；PDF 本地，不提交
output/                    # 生成的图/报告（gitignored）
```

---

## Key decisions

- **M1–M4 是 slot，不是合约。** 换月日四个 rank 同时前移；收益必须按 `FUT_CUR_GEN_TICKER` 对齐到真实合约。
- **Pair eligibility：** 不持有进入交割月的合约；交割月开始前至少 5 个交易日退出；且 `days_to_last_trading > 10`。D=5/20 做稳健性。
- **Spread：** dollar spread 做主交易/P&L；log spread 做参考。两者都保存在 `spread_panel`。
- **Liquidity threshold：** 先出诊断图，不提前写死；代码里是参数。
- **不做 back-adjusted 连续价格作为主结果。** 主结果使用固定合约对的 raw prices。
- **A baseline 回测口径（D-009）：** K=5 ex-ante、gross-notional return
  （lagged denominator）、周五 rebalance、t+1 成交、roll 在 t+1 平旧、
  第 6 个 invalid session forced exit、5 bps/leg。
- **C baseline（D-010）：** additive roll-chained continuous index
  （signal-only）、dollar z L=20、weekly ±2/0、1:1 dollar、5 bps/leg。
- **C hedge-ratio variant（D-011）：** 60-day rolling OLS levels、h>0、
  strict weekly h 调仓、0 bps gross 对照；负结果。
- **C Kalman variant（D-012）：** paper-style DLM、252-day likelihood、
  q grid、0 bps gross；mixed/negative，C closed。

详见 `docs/decisions.md`。

---

## 数据和论文

这是一个 **public repo**。以下内容不提交：

- Bloomberg raw CSV/XLSX（授权限制）
- `paper/*.pdf`、`Project.pdf`（版权/课程材料）
- `calendar-spread-brief.html`（含长引文）
- `data/processed/*.parquet`（可由 notebook 重建）

队友需要 raw CSV 时，通过私有渠道获取，按 `data/raw/README.md` 放置并校验 checksum。

---

## 给 coding agent

- 通用 agent：先读 `AGENTS.md`。
- Claude Code：先读 `CLAUDE.md`，它会指向 `AGENTS.md`。
- 改动前读 `docs/decisions.md` 和 `docs/logs/INDEX.md`；改动后必须 append log 并在同一个 commit 里更新。
- Notebook 只做叙述和调用；逻辑放在 `src/`。
