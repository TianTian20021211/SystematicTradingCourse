# A（Carry）Negative Result — 一页说明

**Scope:** time-series carry sign on the K=5 ex-ante universe.
**Status:** **closed** (2026-10-19); documented negative baseline.
**Not a rescue attempt:** no long-only, threshold, cross-section, or h variants.
**Full detail:** `notebooks/10_idea_a_carry.ipynb` (old `04_a_diagnose`
retired; recovery in `docs/notebook_history.md`).

> **Update 2026-10-20 (D-025):** the original A direction documented here
> remains a closed negative, and its v2 result is unchanged. The adopted
> carry signal is the sign-flipped rule `target_flip = -sign(spread_dollar)`
> (contango → long spread, backwardation → short spread), tested gross-only
> in `notebooks/10_idea_a_carry.ipynb` §7. This is a new hypothesis, not a
> rescue of A; transaction costs are deferred to the final portfolio.

---

## 1. Headline

A 的方向规则是：

- backwardation（spread > 0）→ long spread；
- contango（spread < 0）→ short spread。

数据不支持这个方向：

| Side | Raw mean | t-stat | Gross contribution |
|---|---:|---:|---:|
| Long (backwardation) | −0.000008 | −0.65 | −0.033 |
| Short (contango) | **+0.000024** | **+2.46** | **−0.184** |

`raw mean` 是原始 spread return（`return_gross × direction`）；
`contribution = return_gross / n_active`，加总等于每日 portfolio gross return 的累计和。
负 P&L 主要来自 short side。

**零成本检查：** 这些 raw mean 和下面的 0 bps 结果都是**不考虑 transaction
cost** 的；A 在成本前已经是负的（full-sample gross ann. −0.53%，
gross Sharpe −0.02）。

---

## 2. K=5 vs K=10（都是 ex-ante）

| k | Pair rows | M1–M2 | M2–M3 | Gross ann. | Net ann. | Sharpe gross | Sharpe net | Long raw (t) | Short raw (t) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 236,385 | 159,817 | 76,568 | −0.53% | −1.90% | −0.02 | −0.08 | −0.000008 (−0.65) | +0.000024 (+2.46) |
| 10 | 234,934 | 132,544 | 102,390 | −0.61% | −1.94% | −0.03 | −0.09 | −0.000032 (−2.83) | +0.000018 (+1.84) |

K=10 没有翻正；short 仍然错方向。负结果不是 K=5 buffer 的偶然。

D=10 没有使用：它依赖 `last_trade_proxy`（合约在数据里的最后出现日），是 ex-post；
拿它做回测会有 look-ahead。

---

## 3. 成本 0/5/10/20 bps

| Cost (bps/leg) | Net ann. | Net Sharpe | Max DD |
|---:|---:|---:|---:|
| 0 | −0.53% | −0.02 | −22.6% |
| 5 | −1.90% | −0.08 | −55.3% |
| 10 | −3.24% | −0.13 | −74.7% |
| 20 | −5.89% | −0.22 | −92.0% |

0 bps 就是**不考虑 transaction cost**：full / train / test gross ann.
分别为 −0.53% / −0.44% / −0.76%，gross Sharpe 都是 −0.02。
Gross 已经是负的；5 bps 的 net 只是更差，成本不是负号的原因。

---

## 4. Side × sector × era

- Short side 在多数 sector × era 格子 raw mean 为正（错方向），
  尤其在 Energy、Industrials 2010–2026、Softs 2010–2026。
- Long side 是 mixed：Energy 1986–1999 和 Oilseeds 有小幅正值，
  但 Grains/Industrials/Livestock/Metals 多数为负；没有 broad-based 的正 edge。
- 所以不是“某个板块特别差”；short side 的方向问题是系统性的。

完整 42 个格子见 `10_idea_a_carry.ipynb`（旧 `04_a_diagnose` 已 retired）。

---

## 5. 结论

> **A 在这个 spec 下没有支持：两个 side 的 raw mean 都没有支持假设；
> contango short 显著错方向；K=10 和成本变化不翻符号。**

严格表述是 **no evidence + wrong sign in-sample**，不是 “proven absent”：
- Full-sample short t = +2.46；
- Test 2016–2026 short t = +0.87（不显著）；
- 所以不能声称“A 在所有状态下都不存在”。

机制上，contango 里 near 相对便宜；随着 near 接近到期，它向 spot 收敛，
spread（near − far）倾向于上升。Short spread 是在赌 near 继续弱，
和收敛方向相反。这不是再调一个参数就能修的问题。

---

## 6. 不再做的事

- 不跑 long-only / threshold / cross-section / inverse-vol / h=21；
- 不用 test set 调参；
- 不把 D=10 或 point-in-time proxy 加进来。

**Final status: closed.** A 作为 documented negative baseline 收尾；
不再调参数，不做 long-only / threshold / cross-section / inverse-vol / h 变体。
报告里只写一句：A 的 carry sign 在这个数据上不成立。下一步是 C（mean
reversion），它在另一个 branch 上推进。

---

## 7. Flip follow-up（D-025，2026-10-20）

原始 A 的 sign 是 documented negative；D-025 采用 sign-reversed rule
`target_flip = -sign(spread_dollar)` 作为 carry 的 **adopted candidate
signal**。这不是 §6 禁止的 long-only / threshold / cross-section /
inverse-vol / h 变体，而是一个新的、固定的方向假设；官方 A v2 结果不变。

Gross 信息检验（默认参数；详见 notebook 10 §7；0.5x equal-notional）：

| Period | Ann. ret | Sharpe | NW t | 80% MDE Sharpe |
|---|---:|---:|---:|---:|
| full 1986–2026 | +0.631% | 0.633 | 4.286 | 0.434 |
| train 1986–2015 | +0.694% | 0.672 | 4.056 | 0.507 |
| test 2016–2026 | +0.455% | 0.512 | 1.580 | 0.843 |

- 5-day IC（`score_flip = -carry_ann`, `fwd_1_6`）：ALL full 0.048 /
  train 0.045 / test 0.071；per-root bootstrap p<0.05 的个数
  11/24、10/24、8/24。
- 分箱：Q5（contango long）最强（full/test/train +4.88/+5.21/+3.87 bp）；
  Q1（backwardation short）在 full/train 为负，在 test 为正（+2.42 bp），
  即 short leg 在 test 是拖累。
- Timing：t+1 fill full +0.631%/yr（Sharpe 0.633），same-settle full
  +0.706%/yr（Sharpe 0.744）；edge 没有在 t+1 后消失。

**Verdict:** full/train 的 gross 信息为正且显著；test 方向为正但统计上不
显著（80% MDE Sharpe 0.843 > 观测 0.512），所以是 **suggestive, not
confirmed**。不声称 test-period alpha；§7 不含成本；不做 test tuning。

**Final status for the original direction: closed negative**（§1–§6 不变）。
The flip is a separately adopted candidate signal, not a continuation of A.
