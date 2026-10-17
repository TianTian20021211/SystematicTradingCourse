# Handoff — 当前状态

**最后更新：** 2026-10-17  
**最新数据层 commit：** `595ca49`（本 handoff 之后会多一个 docs commit）  
**Repo：** https://github.com/TianTian20021211/SystematicTradingCourse

---

## 0. 新对话 / 新队友先读什么

1. `README.md` — 5 分钟入口。
2. `docs/HANDOFF.md` — 本文件，当前状态和 open questions。
3. `AGENTS.md`（Claude Code 还会自动读 `CLAUDE.md`）。
4. `docs/decisions.md` — 已锁定的决定。
5. `docs/data_dictionary.md` — 字段和 panel schema。
6. `docs/logs/INDEX.md` + `AGENT_LOG.md` 最近几条 — 谁做了什么。
7. `notebooks/00_data_audit.ipynb`、`01_panel_build.ipynb` — 已执行，带简洁输出。

---

## 1. 一句话

**数据层已经完成：raw → contract-level panel → roll-aware returns → spread/universe/episodes → 两个可读 notebook。**  
**Signals/backtest 还没开始。**

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

这些 parquet 在 `data/processed/`，**gitignored**；见 `data/processed/README.md`。

关键 QA：

- 0 duplicate contract-date
- 0 rank-order violations
- 0 partial rolls
- 0 full-day queue violations
- CL 2020-04-20 = **−37.63** 仍在
- 15 个 pytest 全过
- 两个 notebook 都能 top-to-bottom 跑完

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

---

## 5. 还没做的

- Signals A/B/C/D/H 的正式实现。
- Backtest、cost model、position sizing。
- 最终 liquidity threshold（等你看完图选）。
- Contract multiplier / tick size 静态表（做美元 P&L 和成本需要）。
- Proposal 的 holding horizon `h`（1日/5日/21日？）。
- 队友的 GitHub collaborator 权限（需要 repo owner 添加）。
- Paper replication。

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
```

第二个 notebook 会重建 `data/processed/*.parquet`。

---

## 7. Open questions（下一次决定）

1. **Liquidity threshold**：1k / 5k / 10k / 20k？主结果和 robustness 各用哪个？
2. **Signal 优先级**：A/B/C/D/H 先做哪个？还是先把 common pair 上的 baseline 都跑一遍？
3. **Proposal 的 h**：1 日、5 日还是 21 日？`h + D < days_to_expiry` 怎么处理？
4. **Contract multiplier / tick size**：有没有现成表？没有的话要不要我建 24 商品的静态 spec 表？
5. **Adjacent pairs**：主结果只用 `pairs`，还是某些 idea（curve RV/butterfly）直接用 `adjacent_pairs`？
6. **队友权限**：需要在 GitHub Settings → Collaborators 添加。

---

## 8. 下一步

先 review `notebooks/00_data_audit.ipynb` 和 `01_panel_build.ipynb`，特别是 liquidity 图；确定 threshold 和 signal 优先级后，再进入下一阶段。  
在 Tian 明确说开始之前，不要写 signal/backtest。
