# Handoff — 当前状态

**最后更新：** 2026-10-19  
**Foundation commit：** `f2c4771`（K=5 panel + mark state + carry signal）  
**A/B merge：** 见 `git log`（A diagnosis + B pre-test）  
**C branch：** `feat/idea-c-mean-reversion`（未合入 main）  
**Repo：** https://github.com/TianTian20021211/SystematicTradingCourse

---

## 0. 新对话 / 新队友先读什么

1. `README.md` — 5 分钟入口。
2. `docs/HANDOFF.md` — 本文件，当前状态和 open questions。
3. `AGENTS.md`（Claude Code 还会自动读 `CLAUDE.md`）。
4. `docs/decisions.md` — 已锁定的决定。
5. `docs/data_dictionary.md` — 字段和 panel schema。
6. `docs/logs/INDEX.md` + `AGENT_LOG.md` 最近几条 — 谁做了什么。
7. `notebooks/00_data_audit.ipynb`、`01_panel_build.ipynb` — 数据层。
8. `notebooks/02_carry.ipynb` — A baseline；`04_a_diagnose.ipynb` — A 诊断；
   `05_b_pretest.ipynb` — B 预测试；`docs/PROGRESS.md` — 实时进度。

---

## 1. 一句话

**数据层 + A/B baseline 已完成：K=5 ex-ante panel → carry signal →
return-based event-loop backtest → full/train/test benchmark。**  
**A 和 B 都是负结果，已收尾（不再调参数/不做 rescue）；C 在独立 branch 上
（未合入 main）；D/H 还没开始。**

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
- notebooks 00/01/02/04/05 都能 top-to-bottom 跑完

A baseline（K=5；1986–2026）：

| Period | Gross ann. | Net ann. | Sharpe net | Max DD net |
|---|---:|---:|---:|---:|
| Full | −0.53% | −1.90% | −0.08 | −55.3% |
| Train 1986–2015 | −0.44% | −1.78% | −0.10 | −42.7% |
| Test 2016–2026 | −0.76% | −2.20% | −0.06 | −21.9% |

Conditional raw spread return：`target_positive` ≈ 0（t −0.27）；
`target_negative` 为 **+0.000127（t +2.41）**，即 contango spread 平均会变强，
short spread 是错的方向。**A 在这个 baseline 没有 edge。**

A diagnosis（`04_a_diagnose.ipynb`）：short raw mean +0.000024（t +2.46），
long −0.000008（t −0.65）；K=10 不翻正；0/5/10/20 bps 下 gross 已经负。

B pre-test（`05_b_pretest.ipynb`）：adjacent-carry rank，full gross −1.14%、
net −2.84%（gross Sharpe −0.08）；预注册规则 **skip B = True**。

**Zero-cost check：** A full gross ann. −0.53%（Sharpe −0.02）；B full gross
ann. −1.14%（Sharpe −0.08）。两者在扣交易成本之前已经是负的。

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
- **A benchmark**：`notebooks/02_carry.ipynb`；full/train/test；负结果。
- **A diagnosis**：`src/a_diagnostics.py`、`notebooks/04_a_diagnose.ipynb`；
  side × sector × era、K=5 vs K=10、成本敏感性。
- **B pre-test**：`src/b_pre_test.py`、`notebooks/05_b_pretest.ipynb`；
  adjacent-carry rank；负结果，skip B。
- **36 tests**；`docs/backtest_framework.md`；`docs/PROGRESS.md`。

---

## 5. 还没做的

- C 的正式合入（`feat/idea-c-mean-reversion` 已有 baseline，但未合入 main）。
- D/H 的正式实现（engine 可复用）。
- A/B 已收尾，不再做变体或调参；residual B 不计划，除非以后作为独立预注册 idea。
- Robustness：D=5/20、liquidity buckets、tick-based cost、
  point-in-time D=10 proxy。
- 最终 liquidity threshold（baseline 不硬筛）。
- Contract multiplier / tick size 静态表（做美元 P&L 和容量需要）。
- Proposal 的 holding horizon `h`（baseline 用 weekly；H 扫描 deferred）。
- Paper replication。
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
  --ExecutePreprocessor.timeout=600 notebooks/02_carry.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=600 notebooks/04_a_diagnose.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/05_b_pretest.ipynb
```

第二个 notebook 会重建 `data/processed/*.parquet`；02 跑 A baseline，
04 跑 A 诊断（依赖 02 的 `output/carry_full_*`），05 跑 B 预测试；
结果写到 `output/`（gitignored）。

---

## 7. Open questions（下一次决定）

1. **C 何时合入 main**：C 在 `feat/idea-c-mean-reversion`，已有 baseline
   （gross 正、net 负）；notebook 03 和 LOG-0013–0018 已预留。合入时从
   LOG-0022 继续。
2. **A/B 已收尾**：不再做变体或调参；报告只简短说明 A/B 不行。
   residual B 不计划，除非以后作为独立预注册 idea。
3. **Liquidity threshold**：baseline 不硬筛；robustness 用 1k/5k/10k/20k 中的哪个？
4. **Signal 优先级**：D（curve momentum）和 H（holding-period scan）是下一步。
5. **Proposal 的 h**：baseline 用 weekly；H 扫描 1/5/21 天。
6. **Contract multiplier / tick size**：美元 P&L、容量、tick-based cost 需要时再建。
7. **Adjacent pairs**：A 主结果只用 main pair；B/D 的多腿以后再决定。

---

## 8. 下一步

A 和 B 都已作为负结果收尾：A 的 contango short 方向错，B 的 adjacent-carry
rank 在成本前就为负。**A/B 不再调参数、不做 rescue 变体。** C 在独立
branch 上继续推进，未合入 main。下一步：

1. C 合入时保留 notebook 03 和 LOG-0013–0018，并从 LOG-0022 继续；
2. 做 D/H（engine 可复用）；
3. 不要用 test 调参；A/B 的变体不再做。
