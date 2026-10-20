"""Turn a per-root spread signal into leg-level targets for ``simulate``.

A leg target row is ``date, root, group_id, contract, units, budget, target``.
``units`` fixes the contract ratio between legs (sign = direction), ``budget``
is the group's gross notional as a fraction of capital. The simulator scales
units so that sum(|units| x price x point value) equals budget x capital at the
fill price.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LEG_COLUMNS = ["date", "root", "group_id", "contract", "units", "budget", "target"]


def smooth_target(signal: pd.DataFrame, k: int) -> pd.DataFrame:
    """Average the last ``k`` targets per root (trade 1/k of the book daily).

    This is the overlapping-portfolio construction of Jegadeesh and Titman
    (1993): k sleeves, each formed on one day and held k days, applied to the
    pair that is current today.

    Args:
        signal: ``date, root, target`` (one row per root-date).
        k: Number of overlapping sleeves; ``k=1`` returns the input.

    Returns:
        Copy of ``signal`` with ``target`` replaced by its trailing k-row mean.
    """

    out = signal.sort_values(["root", "date"]).copy()
    if k > 1:
        out["target"] = out.groupby("root")["target"].transform(
            lambda s: s.fillna(0.0).rolling(k, min_periods=1).mean()
        )
    return out.reset_index(drop=True)


def spread_return_vol(pairs: pd.DataFrame, marks: pd.DataFrame, window: int = 60) -> pd.Series:
    """Trailing volatility of the fixed-pair spread return, per pair-date row.

    The daily spread return is 0.5 x (r_near - r_far) with contract-level
    returns, so it never differences across a roll. Lagged one day.
    """

    r = marks.set_index(["root", "contract_code", "date"])["ret"]
    near = r.reindex(pd.MultiIndex.from_arrays([pairs["root"], pairs["contract_near"], pairs["date"]]))
    far = r.reindex(pd.MultiIndex.from_arrays([pairs["root"], pairs["contract_far"], pairs["date"]]))
    spread_ret = pd.Series(0.5 * (near.to_numpy() - far.to_numpy()), index=pairs.index)
    vol = spread_ret.groupby(pairs["root"]).transform(
        lambda s: s.rolling(window, min_periods=20).std().shift()
    )
    return vol


def _stable_total(values: pd.Series, dates: pd.Series, window: int) -> pd.Series:
    """Per-date total, replaced by its trailing ``window``-day maximum.

    On exchange holidays only a few markets trade (e.g. ICE Brent on US
    holidays); a raw daily 1/N would hand them the whole book for one day.
    """

    total = values.groupby(dates).sum().sort_index()
    stable = total.rolling(window, min_periods=1).max()
    return dates.map(stable)


def _budget(frame: pd.DataFrame, scheme: str, n_mode: str, alpha: float = 0.5, window: int = 5) -> pd.Series:
    """Gross-notional budget per root-date before scaling by |target|.

    ``equal``: 1/N. ``inverse_vol``: proportional to 1 / spread vol.
    ``liquidity``: proportional to dollar_ADV ** alpha (thinner leg, lagged),
    so thin markets get a smaller book; alpha = 1 equalises participation
    across roots, alpha = 0 is equal weight.
    """

    active = frame["target"].ne(0)
    pool = active if n_mode == "active" else frame["contract_near"].notna()
    if scheme == "equal":
        return (1.0 / _stable_total(pool.astype(float), frame["date"], window)).where(pool)
    if scheme == "inverse_vol":
        inv = (1.0 / frame["spread_vol"]).where(pool & (frame["spread_vol"] > 0))
        return inv / _stable_total(inv.fillna(0.0), frame["date"], window)
    if scheme == "liquidity":
        liq = (frame["dollar_adv"] ** alpha).where(pool & (frame["dollar_adv"] > 0))
        return liq / _stable_total(liq.fillna(0.0), frame["date"], window)
    raise ValueError(f"Unknown budget scheme: {scheme!r}")


def legs_from_signal(
    signal: pd.DataFrame,
    pairs: pd.DataFrame,
    scheme: str = "equal",
    leg_ratio: str = "notional",
    n_mode: str = "active",
    k: int = 1,
    alpha: float = 0.5,
) -> pd.DataFrame:
    """Map a spread signal (+1 long near / short far) to leg targets.

    Args:
        signal: ``date, root, target``; target in [-1, 1].
        pairs: Pair panel with ``contract_near/far, settle_near/far``; must
            also carry ``spread_vol`` when ``scheme="inverse_vol"``.
        scheme: ``"equal"`` (1/N per root, default), ``"inverse_vol"`` or
            ``"liquidity"`` (dollar ADV ** alpha; needs ``dollar_adv`` from
            ``attach_leg_liquidity``).
        leg_ratio: ``"notional"`` (equal notional legs, as in the papers) or
            ``"contracts"`` (1:1 contracts).
        n_mode: N counts ``"active"`` roots (non-zero target) or
            ``"available"`` roots (any valid pair) on the date.
        k: Overlapping sleeves passed to ``smooth_target``.
        alpha: Exponent of dollar ADV for ``scheme="liquidity"``.

    Returns:
        Leg target table with ``LEG_COLUMNS``. A zero target becomes one
        explicit flat row (``contract`` NaN, ``budget`` 0) so the simulator
        can tell "go flat" from "no signal today" (no row: keep holdings).
    """

    sig = smooth_target(signal[["date", "root", "target"]], k)
    keep = ["date", "root", "contract_near", "contract_far", "settle_near", "settle_far"]
    keep += [c for c in ("spread_vol", "liquid", "dollar_adv") if c in pairs.columns]
    f = pairs[keep].merge(sig, on=["date", "root"], how="inner")
    f = f.loc[f["target"].notna()].copy()
    if "liquid" in f.columns:
        f.loc[~f["liquid"].astype(bool), "target"] = 0.0
    f["budget"] = (_budget(f, scheme, n_mode, alpha) * f["target"].abs()).fillna(0.0)
    flat = f.loc[f["target"].eq(0)].assign(group_id="flat", contract=np.nan, units=0.0, budget=0.0)
    f = f.loc[f["budget"].gt(0) & f["settle_near"].gt(0) & f["settle_far"].gt(0)]
    ratio = f["settle_near"] / f["settle_far"] if leg_ratio == "notional" else 1.0
    f = f.assign(group_id=f["root"] + "_" + f["contract_near"] + "_" + f["contract_far"])
    sign = np.sign(f["target"])
    near = f.assign(contract=f["contract_near"], units=sign)
    far = f.assign(contract=f["contract_far"], units=-sign * ratio)
    out = pd.concat([near, far, flat], ignore_index=True)[LEG_COLUMNS]
    return out.sort_values(["date", "root", "contract"]).reset_index(drop=True)


def attach_leg_liquidity(pairs: pd.DataFrame, marks: pd.DataFrame) -> pd.DataFrame:
    """Add lagged leg ADV (contracts) and the thinner leg's dollar ADV.

    ``dollar_adv = min over legs of ADV x settle x point value`` (USD/day).
    """

    adv = marks.set_index(["root", "contract_code", "date"])["adv"]
    pv = marks.groupby("root")["point_value"].first()
    out = pairs.copy()
    dollar = []
    for leg in ("near", "far"):
        idx = pd.MultiIndex.from_arrays([out["root"], out[f"contract_{leg}"], out["date"]])
        out[f"adv_{leg}"] = adv.reindex(idx).to_numpy()
        dollar.append(out[f"adv_{leg}"] * out[f"settle_{leg}"].abs() * out["root"].map(pv))
    out["dollar_adv"] = np.minimum(dollar[0], dollar[1])
    return out


def filter_liquid(pairs: pd.DataFrame, min_adv: float) -> pd.DataFrame:
    """Flag pair-dates whose thinner leg has lagged ADV >= ``min_adv`` contracts.

    ADV is the trailing mean volume known before the date (ex ante), so the
    filter does not look ahead. Rows are kept and flagged in ``liquid``:
    ``legs_from_signal`` turns an illiquid date into an explicit flat target
    (exit), while missing rows would mean "no signal, keep holdings".
    Requires ``attach_leg_liquidity`` first.
    """

    out = pairs.copy()
    out["liquid"] = out[["adv_near", "adv_far"]].min(axis=1).ge(min_adv)
    return out
