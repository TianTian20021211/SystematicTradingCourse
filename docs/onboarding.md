# 队友上手指南

这是一页纸的 onboarding。更完整的背景在 `docs/project_brief.md`，硬规则在
`AGENTS.md`，决策记录在 `docs/decisions.md`。

## 1. 这个 repo 在做什么

用 1986–2026 的 Bloomberg 商品期货数据研究 calendar spread。数据层已完成：
把 generic M1–M4 还原成真实合约，建 rank/contract/return/spread panel。
A（carry）、B、C（mean reversion）和 D（curve momentum / basis-momentum）
的 baseline 都已跑通，但在最简 K=5 版本里都是负结果或 mixed-negative；
C 的 rolling-OLS 和 Kalman hedge-ratio variant 也没有改善。A/B 已收尾
（不再调参/不做 rescue），C/D 已 closed 并合入 main。v2 holdings-based
回测框架（分层成本、horizon、容量）也已合入 main，notebook 07 是 demo；
v2 重跑 A/D/C/C-hedge/B 已完成，**v2 是正式结果（D-019）**，结论仍是
negative/mixed；v1 notebook 和旧数字保留为历史 baseline。
下一步是按 D-014 做 E，再做 H。D-x（cross-sectional basis-momentum）是
backlog。

## 2. 先读什么

1. `README.md` — 5 分钟入口。
2. `docs/HANDOFF.md` — 当前状态、关键数字、open questions。
3. `docs/decisions.md` — 已经锁定的决定（D=10、no delivery month、dollar/log）。
4. `docs/data_dictionary.md` — 字段和 panel schema。
5. `docs/logs/INDEX.md` + `docs/logs/AGENT_LOG.md` — 最近谁做了什么。
6. `docs/project_brief.md` / `docs/research_notes.md` — 详细背景和 roll/spread 推理。

如果你用 coding agent：让它先读 `AGENTS.md`；Claude Code 读 `CLAUDE.md`。

## 3. 数据怎么放

Public repo 不包含 Bloomberg 原始数据。向 Tian 要 CSV，然后放到：

```text
data/raw/bloomberg_commodity_bulk_tickers_1986_2026.csv
```

校验：

```bash
shasum -a 256 data/raw/bloomberg_commodity_bulk_tickers_1986_2026.csv
# 应为 045293fed420a82a3f85e592835eac6dba70fce0898b0fe8ddf40561e3f37771
```

XLSX 只用于生成 `data/metadata/commodities.csv`；日常 notebook 不依赖它。

## 4. 环境与运行

一条命令（会安装依赖、跑 tests、执行 A/B/C/D notebook）：

```bash
bash scripts/run_all.sh
```

或者手动：

```bash
python -m pip install -r requirements.txt
jupyter lab
```

从 repo 根目录依次运行：

```text
notebooks/00_data_audit.ipynb        # 只读审计 + 流动性诊断
notebooks/01_panel_build.ipynb       # 建 panel，写 data/processed/*.parquet
notebooks/02_carry.ipynb             # A baseline
notebooks/03_mean_reversion.ipynb    # C baseline + hedge-ratio
notebooks/04_a_diagnose.ipynb        # A 负结果诊断（依赖 02 的输出）
notebooks/05_b_pretest.ipynb         # B adjacent-carry 预测试
notebooks/06_curve_momentum.ipynb    # D curve-momentum / basis-momentum baseline
notebooks/07_backtest_framework.ipynb # v2 holdings-based framework demo (A)
notebooks/08_v2_rerun.ipynb          # v2 re-runs A/D/C/C-hedge/B + v1/v2 对照
```

测试（不需要 raw data）：

```bash
python -m pytest -q
```

## 5. 你应该怎么改

- 逻辑放 `src/`，notebook 只叙述和调用。
- 不要提交 raw data、PDF、parquet、secrets。
- 不要跨 roll 对 generic price 做差分；收益按 contract code 对齐。
- 不要改 D=10 / no delivery month / dollar-primary，除非先在
  `docs/decisions.md` 记录并由 Tian 确认。
- 每次 material change：
  1. 在 `docs/logs/AGENT_LOG.md` append 一条 entry；
  2. 更新 `docs/logs/INDEX.md`；
  3. 和代码一起 commit；commit message 里写 `Log: ...#LOG-XXXX`。

## 6. 当前下一步

数据层（Phases R–4）已完成：rank/contract/return/spread/universe/episodes
panel、liquidity diagnostics、adjacent-pair robustness。
A baseline 和 A 诊断已完成（`02_carry`、`04_a_diagnose`），B 预测试也已完成
（`05_b_pretest`），C baseline + rolling-OLS + Kalman variant 已完成
（`03_mean_reversion`、`src/kalman.py`），D curve-momentum baseline 也已完成
（`06_curve_momentum`、`src/signals.py` 的 `curve_momentum_signal`）；
A/B/C/D 都是负结果或 mixed-negative。A/B 已收尾，C/D 已 closed 并合入
main。v2 回测框架（`src/simulate.py` 等、notebook 07）也已合入 main；
v2 重跑 A/D/C/C-hedge/B（`src/v2_signals.py`、`src/v2_rerun.py`、
notebook 08、`docs/v1_v2_comparison.md`）已完成，**v2 是正式结果
（D-019）**；v1 notebook 和旧数字是历史 baseline。结论仍是 negative/mixed。
下一步是按 D-014 做 E，再做 H；D-x 是 backlog。
先读 `docs/PROGRESS.md` 和 `docs/backtest_framework.md`。
不要用 test set 调参。
如果发现数据问题，先更新 `docs/logs/AGENT_LOG.md` 和 `docs/decisions.md`。
