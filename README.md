# Commodity Calendar Spread Research

MTH 9897 · Project 7 · Baruch MFE 2026

用 1986–2026 的 Bloomberg 商品期货数据，研究同一商品不同到期月之间的 **calendar spread**：曲线形状、roll、carry、价差的可预测性与可交易性。

> **正式结果采用 v2 holdings-based 重跑（D-019）。** v2 三层成本下，
> A/B 的 gross 为负；D/C/C-hedge 的 gross 为正但很弱，all-in net 全为负。
> 六个策略都没有可交易的 edge。v1 的 5 bps/leg 结果保留为历史 baseline，
> 不作为最终结果；对照见 `docs/v1_v2_comparison.md`。
>
> A/B 已收尾：不再调参数、不做 rescue 变体。C/D 已 closed；
> E（Nelson–Siegel）已完成并 closed as not tradable（notebook 14，
> D-021–D-023）；下一步是 H（holding-period scan）。
> D-x（cross-sectional basis-momentum）是单独的 backlog，不混入 D。
>
> **A flip（D-025）：** 原始 A 方向仍是 closed negative；`target_flip =
> -sign(spread_dollar)`（contango long / backwardation short）是 adopted
> candidate signal。它只做 gross 信息检验（notebook 10 §7），交易成本留到
> final portfolio；不进下面的 all-in net 表。

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

详细分层表见 `notebooks/10_idea_a_carry.ipynb`、`11_idea_b_adjacent_carry.ipynb`、
`12_idea_c_mean_reversion.ipynb` 和 `13_idea_d_curve_momentum.ipynb`；
E（Nelson–Siegel）不在这个 v2 表中：它是 paper replication，paper timing
可复现（Sharpe 2.03），t+1 fill 后消失；见
`notebooks/14_idea_e_nelson_siegel.ipynb` 和 D-021–D-023。
**融合（D-030，notebook 15）：** 把 A–E 抽象成 12 个连续 alpha 因子合成一个
spread 预测；validation net Sharpe 1.34，但 test 2016–2026 net Sharpe −0.61
（预测 IC 在 test 仍为正，亏损集中在 LB）。
原始 CSV 在 `output/v2_rerun/comparison.csv`（本地，gitignored）。Notebook 11
另含 **B-flip** 的 post-hoc、gross-only signal research（D-026）；上表的 B
仍是原 B 的 negative 结果，B-flip 不进这张 official net 表。D-027 的 daily C
information audit 是另一条线：daily C1/C2/C3 的 validation gross SR 为
0.240 / 0.265 / −0.332，alpha gate 未通过（<0.4）；C 保持 closed，结果在
notebook 12 §9–11。D-029 进一步把 full-sample daily signal / legs / P&L /
positions 保存为 artifacts，并把 2016–2026 test 作为 **descriptive
presentation 只读一次**（notebook 12 §12）；这不改变 gate，也不改变
official weekly 结果。v1 历史口径
（5 bps/leg、`d=None`、1:1 contracts）见 `docs/v1_v2_comparison.md`；
旧 notebook 已 retired，恢复方式见 `docs/notebook_history.md`。

**A flip 不在上表：** 上表的 A carry 是原始方向（official v2 negative）。
§7 的 flip 是 gross-only 信号研究，不是新的 all-in net 结果；不要把它和
上表的 net 数字混在一起。

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
- [x] D signal validity（D-028）：per-root IC/hit/quantile/R²、1/3/6/12m
      horizon、incremental vs static/A/C、stability、placebo；结论是
      detectable but unstable，not independent
- [x] Monthly rebalance engine support
- [x] v2 holdings-based framework：分层成本（half-spread / fee / impact）、
      horizon 诊断、k sweep、容量曲线；见 `docs/backtest_framework.md`
- [x] 用 v2 重跑 A/D/C/C-rolling-OLS/C-Kalman/B；每个 idea 一个 notebook；
      **v2 为正式结果（D-019）**；v1/v2 对比见 `docs/v1_v2_comparison.md`
- [x] E（Nelson–Siegel）：paper timing 复现，t+1 后消失；closed as not tradable
- [x] A flip（sign reversal）信息检验：full/train/test gross；adopted
      candidate signal（D-025，notebook 10 §7）
- [ ] H（holding-period scan）；D-x 是 backlog

`notebooks/00_data_audit.ipynb`、`01_panel_build.ipynb` 和五个 idea notebook
（`10_idea_a_carry`、`11_idea_b_adjacent_carry`、`12_idea_c_mean_reversion`、
`13_idea_d_curve_momentum`、`14_idea_e_nelson_siegel`）可从头运行；01 生成
`data/processed/*.parquet`，10–14 分别生成对应策略的 `output/figures/idea_*`
和 `output/v2_rerun/*_performance.csv`（都不提交）。旧 notebook 02–08 已 retired；
见 `docs/notebook_history.md`。

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
   notebooks/10_idea_a_carry.ipynb
   notebooks/11_idea_b_adjacent_carry.ipynb
   notebooks/12_idea_c_mean_reversion.ipynb
   notebooks/13_idea_d_curve_momentum.ipynb
   ```

   第二个 notebook 会生成 `data/processed/*.parquet`（不提交到 repo）；
   10–14 分别跑 A、B、C（1:1/OLS/Kalman）、D 和 E，每个 notebook 只展示自己的
   PnL、持仓和 overall Sharpe；结果写到 `output/`（不提交）。如果想刷新
   跨策略汇总表，再跑 `python scripts/run_v2_rerun.py --force`。

   Daily C information audit（D-027）是独立的一步：在 notebook 12 之前跑
   `python scripts/run_c_daily_audit.py --stage stage1` 生成 §9–11 的缓存结果。
   Stage 1 只看 2015 年以前；只有 validation gate 通过后，才用
   `--stage stage2 --confirm-read-once` 读一次 test。D-029 的 full-sample
   artifacts 用 `python scripts/run_c_daily_audit.py --stage full
   --confirm-read-once` 生成（写到 `output/c_daily_audit/full/`），
   test read marker 在 `output/c_daily_audit/test_readonce.json`；第二次读取
   需要显式 `--force-test-read`。

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
  notebook_history.md     # 当前 notebook 布局 + 旧 notebook 的替代和恢复
  onboarding.md           # 队友 1 页上手
  logs/                   # agent 操作日志（谁、做了什么、为什么、怎么验证）

src/                      # 所有数据处理逻辑（notebook 只调用）
  continuous.py           # roll-chained leg indices + rolling OLS hedge ratio
  kalman.py               # Kalman-filter hedge ratio (rolling-likelihood DLM)
  signals.py              # signal functions（A carry; A flip = -sign in notebook 10 §7; C mean reversion; D curve momentum）
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
notebooks/                # 00, 01 数据层；10–14 每个 idea 一个 notebook
tests/                    # synthetic fixtures + parser/roll/spread/backtest/simulate tests
scripts/run_all.sh        # 一键复现：依赖 + tests + 数据层 + 五个 idea notebooks
scripts/run_v2_rerun.py   # 跨策略 v2 汇总表（手动刷新 comparison.csv）

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
- **正式结果（D-019）：** v2 重跑是最终报告口径；v1 数字保留为历史
  baseline，不进 headline 表。
- **每个 idea 一个 notebook（D-020）：** 00/01 数据层，10–14 分别是
  A/B/C/D/E；旧 notebook 02–08 已 retired，历史内容在 docs 和 git history。
  每个 idea notebook 固定展示 PnL、持仓（热力图 + 总敞口/换手）和
  一个 full-sample all-in net Sharpe。
- **B-flip（D-026）：** notebook 11 的 post-hoc、gross-only signal research；
  原 B 仍是 negative/closed，B-flip 不进 official comparison。
- **E（D-021–D-023）：** Nelson–Siegel 曲线动态；paper timing 的 Sharpe
  2.03 在 t+1 fill 后消失，E closed as not tradable；notebook 14。
- **云端合并（D-024）：** E 并入 D-020 布局；E 决策重编号为 D-021–D-023，
  notebook 改为 14。
- **A flip（D-025）：** 原始 A 方向 closed negative；`target_flip =
  -sign(spread_dollar)` 是 adopted candidate carry signal；gross-only
  信息检验在 notebook 10 §7；成本留到 final portfolio，不做 test tuning。
- **D signal validity（D-028）：** D-013 固定、不扫参数；rank-index
  t+1 forward（1/3/6/12m）、per-root IC/hit/quantile/R²、incremental vs
  static/A/C、decades/carry/vol + rolling 36m、placebo；6m block bootstrap、
  FDR、max-|IC|。结论：detectable but unstable，not independent。

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
