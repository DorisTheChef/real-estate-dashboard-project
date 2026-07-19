"""Week 5: clean the listing dataset for the "New Listings" dashboard.

The Week 4-5 cleaning covered the sold dataset; this script does the same for
listings, which the Tableau market-analysis workbook needs to count new
listings per month.

    combine_crmls_monthly.py -> enrich_mortgage_rates.py -> week5_clean_listings.py

Listings need less work than solds: there is no sale timeline to validate and
no price ratios to compute, so the cleaning focuses on what the dashboards
actually consume — one row per listing, a trustworthy listing date, California
records only, and usable coordinates. Two issues specific to this file:

- 11 columns arrived duplicated with a ".1" suffix (the combine step picked up
  same-named columns), each identical to its original.
- A few ListingKeys repeat with conflicting listing dates, which would double
  count new listings.
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "data" / "reports" / "week5_listing_cleaning"

INPUT_FILE = (
    PROCESSED_DIR
    / "listings_2_enriched.csv"
)
OUTPUT_FILE = PROCESSED_DIR / "listings_3_cleaned.csv"

MISSING_DROP_THRESHOLD = 90.0


def load_data():
    """Load the mortgage-enriched combined listing dataset."""
    df = pd.read_csv(INPUT_FILE, low_memory=False)
    print(f"Loaded: {len(df):,} rows x {df.shape[1]} columns")
    return df


def drop_duplicate_columns(df):
    """Drop the ".1" suffixed columns, which duplicate their originals."""
    dot1_cols = [c for c in df.columns if c.endswith(".1")]
    for column in dot1_cols:
        original = column[:-2]
        if original in df.columns and not df[original].equals(df[column]):
            raise ValueError(f"{column} differs from {original}; not a safe duplicate")

    df = df.drop(columns=dot1_cols)
    print(f"Dropped {len(dot1_cols)} duplicate columns -> {df.shape[1]} columns")
    return df


def deduplicate_listings(df):
    """Keep one row per ListingKey, using the earliest listing date.

    A handful of ListingKeys repeat with conflicting ListingContractDates.
    The earliest date is the first time the property came to market, which is
    what a "new listing" count should reflect.
    """
    df["ListingContractDate"] = pd.to_datetime(
        df["ListingContractDate"], errors="coerce"
    )
    rows_before = len(df)
    df = (
        df.sort_values("ListingContractDate")
        .drop_duplicates(subset="ListingKey", keep="first")
        .reset_index(drop=True)
    )
    print(f"Deduplicated by ListingKey: {rows_before:,} -> {len(df):,}")
    return df


def filter_california(df):
    """Keep CA rows, plus missing-state rows whose coordinates fall in CA."""
    state = df["StateOrProvince"].astype("string").str.strip().str.upper()
    missing_state = state.isna() | state.eq("")

    latitude = pd.to_numeric(df["Latitude"], errors="coerce")
    longitude = pd.to_numeric(df["Longitude"], errors="coerce")
    plausible_ca = (
        latitude.between(32, 42, inclusive="both")
        & longitude.between(-125, -114, inclusive="both")
    )

    keep = state.isin(["CA", "CALIFORNIA"]) | (missing_state & plausible_ca)
    removed = int((~keep).sum())
    df = df.loc[keep].copy()
    print(f"State filter: removed {removed} non-CA rows -> {len(df):,}")
    return df


def fix_coordinates(df):
    """Clear placeholder coordinates and recover dropped minus signs."""
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    zero = df["Latitude"].eq(0) | df["Longitude"].eq(0)
    df.loc[zero, ["Latitude", "Longitude"]] = pd.NA

    positive = df["Longitude"].gt(0).fillna(False)
    flippable = (
        positive
        & df["Latitude"].between(32, 42)
        & (-df["Longitude"]).between(-125, -114)
    )
    df.loc[flippable, "Longitude"] = -df.loc[flippable, "Longitude"]
    unrecoverable = positive & ~flippable
    df.loc[unrecoverable, ["Latitude", "Longitude"]] = pd.NA

    print(
        f"Coordinates: {int(zero.sum())} zero cleared, "
        f"{int(flippable.sum())} sign-flipped, {int(unrecoverable.sum())} cleared"
    )
    return df


def drop_high_missing_columns(df):
    """Drop columns above the 90% missing threshold used for the sold data."""
    missing_pct = df.isna().mean() * 100
    high_missing = missing_pct[missing_pct > MISSING_DROP_THRESHOLD].index.tolist()
    df = df.drop(columns=high_missing)
    print(f"Dropped {len(high_missing)} columns >{MISSING_DROP_THRESHOLD:.0f}% missing "
          f"-> {df.shape[1]} columns")
    return df


def add_month_key(df):
    """Derive the monthly key the New Listings dashboard groups on."""
    df["list_yrmo"] = df["ListingContractDate"].dt.strftime("%Y-%m")
    print(f"Date range: {df['list_yrmo'].min()} -> {df['list_yrmo'].max()} "
          f"({df['list_yrmo'].nunique()} months)")
    return df


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    listings = load_data()
    listings = drop_duplicate_columns(listings)
    listings = deduplicate_listings(listings)
    listings = filter_california(listings)
    listings = fix_coordinates(listings)
    listings = drop_high_missing_columns(listings)
    listings = add_month_key(listings)

    # New listings per month — the core series behind the dashboard.
    new_by_month = (
        listings.groupby("list_yrmo").size().rename("new_listings").reset_index()
    )
    new_by_month.to_csv(REPORT_DIR / "new_listings_by_month.csv", index=False)

    listings.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved: {OUTPUT_FILE}")
    print(f"  {listings.shape[0]:,} rows x {listings.shape[1]} columns")
    print(f"Saved monthly counts: {REPORT_DIR / 'new_listings_by_month.csv'}")
    print("\n--- New listings per month ---")
    print(new_by_month.to_string(index=False))


if __name__ == "__main__":
    main()
