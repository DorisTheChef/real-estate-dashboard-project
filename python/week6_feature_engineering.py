"""Week 6: feature engineering, school districts, and segment analysis.

Takes the Week 4-5 final cleaned dataset and engineers the market indicators
that power the Tableau dashboards, assigns school districts by spatial join,
and produces segment summary tables.

    week4_5_resolve_flags.py -> week6_feature_engineering.py

Engineered metrics:
- sale_to_list_ratio           ClosePrice / ListPrice (negotiation strength)
- close_to_original_list_ratio ClosePrice / OriginalListPrice (full reduction)
- price_per_sqft               ClosePrice / LivingArea
- close_year / close_month / close_yrmo   time-series keys from CloseDate
- listing_to_contract_days     PurchaseContractDate - ListingContractDate
- contract_to_close_days       CloseDate - PurchaseContractDate

Note: the handbook lists "Price Ratio" and "Close to Original List Ratio" with
the same formula. That is read as a typo; the two standard, distinct ratios
above are computed instead (sale-to-list vs close-to-original-list).
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "data" / "reports" / "week6_feature_engineering"

INPUT_FILE = PROCESSED_DIR / "crmls_sold_final_202401_202606.csv"
OUTPUT_FILE = PROCESSED_DIR / "crmls_sold_features_202401_202606.csv"
SCHOOL_DISTRICT_SHP = (
    PROJECT_ROOT / "data" / "raw" / "school_districts" / "DistrictAreas2425.shp"
)

DATE_FIELDS = ["CloseDate", "PurchaseContractDate", "ListingContractDate"]

# A California residential price below this is a placeholder or unit error
# (e.g., a list price of "695" for a $695,000 sale), not a real price.
MIN_VALID_PRICE = 1000

# Price errors surfaced by the ratio sanity check. Week 4-5 removed only
# ClosePrice <= 0, so these positive-but-wrong prices slipped through.
BRENTWOOD_UNRECOVERABLE_KEY = 1059929060  # ClosePrice $345 = trailing digits of $784,345
ANAHEIM_LISTPRICE_TYPO_KEY = 1065201431   # ListPrice 695 -> 695,000 (at-list sale)


def load_data():
    """Load the Week 4-5 final dataset with date fields typed."""
    df = pd.read_csv(INPUT_FILE, low_memory=False)
    for field in DATE_FIELDS:
        df[field] = pd.to_datetime(df[field], errors="coerce")
    print(f"Loaded: {len(df):,} rows x {df.shape[1]} columns")
    return df


def fix_price_errors(df):
    """Repair or remove the two price errors found via the ratio check.

    - Brentwood row: ClosePrice $345 captured only the trailing digits of its
      $784,345 list price and cannot be reconstructed -> delete (close price
      is essential to sold-market analysis).
    - Anaheim row: list price lost its thousands (695 vs a $695,000 close, an
      at-list sale) -> restore the three zeros.
    """
    rows_before = len(df)
    df = df.loc[~df["ListingKey"].eq(BRENTWOOD_UNRECOVERABLE_KEY)].copy()
    print(f"Deleted unrecoverable ClosePrice row: {rows_before:,} -> {len(df):,}")

    anaheim = df["ListingKey"].eq(ANAHEIM_LISTPRICE_TYPO_KEY)
    df.loc[anaheim, ["ListPrice", "OriginalListPrice"]] = 695000.0
    print(f"Repaired Anaheim list price: {int(anaheim.sum())} row")
    return df


def add_market_metrics(df):
    """Engineer the Week 6 market indicator columns."""
    df["sale_to_list_ratio"] = df["ClosePrice"] / df["ListPrice"]
    df["close_to_original_list_ratio"] = df["ClosePrice"] / df["OriginalListPrice"]

    # LivingArea=0 was set to missing in Week 4-5, so this cannot divide by 0.
    df["price_per_sqft"] = df["ClosePrice"] / df["LivingArea"]

    df["close_year"] = df["CloseDate"].dt.year
    df["close_month"] = df["CloseDate"].dt.month
    df["close_yrmo"] = df["CloseDate"].dt.strftime("%Y-%m")

    df["listing_to_contract_days"] = (
        df["PurchaseContractDate"] - df["ListingContractDate"]
    ).dt.days
    df["contract_to_close_days"] = (
        df["CloseDate"] - df["PurchaseContractDate"]
    ).dt.days
    return df


def guard_ratios(df):
    """Invalidate ratios built on placeholder-grade prices. A ratio using a
    price below $1,000 (or a missing price) is meaningless; the row is kept
    and only the ratio is set to missing. Extreme but legitimately-computed
    ratios (digit typos) are left for Week 7 IQR filtering."""
    for numerator, denominator, ratio in [
        ("ClosePrice", "ListPrice", "sale_to_list_ratio"),
        ("ClosePrice", "OriginalListPrice", "close_to_original_list_ratio"),
    ]:
        invalid = (
            df[numerator].lt(MIN_VALID_PRICE).fillna(True)
            | df[denominator].lt(MIN_VALID_PRICE).fillna(True)
        )
        df.loc[invalid, ratio] = pd.NA
        print(f"{ratio}: {int(invalid.sum())} rows set to missing")
    return df


def add_school_districts(df):
    """Assign school districts by point-in-polygon spatial join on lat/lon.

    California districts come in three types: Unified (K-12), Elementary
    (K-8), and High (9-12). Each type becomes its own column so every
    property keeps exactly one row, whether it falls in a single Unified
    district or an Elementary + High pair.
    """
    districts = gpd.read_file(SCHOOL_DISTRICT_SHP)[
        ["DistrictNa", "DistrictTy", "geometry"]
    ]
    # District polygons ship in Web Mercator (EPSG:3857); our coordinates are
    # lat/lon (EPSG:4326), so reproject before joining.
    districts = districts.to_crs(4326)

    # Join on unique coordinates (many condos share a point), then map back.
    coords = (
        df.loc[df["Latitude"].notna() & df["Longitude"].notna(),
               ["Latitude", "Longitude"]]
        .drop_duplicates()
    )
    points = gpd.GeoDataFrame(
        coords,
        geometry=gpd.points_from_xy(coords["Longitude"], coords["Latitude"]),
        crs=4326,
    )
    matched = gpd.sjoin(points, districts, how="left", predicate="within")

    district_lookup = (
        matched.pivot_table(
            index=["Latitude", "Longitude"],
            columns="DistrictTy",
            values="DistrictNa",
            aggfunc="first",
        )
        .rename(columns={
            "Unified": "school_district_unified",
            "Elementary": "school_district_elementary",
            "High": "school_district_high",
        })
        .reset_index()
    )

    df = df.merge(district_lookup, on=["Latitude", "Longitude"], how="left")

    # Single district column for dashboards: Unified where one exists,
    # otherwise the Elementary district (layered Elementary + High areas).
    df["school_district"] = (
        df["school_district_unified"].fillna(df["school_district_elementary"])
    )

    district_cols = [
        c for c in ["school_district_unified",
                    "school_district_elementary",
                    "school_district_high"] if c in df.columns
    ]
    matched_any = df[district_cols].notna().any(axis=1)
    print(f"School district matched: {matched_any.mean() * 100:.2f}% of rows")
    print(f"school_district (single column) populated: "
          f"{df['school_district'].notna().mean() * 100:.2f}% of rows")
    return df


def summarize_by(df, group_col, min_count=10):
    """Summary stats for the key market metrics, grouped by one dimension.

    Uses medians throughout because they resist the extreme price typos that
    remain in the data until Week 7's outlier treatment.
    """
    summary = (
        df.groupby(group_col)
        .agg(
            homes_sold=("ClosePrice", "size"),
            median_close_price=("ClosePrice", "median"),
            median_price_per_sqft=("price_per_sqft", "median"),
            median_dom=("DaysOnMarket", "median"),
            median_sale_to_list=("sale_to_list_ratio", "median"),
            median_listing_to_contract=("listing_to_contract_days", "median"),
        )
        .round(2)
    )
    summary = summary[summary["homes_sold"] >= min_count]
    return summary.sort_values("homes_sold", ascending=False)


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    sold = load_data()
    sold = fix_price_errors(sold)
    sold = add_market_metrics(sold)
    sold = guard_ratios(sold)
    sold = add_school_districts(sold)

    # Sample output table showing the new columns populated (handbook deliverable).
    new_columns = [
        "sale_to_list_ratio", "close_to_original_list_ratio", "price_per_sqft",
        "close_yrmo", "listing_to_contract_days", "contract_to_close_days",
        "school_district", "school_district_unified",
        "school_district_elementary", "school_district_high",
    ]
    print("\n--- Sample of engineered columns ---")
    print(sold[["ListingKey", "ClosePrice"] + new_columns].head(10).to_string())

    # Segment summaries.
    by_subtype = summarize_by(sold, "PropertySubType")
    by_county = summarize_by(sold, "CountyOrParish")
    by_list_office = summarize_by(sold, "ListOfficeName", min_count=50)

    print("\n--- Segment summary: by PropertySubType ---")
    print(by_subtype.to_string())
    print("\n--- Segment summary: by County (top 15) ---")
    print(by_county.head(15).to_string())

    # Save the feature dataset and the segment reports.
    sold.to_csv(OUTPUT_FILE, index=False)
    by_subtype.to_csv(REPORT_DIR / "summary_by_property_subtype.csv")
    by_county.to_csv(REPORT_DIR / "summary_by_county.csv")
    by_list_office.head(50).to_csv(REPORT_DIR / "summary_by_listing_office.csv")

    print(f"\nSaved feature dataset: {OUTPUT_FILE}")
    print(f"  {sold.shape[0]:,} rows x {sold.shape[1]} columns")
    print(f"Saved 3 segment summaries to: {REPORT_DIR}")


if __name__ == "__main__":
    main()
