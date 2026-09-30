import ctypes
import os
from pathlib import Path
import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def to_short_path(path: Path) -> str:
	"""Convert a Windows path with spaces to its short (8.3) form for Spark/JVM compatibility."""
	if os.name != "nt":
		return str(path)
	buf = ctypes.create_unicode_buffer(260)
	result = ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, len(buf))
	return buf.value if result else str(path)


def create_spark_session():
	"""Create the Spark application session for account metrics."""
	# PySpark on Windows may look for `python3`; use the short path of this interpreter.
	os.environ.setdefault("PYSPARK_PYTHON", to_short_path(Path(sys.executable)))
	os.environ.setdefault("PYSPARK_DRIVER_PYTHON", to_short_path(Path(sys.executable)))
	return SparkSession.builder.appName("FinPayAccountDailyMetrics").getOrCreate()


def build_account_daily_metrics(transactions):
	"""Aggregate transactions by account and calendar date."""
	# Normalize timestamps to calendar dates so transactions on the same day group together.
	transactions_by_day = transactions.withColumn(
		"transaction_date", F.to_date(F.col("Transaction_Date"))
	)

	# Calculate the daily transaction count and amount summary for each account.
	return transactions_by_day.groupBy("Account_Number", "transaction_date").agg(
		F.count("Transaction_ID").alias("transaction_count"),
		F.sum("Transaction_Amount").alias("total_amount"),
		F.avg("Transaction_Amount").alias("average_amount"),
		F.min("Transaction_Amount").alias("minimum_amount"),
		F.max("Transaction_Amount").alias("maximum_amount"),
	)


def main():
	"""Read processed Parquet, write daily account metrics, and report the result."""
	project_root = Path(__file__).resolve().parent.parent
	input_path = project_root / "data" / "processed" / "transactions"
	output_path = project_root / "data" / "curated" / "account_daily_metrics"
	spark = create_spark_session()

	try:
		# Load the existing partitioned Parquet dataset without changing the input.
		transactions = spark.read.parquet(to_short_path(input_path))
		input_row_count = transactions.count()

		account_daily_metrics = build_account_daily_metrics(transactions)
		output_row_count = account_daily_metrics.count()

		# Ensure the output directory exists before Spark tries to write.
		output_path.mkdir(parents=True, exist_ok=True)

		# Overwrite makes this derived output repeatable instead of appending old results.
		account_daily_metrics.write.mode("overwrite").parquet(to_short_path(output_path))

		print("FINPAY ACCOUNT DAILY METRICS")
		print("=" * 56)
		print(f"Input row count: {input_row_count:,}")
		print(f"Output row count: {output_row_count:,}")
		print("Output schema:")
		account_daily_metrics.printSchema()
		print("Sample records:")
		account_daily_metrics.orderBy(
			"Account_Number", "transaction_date"
		).show(10, truncate=False)
		print(f"\nOutput written to: {output_path}")
	finally:
		# Release Spark resources whether processing succeeds or raises an error.
		spark.stop()


if __name__ == "__main__":
	main()