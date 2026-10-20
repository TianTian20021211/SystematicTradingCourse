# Backtest Framework（一页）

目标：队友能看懂、能改；以后 C/D/B 只换 signal，不重写 engine。

## 五层

```text
data panels
  rank / contract / pairs / spread
        │
        ▼
continuous index layer               src/continuous.py
  date, root, spread_index
        │
        ▼
signal layer                         src/signals.py
  date, root, score, target
        │
        ▼
target-leg layer                     src/backtest.py::build_target_legs
  date, root, group_id, contract, units
        │
        ▼
engine                               src/backtest.py::run_backtest
  positions, trades, daily returns, portfolio returns
        │
        ▼
metrics                              src/metrics.py
  summary, conditional mean, sector, plot
```

每层只做一件事：

| 层 | 知道什么 | 不知道什么 |
|---|---|---|
| Continuous | price-change chaining、roll 日不 jump | signal 规则、成交、P&L |
| Signal | carry/mean reversion 怎么算 | 成交、成本、roll |
| Target legs | 用哪张合约、多少 units | signal 内部逻辑 |
| Engine | position、roll、missing、cost、P&L | 这是哪个 idea |
| Metrics | 怎么汇总/检验 | 怎么交易 |

## 最小用法

```python
from src import panel, signals, backtest, metrics

bt = panel.build_backtest_panel(rank, d=None, k=5)
signal = signals.carry_signal(bt["spread"])
targets = backtest.build_target_legs(signal, bt["spread"])
result = backtest.run_backtest(
    bt["spread"], bt["contract"], targets,
    backtest.BacktestConfig(),
)
summary = metrics.summarize(result)
```

`run_backtest` 不读文件；只接受 DataFrame，所以单测可以用 synthetic frames。

## 加一个新 signal（C / D）

C 需要一个 roll-safe 的连续价差序列；这是 `src/continuous.py` 的职责，
signal function 只消费 `spread_index`：

```python
leg = continuous.build_continuous_leg_prices(bt["pairs"], bt["contract"])
spread_index = continuous.build_spread_index(leg)
signal = signals.mean_reversion_signal(
    spread_index,
    signals.MeanReversionParams(window=20),
    trading_days=curve.trading_calendar(bt["contract"]),
    pair_grid=bt["pairs"][["date", "root"]],
)
targets = backtest.build_target_legs(signal, bt["spread"])
result = backtest.run_backtest(bt["spread"], bt["contract"], targets, config)
```

D 需要 rank-level 的 roll-adjusted 收益；这是 `panel.build_return_panel`
的职责，signal function 只消费 `ret_rank`：

```python
returns = panel.build_return_panel(bt["rank"], bt["contract"])
signal = signals.curve_momentum_signal(bt["spread"], returns)
targets = backtest.build_target_legs(signal, bt["spread"])
result = backtest.run_backtest(
    bt["spread"], bt["contract"], targets,
    backtest.BacktestConfig(rebalance="last_trading_day_of_month"),
)
```

signal function 输出同样的 `date, root, score, target`；
engine 和 metrics 不变。

## 改仓位规则

只改 `build_target_legs`：

- A：near/far `units = ±1`；
- hedge ratio：signal 带 `hedge_ratio` 列时，far `units = −target × h`；
- B 多腿：一个 group 输出多行；
- cross-section / inverse-vol：在这一层改权重。

Engine 只认腿级 `units`，所以不用改。

## 改执行/成本

只改 `BacktestConfig`：

```python
BacktestConfig(
    cost_bps_per_leg=5.0,
    rebalance="last_trading_day_of_week",  # or "last_trading_day_of_month"
    execution_lag=1,
    missing_exit_sessions=5,
    return_denominator="gross_notional",
    start_date=None,
    end_date=None,
)
```

`rebalance` 支持 `"last_trading_day_of_week"`（默认）、
`"last_trading_day_of_month"`（D-013）和 `"daily"`（D-015）。
当前只支持 `execution_lag=1`、gross-notional return；其他值会显式报错，
不会静默忽略。Signal 和 engine 必须使用同一个
`curve.weekly_rebalance_dates` / `curve.monthly_rebalance_dates`，避免
signal 日期和调仓日期漂移。`metrics.conditional_mean` 仍按 weekly
evaluation 写；monthly 结果用 `notebooks/06_curve_momentum.ipynb` 里的
月度诊断，不要直接喂给它。

## Engine 的规则（必须知道）

- 按天 event loop；日期内部用 pandas 向量化。
- t 收盘 signal，t+1 收盘成交；先 mark 旧 position，再执行 pending。
- Pending order 绑定 pair；pair 在 fill 前变了就 cancel/reprice。
- Roll：t 发现 pair 变，t+1 平旧、开新；旧腿缺失用 last valid + `roll_leg_missing`。
- Missing/stale：不开新仓；最后有效价格 mark；第 6 个 invalid session 后
  forced exit。
- 成本按实际净腿：entry/exit 2 leg-units ≈ 5 bps；roll/flip 4 leg-units ≈ 10 bps。
- 不使用 `last_trade_proxy`、`is_censored`、episode exit date 等 ex-post 字段。

## 文件

- `src/continuous.py` — roll-chained leg price indices, rolling OLS hedge ratio
- `src/kalman.py` — Kalman-filter hedge ratio (rolling-likelihood DLM)
- `src/signals.py` — signal functions
- `src/backtest.py` — target legs + engine
- `src/metrics.py` — summary, conditional mean, sector, plot
- `src/panel.py` — `build_backtest_panel`, `build_contract_mark_state`
- `notebooks/02_carry.ipynb` — A baseline example
- `docs/data_dictionary.md` §10 — table schemas

## 当前状态

A baseline 已跑通。结果见 `notebooks/02_carry.ipynb` 和
`output/carry_summary.csv`。

C（mean reversion）baseline 已实现：连续价差层 + weekly z-score 状态机，
结果见 `notebooks/03_mean_reversion.ipynb` 和
`output/mean_reversion_summary.csv`。C 的 baseline 是负结果
（full-sample net Sharpe 约 −0.03；energy sanity check 也是负的）。

C 的 rolling-OLS hedge-ratio variant 也已完成（60-day levels、strict
weekly h 调仓、0 bps gross 对照）：h 中位数约 1.008；full/train/test 的
hedge 版本 vol 更低、return 更低、trade 数约翻倍，Sharpe 没有改善；
energy 1992–2013 只是从负接近零。不跑 5 bps。

C 的 Kalman hedge-ratio variant（rolling 252-day likelihood、每 60 天重估
V/W、9 点 q grid）也已完成：aggregate full gross +0.98% / vol 8.9% /
max DD −28.9%；per-root paper sample 里 NG 为正、CL 为负。5 bps 估算后仍为
负，且 paper 的 Sharpe >2 没有在 weekly K=5 设置下复现。**C 作为
mixed/negative 收尾**，不做 daily paper replication。

D（curve momentum / basis-momentum）baseline 已实现：N=2 main pair、
12-month formation、monthly rebalance、±1、5 bps；结果见
`notebooks/06_curve_momentum.ipynb` 和 `output/curve_momentum_*`。
Full-sample gross 为正但很弱，net 为负；test gross 已经为负。D 作为
documented negative/mixed baseline，不做 test-set tuning。`D-x`
（cross-sectional basis-momentum）是单独的 backlog，不混入 D。

## v2（holdings-based, layered costs）

新框架见 `notebooks/07_backtest_framework.ipynb` 和 D-016。v1（本页）保留不动，作为 A
的原始 benchmark。v2 的分层：`marks → sizing → simulate (+ costs) → report`，以及独立于执行的
`horizon` 诊断。成本假设和文献见 `docs/transaction_costs.md`。

```python
mk = marks.build_marks(bt["contract"], specs.load_contract_specs())
pairs = sizing.filter_liquid(sizing.attach_leg_liquidity(bt["spread"], mk), min_adv=100)
legs = sizing.legs_from_signal(signals.carry_signal(pairs), pairs, k=1)
res = simulate.simulate(legs, mk, simulate.SimConfig(capital=1e7))
report.performance_table(res)
```

加一个新 idea：只写 signal function（输出 `date, root, target`，可选 `score`）。

### v2 扩展（D-017）

- **Hedge ratio**：signal 可带可选 `hedge_ratio` 列。near units =
  `sign(target)`，far units = `-sign(target) * h`；`h` 是 contract ratio，
  不是价格比的乘数。invalid/non-positive h 变成显式 flat。
- **多腿**：`sizing.legs_from_rows(legs, budget)` 接受
  `date, root, contract, units, target` 的显式腿表，按 contract 净额合并，
  每个 `(date, root)` 只允许一个非 flat group。
- **Resize key**：`LEG_COLUMNS` 增加可选 `resize_key`；`on_change` key 是
  `(group_id, target, resize_key)`。`legs_from_signal` 在 h 存在时写
  `_h{round(h, 6)}`；`legs_from_rows` 写 contract/units composition。
  不要用原始 notional ratio 做 key，否则价格每天变化会触发日频调仓。
- **完整 calendar**：`SimResult.calendar` 保存 marks 的 union calendar；
  `_daily` 对其 reindex 并零填 flat days，`performance_table` /
  `root_table` / `capacity_curve` 都按完整 calendar 年化。
- **Adapters**：`src/v2_signals.py` 提供 A/D/C(1:1/OLS/Kalman)/B；
  `src/v2_rerun.py` + `scripts/run_v2_rerun.py` 负责重跑和缓存。
  `notebooks/08_v2_rerun.ipynb` 是结果和 v1/v2 对照。
- **B 的例外**：B 的 adjacent-carry 排序是同一 root 内 3 个 maturity
  spreads 的排序，不是跨商品截面；作为 D-017 的 narrow exception 运行，
  使用 `execution="legs"`。它保留 v1 的 raw-rank universe，不是 v2 的
  `d=5` universe。
- **C hedge/Kalman**：h 在 weekly evaluation 日 snap，pair-change 日使用
  当天 h；`resize_key` 让 h 变化只在预期日期触发调仓。
- **口径**：D-018 锁定 `d=5`、`k=5`、`min_adv=100`、USD 10m、
  equal-notional、三层成本；test 是 post-hoc slice；不要用 test 调参。
  `d=5` 目前仍依赖 `last_trade_proxy`，不是严格 point-in-time。
