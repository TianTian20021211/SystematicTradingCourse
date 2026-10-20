# Handoff — 当前状态

**最后更新：** 2026-10-20
**A baseline：** `bd6691b`；**A diagnosis：** `f02f18b`。  
**A flip：** D-025；adopted candidate signal；gross 信息检验在 notebook 10 §7；
test 为 suggestive, not confirmed；成本 deferred。

**B pre-test：** `d257e0e`。  
**C baseline + hedge-ratio + Kalman variant：** 已合入 main；C 已作为
mixed/negative 收尾。  
**E（Nelson–Siegel）：** 已复现并 closed as not tradable；notebook 14；
D-021–D-023。
**D curve-momentum / basis-momentum：** 已实现并收尾为
documented negative/mixed；monthly engine support 已加入。
**Backtest v2（jiaheng/backtest-v2）：** 已合入 main（LOG-0039）；
D-014–D-016。
**v2 重跑 A/D/C/C-hedge/B：** 已完成（LOG-0044）；每个 idea 一个
notebook（10–14，D-020/D-024）；结论仍是 negative/mixed；详见
`docs/v1_v2_comparison.md`。
**D-027 daily C audit（2026-10-20）：** daily C1/C2/C3 validation gross SR
0.240 / 0.265 / −0.332；顺序选择保留 C1；alpha gate 未通过
（0.240 < 0.4）；test 未读。C 保持 closed，daily 结果保留在
notebook 12 §9–11。

**正式结果：** v2 重跑（D-019）；v1 数字仅作历史 baseline。旧 notebook
02–08 已 retired（D-020），见 `docs/notebook_history.md`。

**Repo：** https://github.com/TianTian20021211/SystematicTradingCourse

---

## 0a. Backtest v2 merge（2026-10-19）

`origin/jiaheng/backtest-v2` 已合入 `main`。新增 v2 holdings-based
simulator：`src/specs.py`、`src/marks.py`、`src/sizing.py`、
`src/costs.py`、`src/simulate.py`、`src/horizon.py`、`src/report.py`、
`src/figures.py`、`src/plotstyle.py`；另有
`data/metadata/contract_specs.csv`、`docs/transaction_costs.md`、
`presentations/mid/`。框架说明见 `docs/backtest_framework.md`，当前
展示在 notebooks 10–14。

v2 重跑 A/D/C/C-rolling-OLS/C-Kalman/B 已完成（D-018）。Full-sample
gross → all-in net：

| 策略 | gross | all-in net |
|---|---:|---:|
| A carry | −0.48% | −2.61% |
| D curve momentum | +0.22% | −1.42% |
| C 1:1 | +0.61% | −3.70% |
| C rolling-OLS | +0.12% | −3.06% |
| C Kalman | +0.61% | −6.10% |
| B adjacent carry | −1.13% | −4.47% |

**v2 是正式结果（D-019）**；v1 仅作历史对照。结论仍是 negative/mixed；
v1/v2 不可直接比较。详见 notebooks 10–14、
`docs/v1_v2_comparison.md` 和 `docs/notebook_history.md`。

**A flip（D-025）：** 原始 A 方向仍是 closed negative，正式 v2 结果不变。
`target_flip = -sign(spread_dollar)` 是 adopted candidate signal；notebook 10
§7 的 gross 信息检验：full +0.631%/yr（Sharpe 0.633，NW t 4.286）、train
+0.694%（0.672，4.056）、test +0.455%（0.512，1.580；80% MDE 0.843）。
test 方向为正但不显著，结论 **suggestive, not confirmed**；成本留到 final
portfolio。不要把它放进上面的 all-in net 表。

### B-flip signal research（2026-10-20，D-026）

Notebook 11 新增 post-hoc、gross-only 的 B-flip：long carry 最低的
adjacent spread，short carry 最高的；D=10 eligible、`min_adv=100`、
USD 10m、weekly、k=1。Full-sample gross **+0.499%/年**、vol 0.469%、
gross Sharpe **1.064**、t_NW 7.14、turnover 31.4×；raw exact flip
+1.131%/年、Sharpe 1.263。D=10 static front/back 只有 +0.108%/年、
Sharpe 0.208，说明信息主要来自 carry ranking。

Signal level：1:6 +3.98 bps（t 9.6），1:21 +12.4 bps（t 8.6）；37/41 年
为正；22/24 roots mean 为正；random-ranking placebo p<0.001。Half-spread
一层 84 bps/年，gross 只有 50 bps/年，standalone net 为负；它是组合
candidate，不是 standalone 策略。**Post-hoc sign flip；2016–2026 不是
OOS。** B-flip 不进 official comparison；原 B 仍是 negative/closed。
候选调参（本次未跑）：k-smoothing、D=5/20、ADV=1000、rebalance
frequency、liquidity weighting。

---

## 0. 新对话 / 新队友先读什么

1. `README.md` — 5 分钟入口。
2. `docs/HANDOFF.md` — 本文件，当前状态和 open questions。
3. `AGENTS.md`（Claude Code 还会自动读 `CLAUDE.md`）。
4. `docs/decisions.md` — 已锁定的决定。
5. `docs/data_dictionary.md` — 字段和 panel schema。
6. `docs/logs/INDEX.md` + `AGENT_LOG.md` 最近几条 — 谁做了什么。
7. `notebooks/00_data_audit.ipynb`、`01_panel_build.ipynb` — 数据层。
8. `notebooks/10_idea_a_carry.ipynb` — A；`11_idea_b_adjacent_carry.ipynb`
   — B；`12_idea_c_mean_reversion.ipynb` — C（1:1/OLS/Kalman）；
   `13_idea_d_curve_momentum.ipynb` — D；`14_idea_e_nelson_siegel.ipynb`
   — E。旧 notebook 02–08 的替代和恢复见 `docs/notebook_history.md`；
   `docs/PROGRESS.md` — 实时进度。

---

## 0b. 本地 merge handoff（idea D，2026-10-19）

**Branch：** `feat/idea-d-curve-momentum`（本地，**未 push**）。

**Merged into `main`：** `08de3e7`（local merge commit；未 push）。

**Base：** `main` at `cb755d0`（C merge）。

**Commits：**

- `4db6849` `feat(curve-momentum): add monthly engine and basis-momentum signal`
- `cf94b1f` `feat(curve-momentum): add idea D baseline notebook`
- `8a92198` `docs(curve-momentum): record idea D baseline`
- `c3e9fce` `docs(logs): record idea D baseline commit hash`
- `3bb0f36` `docs(handoff): record idea D local merge handoff`
- `08de3e7` `merge: integrate idea D curve-momentum baseline`（在 `main` 上）

**Working tree：** clean；`pytest -q` → 80 passed；notebook 06 已执行。

**未 push：** 所有 commits 只在本地；不要 push，除非用户明确要求。

**Merge 已完成：** `main` 当前 checkout 在
`/Users/tian/Library/Mobile Documents/com~apple~CloudDocs/Baruch/第三学期/Systematic Trading/Project-ab-merge`，
已经用 `git merge --no-ff feat/idea-d-curve-momentum` 合并；不需要再次 merge。
merge 后保持本地，不要 push。

**D 已完成：**

- monthly rebalance support：`curve.monthly_rebalance_dates`、
  `BacktestConfig.rebalance="last_trading_day_of_month"`；weekly 默认不变。
- `CurveMomentumParams` / `curve_momentum_signal` + synthetic tests。
- `notebooks/13_idea_d_curve_momentum.ipynb`，输出 `output/idea_d_*`
  （gitignored）；旧 `06_curve_momentum` 已 retired。
- `D-013` 和 README / AGENTS / HANDOFF / PROGRESS / onboarding /
  backtest_framework / data_dictionary 更新。
- **结果：** full gross +0.55%、net −0.99%；train gross +0.85%、net
  −0.65%；test gross −0.28%、net −1.89%；static +1 net −0.84%；
  monthly net Sharpe full −0.90 / test −1.66；bootstrap t full −5.87 /
  test −5.41。**D 作为 documented negative/mixed 收尾，不用 test 调参。**

**D 未做（backlog）：**

- H（holding-period scan）。
- D-x（cross-sectional basis-momentum）：按 BM 排序商品、long top /
  short bottom；是独立 idea，不混入 D。
- D robustness：N=4、weekly、6-month formation、liquidity thresholds、
  inverse-vol、exponential decay、D-vs-A correlation、carry-regime
  conditioning。
- Push / PR / merge 到 `origin`：故意只留本地。

---

## 1. 一句话

**数据层 + v1 A/B/C/D baseline 已完成；v2 重跑 A/D/C/C-hedge/B 已完成，
并作为正式结果（D-019）。**

**A、B、C 1:1、C rolling-OLS、C Kalman、D 都是负结果或 mixed-negative；
A/B 已收尾（不再调参/不做 rescue），C/D 已 closed 并合入 main；
下一步是 E 和 H。** v1 结果保留为历史 baseline，见 `docs/v1_v2_comparison.md`。
**A flip（D-025）是 separately adopted candidate signal：** 原始 A 方向仍是
closed negative；`target_flip = -sign(spread_dollar)` 的 gross 信息检验在
notebook 10 §7，test 为 suggestive, not confirmed，成本 deferred。

---

## 2. 当前数据状态（本地生成）

| Panel | Rows | 说明 |
|---|---:|---|
| `rank.parquet` | 1,013,664 | date × commodity × rank，23 列 |
| `contract.parquet` | 950,626 | date × real contract，6,735 张合约 |
| `returns.parquet` | 1,013,664 | contract-level return + rank mapping |
| `pairs.parquet` | 236,186 | 主 pair（最近两个 eligible adjacent contracts） |
| `spread.parquet` | 236,186 | 主 pair 的 dollar/log/pct spread |
| `universe.parquet` | 236,186 | trailing liquidity + 1k/5k/10k/20k booleans |
| `episodes.parquet` | 6,664 | 固定合约对的 episode |
| `adjacent_pairs.parquet` | 610,801 | 所有 eligible adjacent pairs（robustness） |
| `adjacent_spread.parquet` | 610,801 | 所有 adjacent pair 的 spread |
| `backtest_pairs.parquet` | 236,385 | K=5 ex-ante 主 pair（回测用） |
| `backtest_spread.parquet` | 236,385 | K=5 主 pair 的 spread |

这些 parquet 在 `data/processed/`，**gitignored**；见 `data/processed/README.md`。

关键 QA：

- 0 duplicate contract-date
- 0 rank-order violations
- 0 partial rolls
- 0 full-day queue violations
- CL 2020-04-20 = **−37.63** 仍在
- **36 个 pytest 全过**
- notebooks 00/01 和 10–13 都能 top-to-bottom 跑完

A baseline（K=5；1986–2026）：

| Period | Gross ann. | Net ann. | Sharpe net | Max DD net |
|---|---:|---:|---:|---:|
| Full | −0.53% | −1.90% | −0.08 | −55.3% |
| Train 1986–2015 | −0.44% | −1.78% | −0.10 | −42.7% |
| Test 2016–2026 | −0.76% | −2.20% | −0.06 | −21.9% |

Conditional raw spread return：`target_positive` ≈ 0（t −0.27）；
`target_negative` 为 **+0.000127（t +2.41）**，即 contango spread 平均会变强，
short spread 是错的方向。**A 在这个 baseline 没有 edge。**

A diagnosis（v1 历史；当前见 `10_idea_a_carry.ipynb` 和
`docs/a_negative_result.md`）：short raw mean +0.000024（t +2.46），
long −0.000008（t −0.65）；K=10 不翻正；0/5/10/20 bps 下 gross 已经负。

B pre-test（v1 历史；当前见 `11_idea_b_adjacent_carry.ipynb` 和
`docs/b_pretest.md`）：adjacent-carry rank，full gross −1.14%、
net −2.84%（gross Sharpe −0.08）；预注册规则 **skip B = True**。

**Zero-cost check：** A full gross ann. −0.53%（Sharpe −0.02）；B full gross
ann. −1.14%（Sharpe −0.08）。两者在扣交易成本之前已经是负的。

C baseline（C2 additive index、dollar z L=20、weekly、1:1）：full gross
+0.53%、net −1.67%、net Sharpe −0.03；train gross +0.87%、net −1.32%；
test gross −0.39%、net −2.64%；energy 1992–2013 gross −1.05%、net −3.12%。
Conditional mean full sample 不显著；train 的 `target_negative` raw mean
−0.000203（t −2.12），test 不显著（+0.000148，t +1.05）。**C 没有稳健、
可交易的 edge；成本把 gross 的小正收益拖负。**

C hedge-ratio variant（60-day rolling OLS levels、strict weekly h 调仓、
0 bps）：`h` median 1.008，5–95% 0.796–1.312，99.3% valid。Full gross
+0.197% / Sharpe 0.006，低于 1:1 的 +0.535% / 0.010；train +0.290% / 0.012
vs +0.868% / 0.030；test −0.055% / 0.001 vs −0.391% / −0.002。Energy
1992–2013（0 bps）：1:1 −1.05% / −0.013；hedge −0.10% / 0.0002。
Hedge 版本 vol 更低，但 return 也更低、trade 数约翻倍；full/train/test
没有改善，energy 只是从负接近零；不跑 5 bps。

C Kalman variant（paper-style DLM；252-day likelihood、每 60 天重估 V/W、
9 点 q grid、strict weekly h、0 bps）：aggregate full gross +0.98%，
vol 8.9%，max DD −28.9%，turnover 28.3×；test gross +0.52%，vol 16.7%。
按 turnover 估算 5 bps 后约 −1.8%/yr full、−2.5%/yr test。Per-root paper
sample：CL −0.79% / Sharpe −0.257，CO −0.57% / −0.236，HO −0.50% /
−0.458，NG **+1.34% / +0.309**，XB +0.21% / +0.268。CL 最坏单日
2020-04-20（−48.4% of avg gross），但 2020 全年贡献 +10.0%；没有剔除或
cap 任何数据。**NG 方向对、CL 不对；aggregate 不可交易，C 收尾。**

---

## 3. 已锁定的决定

| ID | 决定 |
|---|---|
| D-001 | M1–M4 是 slot；收益按 contract code 对齐，绝不跨 roll 差分 generic price |
| D-002 | Pair eligibility：no delivery month + 交割月开始前至少 5 个 session + `days_to_last_trading > 10`；D=5/20 做稳健性 |
| D-003 | **dollar spread 主交易/P&L**；**log spread 参考**；log 只在两边价格 >0 时有效 |
| D-004 | Liquidity threshold 先出图，不提前写死；1k/5k/10k/20k 都算成 boolean |
| D-005 | Public repo 不提交 raw Bloomberg 数据、paper PDF、course PDF、processed parquet |
| D-006 | Notebook 是叙述层；逻辑在 `src/`；notebook 中英夹杂，方便两位作者阅读 |
| D-007 | 每个 material change 写 `docs/logs/AGENT_LOG.md`，并更新 `INDEX.md` |
| D-008 | 主实验统一一个可交易 spread；adjacent pairs 作为 robustness |
| D-009 | A baseline 回测口径：K=5 ex-ante、per-contract mark state、gross-notional return、周五 rebalance、t+1 fill、roll 在 t+1 平旧、第 6 个 invalid session forced exit、5 bps/leg |
| D-010 | C baseline：additive roll-chained continuous index（signal-only）、dollar z L=20、weekly ±2/0、1:1 dollar、5 bps/leg；daily/log/adjacent 后置 |
| D-011 | C hedge-ratio variant：60-day rolling OLS levels、h>0、strict weekly h 调仓、0 bps gross 对照；returns/20/120/cap 后置 |
| D-012 | C Kalman variant：paper-style DLM、252-day likelihood、q grid、0 bps gross；结果 mixed/negative，C closed；不做 daily replication |
| D-013 | D curve-momentum / basis-momentum baseline：N=2 main pair、12m formation、month-end lookback、rank return index、≥80% valid、负价格 window invalid、纯 sign、target 日度 forward-fill、monthly rebalance、±1、5 bps/leg；结果 gross 弱、net 负，documented negative/mixed；D-x cross-sectional BM 是 backlog |
| D-014 | Ownership：Tian 负责 A/D；Jiaheng 负责 C/E；E（Nelson–Siegel curve dynamics）重新纳入 scope，必须显式处理 3 参数 / 4 合约的自由度问题 |
| D-015 | `BacktestConfig.rebalance` 增加 `"daily"`；weekly 仍是默认；A 结果不变 |
| D-016 | Backtest v2：holdings-based simulator、分层成本（half-spread / fee / impact）、horizon / capacity 诊断；v1 保留为 A 的原始 benchmark，v1/v2 数字不直接可比 |
| D-017 | v2 扩展：optional hedge-ratio legs、`legs_from_rows` 多腿、`resize_key`；B 的 within-root adjacent-carry 排序是 narrow exception，用 `execution="legs"` |
| D-018 | v2 重跑口径：`d=5`、`k=5`、`min_adv=100`、USD 10m、equal-notional、三层成本；C/D/B 大 band；test 是 post-hoc slice，不用 test 调参 |
| D-019 | **v2 重跑是正式/最终结果**；v1 notebook 和旧数字保留为历史 baseline，标注 v1，不重写、不进 headline 表 |
| D-020 | 每个 idea 一个 notebook；00/01 数据层，10–14 分别是 A/B/C/D/E；旧 notebook 02–08 retired |
| D-021 | Idea E 协议：NS 拟合、S/C 信号、tradable vs paper timing、样本、成本 |
| D-022 | E 结果：paper timing Sharpe 2.03，t+1 后消失；closed as not tradable |
| D-023 | E follow-ups：fit significance、paper-timing costs、Kalman A/B not adopted |
| D-024 | 云端 E 并入 D-020 布局；E 决策/日志重编号 |
| D-025 | A flip：`target_flip = -sign(spread)` 为 adopted candidate carry signal；gross 信息检验、成本 deferred、不做 test tuning |

完整内容见 `docs/decisions.md`。

---

## 4. 已经做完的

- Raw loader + contract-code parser（一位/两位年份、spaced roots、`.NA.`）。
- Rank panel：contract identity、roll/stale/code-missing/negative flags。
- Contract panel：每张合约完整一生、`last_trade_proxy`、`days_to_last_trading`。
- Return panel：换月日使用新合约前一天价格；`ret_naive` 只做诊断。
- Pair selection：no delivery month + D=10；adjacency guard。
- Spread panel：dollar/log/pct；negative-price flag。
- Universe：contract-level trailing 252-session median，rank-level fallback，pair min，threshold booleans。
- Episodes：固定合约对的 entry/exit spread + liquidity。
- Adjacent pairs：M1–M2 / M2–M3 / M3–M4 全建，`is_main_pair` 标记主 pair。
- QA：uniqueness、rank monotonicity、roll sync、return mapping、contract calendar、delivery-month、pair adjacency、known events。
- Notebooks 00/01：已执行，输出简洁。
- Agent log / decisions / data dictionary / onboarding。
- **A baseline framework**：`src/signals.py`、`src/backtest.py`、
  `src/metrics.py`；K=5 panel、per-contract mark state、event-loop engine、
  summary/conditional mean/sector/plot。
- **A benchmark**：`notebooks/10_idea_a_carry.ipynb`；full/train/test；负结果。
  旧 v1 baseline 见 `docs/notebook_history.md`。
- **A diagnosis**：`src/a_diagnostics.py`、`notebooks/10_idea_a_carry.ipynb`；
  side × sector × era、K=5 vs K=10、成本敏感性；细节见
  `docs/a_negative_result.md`。
- **B pre-test**：`src/b_pre_test.py`、`notebooks/11_idea_b_adjacent_carry.ipynb`；
  adjacent-carry rank；负结果，skip B；细节见 `docs/b_pretest.md`。
- **C baseline**：`src/continuous.py`、`signals.mean_reversion_signal`、
  `notebooks/12_idea_c_mean_reversion.ipynb`；1:1 weekly；负结果。
- **C hedge-ratio variant**：60-day rolling OLS h、strict weekly 调仓、
  0 bps gross 对照；负结果；统一在 notebook 12 的 C2。
- **C Kalman variant**：`src/kalman.py`、`tests/test_kalman.py`；
  rolling-likelihood DLM；aggregate mixed/negative，per-root NG 为正、
  CL 为负；C 收尾；统一在 notebook 12 的 C3。
- **D curve-momentum / basis-momentum**：`signals.curve_momentum_signal`、
  `curve.monthly_rebalance_dates`、monthly `BacktestConfig`；
  `notebooks/13_idea_d_curve_momentum.ipynb`；N=2、12m、monthly、±1、5 bps；
  full gross +0.55%、net −0.99%；test gross −0.28%、net −1.89%；
  static +1 gross +0.35% / net −0.84%，D 的 gross 略高但 turnover 更高、
  net 更差；monthly net Sharpe full −0.90 / test −1.66，bootstrap t
  full −5.87 / test −5.41。documented negative/mixed。
- **Backtest v2 framework**：holdings-based simulator、分层成本、
  horizon / k sweep / capacity；`docs/backtest_framework.md`、
  `src/specs.py`–`plotstyle.py`。
- **E（Nelson–Siegel）**：`src/nelson_siegel.py`、`src/ns_kalman.py`、
  `notebooks/14_idea_e_nelson_siegel.ipynb`；paper timing 可复现，
  t+1 fill 后消失；closed as not tradable（D-021–D-023）。
- **v2 重跑（正式结果，D-019）**：A/D/C/C-rolling-OLS/C-Kalman/B；
  `src/v2_signals.py`、`src/v2_rerun.py`、`scripts/run_v2_rerun.py`、
  notebooks 10–14；D-017/D-018/D-021–D-023；full-sample 结果全部 negative/mixed。
  v1 数字保留在 docs 和 git history，仅作历史 baseline。
- **136 tests**；`docs/backtest_framework.md`；`docs/v1_v2_comparison.md`；
  `docs/notebook_history.md`；`docs/PROGRESS.md`。

---

## 5. 还没做的

- C 已合入 main 并 closed；不做 daily paper replication。若以后重开，
  daily CL/NG 是独立的 pre-registered 项目。
- D 已 closed 为 documented negative/mixed；不做 test-set tuning；
  D-x（cross-sectional basis-momentum）是单独的 backlog，不混入 D。
- H（holding-period scan）的正式实现；monthly engine support 已就绪。
- 原始 A/B 方向已收尾，不再做变体或调参；A flip 是 separately adopted
  candidate signal（D-025），其 gross 信息检验已完成；不做 flip test tuning。
  residual B 不计划，除非以后作为独立预注册 idea。
- Robustness：D=5/20、liquidity buckets、tick-based cost、
  point-in-time D=10 proxy。
- 最终 liquidity threshold（baseline 不硬筛）。
- Contract multiplier / tick size 静态表（做美元 P&L 和容量需要）。
- Proposal 的 holding horizon `h`（baseline 用 weekly/monthly；H 扫描 deferred）。
- C daily paper replication not planned; E paper replication is complete
  (notebook 14).
- 队友 GitHub collaborator 权限已解决。

---

## 6. 如何复现

前提：raw CSV 在：

```text
data/raw/bloomberg_commodity_bulk_tickers_1986_2026.csv
```

一条命令：

```bash
bash scripts/run_all.sh
```

或者手动：

```bash
python -m pip install -r requirements.txt
python -m pytest -q
jupyter nbconvert --execute --to notebook --inplace notebooks/00_data_audit.ipynb
jupyter nbconvert --execute --to notebook --inplace notebooks/01_panel_build.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/10_idea_a_carry.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/11_idea_b_adjacent_carry.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=1800 notebooks/12_idea_c_mean_reversion.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/13_idea_d_curve_momentum.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=3600 notebooks/14_idea_e_nelson_siegel.ipynb
```

第二个 notebook 会重建 `data/processed/*.parquet`；10–14 分别跑 A、B、
C（1:1/OLS/Kalman）、D 和 E；结果写到 `output/`（gitignored）。旧 notebook
02–08 不再运行，替代关系见 `docs/notebook_history.md`。

---

## 7. Open questions（下一次决定）

1. **C 已合入 main**：C 已有 1:1 baseline、rolling-OLS 和 Kalman variant；
   notebook 12、LOG-0013–0018（baseline）、LOG-0022–0024（rolling OLS）和
   LOG-0026（Kalman）已合并。C 已作为 mixed/negative 收尾，不再做 daily
   replication。
2. **A/B 已收尾**：不再做变体或调参；报告只简短说明 A/B 不行。
   residual B 不计划，除非以后作为独立预注册 idea。
3. **Liquidity threshold**：baseline 不硬筛；robustness 用 1k/5k/10k/20k 中的哪个？
4. **Signal 优先级**：A/B/C/D/E 已 closed；v2 重跑完成。下一步是
   H（holding-period scan）；E 已完成并作为 not tradable 收尾。
5. **Proposal 的 h**：A/C baseline 用 weekly，D 用 monthly；H 扫描 1/5/21 天。
   v2 的 horizon 诊断只做信号层，不替代 H 的正式回测。
6. **Contract multiplier / tick size**：美元 P&L、容量、tick-based cost 需要时再建。
7. **Adjacent pairs**：A/D 主结果只用 main pair；D-x 的横截面组合以后再决定。

---

## 8. 下一步

A、B、C、D、E 都已作为负结果或 not-tradable 收尾：A 的 contango short 方向错；
B 的 adjacent-carry rank 在成本前就为负；C 的 1:1、rolling-OLS 和 Kalman
都没有稳健、可交易的 edge；D 的 gross 很弱，5 bps 后为负，test gross 已经
为负。C/D 已合入 main 并 closed。下一步：

1. C/D 已 closed；不做 daily paper replication；v2 的 `rebalance="daily"`
   只用于新的日频策略（C/E），不改变 C 的收尾结论；
2. v2 重跑 A/D/C/C-hedge/B 已完成；结论仍是 negative/mixed，不再用 v2
   数字调参或做 rescue 变体；
3. E（Nelson–Siegel curve dynamics）已完成并 closed as not tradable
   （D-021–D-023，notebook 14）；
4. 做 H（holding-period scan）；monthly engine support 已就绪；
5. D-x（cross-sectional basis-momentum）作为独立 backlog，等 H 之后决定；
6. 不要用 test 调参；原始 A/B 已收尾，C/D 不再做 rescue 变体；
7. A flip 的 gross 信息检验已完成（D-025，notebook 10 §7）；下一步是
   final portfolio 的成本/sizing；不要用 2016–2026 调 flip。

---

## 9. Failure diagnostics plan（2026-10-19）

`docs/diagnostics_plan.md` 记录了 A/B/D 的诊断协议：v2 rerun 为主，per-root
Sharpe bootstrap CI + 3 年窗口正收益比例，A 的 days-to-expiry / beta-neutral /
seasonality，B 的一段话，D 的机制检验待下一次对话确认。**部分实现
（2026-10-20）：** A flip 的 gross 信息检验在 notebook 10 §7（D-025）；
A 的 failure-diagnostic card、B 和 D 的 card 仍未实现。

下一步：确认 D 的机制检验和是否需要 A 的 v1 对齐 robustness，再补
`src/diagnostics.py` 的 A/B/D card 和（如需要）`notebooks/15_failure_diagnostics.ipynb`。
