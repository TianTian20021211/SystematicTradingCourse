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

## 加一个新 signal（例如 C）

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

signal function 输出同样的 `date, root, score, target`；
engine 和 metrics 不变。

## 改仓位规则

只改 `build_target_legs`：

- A：near/far `units = ±1`；
- B 多腿：一个 group 输出多行；
- cross-section / inverse-vol：在这一层改权重。

Engine 只认腿级 `units`，所以不用改。

## 改执行/成本

只改 `BacktestConfig`：

```python
BacktestConfig(
    cost_bps_per_leg=5.0,
    rebalance="last_trading_day_of_week",
    execution_lag=1,
    missing_exit_sessions=5,
    return_denominator="gross_notional",
    start_date=None,
    end_date=None,
)
```

当前只支持 `execution_lag=1`、weekly rebalance、gross-notional return；
其他值会显式报错，不会静默忽略。

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

- `src/continuous.py` — roll-chained leg price indices
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
D/B 还没实现。
