from pathlib import Path

import pandas as pd


COMPARISON_COLUMNS = [
	"Account_Number",
	"Account_Name",
	"Transaction_Amount",
	"Transaction_Mode",
	"Transaction_Type",
	"Transaction_Date",
	"Transaction_Source",
	"Transaction_Destination",
]
SAMPLE_PATTERNS = 3
SAMPLES_PER_PATTERN = 2


def analyze_duplicate_conflicts():
	"""Summarize field conflicts within repeated Transaction_ID pairs."""
	# Resolve the raw CSV path relative to the project, not the current directory.
	project_root = Path(__file__).resolve().parent.parent
	csv_path = project_root / "data" / "raw" / "SFinDSet.csv"

	# Read the source file for analysis only; this script never writes data.
	try:
		dataset = pd.read_csv(csv_path)
	except FileNotFoundError:
		print(f"Error: dataset not found at {csv_path}")
		return
	except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError, UnicodeDecodeError) as error:
		print(f"Error: could not read the dataset: {error}")
		return

	print("FINPAY DUPLICATE-ID CONFLICT ANALYSIS")
	print("=" * 60)

	# Confirm that the key and all requested comparison fields are available.
	required_columns = ["Transaction_ID", *COMPARISON_COLUMNS]
	missing_columns = [column for column in required_columns if column not in dataset.columns]
	if missing_columns:
		print("Error: required columns not found: " + ", ".join(missing_columns))
		return

	# Keep only IDs with exactly two non-missing-key records.
	id_counts = dataset["Transaction_ID"].value_counts(dropna=True)
	paired_ids = id_counts[id_counts == 2].index
	paired_rows = dataset[dataset["Transaction_ID"].isin(paired_ids)]

	# Compare each pair across all columns to identify exact duplicate records.
	all_columns = list(dataset.columns)
	pair_uniqueness = paired_rows.groupby("Transaction_ID", sort=False)[
		all_columns
	].nunique(dropna=False)
	identical_pair_mask = pair_uniqueness.eq(1).all(axis=1)
	identical_pair_count = int(identical_pair_mask.sum())
	conflict_ids = identical_pair_mask.index[~identical_pair_mask]

	print(f"Transaction_ID pairs occurring exactly twice: {len(paired_ids):,}")
	print(f"Completely identical pairs excluded: {identical_pair_count:,}")
	print(f"Conflicting pairs analyzed: {len(conflict_ids):,}")

	if len(conflict_ids) == 0:
		print("\nNo conflicting duplicate pairs found.")
		return

	# Compare the requested fields within each remaining pair.
	conflict_rows = paired_rows[paired_rows["Transaction_ID"].isin(conflict_ids)]
	field_uniqueness = conflict_rows.groupby("Transaction_ID", sort=False)[
		COMPARISON_COLUMNS
	].nunique(dropna=False)
	field_differs = field_uniqueness.gt(1)
	conflicting_pair_count = len(field_differs)

	print("\nField differences among conflicting pairs:")
	for column in COMPARISON_COLUMNS:
		differing_pairs = int(field_differs[column].sum())
		percentage = differing_pairs / conflicting_pair_count * 100
		print(f"- {column}: {differing_pairs:,} pairs ({percentage:.2f}%)")

	# Group IDs by the exact set of comparison fields that differ in each pair.
	patterns = field_differs.apply(
		lambda row: tuple(column for column in COMPARISON_COLUMNS if row[column]),
		axis=1,
	)
	pattern_counts = patterns.value_counts()
	print("\nMost common differing-field combinations:")
	for pattern, pair_count in pattern_counts.head(10).items():
		percentage = pair_count / conflicting_pair_count * 100
		if len(pattern) == 1:
			pattern_label = f"only {pattern[0]} differs"
		elif len(pattern) == 2:
			pattern_label = " + ".join(pattern) + " differ"
		else:
			pattern_label = f"{len(pattern)} fields differ: " + ", ".join(pattern)
		print(f"- {pattern_label}: {pair_count:,} pairs ({percentage:.2f}%)")

	# Show representative records for the most frequent difference patterns.
	print("\nRepresentative samples for major conflict patterns:")
	sample_patterns = pattern_counts.head(SAMPLE_PATTERNS).index
	for pattern in sample_patterns:
		pattern_ids = patterns[patterns == pattern].head(SAMPLES_PER_PATTERN).index
		pattern_label = " + ".join(pattern)
		print(f"\nPattern: {pattern_label} ({pattern_counts[pattern]:,} pairs)")
		for transaction_id in pattern_ids:
			pair = conflict_rows[conflict_rows["Transaction_ID"] == transaction_id]
			print(f"Transaction_ID: {transaction_id}")
			print(pair[["Transaction_ID", *COMPARISON_COLUMNS]].to_string(index=False))


if __name__ == "__main__":
	analyze_duplicate_conflicts()