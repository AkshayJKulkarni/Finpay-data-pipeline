from pathlib import Path
import shutil
import sys
import tempfile

import pandas as pd


REQUIRED_COLUMNS = [
	"Transaction_ID",
	"Account_Number",
	"Account_Name",
	"Transaction_Amount",
	"Transaction_Mode",
	"Transaction_Type",
	"Transaction_Date",
	"Transaction_Source",
	"Transaction_Destination",
]


def load_raw_transactions(csv_path):
	"""Load the source CSV and verify the columns required by this stage."""
	if not csv_path.exists():
		raise FileNotFoundError(f"Raw dataset not found: {csv_path}")

	transactions = pd.read_csv(csv_path)
	missing_columns = [
		column for column in REQUIRED_COLUMNS if column not in transactions.columns
	]
	if missing_columns:
		raise ValueError("Missing required columns: " + ", ".join(missing_columns))
	return transactions


def prepare_transactions(raw_transactions):
	"""Parse dates, add year, remove exact duplicate copies, and find conflicts."""
	raw_row_count = len(raw_transactions)

	# Detect exact duplicate rows before parsing dates changes any source values.
	exact_duplicate_mask = raw_transactions.duplicated(
		subset=REQUIRED_COLUMNS, keep="first"
	)
	exact_duplicate_rows_removed = int(exact_duplicate_mask.sum())
	transactions = raw_transactions.loc[~exact_duplicate_mask].copy()

	# Parse mixed date formats for the processed data and refuse invalid partition dates.
	transactions["Transaction_Date"] = pd.to_datetime(
		transactions["Transaction_Date"], format="mixed", errors="coerce"
	)
	invalid_dates = int(transactions["Transaction_Date"].isna().sum())
	if invalid_dates:
		raise ValueError(
			f"Cannot process {invalid_dates:,} missing or unparseable Transaction_Date values."
		)
	transactions["transaction_year"] = transactions["Transaction_Date"].dt.year

	# Select IDs with exactly two rows whose destinations differ, and retain both rows.
	id_counts = transactions["Transaction_ID"].value_counts(dropna=True)
	twice_used_ids = id_counts[id_counts == 2].index
	paired_rows = transactions[
		transactions["Transaction_ID"].isin(twice_used_ids)
	]
	destination_counts = paired_rows.groupby("Transaction_ID", sort=False)[
		"Transaction_Destination"
	].nunique(dropna=False)
	conflicting_ids = destination_counts[destination_counts > 1].index
	conflict_mask = transactions["Transaction_ID"].isin(conflicting_ids)
	conflict_records = transactions.loc[conflict_mask].copy()

	rows_per_year = {
		int(year): int(row_count)
		for year, row_count in transactions.groupby("transaction_year", sort=True).size().items()
	}

	return {
		"transactions": transactions,
		"conflict_records": conflict_records,
		"raw_row_count": raw_row_count,
		"exact_duplicate_rows_detected": exact_duplicate_rows_removed,
		"exact_duplicate_rows_removed": exact_duplicate_rows_removed,
		"conflicting_transaction_ids": len(conflicting_ids),
		"conflict_rows_quarantined": len(conflict_records),
		"final_processed_row_count": len(transactions),
		"rows_per_year": rows_per_year,
	}


def write_parquet_outputs(processing_result, processed_dir):
	"""Write staged Parquet outputs and replace previous run outputs on success."""
	processed_dir.mkdir(parents=True, exist_ok=True)
	quality_dir = processed_dir / "quality_exceptions"
	transactions_path = processed_dir / "transactions"
	conflicts_path = quality_dir / "duplicate_transaction_id_conflicts.parquet"

	# Stage on the same filesystem so final replacements do not append old partitions.
	staging_dir = Path(tempfile.mkdtemp(prefix=".process_transactions_", dir=processed_dir))
	staged_transactions = staging_dir / "transactions"
	staged_conflicts = staging_dir / "duplicate_transaction_id_conflicts.parquet"
	backup_transactions = staging_dir / "previous_transactions"
	backup_conflicts = staging_dir / "previous_conflicts.parquet"
	transactions_backed_up = False
	conflicts_backed_up = False
	new_transactions_installed = False
	new_conflicts_installed = False

	try:
		transactions = processing_result["transactions"]
		transactions["Transaction_Date"] = pd.to_datetime(
			transactions["Transaction_Date"]
		).astype("datetime64[us]")
		transactions.to_parquet(
			staged_transactions,
			engine="pyarrow",
			index=False,
			partition_cols=["transaction_year"],
		)
		processing_result["conflict_records"].to_parquet(
			staged_conflicts,
			engine="pyarrow",
			index=False,
		)

		quality_dir.mkdir(parents=True, exist_ok=True)
		if transactions_path.exists():
			transactions_path.replace(backup_transactions)
			transactions_backed_up = True
		if conflicts_path.exists():
			conflicts_path.replace(backup_conflicts)
			conflicts_backed_up = True

		staged_conflicts.replace(conflicts_path)
		new_conflicts_installed = True
		staged_transactions.replace(transactions_path)
		new_transactions_installed = True
	except Exception:
		# Restore the prior complete outputs if either installation step fails.
		if new_transactions_installed and transactions_path.exists():
			shutil.rmtree(transactions_path)
		if new_conflicts_installed and conflicts_path.exists():
			conflicts_path.unlink()
		if transactions_backed_up and backup_transactions.exists():
			backup_transactions.replace(transactions_path)
		if conflicts_backed_up and backup_conflicts.exists():
			backup_conflicts.replace(conflicts_path)
		raise
	finally:
		shutil.rmtree(staging_dir, ignore_errors=True)


def print_processing_summary(result):
	"""Print the row counts and output-year distribution for this run."""
	print("FINPAY TRANSACTION PROCESSING SUMMARY")
	print("=" * 56)
	print(f"Raw row count: {result['raw_row_count']:,}")
	print(f"Exact duplicate rows detected: {result['exact_duplicate_rows_detected']:,}")
	print(f"Exact duplicate rows removed: {result['exact_duplicate_rows_removed']:,}")
	print(f"Conflicting Transaction_ID values: {result['conflicting_transaction_ids']:,}")
	print(f"Conflict rows quarantined: {result['conflict_rows_quarantined']:,}")
	print(f"Final processed row count: {result['final_processed_row_count']:,}")
	print("Rows written per transaction_year:")
	for year, row_count in result["rows_per_year"].items():
		print(f"  {year}: {row_count:,}")


def main():
	"""Run the deterministic raw-to-processed transaction preparation stage."""
	project_root = Path(__file__).resolve().parent.parent
	csv_path = project_root / "data" / "raw" / "SFinDSet.csv"
	processed_dir = project_root / "data" / "processed"

	try:
		raw_transactions = load_raw_transactions(csv_path)
		processing_result = prepare_transactions(raw_transactions)
		write_parquet_outputs(processing_result, processed_dir)
	except (FileNotFoundError, ValueError, OSError, ImportError) as error:
		print(f"Processing failed: {error}")
		return 1
	except Exception as error:
		print(f"Processing failed while writing Parquet outputs: {error}")
		return 1

	print_processing_summary(processing_result)
	print(f"\nTransactions: {processed_dir / 'transactions'}")
	print(
		"Conflict exceptions: "
		f"{processed_dir / 'quality_exceptions' / 'duplicate_transaction_id_conflicts.parquet'}"
	)
	return 0


if __name__ == "__main__":
	sys.exit(main())