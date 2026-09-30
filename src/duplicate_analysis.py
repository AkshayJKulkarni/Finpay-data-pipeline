from pathlib import Path

import pandas as pd


COMPARISON_COLUMNS = [
	"Transaction_Amount",
	"Account_Number",
	"Account_Name",
	"Transaction_Mode",
	"Transaction_Type",
	"Transaction_Date",
	"Transaction_Source",
	"Transaction_Destination",
]
SAMPLE_GROUP_COUNT = 3


def analyze_duplicate_transactions():
	"""Report repeated Transaction_ID values without changing the raw data."""
	# Resolve the input from the project root, independent of the current directory.
	project_root = Path(__file__).resolve().parent.parent
	csv_path = project_root / "data" / "raw" / "SFinDSet.csv"

	# Read the raw CSV for analysis only; this script never writes to the dataset.
	try:
		dataset = pd.read_csv(csv_path)
	except FileNotFoundError:
		print(f"Error: dataset not found at {csv_path}")
		return
	except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError, UnicodeDecodeError) as error:
		print(f"Error: could not read the dataset: {error}")
		return

	print("FINPAY DUPLICATE TRANSACTION_ID ANALYSIS")
	print("=" * 60)

	# Stop with a clear message if the key needed for this analysis is absent.
	if "Transaction_ID" not in dataset.columns:
		print("Error: required column 'Transaction_ID' was not found.")
		return

	# Count each non-missing ID, then keep only IDs that occur multiple times.
	id_counts = dataset["Transaction_ID"].value_counts(dropna=True)
	duplicated_id_counts = id_counts[id_counts > 1]
	duplicated_row_count = int(duplicated_id_counts.sum())

	print(f"\nDuplicated Transaction_ID values: {len(duplicated_id_counts):,}")
	print(f"Rows belonging to duplicated IDs: {duplicated_row_count:,}")

	# Show how many duplicated IDs occur at each frequency.
	print("\nFrequency distribution:")
	if duplicated_id_counts.empty:
		print("No duplicated Transaction_ID values found.")
	else:
		frequency_distribution = duplicated_id_counts.value_counts().sort_index()
		for occurrence_count, id_count in frequency_distribution.items():
			print(f"IDs occurring {occurrence_count:,} times: {id_count:,}")

	# Compare every repeated-ID group to distinguish exact repeated rows from conflicts.
	if not duplicated_id_counts.empty:
		duplicate_rows = dataset[
			dataset["Transaction_ID"].isin(duplicated_id_counts.index)
		]
		field_value_counts = duplicate_rows.groupby(
			"Transaction_ID", sort=False
		).nunique(dropna=False)
		identical_groups = field_value_counts.eq(1).all(axis=1)
		print("\nFull-record comparison across all duplicated IDs:")
		print(f"IDs with completely identical records: {identical_groups.sum():,}")
		print(f"IDs with one or more differing fields: {(~identical_groups).sum():,}")

	# Inspect a small, repeatable sample, starting with the most frequent duplicate IDs.
	if duplicated_id_counts.empty:
		return

	sample_ids = duplicated_id_counts.sort_values(ascending=False).head(SAMPLE_GROUP_COUNT).index
	sample_records = dataset[dataset["Transaction_ID"].isin(sample_ids)]
	available_comparison_columns = [
		column for column in COMPARISON_COLUMNS if column in dataset.columns
	]
	missing_comparison_columns = [
		column for column in COMPARISON_COLUMNS if column not in dataset.columns
	]

	print(f"\nSample records for {len(sample_ids)} highest-frequency duplicated IDs:")
	for transaction_id in sample_ids:
		group = sample_records[sample_records["Transaction_ID"] == transaction_id]
		print(f"\nTransaction_ID: {transaction_id} ({len(group)} rows)")
		print(group.to_string(index=False))

		# Compare the requested fields, and separately check whether every full row matches.
		varying_columns = [
			column
			for column in available_comparison_columns
			if group[column].nunique(dropna=False) > 1
		]
		all_rows_identical = len(group.drop_duplicates()) == 1
		print(f"Completely identical records: {'Yes' if all_rows_identical else 'No'}")
		if varying_columns:
			print(f"Requested fields that differ: {', '.join(varying_columns)}")
		else:
			print("Requested fields that differ: None")

	if missing_comparison_columns:
		print(
			"\nComparison columns not present in the dataset: "
			+ ", ".join(missing_comparison_columns)
		)


if __name__ == "__main__":
	analyze_duplicate_transactions()