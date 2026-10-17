from datetime import date
from pathlib import Path

import pandas as pd

from src.load import (
    ContractId,
    build_rank_panel,
    normalize_contract_code,
    parse_contract_code,
    parse_ticker,
    read_commodity_metadata,
    read_raw_wide,
)

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_wide.csv"


def test_parse_ticker():
    assert parse_ticker("CL1 Comdty") == ("CL", 1)
    assert parse_ticker("C 1 Comdty") == ("C", 1)
    assert parse_ticker("S 4 Comdty") == ("S", 4)
    assert parse_ticker("XB2 Comdty") == ("XB", 2)


def test_normalize_contract_code():
    assert normalize_contract_code("C H86") == "CH86"
    assert normalize_contract_code(" clg86 ") == "CLG86"
    assert normalize_contract_code(".NA.") is None
    assert normalize_contract_code("") is None
    assert normalize_contract_code(None) is None


def test_parse_contract_code():
    assert parse_contract_code("CLG86", "CL") == ContractId(1986, 2)
    assert parse_contract_code("C H86", "C") == ContractId(1986, 3)
    assert parse_contract_code("COU88", "CO") == ContractId(1988, 9)
    assert parse_contract_code("CCZ6", "CC") == ContractId(2026, 12)
    assert parse_contract_code("CLX6", "CL", date(2026, 10, 13)) == ContractId(2026, 11)
    assert parse_contract_code("LBK3", "LB", date(2023, 1, 12)) == ContractId(2023, 5)
    assert parse_contract_code("CLG", "CL") is None
    assert parse_contract_code("CLG86", "CO") is None
    assert parse_contract_code(".NA.", "CL") is None


def test_read_raw_wide_fixture():
    raw = read_raw_wide(FIXTURE, expected_tickers=8)
    assert len(raw.tickers) == 8
    assert len(raw.fields) == 32
    assert raw.data.shape == (13, 33)
    assert raw.tickers[0] == "CL1 Comdty"
    assert raw.tickers[4] == "C 1 Comdty"


def test_build_rank_panel_fixture():
    raw = read_raw_wide(FIXTURE, expected_tickers=8)
    metadata = read_commodity_metadata()
    panel = build_rank_panel(raw, metadata)

    # 2 commodities x 4 ranks x 12 non-holiday dates.
    assert panel.shape[0] == 96
    assert panel.date.nunique() == 12
    assert pd.Timestamp("2020-01-20") not in set(panel.date)
    assert set(panel.root.unique()) == {"C", "CL"}
    assert panel.parse_failed.sum() == 0
    assert panel.code_missing.sum() == 1
    assert panel.negative_price.sum() == 1
    assert panel.is_roll.sum() == 8

    roll_date = panel.loc[panel.is_roll, "date"].unique()
    assert len(roll_date) == 1
    assert pd.Timestamp(roll_date[0]) == pd.Timestamp("2020-01-09")
    assert panel.loc[panel.date.eq(roll_date[0])].groupby("root")["is_roll"].sum().eq(4).all()

    # Contract codes are unique across ranks on any date.
    duplicates = (
        panel.dropna(subset=["contract_code"])
        .groupby(["date", "root", "contract_code"])
        .size()
    )
    assert duplicates.max() == 1
