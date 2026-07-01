from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "data" / "reports" / "week2_3_sold_eda"
FIGURE_DIR = REPORT_DIR / "figures"

START_MONTH = "202401"
END_MONTH = "202605"
MISSING_DROP_THRESHOLD = 90.0

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
]

CORE_FIELDS = {
    "ListingKey",
    "ListingId",
    "CloseDate",
    "ClosePrice",
    "ListPrice",
    "OriginalListPrice",
    "PropertyType",
    "PropertySubType",
    "LivingArea",
    "LotSizeAcres",
    "BedroomsTotal",
    "BathroomsTotalInteger",
    "DaysOnMarket",
    "YearBuilt",
    "CountyOrParish",
    "City",
    "PostalCode",
    "Latitude",
    "Longitude",
    "ListingContractDate",
    "PurchaseContractDate",
}

METADATA_FIELDS = {
    "ListingKeyNumeric",
    "ListAgentEmail",
    "ListAgentFirstName",
    "ListAgentLastName",
    "ListAgentFullName",
    "CoListAgentFirstName",
    "CoListAgentLastName",
    "CoBuyerAgentFirstName",
    "BuyerAgentMlsId",
    "BuyerAgentFirstName",
    "BuyerAgentLastName",
    "ListOfficeName",
    "BuyerOfficeName",
    "CoListOfficeName",
    "BuyerOfficeAOR",
    "BuyerAgentAOR",
    "ListAgentAOR",
    "OriginatingSystemName",
    "OriginatingSystemSubName",
    "MlsStatus",
}


def month_range(start_month, end_month):
    """Yield YYYYMM strings from start_month through end_month, inclusive."""
    year = int(start_month[:4])
    month = int(start_month[4:])
    end_year = int(end_month[:4])
    end_month_num = int(end_month[4:])

    while (year, month) <= (end_year, end_month_num):
        yield f"{year}{month:02d}"
        month += 1
        if month == 13:
            month = 1
            year += 1


def select_sold_file(month):
    """Choose the sold source file for a month, preferring _filled files."""
    filled_file = RAW_DIR / f"CRMLSSold{month}_filled.csv"
    regular_file = RAW_DIR / f"CRMLSSold{month}.csv"

    if filled_file.exists():
        return filled_file
    if regular_file.exists():
        return regular_file
    return None


def read_sold_file(file_path):
    df = pd.read_csv(file_path, low_memory=False)

    # *_filled.csv files have two helper columns at the end. Drop them before
    # combining with regular monthly files.
    if file_path.stem.endswith("_filled"):
        df = df.iloc[:, :-2]

    return df


def load_sold_data():
    frames = []
    missing_months = []

    print(f"Loading sold files from {START_MONTH} through {END_MONTH}")

    for month in month_range(START_MONTH, END_MONTH):
        file_path = select_sold_file(month)
        if file_path is None:
            missing_months.append(month)
            print(f"  Missing sold file for {month}")
            continue

        df = read_sold_file(file_path)
        df["SourceMonth"] = month
        df["SourceFile"] = file_path.name
        frames.append(df)
        print(f"  Loaded {file_path.name}: {len(df):,} rows")

    if not frames:
        raise ValueError(f"No sold files were found in {RAW_DIR}")

    sold = pd.concat(frames, ignore_index=True, sort=False)
    print(f"Combined sold rows before Residential filter: {len(sold):,}")

    if missing_months:
        print(f"Missing months: {', '.join(missing_months)}")
    else:
        print("Missing months: none")

    return sold


def classify_fields(columns):
    rows = []

    for column in columns:
        if column in METADATA_FIELDS:
            category = "metadata"
        elif column in CORE_FIELDS:
            category = "market_analysis_core"
        else:
            category = "market_analysis_other"

        rows.append({"column": column, "field_category": category})

    return pd.DataFrame(rows)


def build_missing_report(df):
    missing_count = df.isna().sum()
    missing_pct = missing_count / len(df) * 100
    rows = []

    for column in df.columns:
        pct = missing_pct[column]
        is_core = column in CORE_FIELDS
        over_threshold = pct > MISSING_DROP_THRESHOLD

        if over_threshold and is_core:
            recommendation = "retain_core_review"
        elif over_threshold:
            recommendation = "drop_candidate"
        else:
            recommendation = "retain"

        rows.append(
            {
                "column": column,
                "missing_count": int(missing_count[column]),
                "missing_pct": round(float(pct), 2),
                "over_90_pct_missing": over_threshold,
                "recommendation": recommendation,
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["missing_pct", "missing_count"], ascending=False
    )


def numeric_distribution_summary(df, fields):
    rows = []

    for field in fields:
        if field not in df.columns:
            rows.append({"field": field, "note": "column_not_found"})
            continue

        series = pd.to_numeric(df[field], errors="coerce").dropna()
        if series.empty:
            rows.append({"field": field, "note": "no_numeric_values"})
            continue

        percentiles = series.quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
        rows.append(
            {
                "field": field,
                "count": int(series.count()),
                "missing_count": int(df[field].isna().sum()),
                "min": series.min(),
                "max": series.max(),
                "mean": series.mean(),
                "median": series.median(),
                "std": series.std(),
                "p01": percentiles.loc[0.01],
                "p05": percentiles.loc[0.05],
                "p25": percentiles.loc[0.25],
                "p50": percentiles.loc[0.5],
                "p75": percentiles.loc[0.75],
                "p95": percentiles.loc[0.95],
                "p99": percentiles.loc[0.99],
                "note": "",
            }
        )

    return pd.DataFrame(rows)


def outlier_report(df, fields):
    rows = []

    for field in fields:
        if field not in df.columns:
            continue

        series = pd.to_numeric(df[field], errors="coerce").dropna()
        if series.empty:
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        low_outliers = int((series < lower_bound).sum())
        high_outliers = int((series > upper_bound).sum())

        rows.append(
            {
                "field": field,
                "iqr_lower_bound": lower_bound,
                "iqr_upper_bound": upper_bound,
                "low_outlier_count": low_outliers,
                "high_outlier_count": high_outliers,
                "total_outlier_count": low_outliers + high_outliers,
                "outlier_pct": round((low_outliers + high_outliers) / len(series) * 100, 2),
                "min": series.min(),
                "max": series.max(),
            }
        )

    return pd.DataFrame(rows)


def save_numeric_plots(df, fields):
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print("matplotlib is not installed; skipping histograms and boxplots.")
        return

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    for field in fields:
        if field not in df.columns:
            continue

        series = pd.to_numeric(df[field], errors="coerce").dropna()
        if series.empty:
            continue

        plt.figure(figsize=(9, 5))
        plt.hist(series, bins=50)
        plt.title(f"{field} Histogram")
        plt.xlabel(field)
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(FIGURE_DIR / f"{field}_histogram.png")
        plt.close()

        plt.figure(figsize=(9, 3))
        plt.boxplot(series, vert=False, showfliers=True)
        plt.title(f"{field} Boxplot")
        plt.xlabel(field)
        plt.tight_layout()
        plt.savefig(FIGURE_DIR / f"{field}_boxplot.png")
        plt.close()


def write_question_summary(sold, residential):
    property_counts = sold["PropertyType"].fillna("Missing").value_counts(dropna=False)
    residential_count = int(
        sold["PropertyType"].astype(str).str.strip().eq("Residential").sum()
    )
    residential_share = residential_count / len(sold) * 100

    close_price = pd.to_numeric(residential["ClosePrice"], errors="coerce")
    list_price = pd.to_numeric(residential["ListPrice"], errors="coerce")
    days_on_market = pd.to_numeric(residential["DaysOnMarket"], errors="coerce")

    valid_price_pairs = residential[close_price.notna() & list_price.notna()].copy()
    valid_price_pairs["ClosePriceNumeric"] = pd.to_numeric(
        valid_price_pairs["ClosePrice"], errors="coerce"
    )
    valid_price_pairs["ListPriceNumeric"] = pd.to_numeric(
        valid_price_pairs["ListPrice"], errors="coerce"
    )

    above_list_pct = (
        (valid_price_pairs["ClosePriceNumeric"] > valid_price_pairs["ListPriceNumeric"]).mean()
        * 100
    )
    below_list_pct = (
        (valid_price_pairs["ClosePriceNumeric"] < valid_price_pairs["ListPriceNumeric"]).mean()
        * 100
    )
    at_list_pct = (
        (valid_price_pairs["ClosePriceNumeric"] == valid_price_pairs["ListPriceNumeric"]).mean()
        * 100
    )

    close_date = pd.to_datetime(residential["CloseDate"], errors="coerce")
    listing_date = pd.to_datetime(residential["ListingContractDate"], errors="coerce")
    purchase_date = pd.to_datetime(residential["PurchaseContractDate"], errors="coerce")
    close_before_listing = int((close_date < listing_date).sum())
    close_before_purchase = int((close_date < purchase_date).sum())

    county_price = (
        residential.assign(ClosePriceNumeric=close_price)
        .dropna(subset=["CountyOrParish", "ClosePriceNumeric"])
        .groupby("CountyOrParish")["ClosePriceNumeric"]
        .median()
        .sort_values(ascending=False)
        .head(10)
    )

    lines = [
        "Week 2-3 Sold Dataset EDA Summary",
        "",
        f"Raw sold rows before filtering: {len(sold):,}",
        f"Residential sold rows after filtering: {len(residential):,}",
        f"Residential share of sold data: {residential_share:.2f}%",
        "",
        "Unique property types found:",
    ]

    for property_type, count in property_counts.items():
        lines.append(f"- {property_type}: {count:,}")

    lines.extend(
        [
            "",
            "Filtering logic applied:",
            "- Keep rows where PropertyType, after trimming whitespace, equals 'Residential'.",
            "",
            "Suggested intern questions:",
            f"- Average close price: ${close_price.mean():,.2f}",
            f"- Median close price: ${close_price.median():,.2f}",
            f"- Median Days on Market: {days_on_market.median():,.0f}",
            f"- Average Days on Market: {days_on_market.mean():,.2f}",
            f"- Sold above list price: {above_list_pct:.2f}%",
            f"- Sold below list price: {below_list_pct:.2f}%",
            f"- Sold at list price: {at_list_pct:.2f}%",
            f"- CloseDate before ListingContractDate rows: {close_before_listing:,}",
            f"- CloseDate before PurchaseContractDate rows: {close_before_purchase:,}",
            "",
            "Top counties by median close price:",
        ]
    )

    for county, median_price in county_price.items():
        lines.append(f"- {county}: ${median_price:,.2f}")

    (REPORT_DIR / "eda_questions_summary.txt").write_text("\n".join(lines))


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    sold = load_sold_data()

    if "PropertyType" not in sold.columns:
        raise ValueError("Sold data does not contain PropertyType")

    residential = sold[
        sold["PropertyType"].astype(str).str.strip().eq("Residential")
    ].copy()

    filtered_output = (
        PROCESSED_DIR / f"crmls_sold_residential_eda_filtered_{START_MONTH}_{END_MONTH}.csv"
    )
    residential.to_csv(filtered_output, index=False)

    structure = pd.DataFrame(
        [
            {
                "dataset": "sold_all_property_types",
                "rows": len(sold),
                "columns": sold.shape[1],
            },
            {
                "dataset": "sold_residential_filtered",
                "rows": len(residential),
                "columns": residential.shape[1],
            },
        ]
    )
    structure.to_csv(REPORT_DIR / "structure_summary.csv", index=False)

    sold.dtypes.astype(str).reset_index(name="dtype").rename(
        columns={"index": "column"}
    ).to_csv(REPORT_DIR / "dtypes_summary.csv", index=False)

    sold["PropertyType"].fillna("Missing").value_counts(dropna=False).rename_axis(
        "PropertyType"
    ).reset_index(name="row_count").to_csv(
        REPORT_DIR / "property_type_counts.csv", index=False
    )

    classify_fields(residential.columns).to_csv(
        REPORT_DIR / "field_classification.csv", index=False
    )
    build_missing_report(residential).to_csv(
        REPORT_DIR / "missing_value_report.csv", index=False
    )
    numeric_distribution_summary(residential, NUMERIC_FIELDS).to_csv(
        REPORT_DIR / "numeric_distribution_summary.csv", index=False
    )
    outlier_report(residential, NUMERIC_FIELDS).to_csv(
        REPORT_DIR / "numeric_outlier_report.csv", index=False
    )
    write_question_summary(sold, residential)
    save_numeric_plots(residential, NUMERIC_FIELDS)

    print("\nSaved Week 2-3 outputs:")
    print(f"  Filtered dataset: {filtered_output}")
    print(f"  Reports folder: {REPORT_DIR}")
    print(f"  Figures folder: {FIGURE_DIR}")


if __name__ == "__main__":
    main()
