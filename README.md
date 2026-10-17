# Commodity Calendar Spread Research

MTH 9897 · Project 7 · Baruch MFE 2026

用 1986–2026 的 Bloomberg 商品期货数据，研究同一商品不同到期月之间的 **calendar spread**：曲线形状、roll、carry、价差的可预测性与可交易性。

> 这个 repo 是**数据层 + 研究脚手架**。当前阶段做数据审计、contract-level panel、spread panel 和流动性诊断；signals/backtest 是下一阶段。

---

## 当前状态

- [x] 原始数据审计：24 commodities × 4 nearby ranks，1986–2026
- [x] Repo scaffold、agent collaboration protocol、decision/log 体系
- [ ] Rank / contract / return / spread panels
- [ ] Liquidity diagnostics（threshold 由你看完图后决定）
- [ ] Signals A/B/C/D/H + backtest（下一阶段）

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
   ```

   第二个 notebook 会生成 `data/processed/*.parquet`（不提交到 repo）。

---

## Repo map

```text
README.md                 # 本文件：简洁入口
AGENTS.md                 # 通用 coding agent 入口与硬规则
CLAUDE.md                 # Claude Code 专用入口

docs/
  project_brief.md        # 详细项目背景、五个 idea、数据说明
  data_dictionary.md      # raw + derived fields + panel schemas
  decisions.md            # 已锁定的研究/数据决定
  onboarding.md           # 队友 1 页上手
  logs/                   # agent 操作日志（谁、做了什么、为什么、怎么验证）

src/                      # 所有数据处理逻辑（notebook 只调用）
notebooks/                # 00_data_audit, 01_panel_build
tests/                    # synthetic fixtures + parser/roll/spread tests

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
