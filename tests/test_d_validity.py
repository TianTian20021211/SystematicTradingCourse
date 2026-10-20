"""Synthetic tests for idea-D signal-validity diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import d_validity


def _month_ends(start: str = "2010-01-31", periods: int = 120) -> pd.DatetimeIndex:
    return pd.date_range(start, periods=periods, freq="ME")


def _panel(
    roots: tuple[str, ...] = ("SIG",),
    n: int = 120,
    beta: float = 0.5,
    noise: float = 0.05,
    seed: int = 0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = _month_ends(periods=n)
    rows = []
    for root in roots:
        for i, date in enumerate(dates):
            score = rng.normal()
            fwd = beta * score + rng.normal(scale=noise)
            rows.append(
                {
                    "date": date,
                    "root": root,
                    "score": score,
                    "target": np.sign(score),
                    "a_carry": rng.normal(),
                    "c_z": rng.normal(),
                    "spread_vol_6m": 0.1,
                    "fwd_1m": fwd,
                    "fwd_3m": np.nan,
                    "fwd_6m": np.nan,
                    "fwd_12m": np.nan,
                    "fwd_1m_same_close": fwd,
                    "fwd_3m_same_close": np.nan,
                    "fwd_6m_same_close": np.nan,
                    "fwd_12m_same_close": np.nan,
                    "end_1m": date,
                    "end_3m": pd.NaT,
                    "end_6m": pd.NaT,
                    "end_12m": pd.NaT,
                    "end_1m_same_close": date,
                    "end_3m_same_close": pd.NaT,
                    "end_6m_same_close": pd.NaT,
                    "end_12m_same_close": pd.NaT,
                    "static": 1.0,
                }
            )
    return pd.DataFrame(rows)


def _returns_panel(dates: pd.DatetimeIndex, root: str = "X") -> pd.DataFrame:
    rows = []
    for rank, ret in ((1, 0.001), (2, 0.0005)):
        for date in dates:
            rows.append(
                {
                    "date": date,
                    "root": root,
                    "rank": rank,
                    "ret_rank": ret,
                    "negative_price": False,
                }
            )
    return pd.DataFrame(rows)


def _pair_panel(dates: pd.DatetimeIndex, root: str = "X") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": date,
                "root": root,
                "rank_near": 1,
                "rank_far": 2,
                "contract_near": "A",
                "contract_far": "B",
            }
            for date in dates
        ]
    )


def test_forward_rank_returns_t_plus_one_and_missing_endpoint() -> None:
    dates = pd.bdate_range("2020-01-01", "2021-12-31")
    pair = _pair_panel(dates)
    returns = _returns_panel(dates)
    month_ends = pair.groupby(pair["date"].dt.to_period("M"))["date"].max().reset_index(drop=True)
    signal = pd.DataFrame(
        {
            "date": month_ends,
            "root": "X",
            "rank_near": 1,
            "rank_far": 2,
            "score": 0.01,
        }
    )

    out = d_validity.forward_rank_returns(
        signal, pair, returns, horizons=(1, 3), timing="t+1"
    )

    assert {"fwd_1m", "fwd_3m", "fwd_1m_same_close", "end_1m", "end_3m"} <= set(out.columns)
    assert out["fwd_1m"].notna().sum() > 0
    assert (out["fwd_1m"].dropna() > 0).all()
    assert (out["fwd_3m"].dropna() > out["fwd_1m"].dropna().reindex(
        out["fwd_3m"].dropna().index
    )).all()
    # Same-close starts one day earlier, so it must be at least as large.
    both = out[["fwd_1m", "fwd_1m_same_close"]].dropna()
    assert (both["fwd_1m_same_close"] >= both["fwd_1m"]).all()
    # The last signal has no complete next-month endpoint.
    assert pd.isna(out.iloc[-1]["fwd_1m"])


def test_period_panel_requires_endpoint_inside_period() -> None:
    panel = _panel(n=24)
    panel["end_1m"] = panel["date"]
    sl = d_validity.period_panel(
        panel, 1, "2010-01-01", "2010-12-31"
    )
    assert len(sl) == 12
    assert sl["end_1m"].max() <= pd.Timestamp("2010-12-31")


def test_per_root_ic_detects_signal_and_null() -> None:
    panel = _panel(roots=("SIG", "NUL"), beta=0.5, noise=0.03, seed=1)
    # Make NUL independent of its score.
    dates = panel.loc[panel["root"].eq("NUL"), "date"]
    rng = np.random.default_rng(2)
    panel.loc[panel["root"].eq("NUL"), "fwd_1m"] = rng.normal(scale=0.05, size=len(dates))

    table = d_validity.per_root_ic(
        panel, horizon=1, block=3, n_boot=300, min_obs=24, seed=0
    ).set_index("root")

    assert table.loc["SIG", "ic"] > 0.5
    assert table.loc["SIG", "p_value"] < 0.05
    assert table.loc["NUL", "p_value"] > 0.05
    assert table.loc["ALL", "ic"] > 0


def test_hit_rate_and_quantile_monotonicity() -> None:
    panel = _panel(beta=0.5, noise=0.03, seed=3)
    hit = d_validity.hit_rate(
        panel, horizon=1, block=3, n_boot=300, min_obs=24, seed=0
    ).set_index("root")
    bins = d_validity.quantile_profile(panel, horizon=1, min_history=24)

    assert hit.loc["SIG", "hit_rate"] > 0.6
    assert hit.loc["SIG", "p_value"] < 0.05
    assert bins["mean_bps"].iloc[-1] > bins["mean_bps"].iloc[0]


def test_predictive_regression_and_incremental_information() -> None:
    panel = _panel(beta=0.5, noise=0.03, seed=4)
    reg = d_validity.predictive_regression(
        panel, horizon=1, block=3, n_boot=200, min_obs=24, seed=0
    ).set_index("root")
    assert reg.loc["SIG", "beta_score"] > 0
    assert reg.loc["SIG", "r2"] > 0.5

    inc = d_validity.incremental_information(
        panel, horizon=1, block=3, n_boot=200, min_obs=24, seed=0
    )
    per = inc["per_root"].set_index("root")
    assert per.loc["SIG", "adj_+D"] > per.loc["SIG", "adj_static"]
    step = inc["deltas"].loc[
        inc["deltas"]["root"].eq("ALL") & inc["deltas"]["step"].eq("static -> +D")
    ]
    assert step["delta_adj_r2"].iloc[0] > 0
    residual = inc["residual_ic"].set_index("root")
    assert residual.loc["SIG", "ic_residual"] > 0


def test_fdr_bh_known_values() -> None:
    p = np.array([0.01, 0.02, 0.5, 0.9])
    q = d_validity.fdr_bh(p)
    np.testing.assert_allclose(q, [0.04, 0.04, 2 / 3, 0.9])
    # NaN handling.
    q2 = d_validity.fdr_bh(np.array([0.01, np.nan, 0.5]))
    assert np.isnan(q2[1])


def test_placebo_shuffle_null_is_centered() -> None:
    panel = _panel(beta=0.0, noise=0.05, seed=5)
    out = d_validity.placebo(
        panel, horizon=1, n_shuffle=60, block=3, min_obs=24, seed=0
    )
    summary = out["summary"].set_index("test")
    assert abs(summary.loc["actual", "ic_mean"]) < 0.1
    assert summary.loc["block_shuffle", "p_value"] > 0.05
    assert abs(np.mean(out["null_mean"])) < 0.05


def test_stability_groups_and_rolling() -> None:
    panel = _panel(beta=0.5, noise=0.03, seed=6)
    out = d_validity.stability(panel, horizon=1, min_obs=20)
    groups = out["groups"]
    assert {"decade", "carry", "vol"} <= set(groups["group_type"])
    assert groups["n_roots"].gt(0).all()
    assert out["rolling_table"]["n_dates"].iloc[0] > 0


def test_parameter_guards() -> None:
    panel = _panel(n=12)
    with pytest.raises(ValueError):
        d_validity.forward_rank_returns(
            panel, _pair_panel(_month_ends(periods=12)), _returns_panel(_month_ends(periods=12)),
            timing="bad",
        )
