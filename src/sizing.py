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

LEG_COLUMNS = [
    "date", "root", "group_id", "contract", "units", "budget", "target",
    "resize_key",
]


def smooth_target(signal: pd.DataFrame, k: int) -> pd.DataFrame:
    """Average the last ``k`` targets per root (trade 1/k of the book daily).

    This is the overlapping-portfolio construction of Jegadeesh and Titman
    (1993): k sleeves, each formed on one day and held k days, applied to the
    pair that is current today.

    Args:
        signal: ``date, root, target`` (one row per root-date); extra
            columns such as ``hedge_ratio`` are preserved.
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
        signal: ``date, root, target``; target in [-1, 1]. An optional
            ``hedge_ratio`` column replaces the default leg ratio; invalid
            or non-positive values force an explicit flat row.
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

    has_hedge = "hedge_ratio" in signal.columns
    sig = smooth_target(signal.copy(), k)
    keep = ["date", "root", "contract_near", "contract_far", "settle_near", "settle_far"]
    keep += [c for c in ("spread_vol", "liquid", "dollar_adv") if c in pairs.columns]
    f = pairs[keep].merge(sig, on=["date", "root"], how="inner")
    f = f.loc[f["target"].notna()].copy()
    if "liquid" in f.columns:
        f.loc[~f["liquid"].astype(bool), "target"] = 0.0
    if has_hedge:
        h = pd.to_numeric(f["hedge_ratio"], errors="coerce")
        f.loc[~np.isfinite(h) | h.le(0), "target"] = 0.0
    f["budget"] = (_budget(f, scheme, n_mode, alpha) * f["target"].abs()).fillna(0.0)
    flat = f.loc[f["target"].eq(0)].assign(
        group_id="flat", contract=np.nan, units=0.0, budget=0.0, resize_key=""
    )
    f = f.loc[f["budget"].gt(0) & f["settle_near"].gt(0) & f["settle_far"].gt(0)].copy()
    if has_hedge:
        ratio = pd.to_numeric(f["hedge_ratio"], errors="coerce")
        resize_key = "_h" + ratio.round(6).astype(str)
    else:
        ratio = f["settle_near"] / f["settle_far"] if leg_ratio == "notional" else 1.0
        resize_key = ""
    f = f.assign(
        group_id=f["root"] + "_" + f["contract_near"] + "_" + f["contract_far"],
        resize_key=resize_key,
    )
    sign = np.sign(f["target"])
    near = f.assign(contract=f["contract_near"], units=sign)
    far = f.assign(contract=f["contract_far"], units=-sign * ratio)
    out = pd.concat([near, far, flat], ignore_index=True)[LEG_COLUMNS]
    return out.sort_values(["date", "root", "contract"]).reset_index(drop=True)


def legs_from_rows(
    legs: pd.DataFrame,
    budget: float | pd.Series | pd.DataFrame,
) -> pd.DataFrame:
    """Map explicit leg rows to ``LEG_COLUMNS`` for ``simulate``.

    Args:
        legs: ``date, root, contract, units, target``; optional ``group_id``
            and ``resize_key``. A ``group_id="flat"`` row is an explicit exit.
        budget: gross-notional fraction of capital per ``(date, root)``
            group: scalar, Series indexed by ``(date, root)``, or DataFrame
            with ``date, root, budget``.

    Returns:
        ``LEG_COLUMNS`` with at most one non-flat group per ``(date, root)``.
        ``resize_key`` defaults to the sorted contract/units composition so a
        leg-set change triggers a resize even when the target is unchanged.
    """

    required = {"date", "root", "contract", "units", "target"}
    missing = required.difference(legs.columns)
    if missing:
        raise ValueError(f"legs missing columns: {sorted(missing)}")
    out = legs.copy()
    out["date"] = pd.to_datetime(out["date"])
    missing_group = "group_id" not in out.columns
    if missing_group:
        out["group_id"] = ""
    else:
        out["group_id"] = out["group_id"].fillna("").astype(str)
    flat = out["group_id"].eq("flat")
    flat_rows = out.loc[flat].copy()
    active = out.loc[~flat].copy()
    if active.empty and flat_rows.empty:
        return pd.DataFrame(columns=LEG_COLUMNS)

    if not active.empty:
        if active["contract"].isna().any():
            raise ValueError("active leg rows must have a non-null contract")
        if active["target"].isna().any():
            raise ValueError("active leg rows must have a target")
        if missing_group or active["group_id"].eq("").all():
            labels = (
                active.assign(_c=active["contract"].astype(str))
                .groupby(["date", "root"])["_c"]
                .agg("|".join)
                .rename("group_id")
                .reset_index()
            )
            active = active.drop(columns="group_id").merge(
                labels, on=["date", "root"], how="left"
            )
        elif active["group_id"].eq("").any():
            raise ValueError("group_id must be supplied for all active rows or none")
        active["contract"] = active["contract"].astype(str)
        active = active.sort_values(["date", "root", "group_id", "contract"])
        agg = {"units": ("units", "sum"), "target": ("target", "first")}
        if "resize_key" in active.columns:
            agg["resize_key"] = ("resize_key", "first")
        active = (
            active.groupby(["date", "root", "group_id", "contract"], as_index=False)
            .agg(**agg)
        )
        active = active.loc[active["units"].ne(0)].copy()
        if active.empty:
            return pd.DataFrame(columns=LEG_COLUMNS)
        n_groups = active.groupby(["date", "root"])["group_id"].nunique()
        if (n_groups > 1).any():
            bad = n_groups[n_groups > 1].index[0]
            raise ValueError(
                "multiple non-flat leg groups on the same (date, root): "
                f"{bad}; net them in the adapter"
            )

        if isinstance(budget, (int, float, np.integer, np.floating)):
            active["budget"] = float(budget)
        elif isinstance(budget, pd.DataFrame):
            b = budget.copy()
            b["date"] = pd.to_datetime(b["date"])
            if not {"date", "root", "budget"}.issubset(b.columns):
                raise ValueError("budget frame needs date, root, budget")
            active = active.merge(
                b[["date", "root", "budget"]], on=["date", "root"], how="left"
            )
        else:
            idx = pd.MultiIndex.from_frame(active[["date", "root"]])
            active["budget"] = np.asarray(pd.Series(budget).reindex(idx))
        if active["budget"].isna().any():
            raise ValueError("budget missing for some (date, root) groups")

        comp = (
            active.assign(
                _leg=active["contract"] + ":" + active["units"].round(6).astype(str)
            )
            .groupby(["date", "root", "group_id"])["_leg"]
            .agg("|".join)
            .rename("_composition")
            .reset_index()
        )
        active = active.merge(comp, on=["date", "root", "group_id"], how="left")
        if "resize_key" in active.columns:
            active["resize_key"] = (
                active["resize_key"].fillna(active["_composition"]).astype(str)
            )
        else:
            active["resize_key"] = active["_composition"]
        active["units"] = active["units"].astype(float)
        active["budget"] = active["budget"].astype(float)
        active["target"] = active["target"].astype(float)

    if not flat_rows.empty:
        if flat_rows.duplicated(["date", "root"]).any():
            raise ValueError("duplicate flat rows on the same (date, root)")
        if not active.empty:
            flat_keys = set(zip(flat_rows["date"], flat_rows["root"]))
            active_keys = set(zip(active["date"], active["root"]))
            if flat_keys & active_keys:
                raise ValueError(
                    "mixed flat and active leg rows on the same (date, root)"
                )
        flat_rows = flat_rows.assign(
            group_id="flat", contract=np.nan, units=0.0,
            budget=0.0, target=0.0, resize_key="",
        )

    frames = [df for df in (active, flat_rows) if not df.empty]
    out = pd.concat(frames, ignore_index=True)[LEG_COLUMNS]
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
