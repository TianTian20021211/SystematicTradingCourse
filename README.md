# Commodity Calendar Spread Research

MTH 9897 · Project 7 · Baruch MFE 2026

用 1986–2026 的 Bloomberg 商品期货数据，研究同一商品不同到期月之间的 **calendar spread**：曲线形状、roll、carry、价差的可预测性与可交易性。

> **正式结果采用 v2 holdings-based 重跑（D-019）。** v2 三层成本下，
> A/B 的 gross 为负；D/C/C-hedge 的 gross 为正但很弱，all-in net 全为负。
> 六个策略都没有可交易的 edge。v1 的 5 bps/leg 结果保留为历史 baseline，
> 不作为最终结果；对照见 `docs/v1_v2_comparison.md`。
>
> A/B 已收尾：不再调参数、不做 rescue 变体。C/D 已 closed；
> 下一步是 E（Nelson–Siegel）和 H（holding-period scan）。
> D-x（cross-sectional basis-momentum）是单独的 backlog，不混入 D。

---

## 最终结果（v2，正式）

Full sample 1986–2026；all-in net 已扣 half-spread、fee 和 impact；
test 是 2016–2026 的 post-hoc slice。

| 策略 | gross | all-in net | test gross |
|---|---:|---:|---:|
| A carry | −0.48% | −2.61% | −0.27% |
| D curve momentum | +0.22% | −1.42% | −0.21% |
| C mean reversion 1:1 | +0.61% | −3.70% | +0.16% |
| C rolling-OLS hedge | +0.12% | −3.06% | −0.01% |
| C Kalman hedge | +0.61% | −6.10% | +0.98% |
| B adjacent carry | −1.13% | −4.47% | −1.23% |

详细分层表见 `notebooks/08_v2_rerun.ipynb`；原始 CSV 在
`output/v2_rerun/comparison.csv`（本地，gitignored）。v1 历史口径
（5 bps/leg、`d=None`、1:1 contracts）见 `docs/v1_v2_comparison.md`
和 notebooks 02/03/05/06。

---

## 当前状态（含 v1 历史 baselines；正式结果见上表）

- [x] 原始数据审计：24 commodities × 4 nearby ranks，1986–2026
- [x] Repo scaffold、agent collaboration protocol、decision/log 体系
- [x] Rank / contract / return / spread panels + QA
- [x] Liquidity diagnostics（threshold 由你看完图后决定）
- [x] A baseline：K=5 panel + carry signal + return-based event-loop backtest
- [x] A 负结果诊断：side × sector × era、K=5 vs K=10、成本敏感性
- [x] B 预测试：adjacent-carry rank；负结果，skip B
- [x] A/B 负结果确认并收尾（不再调参/不做 rescue）
- [x] C baseline：continuous index + weekly mean-reversion；负结果
- [x] C hedge-ratio variant：60-day rolling OLS；负结果
- [x] C Kalman variant：rolling-likelihood DLM；mixed/negative，C closed
- [x] D curve-momentum / basis-momentum baseline：N=2、12m、monthly；
      gross 弱、net 负，D documented negative/mixed
- [x] Monthly rebalance engine support
- [x] v2 holdings-based framework：分层成本（half-spread / fee / impact）、
      horizon 诊断、k sweep、容量曲线；notebook 07
- [x] 用 v2 重跑 A/D/C/C-rolling-OLS/C-Kalman/B；notebook 08；
      **v2 为正式结果（D-019）**；v1/v2 对比见 `docs/v1_v2_comparison.md`
- [ ] E（Nelson–Siegel）；H（holding-period scan）；D-x 是 backlog

`notebooks/00_data_audit.ipynb`、`01_panel_build.ipynb`、`02_carry.ipynb`、
`03_mean_reversion.ipynb`、`04_a_diagnose.ipynb`、`05_b_pretest.ipynb`、
`06_curve_momentum.ipynb`、`07_backtest_framework.ipynb` 和
`08_v2_rerun.ipynb` 已可从头运行；01 生成 `data/processed/*.parquet`，
02 生成 `output/carry_*`，03 生成 `output/mean_reversion_*`，04/05 生成
诊断和 B 预测试输出，06 生成 `output/curve_momentum_*`，07 生成
`output/figures/`，08 读取 `output/v2_rerun/`（都不提交）。

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
   notebooks/06_curve_momentum.ipynb
   notebooks/07_backtest_framework.ipynb
   notebooks/08_v2_rerun.ipynb
   ```

   第二个 notebook 会生成 `data/processed/*.parquet`（不提交到 repo）；
   第三个跑 A baseline，03 跑 C baseline + hedge-ratio，04 跑 A 诊断，
   05 跑 B 预测试，06 跑 D curve-momentum baseline，07 用 v2 框架演示
   A 的分层成本和 horizon 诊断，08 展示 v2 重跑 A/D/C/C-hedge/B 和
   v1/v2 对照；结果写到 `output/`（不提交）。08 之前先跑
   `python scripts/run_v2_rerun.py --force`。

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
  backtest_framework.md   # 回测框架一页：v1、v2 五层、接口、扩展方式
  v1_v2_comparison.md     # v1/v2 架构与结果对照、已知限制
  transaction_costs.md    # v2 成本模型：half-spread / fee / impact 与文献
  research_notes.md       # roll / spread 的论文与业界惯例、为什么这样选
  data_dictionary.md      # raw + derived fields + panel schemas
  decisions.md            # 已锁定的研究/数据决定
  onboarding.md           # 队友 1 页上手
  logs/                   # agent 操作日志（谁、做了什么、为什么、怎么验证）

src/                      # 所有数据处理逻辑（notebook 只调用）
  continuous.py           # roll-chained leg indices + rolling OLS hedge ratio
  kalman.py               # Kalman-filter hedge ratio (rolling-likelihood DLM)
  signals.py              # signal functions（A carry; C mean reversion; D curve momentum）
  backtest.py             # v1：target legs + event-loop engine（weekly/monthly/daily）
  metrics.py              # v1 summary / conditional mean / sector / plot
  a_diagnostics.py        # A 负结果诊断
  b_pre_test.py           # cheap adjacent-carry B 预测试
  specs.py                # v2 contract specs（point value, tick）
  marks.py                # v2 contract marks / tradability / lagged ADV
  sizing.py               # v2 signal → leg targets（equal / inverse-vol / liquidity）
  costs.py                # v2 half-spread / fee / square-root impact
  simulate.py             # v2 holdings-based simulator
  horizon.py              # v2 forward returns, time-series IC, bootstrap
  report.py               # v2 performance / root / capacity tables
  figures.py              # v2 journal-grade figures
  plotstyle.py            # v2 matplotlib style and export
  v2_signals.py           # A/D/C/C-hedge/B adapters to LEG_COLUMNS
  v2_rerun.py             # v2 rerun orchestration and CSV output
notebooks/                # 00, 01, 02, 03, 04, 05, 06, 07, 08
tests/                    # synthetic fixtures + parser/roll/spread/backtest/simulate tests
scripts/run_all.sh        # 一键复现：依赖 + tests + A/B/C/D + v2 reruns
scripts/run_v2_rerun.py   # v2 A/D/C/C-hedge/B rerun driver

data/raw/                  # 原始数据（本地；public repo 不提交）
data/metadata/             # 24 商品元数据 + checksum + contract_specs.csv（提交）
data/processed/            # 生成的 parquet（本地；gitignored）

presentations/mid/         # mid-term slides source（LaTeX；build 不提交）
paper/README.md            # 论文引用；PDF 本地，不提交
output/                    # 生成的图/报告（gitignored）
```

---

## Key decisions

> D-009–D-013 是 v1 历史口径；正式结果按 D-018/D-019（v2）报告。

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
- **D curve-momentum baseline（D-013）：** N=2 main pair、12m formation、
  monthly rebalance、±1、5 bps/leg；gross 弱、net 负，documented
  negative/mixed。
- **Ownership（D-014）：** Tian 负责 A/D；Jiaheng 负责 C/E；E
  （Nelson–Siegel curve dynamics）重新纳入 scope。
- **Daily rebalance（D-015）：** `BacktestConfig.rebalance="daily"`；
  weekly 仍是默认。
- **Backtest v2（D-016）：** holdings-based simulator、分层成本、
  horizon / capacity 诊断；v1 保留为 A 的原始 benchmark，两套数字不直接可比。
- **v2 扩展（D-017）：** optional hedge-ratio legs、`legs_from_rows`
  多腿目标、`resize_key`；B 的 within-root adjacent-carry 排序是
  time-series-only 规则的 narrow exception，用 `execution="legs"`。
- **v2 重跑口径（D-018）：** `d=5`、`k=5`、`min_adv=100`、USD 10m、
  equal-notional、三层成本；C/D/B 用大 `rebalance_band`；test 是
  post-hoc slice，不用 test 调参。
- **正式结果（D-019）：** v2 重跑是最终报告口径；v1 notebook 和旧数字
  保留为历史 baseline，不删除、不重写、不进 headline 表。

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
