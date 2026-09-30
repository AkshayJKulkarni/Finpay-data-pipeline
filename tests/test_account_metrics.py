from pyspark.sql import SparkSession

from spark.account_metrics import build_account_daily_metrics


def create_spark():
    return (
        SparkSession.builder
        .master("local[2]")
        .appName("FinPayTests")
        .getOrCreate()
    )


def test_account_daily_aggregation():
    spark = create_spark()

    try:
        transactions = spark.createDataFrame(
            [
                (1001, "2024-01-01", "TX001", 100.0),
                (1001, "2024-01-01", "TX002", 300.0),
                (1001, "2024-01-02", "TX003", 500.0),
                (1002, "2024-01-01", "TX004", 200.0),
            ],
            [
                "Account_Number",
                "Transaction_Date",
                "Transaction_ID",
                "Transaction_Amount",
            ],
        )

        result = build_account_daily_metrics(transactions)

        rows = result.collect()

        assert len(rows) == 3

        first_day = next(
            row for row in rows
            if row["Account_Number"] == 1001
            and str(row["transaction_date"]) == "2024-01-01"
        )

        assert first_day["transaction_count"] == 2
        assert first_day["total_amount"] == 400.0
        assert first_day["average_amount"] == 200.0
        assert first_day["minimum_amount"] == 100.0
        assert first_day["maximum_amount"] == 300.0

    finally:
        spark.stop()