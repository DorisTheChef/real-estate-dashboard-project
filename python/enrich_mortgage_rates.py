from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

START_MONTH = "202401"
END_MONTH = "202606"

FRED_MORTGAGE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"

SOLD_INPUT = (
    PROCESSED_DIR / f"sold_1_combined.csv"
)
LISTINGS_INPUT = (
    PROCESSED_DIR / f"listings_1_combined.csv"
)

SOLD_OUTPUT = (
    PROCESSED_DIR
    / f"sold_2_enriched.csv"
)
LISTINGS_OUTPUT = (
    PROCESSED_DIR
    / f"listings_2_enriched.csv"
)


def fetch_monthly_mortgage_rates():
    """Fetch weekly FRED MORTGAGE30US rates and average them by month."""
    mortgage = pd.read_csv(FRED_MORTGAGE_URL, parse_dates=["observation_date"])
    mortgage = mortgage.rename(
        columns={
            "observation_date": "date",
            "MORTGAGE30US": "rate_30yr_fixed",
        }
    )

    # FRED can use "." for missing observations. Convert those to NaN before
    # calculating monthly averages.
    mortgage["rate_30yr_fixed"] = pd.to_numeric(
        mortgage["rate_30yr_fixed"], errors="coerce"
    )
    mortgage["year_month"] = mortgage["date"].dt.to_period("M").astype(str)

    mortgage_monthly = (
        mortgage.groupby("year_month", as_index=False)["rate_30yr_fixed"].mean()
    )

    return mortgage_monthly


def add_year_month_key(df, date_column, dataset_label):
    """Create YYYY-MM join key from the relevant MLS date column."""
    if date_column not in df.columns:
        raise ValueError(f"{dataset_label} data is missing {date_column}")

    parsed_dates = pd.to_datetime(df[date_column], errors="coerce")
    missing_dates = int(parsed_dates.isna().sum())

    if missing_dates:
        print(
            f"Warning: {dataset_label} has {missing_dates:,} rows with missing or "
            f"invalid {date_column}; those rows may not receive a mortgage rate."
        )

    df = df.copy()
    df["year_month"] = parsed_dates.dt.to_period("M").astype(str)
    df.loc[parsed_dates.isna(), "year_month"] = pd.NA

    return df


def merge_mortgage_rates(df, mortgage_monthly, date_column, dataset_label):
    """Attach monthly mortgage rates to an MLS dataset and validate the merge."""
    keyed = add_year_month_key(df, date_column, dataset_label)
    enriched = keyed.merge(mortgage_monthly, on="year_month", how="left")

    missing_rates = int(enriched["rate_30yr_fixed"].isna().sum())
    print(f"{dataset_label} rows after merge: {len(enriched):,}")
    print(f"{dataset_label} null mortgage rates after merge: {missing_rates:,}")

    if missing_rates:
        unmatched_months = (
            enriched.loc[enriched["rate_30yr_fixed"].isna(), "year_month"]
            .dropna()
            .sort_values()
            .unique()
        )
        raise ValueError(
            f"{dataset_label} has {missing_rates:,} rows without mortgage rates. "
            f"Unmatched months: {', '.join(unmatched_months)}"
        )

    return enriched


def main():
    if not SOLD_INPUT.exists():
        raise FileNotFoundError(f"Sold input not found: {SOLD_INPUT}")
    if not LISTINGS_INPUT.exists():
        raise FileNotFoundError(f"Listings input not found: {LISTINGS_INPUT}")

    print("Fetching FRED MORTGAGE30US data...")
    mortgage_monthly = fetch_monthly_mortgage_rates()
    print(
        "Monthly mortgage rate coverage: "
        f"{mortgage_monthly['year_month'].min()} through "
        f"{mortgage_monthly['year_month'].max()}"
    )

    print(f"\nLoading sold data: {SOLD_INPUT}")
    sold = pd.read_csv(SOLD_INPUT, low_memory=False)
    sold_with_rates = merge_mortgage_rates(
        sold, mortgage_monthly, "CloseDate", "sold"
    )

    print(f"\nLoading listings data: {LISTINGS_INPUT}")
    listings = pd.read_csv(LISTINGS_INPUT, low_memory=False)
    listings_with_rates = merge_mortgage_rates(
        listings, mortgage_monthly, "ListingContractDate", "listings"
    )

    sold_with_rates.to_csv(SOLD_OUTPUT, index=False)
    listings_with_rates.to_csv(LISTINGS_OUTPUT, index=False)

    print("\nSaved enriched datasets:")
    print(f"  {SOLD_OUTPUT}")
    print(f"  {LISTINGS_OUTPUT}")

    print("\nPreview:")
    print(
        sold_with_rates[
            ["CloseDate", "year_month", "ClosePrice", "rate_30yr_fixed"]
        ].head()
    )
    print(
        listings_with_rates[
            ["ListingContractDate", "year_month", "ListPrice", "rate_30yr_fixed"]
        ].head()
    )


if __name__ == "__main__":
    main()
