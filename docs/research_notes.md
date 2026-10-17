# Research Notes — Roll、Spread、以及我们为什么这样选

这份笔记把对话里关于 roll / spread 的推理压缩成一页，方便新对话或队友快速恢复 context。  
更正式的决策见 `docs/decisions.md`，数据字段见 `docs/data_dictionary.md`。

---

## 1. Raw data 里的 roll 是什么

Bloomberg generic M1–M4 是**槽位**，不是合约。换月日四个 rank 同时前移一格：

```text
t-1:  M1=A,  M2=B,  M3=C
t:    M1=B,  M2=C,  M3=D
```

- 旧 M1（A）在 t 之后从 panel 里消失；你必须在 t-1 收盘前（或更早）平掉它。
- 新 M1（B）在 t-1 的价格存在于旧 M2 里，所以换月日正确的 rank 收益是：

\[
r_t = \frac{P_B(t)}{P_B(t-1)} - 1
\]

不是：

\[
\frac{P_B(t)}{P_A(t-1)} - 1
\]

后者把 A 和 B 的价差当成了收益。`src/panel.build_return_panel` 实现了正确 mapping；`ret_naive` 只保留作诊断。

---

## 2. 论文里的 roll 惯例

| 论文 | 做法 | 隐含 buffer |
|---|---|---|
| Paschke, Prokopczuk & Wese Simen (2020), *Curve Momentum* | “roll the first nearby contract at the end of the second month before the last trading day”；换月日收益用 \((i+1)\)-th nearby 的前一天价格 | 约 2 个月（~35–45 trading days） |
| Bianchi, Fan, Miffre & Zhang (2023), *Curve Dynamics* | “hold a given contract until the last trading day before the front contract enters its maturity month” | 日历规则，约 15–20 trading days |
| Lubnau & Todorova (2015), *Mean Reversion* | Datastream 连续序列 “rolling over on the first trading day of the month” | 没有固定 D；数据商月初换 |

Paschke 的 roll 收益公式正好是：

\[
R_{t+1}^{(i)} =
\begin{cases}
F_{t+1}^{(i)}/F_t^{(i)} - 1, & \text{no roll at } t \\
F_{t+1}^{(i)}/F_t^{(i+1)} - 1, & \text{roll at } t
\end{cases}
\]

---

## 3. 业界惯例

- **BCOM / S&P GSCI**：每月第 5–9 个 business day 滚动，5 天窗口，每天 20%。这是日历窗口，不是按到期日倒推。
- **商品 ETF（USO/UNG 等）**：通常在月初第 5–6 个 business day 附近启动，持续 3–5 个交易日，不进入交割。
- **CTA / 经纪商常见做法**：first notice 或 last trading 前 5–10 个 business day 平仓/换月。

参考：
- [S&P GSCI Methodology](https://spglobal.com/spdji/en/documents/methodologies/methodology-sp-gsci.pdf)
- [GSG 424B3 (SEC)](https://www.sec.gov/Archives/edgar/data/1332174/000143774926018223/gsg20260520_424b3.htm)
- [BCOM roll overview (Phillip Invest)](https://www.phillipinvest.com.my/private-managed-account-pma-alpha-strategy-explained/)

---

## 4. 我们的选择（D-002）

> **不持有进入交割月的合约；交割月开始前至少 5 个 trading sessions 退出；且 `days_to_last_trading > 10`。D=5/20 做稳健性。**

为什么不是一个裸 D：

- 同一个 D 在不同商品上含义不同。CL/NG 的 generic roll 已经在交割月前约 1 个月；corn/soybean/sugar/metals 的 roll 常在交割月内。
- 只用 D=10，对 grains/softs 仍然可能在交割月里持有。
- 所以我们用**两条约束**：
  1. 日历约束：不进入 delivery month（K=5 sessions 作为 first notice 的 proxy）；
  2. 流动性约束：`days_to_last_trading > D`。
- 对 energy，第 2 条通常先触发；对 grains/softs/metals，第 1 条通常先触发。这样更接近 Bianchi 的“交割月前退出”，同时保留 industry 的 5–10 天流动性 buffer。

---

## 5. Spread 的几种表示

设 near=A，far=B。

| 表示 | 定义 | 用途 |
|---|---|---|
| Dollar spread | \(C=P_A-P_B\) | **主交易/P&L**；1:1 两条腿，P&L = multiplier × ΔC |
| Percentage spread | \((P_A-P_B)/P_A\) | carry、跨品种比较、notional sizing |
| Ratio spread | \(P_A/P_B\) | 统计信号；围绕 1 不对称 |
| Log spread | \(\log P_A-\log P_B\) | z-score/回归；对称、可加；要求两边价格 >0 |
| Spread return index | 累计 \(\Delta P_A-\Delta P_B\) | 回测、momentum、performance |

关键区别：

- **Dollar spread 是交易价格**；ratio/log 是看它的方式。
- 主实验统一 dollar spread；ratio/log 只做信号归一化/稳健性。
- 换月时 raw spread level 会跳；这个跳不是收益。要拼**收益**，不是拼价格水平。
- 主结果不做 back-adjusted 连续价格；固定合约对 episode + raw prices，和 proposal 的 “raw contract prices, never back-adjusted” 一致。
- CL 2020-04-20 负价格：dollar spread 仍然定义；log spread 置 NaN + flag。

---

## 6. 数据审计的关键事实

- 10,640 个 weekday rows；128 个全空假日；panel union 10,559 天。
- 24 commodities、96 generic series、6,735 张真实合约、950,626 contract-date rows。
- 6,377 个 full roll dates；四个 rank 全部同时换；0 partial / 0 queue violation。
- 583 行有 settle 但无 contract code，主要是假日/中断；丢弃对齐。
- Volume/OI 缺失 overall ~16–20%，2000 年后约 4%，1986–1990 更差；missing ≠ 0。
- 唯一负价格：CL 2020-04-20 = −37.63。
- 主 pair mix（D=10 + no delivery month）：139,017 M1–M2 / 97,169 M2–M3；adjacent pairs 610,801 rows。

---

## 7. 还没定的事

- Liquidity threshold：1k/5k/10k/20k。
- Signal 优先级：A/B/C/D/H。
- Proposal 的 h（1/5/21 天）。
- Contract multiplier / tick size 静态表。
- Adjacent pairs 在哪些 idea 里用。
