# FinPay Data Pipeline

A production-oriented transaction data processing pipeline built with **Python, Pandas, PyArrow, Apache Parquet, and PySpark**.

The pipeline ingests raw financial transaction data, performs deterministic data cleaning and quality checks, quarantines conflicting records, generates partitioned Parquet datasets, and uses PySpark to produce curated account-level daily transaction metrics.

---

## 1. Project Overview

Financial transaction datasets often contain duplicate records, inconsistent transaction identifiers, invalid dates, and conflicting records that can affect downstream analytics.

This project implements an end-to-end data processing pipeline that transforms raw transaction data into validated, analytics-ready datasets.

### Pipeline

```text
Raw Transaction CSV
        │
        ▼
Schema Validation
        │
        ▼
Data Cleaning & Date Parsing
        │
        ├── Exact Duplicate Detection
        │
        └── Conflicting Transaction ID Detection
        │
        ▼
Processed Partitioned Parquet
        │
        ▼
PySpark Daily Aggregation
        │
        ▼
Curated Account Daily Metrics
        │
        ▼
Data Quality Validation
        │
        ▼
Automated Tests
```

---

## 2. Key Results

The pipeline was executed against a dataset containing **1,048,575 raw transaction records**.

| Metric                          |    Result |
| ------------------------------- | --------: |
| Raw transaction rows            | 1,048,575 |
| Exact duplicate copies detected |       109 |
| Exact duplicate copies removed  |       109 |
| Conflicting Transaction IDs     |     3,962 |
| Conflict records quarantined    |     7,924 |
| Final processed transactions    | 1,048,466 |
| Curated account-date records    | 1,044,504 |
| Accounts represented            | 1,044,443 |
| Data-quality checks             |  6/6 PASS |
| Automated tests                 |  7/7 PASS |

---

## 3. Technology Stack

### Languages & Libraries

* Python
* Pandas
* PyArrow
* PySpark
* Pytest

### Storage & Data Formats

* CSV
* Apache Parquet

### Development Environment

* Visual Studio Code
* WSL2
* Ubuntu
* Java 17
* Git

---

## 4. Project Structure

```text
Finpay-data-pipeline/
│
├── data/
│   ├── raw/
│   │   └── SFinDSet.csv
│   │
│   ├── processed/
│   │   ├── transactions/
│   │   │   ├── transaction_year=2020/
│   │   │   ├── transaction_year=2021/
│   │   │   ├── transaction_year=2022/
│   │   │   ├── transaction_year=2023/
│   │   │   └── transaction_year=2024/
│   │   │
│   │   └── quality_exceptions/
│   │       └── duplicate_transaction_id_conflicts.parquet
│   │
│   └── curated/
│       └── account_daily_metrics/
│
├── spark/
│   └── account_metrics.py
│
├── src/
│   └── process_transactions.py
│
├── tests/
│   ├── test_processing.py
│   └── test_account_metrics.py
│
├── requirements.txt
└── README.md
```

---

## 5. Transaction Processing

The first stage is implemented in:

```text
src/process_transactions.py
```

### Schema Validation

The pipeline verifies that all required transaction fields exist before processing.

Required columns include:

```text
Transaction_ID
Account_Number
Account_Name
Transaction_Amount
Transaction_Mode
Transaction_Type
Transaction_Date
Transaction_Source
Transaction_Destination
```

If required columns are missing, processing stops with a validation error.

---

## 6. Date Processing

Transaction dates are parsed using Pandas with support for mixed date formats.

Invalid or unparseable transaction dates are rejected rather than silently entering the processed dataset.

A `transaction_year` field is derived from the parsed transaction date.

This field is subsequently used to partition the processed Parquet dataset.

---

## 7. Duplicate Handling

The pipeline distinguishes between **exact duplicates** and **conflicting transaction IDs**.

### Exact duplicates

Exact duplicate rows are detected using the required transaction columns.

For the current dataset:

```text
109 duplicate copies
```

were detected and removed.

This reduced the dataset from:

```text
1,048,575
```

to:

```text
1,048,466
```

processed transaction records.

---

## 8. Conflicting Transaction IDs

The pipeline separately identifies transaction IDs that occur exactly twice with different destination accounts.

These records are not silently deleted.

Instead, both records are retained in a dedicated quality-exception dataset:

```text
data/processed/quality_exceptions/
└── duplicate_transaction_id_conflicts.parquet
```

Current result:

```text
Conflicting Transaction IDs: 3,962
Conflict records quarantined: 7,924
```

This preserves potentially useful source information while preventing conflicting records from being treated as silently resolved.

---

## 9. Partitioned Parquet Storage

Processed transactions are written using Apache Parquet and partitioned by:

```text
transaction_year
```

Resulting structure:

```text
transactions/
├── transaction_year=2020/
├── transaction_year=2021/
├── transaction_year=2022/
├── transaction_year=2023/
└── transaction_year=2024/
```

The verified row distribution is:

| Year      |          Rows |
| --------- | ------------: |
| 2020      |       254,652 |
| 2021      |       253,502 |
| 2022      |       254,090 |
| 2023      |       252,476 |
| 2024      |        33,746 |
| **Total** | **1,048,466** |

The transaction timestamp is stored using microsecond precision (`timestamp[us]`) to maintain compatibility with the Spark processing stage.

---

## 10. PySpark Processing

The second major stage is implemented in:

```text
spark/account_metrics.py
```

PySpark reads the processed Parquet dataset and converts transaction timestamps into calendar dates.

Transactions are then grouped by:

```text
Account_Number
transaction_date
```

The following metrics are calculated:

```text
transaction_count
total_amount
average_amount
minimum_amount
maximum_amount
```

The resulting dataset is written to:

```text
data/curated/account_daily_metrics/
```

### Curated Dataset

The final curated dataset contains:

```text
1,044,504 rows
```

with the following schema:

```text
Account_Number       int64
transaction_date     date32[day]
transaction_count    int64
total_amount         double
average_amount       double
minimum_amount       double
maximum_amount       double
```

---

## 11. Data Quality Validation

The curated dataset was independently validated after Spark processing.

### Null validation

All seven output columns contain zero null values.

### Grain validation

The expected analytical grain is:

```text
Account_Number + transaction_date
```

Duplicate records at this grain:

```text
0
```

### Transaction count validation

```text
Minimum transaction count: 1
Zero transaction counts: 0
Negative transaction counts: 0
```

### Aggregation consistency

The following rules were validated:

```text
minimum_amount <= average_amount <= maximum_amount
```

and:

```text
total_amount >= minimum_amount
```

Both checks passed for all records.

### Final validation result

```text
6/6 checks passed
DATA QUALITY STATUS: PASS
```

---

## 12. Automated Testing

The project includes automated tests using Pytest.

Tests cover:

### Transaction processing

* Required column validation
* Exact duplicate removal
* Conflicting transaction ID detection
* Transaction year generation
* Invalid date handling
* Missing-column handling

### Spark aggregation

* Account/date aggregation
* Transaction count
* Total amount
* Average amount
* Minimum amount
* Maximum amount

Test execution:

```bash
python -m pytest -q
```

Current result:

```text
7 passed in 26.02s
```

---

## 13. Running the Project

### Activate the virtual environment

```bash
source .venv/bin/activate
```

### Process the raw transactions

```bash
python src/process_transactions.py
```

This creates:

```text
data/processed/transactions/
data/processed/quality_exceptions/
```

### Run the Spark aggregation

```bash
python spark/account_metrics.py
```

This creates:

```text
data/curated/account_daily_metrics/
```

### Run automated tests

```bash
python -m pytest -q
```

---

## 14. Reproducibility

The processing stage uses a staging directory and replaces previous processed outputs after successful generation.

This prevents previous Parquet partitions from being accidentally retained across repeated pipeline executions.

The Spark aggregation similarly writes the curated output using overwrite mode.

As a result, repeated executions produce deterministic output from the same source dataset.

---

## 15. Data Quality & Reliability Design

The pipeline intentionally separates different classes of data problems.

```text
Exact duplicate
      ↓
Removed

Conflicting Transaction ID
      ↓
Quarantined

Invalid Transaction Date
      ↓
Processing failure

Missing required column
      ↓
Processing failure
```

This approach avoids silently deleting ambiguous transaction records while ensuring invalid data does not propagate into the curated analytical layer.

---

## 16. Engineering Decisions

### Why Parquet?

Parquet provides a columnar storage format suitable for analytical workloads and integrates directly with PySpark.

### Why partition by year?

Transaction year provides a natural partitioning dimension and allows downstream processing to work with a smaller subset of files when only specific years are required.

### Why quarantine conflicting records?

Conflicting transaction IDs cannot safely be resolved without additional business rules. Keeping them separately preserves the source information while preventing ambiguous records from being silently interpreted.

### Why use PySpark?

The Spark stage demonstrates distributed-data-processing patterns and creates an analytics-ready account/date dataset from the processed transaction data.

### Why automated tests?

Automated tests protect important processing rules such as duplicate removal, conflict detection, date validation, and aggregation behavior against future changes.

---

## 17. Current Pipeline Output

The completed pipeline produces three logical layers:

### Processed Layer

```text
data/processed/transactions/
```

Cleaned, validated and partitioned transaction records.

### Quality Exception Layer

```text
data/processed/quality_exceptions/
```

Records requiring separate investigation or business-rule decisions.

### Curated Layer

```text
data/curated/account_daily_metrics/
```

Account-level daily transaction metrics ready for downstream analytics.

---

## 18. Project Highlights

* Processed **1M+ financial transaction records**
* Implemented deterministic duplicate handling
* Identified and quarantined **3,962 conflicting transaction IDs**
* Generated partitioned Parquet datasets
* Built PySpark account-level daily aggregations
* Implemented independent data-quality validation
* Added automated unit/integration tests
* Designed repeatable output replacement to avoid stale partitions
* Developed and validated the pipeline in a WSL2 Linux environment

---

## 19. Future Extensions

Potential extensions include:

* Incremental processing for newly arrived transactions
* Pipeline orchestration
* Cloud object storage
* Data-quality monitoring
* API access to curated metrics
* Dashboarding and analytical consumption
* CI-based automated testing

These are intentionally outside the current implementation so that the repository reflects the functionality that has actually been implemented and tested.
