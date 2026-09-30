from pathlib import Path
import sys

import pandas as pd


EXPECTED_COLUMNS = [
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
NUMERIC_COLUMNS = [
	"Account_Number",
	"Transaction_Amount",
	"Transaction_Source",
	"Transaction_Destination",
]


def validate_schema(dataset):
	"""Check that all expected columns are present."""
	missing_columns = [column for column in EXPECTED_COLUMNS if column not in dataset.columns]
	return {
		"passed": not missing_columns,
		"missing_columns": missing_columns,
	}


def validate_missing_values(dataset):
	"""Count missing values in every available column."""
	missing_counts = dataset.isna().sum().to_dict()
	return {
		"passed": not any(missing_counts.values()),
		"counts": missing_counts,
		"total": int(sum(missing_counts.values())),
	}


def validate_numeric_columns(dataset):
	"""Check that non-missing values in the required numeric columns parse as numbers."""
	results = {}
	for column in NUMERIC_COLUMNS:
		if column not in dataset.columns:
			results[column] = {"passed": False, "invalid_count": None}
			continue

		parsed_values = pd.to_numeric(dataset[column], errors="coerce")
		invalid_values = dataset[column].notna() & parsed_values.isna()
		results[column] = {
			"passed": not invalid_values.any(),
			"invalid_count": int(invalid_values.sum()),
		}

	return {
		"passed": all(result["passed"] for result in results.values()),
		"columns": results,
	}


def validate_transaction_dates(dataset):
	"""Parse mixed-format transaction dates for validation without changing the data."""
	if "Transaction_Date" not in dataset.columns:
		return {
			"passed": False,
			"parsed_count": 0,
			"invalid_count": None,
			"invalid_examples": [],
		}

	parsed_dates = pd.to_datetime(
		dataset["Transaction_Date"], format="mixed", errors="coerce"
	)
	invalid_dates = parsed_dates.isna()
	invalid_examples = (
		dataset.loc[invalid_dates, "Transaction_Date"]
		.dropna()
		.astype(str)
		.drop_duplicates()
		.head(5)
		.tolist()
	)
	return {
		"passed": not invalid_dates.any(),
		"parsed_count": int(parsed_dates.notna().sum()),
		"invalid_count": int(invalid_dates.sum()),
		"invalid_examples": invalid_examples,
	}


def validate_transaction_ids(dataset):
	"""Check the required transaction key for null values."""
	if "Transaction_ID" not in dataset.columns:
		return {"passed": False, "invalid_count": None}

	invalid_count = int(dataset["Transaction_ID"].isna().sum())
	return {"passed": invalid_count == 0, "invalid_count": invalid_count}


def validate_transaction_amounts(dataset):
	"""Check that each transaction amount is numeric and greater than zero."""
	if "Transaction_Amount" not in dataset.columns:
		return {
			"passed": False,
			"positive_count": 0,
			"invalid_numeric_count": None,
			"non_positive_count": None,
			"invalid_record_count": None,
		}

	amounts = pd.to_numeric(dataset["Transaction_Amount"], errors="coerce")
	invalid_numeric = dataset["Transaction_Amount"].notna() & amounts.isna()
	non_positive = amounts.notna() & amounts.le(0)
	valid_amounts = amounts.notna() & amounts.gt(0)
	invalid_records = ~valid_amounts
	return {
		"passed": not invalid_records.any(),
		"positive_count": int(valid_amounts.sum()),
		"invalid_numeric_count": int(invalid_numeric.sum()),
		"non_positive_count": int(non_positive.sum()),
		"invalid_record_count": int(invalid_records.sum()),
	}


def analyze_duplicate_ids(dataset):
	"""Separate exact duplicate pairs from conflicting duplicate-key pairs."""
	if "Transaction_ID" not in dataset.columns:
		return {
			"passed": False,
			"duplicated_ids": None,
			"exact_pairs": None,
			"conflict_pairs": None,
			"other_repeated_groups": None,
		}

	id_counts = dataset["Transaction_ID"].value_counts(dropna=True)
	duplicated_id_counts = id_counts[id_counts > 1]
	paired_id_counts = duplicated_id_counts[duplicated_id_counts == 2]
	other_repeated_groups = int((duplicated_id_counts != 2).sum())
	
	if paired_id_counts.empty:
		return {
			"passed": duplicated_id_counts.empty,
			"duplicated_ids": len(duplicated_id_counts),
			"exact_pairs": 0,
			"conflict_pairs": 0,
			"other_repeated_groups": other_repeated_groups,
		}

	duplicate_rows = dataset[
		dataset["Transaction_ID"].isin(paired_id_counts.index)
	]
	field_counts = duplicate_rows.groupby("Transaction_ID", sort=False)[
		list(dataset.columns)
	].nunique(dropna=False)
	identical_pairs = field_counts.eq(1).all(axis=1)
	exact_pairs = int(identical_pairs.sum())
	conflict_pairs = int((~identical_pairs).sum())
	return {
		"passed": duplicated_id_counts.empty,
		"duplicated_ids": len(duplicated_id_counts),
		"exact_pairs": exact_pairs,
		"conflict_pairs": conflict_pairs,
		"other_repeated_groups": other_repeated_groups,
	}


def print_check(label, passed, detail):
	"""Print one consistently formatted validation result."""
	status = "PASS" if passed else "FAIL"
	print(f"{status} | {label}: {detail}")


def print_validation_report(dataset, checks):
	"""Print row totals and the outcome of every validation category."""
	print("FINPAY DATA VALIDATION REPORT")
	print("=" * 64)
	print(f"Rows: {len(dataset):,} | Columns: {len(dataset.columns):,}")

	schema = checks["schema"]
	schema_detail = "all expected columns are present"
	if schema["missing_columns"]:
		schema_detail = "missing: " + ", ".join(schema["missing_columns"])
	print_check("Expected schema", schema["passed"], schema_detail)

	missing = checks["missing"]
	print_check(
		"Missing values",
		missing["passed"],
		f"{missing['total']:,} missing values across all columns",
	)
	for column, count in missing["counts"].items():
		print(f"  {column}: {count:,}")

	numeric = checks["numeric"]
	print_check(
		"Numeric columns",
		numeric["passed"],
		"all required numeric values are interpretable" if numeric["passed"] else "invalid values found",
	)
	for column, result in numeric["columns"].items():
		invalid_count = result["invalid_count"]
		if invalid_count is None:
			detail = "column missing"
		else:
			detail = f"{invalid_count:,} non-numeric values"
		print(f"  {column}: {detail}")

	dates = checks["dates"]
	if dates["invalid_count"] is None:
		date_detail = "Transaction_Date column missing"
	else:
		date_detail = f"{dates['parsed_count']:,} parsed; {dates['invalid_count']:,} invalid"
	print_check("Transaction_Date parsing", dates["passed"], date_detail)
	if dates["invalid_examples"]:
		print("  Unparseable examples: " + ", ".join(dates["invalid_examples"]))

	transaction_ids = checks["transaction_ids"]
	print_check(
		"Transaction_ID not null",
		transaction_ids["passed"],
		f"{transaction_ids['invalid_count']:,} null IDs"
		if transaction_ids["invalid_count"] is not None
		else "column missing",
	)

	amounts = checks["amounts"]
	if amounts["invalid_record_count"] is None:
		amount_detail = "Transaction_Amount column missing"
	else:
		amount_detail = (
			f"{amounts['positive_count']:,} positive; "
			f"{amounts['non_positive_count']:,} zero/negative; "
			f"{amounts['invalid_numeric_count']:,} non-numeric; "
			f"{amounts['invalid_record_count']:,} invalid records"
		)
	print_check("Transaction_Amount > 0", amounts["passed"], amount_detail)

	duplicates = checks["duplicates"]
	if duplicates["duplicated_ids"] is None:
		duplicate_detail = "Transaction_ID column missing"
	else:
		duplicate_detail = (
			f"{duplicates['duplicated_ids']:,} repeated IDs; "
			f"{duplicates['exact_pairs']:,} exact pairs; "
			f"{duplicates['conflict_pairs']:,} conflict pairs; "
			f"{duplicates['other_repeated_groups']:,} repeated groups not occurring twice"
		)
	print_check("Duplicate Transaction_ID analysis", duplicates["passed"], duplicate_detail)
	print("  Exact duplicate and conflicting pairs are reported separately; no rows were removed.")


def run_validation(dataset):
	"""Run each validation check and return results for reuse by orchestration tools."""
	return {
		"schema": validate_schema(dataset),
		"missing": validate_missing_values(dataset),
		"numeric": validate_numeric_columns(dataset),
		"dates": validate_transaction_dates(dataset),
		"transaction_ids": validate_transaction_ids(dataset),
		"amounts": validate_transaction_amounts(dataset),
		"duplicates": analyze_duplicate_ids(dataset),
	}


def main():
	"""Load the raw dataset, print validation results, and return a process status."""
	project_root = Path(__file__).resolve().parent.parent
	csv_path = project_root / "data" / "raw" / "SFinDSet.csv"
	try:
		dataset = pd.read_csv(csv_path)
	except FileNotFoundError:
		print(f"Error: dataset not found at {csv_path}")
		return 1
	except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError, UnicodeDecodeError) as error:
		print(f"Error: could not read the dataset: {error}")
		return 1

	checks = run_validation(dataset)
	print_validation_report(dataset, checks)
	return 0 if all(check["passed"] for check in checks.values()) else 1


if __name__ == "__main__":
	sys.exit(main())