import pandas as pd
import pytest

from src.process_transactions import (
    REQUIRED_COLUMNS,
    load_raw_transactions,
    prepare_transactions,
)


def make_transaction(**overrides):
    row = {
        "Transaction_ID": "TX001",
        "Account_Number": 1001,
        "Account_Name": "Test Account",
        "Transaction_Amount": 1000.0,
        "Transaction_Mode": "Online",
        "Transaction_Type": "Debit",
        "Transaction_Date": "2024-01-15",
        "Transaction_Source": 1001,
        "Transaction_Destination": 2001,
    }
    row.update(overrides)
    return row


def test_required_columns_are_present():
    dataframe = pd.DataFrame([make_transaction()])

    assert all(column in dataframe.columns for column in REQUIRED_COLUMNS)


def test_exact_duplicate_rows_are_removed():
    dataframe = pd.DataFrame([
        make_transaction(),
        make_transaction(),
    ])

    result = prepare_transactions(dataframe)

    assert result["exact_duplicate_rows_removed"] == 1
    assert result["final_processed_row_count"] == 1


def test_conflicting_transaction_ids_are_quarantined():
    dataframe = pd.DataFrame([
        make_transaction(
            Transaction_ID="TX100",
            Transaction_Destination=2001,
        ),
        make_transaction(
            Transaction_ID="TX100",
            Transaction_Destination=3001,
        ),
    ])

    result = prepare_transactions(dataframe)

    assert result["conflicting_transaction_ids"] == 1
    assert result["conflict_rows_quarantined"] == 2


def test_transaction_year_is_created():
    dataframe = pd.DataFrame([
        make_transaction(Transaction_Date="2024-02-18")
    ])

    result = prepare_transactions(dataframe)

    assert result["transactions"]["transaction_year"].iloc[0] == 2024


def test_invalid_transaction_date_raises_error():
    dataframe = pd.DataFrame([
        make_transaction(Transaction_Date="not-a-date")
    ])

    with pytest.raises(ValueError, match="Transaction_Date"):
        prepare_transactions(dataframe)


def test_missing_required_column_raises_error(tmp_path):
    dataframe = pd.DataFrame([
        make_transaction()
    ]).drop(columns=["Account_Name"])

    csv_path = tmp_path / "invalid.csv"
    dataframe.to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="Missing required columns"):
        load_raw_transactions(csv_path)