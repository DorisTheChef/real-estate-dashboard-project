from pathlib import Path

import pandas as pd


# Project paths and date range used for this cleaning deliverable.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "data" / "reports" / "week4_5_sold_cleaning"

START_MONTH = "202401"
END_MONTH = "202606"
MISSING_DROP_THRESHOLD = 90.0

INPUT_FILE = (
    PROCESSED_DIR
    / f"sold_2_enriched.csv"
)
OUTPUT_FILE = (
    PROCESSED_DIR
    / f"sold_3_cleaned.csv"
)

# Date columns must be true datetime values before timeline checks can work.
DATE_FIELDS = [
    "CloseDate",
    "PurchaseContractDate",
    "ListingContractDate",
    "ContractStatusChangeDate",
]

# Numeric columns are coerced to numeric so invalid values become NaN instead
# of breaking calculations or comparisons.
NUMERIC_FIELDS = [
    "ClosePrice",
    "ListPrice",
    "OriginalListPrice",
    "LivingArea",
    "LotSizeAcres",
    "BedroomsTotal",
    "BathroomsTotalInteger",
    "DaysOnMarket",
    "YearBuilt",
    "Latitude",
    "Longitude",
    "rate_30yr_fixed",
]

# These fields are not needed for the Market Analysis or Competitive Analysis
# dashboards. Agent/office fields that may support competitive analysis are
# intentionally kept if they survive the >90% missing-value rule.
UNNECESSARY_METADATA_FIELDS = [
    "ListingKeyNumeric",
    "ListAgentEmail",
    "ListAgentFirstName",
    "ListAgentLastName",
    "CoListAgentFirstName",
    "CoListAgentLastName",
    "CoBuyerAgentFirstName",
    "CoListOfficeName",
    "BuyerOfficeAOR",
    "BuyerAgentAOR",
    "ListAgentAOR",
    "OriginatingSystemName",
    "OriginatingSystemSubName",
]


def ensure_output_dirs():
    """Create folders for cleaned data and Week 4-5 reports."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def build_missing_report(df):
    """Summarize missing counts and percentages for every column."""
    missing_count = df.isna().sum()
    missing_pct = missing_count / len(df) * 100

    return (
        pd.DataFrame(
            {
                "column": df.columns,
                "missing_count": missing_count.values,
                "missing_pct": missing_pct.round(2).values,
                "over_90_pct_missing": (missing_pct > MISSING_DROP_THRESHOLD).values,
            }
        )
        .sort_values(["missing_pct", "missing_count"], ascending=False)
        .reset_index(drop=True)
    )


def convert_date_fields(df):
    """Convert required date fields and record resulting dtypes."""
    rows = []

    for field in DATE_FIELDS:
        if field not in df.columns:
            rows.append({"field": field, "status": "missing_column", "dtype": None})
            continue

        df[field] = pd.to_datetime(df[field], errors="coerce")
        rows.append({"field": field, "status": "converted", "dtype": str(df[field].dtype)})

    return pd.DataFrame(rows)


def convert_numeric_fields(df):
    """Convert required numeric fields and record resulting dtypes."""
    rows = []

    for field in NUMERIC_FIELDS:
        if field not in df.columns:
            rows.append({"field": field, "status": "missing_column", "dtype": None})
            continue

        df[field] = pd.to_numeric(df[field], errors="coerce")
        rows.append({"field": field, "status": "converted", "dtype": str(df[field].dtype)})

    return pd.DataFrame(rows)


def drop_high_missing_columns(df, missing_report):
    """Drop columns above the boss-approved 90% missingness threshold."""
    columns_to_drop = missing_report.loc[
        missing_report["over_90_pct_missing"], "column"
    ].tolist()

    return df.drop(columns=columns_to_drop), columns_to_drop


def drop_unnecessary_metadata_columns(df):
    """Drop metadata fields that do not support the planned dashboards."""
    columns_to_drop = [col for col in UNNECESSARY_METADATA_FIELDS if col in df.columns]
    return df.drop(columns=columns_to_drop), columns_to_drop


def add_invalid_numeric_flags(df):
    """Flag invalid numeric values while keeping rows available for review."""
    flag_definitions = {
        "invalid_close_price_flag": ("ClosePrice", lambda s: s <= 0),
        "invalid_living_area_flag": ("LivingArea", lambda s: s <= 0),
        "negative_days_on_market_flag": ("DaysOnMarket", lambda s: s < 0),
        "negative_bedrooms_flag": ("BedroomsTotal", lambda s: s < 0),
        "negative_bathrooms_flag": ("BathroomsTotalInteger", lambda s: s < 0),
    }

    for flag_name, (field, condition) in flag_definitions.items():
        if field in df.columns:
            df[flag_name] = condition(df[field]).fillna(False)
        else:
            df[flag_name] = False


def add_date_consistency_flags(df):
    """Flag records where the transaction timeline is logically inconsistent."""
    listing_date = df.get("ListingContractDate")
    purchase_date = df.get("PurchaseContractDate")
    close_date = df.get("CloseDate")

    if listing_date is not None and close_date is not None:
        df["listing_after_close_flag"] = (
            listing_date.notna() & close_date.notna() & (listing_date > close_date)
        )
    else:
        df["listing_after_close_flag"] = False

    if purchase_date is not None and close_date is not None:
        df["purchase_after_close_flag"] = (
            purchase_date.notna() & close_date.notna() & (purchase_date > close_date)
        )
    else:
        df["purchase_after_close_flag"] = False

    negative_listing_close = df["listing_after_close_flag"]
    negative_purchase_close = df["purchase_after_close_flag"]

    if listing_date is not None and purchase_date is not None:
        purchase_before_listing = (
            listing_date.notna()
            & purchase_date.notna()
            & (purchase_date < listing_date)
        )
    else:
        purchase_before_listing = False

    df["negative_timeline_flag"] = (
        negative_listing_close | negative_purchase_close | purchase_before_listing
    )


def add_geographic_quality_flags(df):
    """Flag missing, zero, positive, or implausible California coordinates."""
    latitude = df.get("Latitude")
    longitude = df.get("Longitude")

    if latitude is None or longitude is None:
        df["missing_coordinate_flag"] = False
        df["zero_coordinate_flag"] = False
        df["positive_longitude_flag"] = False
        df["implausible_coordinate_flag"] = False
        return

    df["missing_coordinate_flag"] = latitude.isna() | longitude.isna()
    df["zero_coordinate_flag"] = (latitude == 0) | (longitude == 0)
    df["positive_longitude_flag"] = longitude > 0

    # Broad California bounding box used only as a data quality screen.
    plausible_latitude = latitude.between(32, 42, inclusive="both")
    plausible_longitude = longitude.between(-125, -114, inclusive="both")
    df["implausible_coordinate_flag"] = (
        latitude.notna()
        & longitude.notna()
        & (~plausible_latitude | ~plausible_longitude)
    )


def add_outlier_review_flags(df):
    """Flag extreme values for review without removing high-value records."""
    rows = []

    # Price per square foot helps identify unusual pricing relative to home size.
    if {"ClosePrice", "LivingArea"}.issubset(df.columns):
        valid_living_area = df["LivingArea"].notna() & (df["LivingArea"] > 0)
        df["price_per_sqft"] = pd.NA
        df.loc[valid_living_area, "price_per_sqft"] = (
            df.loc[valid_living_area, "ClosePrice"]
            / df.loc[valid_living_area, "LivingArea"]
        )
        df["price_per_sqft"] = pd.to_numeric(df["price_per_sqft"], errors="coerce")
    else:
        df["price_per_sqft"] = pd.NA

    outlier_fields = {
        "ClosePrice": "close_price_outlier_flag",
        "LivingArea": "living_area_outlier_flag",
        "price_per_sqft": "price_per_sqft_outlier_flag",
    }

    # Use the top 1% as a review threshold. These may be valid luxury,
    # multi-unit, or portfolio transactions, so they are flagged, not deleted.
    for field, flag_name in outlier_fields.items():
        if field not in df.columns:
            df[flag_name] = False
            rows.append(
                {
                    "field": field,
                    "method": "99th_percentile",
                    "threshold": None,
                    "flag": flag_name,
                    "flagged_count": 0,
                    "note": "field_not_found",
                }
            )
            continue

        series = pd.to_numeric(df[field], errors="coerce")
        valid_series = series.dropna()

        if valid_series.empty:
            df[flag_name] = False
            rows.append(
                {
                    "field": field,
                    "method": "99th_percentile",
                    "threshold": None,
                    "flag": flag_name,
                    "flagged_count": 0,
                    "note": "no_valid_values",
                }
            )
            continue

        threshold = valid_series.quantile(0.99)
        df[flag_name] = (series > threshold).fillna(False)
        flagged_count = int(df[flag_name].sum())

        rows.append(
            {
                "field": field,
                "method": "99th_percentile",
                "threshold": threshold,
                "flag": flag_name,
                "flagged_count": flagged_count,
                "note": "flagged_not_removed",
            }
        )

    # Combined flag gives dashboard users one simple filter for non-standard
    # residential records while preserving the more specific outlier flags.
    df["possible_non_standard_residential_flag"] = (
        df["close_price_outlier_flag"]
        | df["living_area_outlier_flag"]
        | df["price_per_sqft_outlier_flag"]
    )

    rows.append(
        {
            "field": "combined_outlier_review",
            "method": "any_outlier_flag",
            "threshold": None,
            "flag": "possible_non_standard_residential_flag",
            "flagged_count": int(df["possible_non_standard_residential_flag"].sum()),
            "note": "possible luxury, multi-unit, portfolio sale, or data entry issue",
        }
    )

    return pd.DataFrame(rows)


def build_flag_summary(df):
    """Count every boolean quality flag added during cleaning."""
    flag_columns = [col for col in df.columns if col.endswith("_flag")]
    rows = []

    for column in flag_columns:
        flagged_count = int(df[column].sum())
        rows.append(
            {
                "flag": column,
                "flagged_count": flagged_count,
                "flagged_pct": round(flagged_count / len(df) * 100, 4),
            }
        )

    return pd.DataFrame(rows).sort_values("flag")


def build_dtype_confirmation(df):
    """Confirm final dtypes for the required date and numeric fields."""
    fields = [field for field in DATE_FIELDS + NUMERIC_FIELDS if field in df.columns]
    return pd.DataFrame(
        {
            "field": fields,
            "dtype_after_cleaning": [str(df[field].dtype) for field in fields],
        }
    )


def save_cleaning_summary(
    before_shape,
    after_shape,
    high_missing_count,
    metadata_count,
):
    """Build a one-table summary of the main cleaning transformations."""
    summary_rows = [
        {
            "metric": "input_file",
            "value": str(INPUT_FILE.relative_to(PROJECT_ROOT)),
        },
        {
            "metric": "output_file",
            "value": str(OUTPUT_FILE.relative_to(PROJECT_ROOT)),
        },
        {"metric": "rows_before_cleaning", "value": before_shape[0]},
        {"metric": "columns_before_cleaning", "value": before_shape[1]},
        {"metric": "rows_after_cleaning", "value": after_shape[0]},
        {"metric": "columns_after_cleaning", "value": after_shape[1]},
        {"metric": "columns_dropped_over_90_pct_missing", "value": high_missing_count},
        {"metric": "unnecessary_metadata_columns_dropped", "value": metadata_count},
        {
            "metric": "rows_removed",
            "value": before_shape[0] - after_shape[0],
        },
        {
            "metric": "row_removal_note",
            "value": "No rows were removed. Invalid values were flagged for investigation.",
        },
    ]

    return pd.DataFrame(summary_rows)


def main():
    ensure_output_dirs()

    # Load the mortgage-enriched sold dataset created in Weeks 2-3.
    print(f"Loading sold dataset: {INPUT_FILE}")
    sold = pd.read_csv(INPUT_FILE, low_memory=False)
    before_shape = sold.shape
    print(f"Rows before cleaning: {before_shape[0]:,}")
    print(f"Columns before cleaning: {before_shape[1]:,}")

    # Standardize field types before any validation logic is applied.
    date_dtype_report = convert_date_fields(sold)
    numeric_dtype_report = convert_numeric_fields(sold)

    # Drop columns that are too sparse to support reliable analysis.
    missing_report_before = build_missing_report(sold)
    sold, high_missing_columns = drop_high_missing_columns(sold, missing_report_before)

    # Remove non-dashboard metadata after the high-missing rule has been applied.
    sold, metadata_columns = drop_unnecessary_metadata_columns(sold)

    # Add data-quality flags. Rows are retained so issues can be reviewed or
    # filtered later in dashboards.
    add_invalid_numeric_flags(sold)
    add_date_consistency_flags(sold)
    add_geographic_quality_flags(sold)
    outlier_threshold_report = add_outlier_review_flags(sold)

    # Remove fields that do not add useful information to the final dashboards.
    # PropertyType is constant after the Residential filter; the location and
    # compensation fields are redundant, overly granular, or outside the planned
    # analysis; and ListingId is unnecessary because ListingKey identifies records.
    final_columns_to_drop = [
        "ListingId",
        "PropertyType",
        "AssociationFeeFrequency",
        "MLSAreaMajor",
        "SubdivisionName",
        "BuyerAgencyCompensationType",
        "StreetNumberNumeric",
    ]
    final_columns_to_drop = [
        column for column in final_columns_to_drop if column in sold.columns
    ]
    sold = sold.drop(columns=final_columns_to_drop)
    metadata_columns.extend(final_columns_to_drop)

    # Build reports that document the cleaned dataset and all transformations.
    after_shape = sold.shape
    missing_report_after = build_missing_report(sold)
    flag_summary = build_flag_summary(sold)
    dtype_confirmation = build_dtype_confirmation(sold)
    transformation_summary = save_cleaning_summary(
        before_shape,
        after_shape,
        len(high_missing_columns),
        len(metadata_columns),
    )

    # Keep a record of every dropped column and the reason it was removed.
    dropped_columns = pd.DataFrame(
        [
            {"column": column, "drop_reason": "over_90_pct_missing"}
            for column in high_missing_columns
        ]
        + [
            {"column": column, "drop_reason": "unnecessary_metadata"}
            for column in metadata_columns
        ]
    )

    # Save the cleaned analysis-ready dataset and the Week 4-5 deliverable reports.
    sold.to_csv(OUTPUT_FILE, index=False)
    missing_report_before.to_csv(REPORT_DIR / "missing_report_before_cleaning.csv", index=False)
    missing_report_after.to_csv(REPORT_DIR / "missing_report_after_cleaning.csv", index=False)
    dropped_columns.to_csv(REPORT_DIR / "dropped_columns.csv", index=False)
    flag_summary.to_csv(REPORT_DIR / "flag_counts.csv", index=False)
    dtype_confirmation.to_csv(REPORT_DIR / "dtype_confirmations.csv", index=False)
    date_dtype_report.to_csv(REPORT_DIR / "date_field_conversions.csv", index=False)
    numeric_dtype_report.to_csv(REPORT_DIR / "numeric_field_conversions.csv", index=False)
    outlier_threshold_report.to_csv(REPORT_DIR / "outlier_thresholds.csv", index=False)
    transformation_summary.to_csv(REPORT_DIR / "cleaning_summary.csv", index=False)

    print(f"Columns dropped for >90% missing: {len(high_missing_columns):,}")
    print(f"Unnecessary metadata columns dropped: {len(metadata_columns):,}")
    print(f"Rows after cleaning: {after_shape[0]:,}")
    print(f"Columns after cleaning: {after_shape[1]:,}")
    print(f"Saved cleaned dataset: {OUTPUT_FILE}")
    print(f"Saved cleaning reports: {REPORT_DIR}")


if __name__ == "__main__":
    main()
