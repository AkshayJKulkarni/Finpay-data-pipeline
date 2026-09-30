from pathlib import Path

import pandas as pd


def profile_dataset():
	"""Read the raw CSV and print a human-readable profiling report."""
	# Build the input path from this file so the script works from the project root.
	project_root = Path(__file__).resolve().parent.parent
	csv_path = project_root / "data" / "raw" / "SFinDSet.csv"

	# Load the original data for inspection only; no values are written back.
	try:
		dataset = pd.read_csv(csv_path)
	except FileNotFoundError:
		print(f"Error: dataset not found at {csv_path}")
		return
	except (pd.errors.ParserError, OSError, UnicodeDecodeError) as error:
		print(f"Error: could not read the dataset: {error}")
		return

	print("FINPAY DATASET PROFILE")
	print("=" * 60)

	# Show the size and names of the fields in the raw dataset.
	print("\nDataset shape:")
	print(f"Rows: {dataset.shape[0]:,} | Columns: {dataset.shape[1]:,}")

	print("\nColumn names:")
	for column in dataset.columns:
		print(f"- {column}")

	# Show the types pandas inferred when reading the CSV.
	print("\nData types:")
	print(dataset.dtypes.to_string())

	# Report missing values without changing or filling any data.
	print("\nMissing values by column:")
	missing_counts = dataset.isna().sum()
	if len(dataset) == 0:
		missing_percentages = missing_counts * 0
	else:
		missing_percentages = missing_counts / len(dataset) * 100
	for column in dataset.columns:
		print(
			f"- {column}: {missing_counts[column]:,} "
			f"({missing_percentages[column]:.2f}%)"
		)

	# Count duplicate rows and repeated, non-missing transaction IDs.
	print("\nDuplicate checks:")
	print(f"Completely duplicated rows: {dataset.duplicated().sum():,}")
	if "Transaction_ID" in dataset.columns:
		duplicate_ids = dataset["Transaction_ID"].dropna().duplicated().sum()
		print(f"Duplicated Transaction_ID values: {duplicate_ids:,}")
	else:
		print("Duplicated Transaction_ID values: column not found")

	# Count distinct non-missing values in each column.
	print("\nUnique values by column (excluding missing values):")
	for column in dataset.columns:
		print(f"- {column}: {dataset[column].nunique(dropna=True):,}")

	# Display standard summary statistics for columns pandas recognizes as numeric.
	print("\nBasic numerical statistics:")
	numerical_columns = dataset.select_dtypes(include="number")
	if numerical_columns.empty:
		print("No numerical columns found.")
	else:
		print(numerical_columns.describe().to_string())

	# Parse dates for reporting only; invalid values become missing in this temporary Series.
	print("\nTransaction_Date range:")
	if "Transaction_Date" not in dataset.columns:
		print("Transaction_Date column not found.")
	else:
		parsed_dates = pd.to_datetime(
			dataset["Transaction_Date"], format="mixed", errors="coerce"
		)
		valid_dates = parsed_dates.dropna()
		if valid_dates.empty:
			print("No Transaction_Date values could be parsed.")
		else:
			print(f"Minimum: {valid_dates.min()}")
			print(f"Maximum: {valid_dates.max()}")
			invalid_count = parsed_dates.isna().sum()
			if invalid_count:
				print(f"Unparseable or missing dates: {invalid_count:,}")

	# Summarize the transaction amount after safely converting values for calculation.
	print("\nTransaction_Amount summary:")
	if "Transaction_Amount" not in dataset.columns:
		print("Transaction_Amount column not found.")
	else:
		amounts = pd.to_numeric(dataset["Transaction_Amount"], errors="coerce").dropna()
		if amounts.empty:
			print("No Transaction_Amount values could be interpreted as numbers.")
		else:
			print(f"Minimum: {amounts.min()}")
			print(f"Maximum: {amounts.max()}")
			print(f"Mean: {amounts.mean()}")
			print(f"Median: {amounts.median()}")

	# Show distributions for categorical fields, including the requested transaction fields.
	print("\nCategorical value counts:")
	requested_categories = [
		"Transaction_Mode",
		"Transaction_Type",
		"Transaction_Source",
	]
	inferred_categories = dataset.select_dtypes(include=["object", "category"]).columns
	category_columns = list(dict.fromkeys(requested_categories + list(inferred_categories)))
	available_categories = [column for column in category_columns if column in dataset.columns]
	if not available_categories:
		print("No categorical columns found.")
	else:
		for column in available_categories:
			unique_count = dataset[column].nunique(dropna=True)
			if unique_count > 50:
				print(f"\n{column}: skipped detailed counts ({unique_count:,} unique values)")
				continue
			print(f"\n{column}:")
			print(dataset[column].value_counts(dropna=False).to_string())


if __name__ == "__main__":
	profile_dataset()
