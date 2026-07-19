"""Week 7: IQR-based outlier detection and filtered analysis dataset.

Adds statistical outlier flags to the Week 6 feature dataset using the
Interquartile Range (IQR) method, then saves two datasets:
- a full FLAGGED dataset (every row kept, IQR flags added), and
- a clean FILTERED dataset (extreme records removed for typical-market analysis).

    week6_feature_engineering.py -> week7_outlier_detection.py

Multiplier choice (k=3.0, not the textbook 1.5): ClosePrice, LivingArea, and
DaysOnMarket are all right-skewed, so the standard 1.5x fences push the upper
bound too low and flag ~7% of records, misclassifying normal high-end homes as
outliers. The 3.0x "extreme outlier" fences flag ~1-3% per field and isolate
genuinely extreme records. This follows the tiered approach the handbook asks
for: business-rule invalid values were already handled in Weeks 4-6; the IQR
step flags statistically extreme (but potentially valid) records without
deleting them, and the filtered dataset is separate from the raw records.
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "data" / "reports" / "week7_outlier_detection"

INPUT_FILE = PROCESSED_DIR / "crmls_sold_features_202401_202606.csv"
FLAGGED_FILE = PROCESSED_DIR / "crmls_sold_flagged_202401_202606.csv"
FILTERED_FILE = PROCESSED_DIR / "crmls_sold_filtered_202401_202606.csv"

# 3.0 marks "extreme" outliers (1.5 marks "mild"); see module docstring.
IQR_K = 3.0
IQR_FIELDS = ["ClosePrice", "LivingArea", "DaysOnMarket"]


def load_data():
    """Load the Week 6 feature-engineered dataset."""
    df = pd.read_csv(INPUT_FILE, low_memory=False)
    print(f"Loaded: {len(df):,} rows x {df.shape[1]} columns")
    return df


def iqr_bounds(series, k=IQR_K):
    """IQR fences: [Q1 - k*IQR, Q3 + k*IQR]."""
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    return q1 - k * iqr, q3 + k * iqr


def add_iqr_flags(df):
    """Add a k=3.0 IQR outlier flag per field, plus a combined 'any' flag.

    These IQR flags are distinct from the 99th-percentile outlier flags added
    in Week 4-5; both methods coexist so they can be compared. Rows are never
    deleted here — only flagged.
    """
    flag_cols = []
    for col in IQR_FIELDS:
        lower, upper = iqr_bounds(df[col].dropna())
        lower = max(lower, 0)  # a negative price/size/DOM lower fence is meaningless
        flag = f"{col.lower()}_iqr_outlier_flag"
        df[flag] = ((df[col] < lower) | (df[col] > upper)).fillna(False)
        flag_cols.append(flag)
        print(f"{flag}: {int(df[flag].sum()):,} rows "
              f"({df[flag].mean() * 100:.2f}%)  fences [{lower:,.0f}, {upper:,.0f}]")

    # A sale is atypical if ANY of the three fields is an outlier.
    df["iqr_outlier_any_flag"] = df[flag_cols].any(axis=1)
    print(f"iqr_outlier_any_flag (union): {int(df['iqr_outlier_any_flag'].sum()):,} rows "
          f"({df['iqr_outlier_any_flag'].mean() * 100:.2f}%)")
    return df


def build_comparison(full, filtered):
    """Before/after comparison of dataset size and median values.

    Medians barely move because they resist outliers by construction — the
    real distortion is in the means, so both are reported.
    """
    metrics = {
        "rows": ("size", None),
        "median_close_price": ("median", "ClosePrice"),
        "median_living_area": ("median", "LivingArea"),
        "median_dom": ("median", "DaysOnMarket"),
        "median_price_per_sqft": ("median", "price_per_sqft"),
        "mean_close_price": ("mean", "ClosePrice"),
        "mean_price_per_sqft": ("mean", "price_per_sqft"),
    }

    def value(df, agg, col):
        if agg == "size":
            return len(df)
        return getattr(df[col], agg)()

    compare = pd.DataFrame({
        "full_flagged": [value(full, a, c) for a, c in metrics.values()],
        "clean_filtered": [value(filtered, a, c) for a, c in metrics.values()],
    }, index=list(metrics.keys()))
    compare["pct_change"] = (
        (compare["clean_filtered"] - compare["full_flagged"])
        / compare["full_flagged"] * 100
    ).round(2)
    return compare.round(2)


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    sold = load_data()
    sold = add_iqr_flags(sold)

    # Full flagged dataset: every row kept.
    sold.to_csv(FLAGGED_FILE, index=False)

    # Clean filtered dataset: rows flagged on ANY field removed.
    filtered = sold.loc[~sold["iqr_outlier_any_flag"]].copy()
    filtered.to_csv(FILTERED_FILE, index=False)

    comparison = build_comparison(sold, filtered)
    comparison.to_csv(REPORT_DIR / "before_after_comparison.csv")

    print(f"\nRows removed: {len(sold) - len(filtered):,} "
          f"({(1 - len(filtered) / len(sold)) * 100:.2f}%)")
    print(f"Saved flagged : {FLAGGED_FILE}  ({sold.shape[0]:,} rows)")
    print(f"Saved filtered: {FILTERED_FILE}  ({filtered.shape[0]:,} rows)")
    print("\n--- Before / after comparison ---")
    print(comparison.to_string())


if __name__ == "__main__":
    main()
