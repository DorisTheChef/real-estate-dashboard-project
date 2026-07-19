from pathlib import Path

import pandas as pd


# Project folders. Raw MLS exports stay ignored by Git under data/raw, while
# analysis-ready combined files are written to data/processed.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Week 1 scope: combine all available monthly files from Jan 2024 through
# May 2026. Change END_MONTH when a newer completed month is available.
START_MONTH = "202401"
END_MONTH = "202606"


def month_range(start_month, end_month):
    """Yield YYYYMM strings from start_month through end_month, inclusive."""
    start_year = int(start_month[:4])
    start_month_num = int(start_month[4:])
    end_year = int(end_month[:4])
    end_month_num = int(end_month[4:])

    year = start_year
    month = start_month_num

    while (year, month) <= (end_year, end_month_num):
        yield f"{year}{month:02d}"
        month += 1
        if month == 13:
            month = 1
            year += 1


def select_monthly_file(prefix, month):
    """Choose the best source file for a month, preferring _filled files."""
    filled_file = RAW_DIR / f"{prefix}{month}_filled.csv"
    regular_file = RAW_DIR / f"{prefix}{month}.csv"

    if filled_file.exists():
        return filled_file
    if regular_file.exists():
        return regular_file
    return None


def read_monthly_file(file_path):
    df = pd.read_csv(file_path, low_memory=False)

    # Boss note: *_filled.csv files include two extra columns at the end.
    # Drop those columns before concatenation so schemas line up with regular
    # monthly files.
    if file_path.stem.endswith("_filled"):
        dropped_columns = list(df.columns[-2:])
        df = df.iloc[:, :-2]
        print(
            f"  Dropped last 2 columns from {file_path.name}: "
            f"{', '.join(dropped_columns)}"
        )

    return df


def combine_dataset(prefix, dataset_label, months):
    """Load, concatenate, and Residential-filter one CRMLS dataset type."""
    dataframes = []
    missing_months = []
    expected_columns = None
    expected_column_set = None

    print(f"\nLoading {dataset_label} files:")

    for month in months:
        file_path = select_monthly_file(prefix, month)

        if file_path is None:
            missing_months.append(month)
            print(f"  Missing {dataset_label} file for {month}")
            continue

        df = read_monthly_file(file_path)

        if expected_columns is None:
            expected_columns = list(df.columns)
            expected_column_set = set(df.columns)
        elif list(df.columns) != expected_columns:
            # Some monthly exports contain slightly different API fields.
            # pandas.concat keeps the union of all columns and fills blanks
            # where a month does not contain a field.
            missing_columns = sorted(expected_column_set - set(df.columns))
            added_columns = sorted(set(df.columns) - expected_column_set)
            print(f"  Column note: layout differs in {file_path.name}")
            if missing_columns:
                print(f"    Missing vs first loaded file: {', '.join(missing_columns)}")
            if added_columns:
                print(f"    Added vs first loaded file: {', '.join(added_columns)}")

        print(f"  Loaded {file_path.name}: {len(df):,} rows")
        dataframes.append(df)

    if not dataframes:
        raise ValueError(f"No {dataset_label} files were loaded from {RAW_DIR}")

    combined = pd.concat(dataframes, ignore_index=True, sort=False)
    print(f"{dataset_label} rows before Residential filter: {len(combined):,}")

    if "PropertyType" not in combined.columns:
        raise ValueError(f"{dataset_label} data does not contain a PropertyType column")

    # Strip whitespace so values like "Residential " still pass the filter.
    residential = combined[
        combined["PropertyType"].astype(str).str.strip().eq("Residential")
    ].copy()

    print(f"{dataset_label} rows after Residential filter: {len(residential):,}")
    print(f"{dataset_label} rows removed by filter: {len(combined) - len(residential):,}")

    if missing_months:
        print(f"{dataset_label} missing months: {', '.join(missing_months)}")
    else:
        print(f"{dataset_label} missing months: none")

    return residential


def main():
    if not RAW_DIR.exists():
        raise FileNotFoundError(f"Raw data folder not found: {RAW_DIR}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    months = list(month_range(START_MONTH, END_MONTH))

    print(f"Combining CRMLS data from {START_MONTH} through {END_MONTH}")
    print(f"Raw input folder: {RAW_DIR}")
    print(f"Processed output folder: {PROCESSED_DIR}")

    listings = combine_dataset("CRMLSListing", "listing", months)
    sold = combine_dataset("CRMLSSold", "sold", months)

    listings_output = (
        PROCESSED_DIR
        / f"listings_1_combined.csv"
    )
    sold_output = (
        PROCESSED_DIR
        / f"sold_1_combined.csv"
    )

    listings.to_csv(listings_output, index=False)
    sold.to_csv(sold_output, index=False)

    print("\nSaved output files:")
    print(f"  {listings_output}")
    print(f"  {sold_output}")


if __name__ == "__main__":
    main()
