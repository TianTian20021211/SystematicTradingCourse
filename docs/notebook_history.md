# Notebook History

**Status:** current layout after D-020 (2026-10-19).

## 当前 notebook

| Notebook | Idea | 内容 |
|---|---|---|
| `00_data_audit.ipynb` | 数据层 | raw data audit、coverage、roll、流动性诊断 |
| `01_panel_build.ipynb` | 数据层 | 生成 `data/processed/*.parquet` |
| `10_idea_a_carry.ipynb` | A — carry | PnL、持仓、overall Sharpe；closed negative |
| `11_idea_b_adjacent_carry.ipynb` | B — adjacent carry | PnL、持仓、overall Sharpe；pre-registered skip |
| `12_idea_c_mean_reversion.ipynb` | C — mean reversion | 1:1、rolling OLS、Kalman 三个变体；closed mixed/negative |
| `13_idea_d_curve_momentum.ipynb` | D — curve momentum | PnL、持仓、overall Sharpe；documented negative/mixed |

每个 idea notebook 只运行自己的策略，统一展示：

1. full-sample PnL 曲线（gross + 三层成本）
2. 持仓热力图（最近到期腿方向 × 该品种 gross notional / capital）+ 组合总敞口/换手
3. 一个 full-sample all-in net Sharpe

## 已 retired 的 notebook

这些文件在 D-020 中从工作区删除。它们仍完整保存在 git 历史里（含当时的 outputs），没有被重写。

| 旧 notebook | 最后 commit | 原来内容 | 当前替代 |
|---|---|---|---|
| `02_carry.ipynb` | `bd6691b` | A v1 baseline | `10_idea_a_carry.ipynb`；`docs/a_negative_result.md` |
| `03_mean_reversion.ipynb` | `ee3bab9` | C v1 1:1 + rolling OLS | `12_idea_c_mean_reversion.ipynb` |
| `04_a_diagnose.ipynb` | `4c7dee8` | A v1 诊断（side × sector × era、K、成本） | `10_idea_a_carry.ipynb`；`docs/a_negative_result.md` |
| `05_b_pretest.ipynb` | `4c7dee8` | B v1 pre-test | `11_idea_b_adjacent_carry.ipynb`；`docs/b_pretest.md` |
| `06_curve_momentum.ipynb` | `cf94b1f` | D v1 baseline | `13_idea_d_curve_momentum.ipynb` |
| `07_backtest_framework.ipynb` | `3d5019b` | v2 framework demo（只演示 A） | `docs/backtest_framework.md`、`src/` 模块、10–13 |
| `08_v2_rerun.ipynb` | `3d5019b` | 六个策略的 v2 汇总 | 10–13；`output/v2_rerun/comparison.csv`；`docs/v1_v2_comparison.md` |

## 历史恢复

查看某个旧 notebook 的删除记录：

```bash
git log --all --diff-filter=D -- notebooks/02_carry.ipynb
```

恢复到最后一次提交的版本（把 `<commit>` 换成上表或 log 里的 hash）：

```bash
git show <commit>:notebooks/02_carry.ipynb > /tmp/02_carry.ipynb
```

注意：

- 旧 notebook 里的 v1 数字和 v2 不可直接比较；v1 只作历史 baseline。
- 正式结果仍是 v2（D-019）；当前展示以 10–13 为准。
- 不要为了补历史而重新创建旧 notebook；在对应 idea notebook 或 `docs/logs/` 里追加。
