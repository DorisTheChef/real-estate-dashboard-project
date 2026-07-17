"""Week 4-5, stage 2: resolve every data-quality flag and produce the final dataset.

This script replays, as a reproducible pipeline, the decisions made in
``notebooks/week4_5_flagged_rows_investigation.ipynb``. The notebook documents
HOW each issue was investigated; this script records WHAT was done and WHY,
so the full pipeline can be rerun from the command line:

    combine_crmls_monthly.py -> enrich_mortgage_rates.py
        -> week4_5_clean_sold_data.py -> week4_5_resolve_flags.py

Guiding principles (established during the investigation):
- Delete a row only when independent fields AGREE the property is not a
  California sale (or when the record is unusable for sold-market analysis).
- Repair a value only when the correction is unambiguous and verifiable.
- Otherwise set the corrupted field to missing — never guess.
- Outlier flags (price/area/price-per-sqft) are kept as flags: those rows are
  valid luxury / multi-unit sales, not errors.
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

INPUT_FILE = PROCESSED_DIR / "crmls_sold_cleaned_before_ca_filter_202401_202606.csv"
OUTPUT_FILE = PROCESSED_DIR / "crmls_sold_final_202401_202606.csv"

DATE_FIELDS = [
    "CloseDate",
    "PurchaseContractDate",
    "ListingContractDate",
    "ContractStatusChangeDate",
]

# --- Row deletions (verified case by case in the notebook) -------------------

# Properties confirmed to be OUTSIDE California. Each was cross-checked on
# four independent fields (City, CountyOrParish, PostalCode, coordinates),
# which all agree on the same non-CA location. Their StateOrProvince says
# "CA", which is why the state filter alone could not catch them.
NON_CALIFORNIA_LISTING_KEYS = [
    1093448041,  # Ensenada, Mexico — County "Foreign Country", zip 22880
    1093445263,  # Ensenada, Mexico — City "Outside Ca", zip 22870
    1099893565,  # Ensenada, Mexico — County "Foreign Country", zip 22785
    1092500840,  # Ensenada, Mexico — County "Other State", zip 22880
    1123830005,  # Prescott Valley, AZ — zip 86314 agrees with AZ coordinates
    1109528025,  # Las Vegas, NV — zip 89139 agrees with NV coordinates
    1146057687,  # Henderson, NV — County Clark, zip 89011
]

# The positive-longitude row whose latitude (40) contradicts its city
# (East Los Angeles, ~34): the coordinate is unreliable even after a sign
# flip, so it is treated as missing instead of flipped.
EAST_LA_BAD_COORD_KEY = 1084837618

# --- Zip code repairs ---------------------------------------------------------

# Single-edit typos: each recorded value maps unambiguously to a real zip of
# the row's city (wrong first digit, transposed digits, or one extra digit).
ZIP_FIXES = {
    "01010": "91010",   # Duarte
    "80802": "90802",   # Long Beach
    "980803": "90803",  # Long Beach (extra digit)
    "97381": "91381",   # Valencia
    "96962": "96062",   # Millville
    "83551": "93551",   # Palmdale
    "83536": "93536",   # Lancaster
    "82630": "92630",   # Lake Forest
    "82553": "92553",   # Moreno Valley
    "73465": "93465",   # Templeton
    "49603": "94603",   # Oakland (transposed 49 -> 94)
    "39534": "93534",   # Lancaster (transposed 39 -> 93)
    "22677": "92677",   # Laguna Niguel
    "19351": "91351",   # Canyon Country (transposed 19 -> 91)
    "06021": "96021",   # Corning
    "02637": "92637",   # Laguna Woods
    "02336": "92336",   # Fontana
    "98245": "92845",   # Garden Grove (transposed 8 <-> 2)
}

# Systematically corrupted values with no recoverable typo pattern. The true
# zips were recovered by reverse-geocoding each row's verified coordinates
# (OpenStreetMap Nominatim) — see the investigation notebook for the process.
# Hardcoded here so the script stays offline-reproducible.
ZIP_RECOVERED_FROM_COORDS = {
    "20448": "92377",  # Rialto (7 rows, systematic feed value)
    "20205": "92377",  # Rialto
    "20536": "91761",  # Ontario (7 rows, systematic feed value)
    "88888": "92880",  # Corona (placeholder value)
    "05073": "95973",  # Chico (ambiguous typo, resolved by coordinates)
}

# --- Contract date repairs ----------------------------------------------------

# Year typos in PurchaseContractDate, found among purchase-before-listing
# rows with multi-year gaps. Each correction is verified: the repaired
# timeline becomes fully consistent, and for the Carmel row the listing-to-
# purchase span exactly matches its recorded DaysOnMarket of 151.
PURCHASE_DATE_FIXES = {
    1041330748: "2023-11-16",  # Millbrae: 1923 -> 2023 (century typo)
    1119467517: "2025-06-13",  # Los Angeles: 2023 -> 2025 (matches listing date)
    1079404126: "2025-01-10",  # Carmel: 2024 -> 2025 (validated by DOM = 151)
}


def load_data():
    """Load the stage-1 cleaned dataset with analysis-friendly dtypes."""
    df = pd.read_csv(
        INPUT_FILE, low_memory=False, dtype={"PostalCode": "string"}
    )
    for field in DATE_FIELDS:
        if field in df.columns:
            df[field] = pd.to_datetime(df[field], errors="coerce")
    print(f"Loaded: {len(df):,} rows x {df.shape[1]} columns")
    return df


def filter_california(df):
    """Keep explicit CA rows, plus missing-state rows whose coordinates fall
    inside the California bounding box (the single such row was also manually
    verified as a Los Angeles County sale in the notebook)."""
    state = df["StateOrProvince"].astype("string").str.strip().str.upper()
    missing_state = state.isna() | state.eq("")

    plausible_ca_coordinates = (
        df["Latitude"].between(32, 42, inclusive="both")
        & df["Longitude"].between(-125, -114, inclusive="both")
    )
    keep = state.isin(["CA", "CALIFORNIA"]) | (missing_state & plausible_ca_coordinates)

    removed = int((~keep).sum())
    df = df.loc[keep].copy()
    print(f"State filter: removed {removed} non-CA rows -> {len(df):,}")
    return df


def drop_empty_flag_columns(df):
    """Drop quality-flag columns with zero hits — an all-False column carries
    no information (the fact that the check ran is documented in the Week 4-5
    flag_counts report)."""
    empty_flags = [
        column for column in df.columns
        if column.endswith("_flag")
        and not df[column].fillna(False).astype(bool).any()
    ]
    df = df.drop(columns=empty_flags)
    print(f"Dropped empty flag columns: {empty_flags}")
    return df


def remove_invalid_close_price(df):
    """Delete rows with ClosePrice <= 0. Close price is essential to
    sold-market analysis; the single such row was a data-entry gap (a real
    Temple City sale whose price was never recorded)."""
    invalid = df["ClosePrice"].le(0).fillna(False)
    df = df.loc[~invalid].copy()
    print(f"Invalid ClosePrice rows deleted: {int(invalid.sum())} -> {len(df):,}")
    return df


def fix_coordinates(df):
    """Repair or clear corrupted coordinates while keeping the rows.

    - (0, 0) coordinates are system placeholders -> set to missing.
    - Positive longitudes are dropped minus signs: flip the sign when the
      flipped point lands inside California AND the latitude is consistent;
      otherwise set the pair to missing.
    - Remaining implausible coordinates on verified-CA rows are left as-is;
      they stay covered by implausible_coordinate_flag for map exclusion.
    """
    zero = df["Latitude"].eq(0) | df["Longitude"].eq(0)
    df.loc[zero, ["Latitude", "Longitude"]] = pd.NA
    print(f"Zero coordinates set to missing: {int(zero.sum())} rows")

    positive = df["Longitude"].gt(0).fillna(False)
    flippable = (
        positive
        & df["Latitude"].between(32, 42)
        & (-df["Longitude"]).between(-125, -114)
        & ~df["ListingKey"].eq(EAST_LA_BAD_COORD_KEY)
    )
    df.loc[flippable, "Longitude"] = -df.loc[flippable, "Longitude"]
    unrecoverable = positive & ~flippable
    df.loc[unrecoverable, ["Latitude", "Longitude"]] = pd.NA
    print(
        f"Positive longitude: {int(flippable.sum())} recovered by sign flip, "
        f"{int(unrecoverable.sum())} set to missing"
    )
    return df


def remove_non_california_properties(df):
    """Delete the 7 properties verified to be outside California (4 in
    Ensenada MX, 1 Prescott Valley AZ, 1 Las Vegas NV, 1 Henderson NV).
    Their zip codes and coordinates agree on the same non-CA location, so
    the mislabeled StateOrProvince="CA" is the field that is wrong."""
    mask = df["ListingKey"].isin(NON_CALIFORNIA_LISTING_KEYS)
    df = df.loc[~mask].copy()
    print(f"Non-CA properties deleted: {int(mask.sum())} -> {len(df):,}")
    return df


def repair_zip_codes(df):
    """Repair corrupted zip codes on verified-CA rows (City, County, and
    coordinates all agree on California; only the zip disagreed)."""
    zips = df["PostalCode"].astype("string").str.strip()

    typo = zips.isin(ZIP_FIXES)
    df.loc[typo, "PostalCode"] = zips[typo].map(ZIP_FIXES)

    recovered = zips.isin(ZIP_RECOVERED_FROM_COORDS)
    df.loc[recovered, "PostalCode"] = zips[recovered].map(ZIP_RECOVERED_FROM_COORDS)

    print(
        f"Zip codes repaired: {int(typo.sum())} typo fixes, "
        f"{int(recovered.sum())} recovered from coordinates"
    )
    return df


def resolve_timeline_issues(df):
    """Resolve every date-consistency violation. The sales themselves are
    real (close dates and prices are valid), so rows are kept and only the
    impossible date fields are repaired or cleared.

    - listing_after_close (68): the listing date is the MLS entry date, not
      a real listing date (median 5 days after close, DOM often 0) -> clear.
    - purchase_after_close (240): signing after closing is impossible; same
      after-the-fact entry pattern -> clear the purchase date.
    - purchase-before-listing: 3 rows are verifiable year typos in the
      purchase date -> repair; the remaining ~222 follow the backfilled-entry
      pattern (listing date after the purchase, often equal to the close
      date, DOM 0) -> clear the listing date.
    """
    listing_after_close = df["listing_after_close_flag"].fillna(False).astype(bool)
    purchase_after_close = df["purchase_after_close_flag"].fillna(False).astype(bool)

    df.loc[listing_after_close, "ListingContractDate"] = pd.NaT
    print(f"listing_after_close: listing date cleared on {int(listing_after_close.sum())} rows")

    df.loc[purchase_after_close, "PurchaseContractDate"] = pd.NaT
    print(f"purchase_after_close: purchase date cleared on {int(purchase_after_close.sum())} rows")

    for key, fixed_date in PURCHASE_DATE_FIXES.items():
        df.loc[df["ListingKey"].eq(key), "PurchaseContractDate"] = pd.Timestamp(fixed_date)
    print(f"Purchase-date year typos repaired: {len(PURCHASE_DATE_FIXES)}")

    backfilled = (
        df["PurchaseContractDate"].notna()
        & df["ListingContractDate"].notna()
        & df["PurchaseContractDate"].lt(df["ListingContractDate"])
    )
    df.loc[backfilled, "ListingContractDate"] = pd.NaT
    print(f"Backfilled entries: listing date cleared on {int(backfilled.sum())} rows")
    return df


def clear_invalid_numerics(df):
    """Set impossible numeric values to missing (never guess a replacement).

    - DaysOnMarket < 0 (51): the dates on these rows are internally
      consistent, so only the source system's DOM counter is corrupted.
    - LivingArea = 0 (165): a "not recorded" placeholder, mostly on luxury
      homes and mobile homes; a zero area would poison price-per-sqft.
    """
    negative_dom = df["DaysOnMarket"].lt(0).fillna(False)
    df.loc[negative_dom, "DaysOnMarket"] = pd.NA
    print(f"Negative DaysOnMarket set to missing: {int(negative_dom.sum())} rows")

    zero_area = df["LivingArea"].le(0).fillna(False)
    df.loc[zero_area, "LivingArea"] = pd.NA
    print(f"LivingArea=0 set to missing: {int(zero_area.sum())} rows")
    return df


def verify(df):
    """Assert the invariants the investigation established."""
    listing, purchase, close = (
        df["ListingContractDate"], df["PurchaseContractDate"], df["CloseDate"],
    )
    checks = {
        "listing > close": int((listing.notna() & close.notna() & (listing > close)).sum()),
        "purchase > close": int((purchase.notna() & close.notna() & (purchase > close)).sum()),
        "purchase < listing": int((purchase.notna() & listing.notna() & (purchase < listing)).sum()),
        "ClosePrice <= 0": int(df["ClosePrice"].le(0).fillna(False).sum()),
        "negative DOM": int(df["DaysOnMarket"].lt(0).fillna(False).sum()),
        "LivingArea = 0": int(df["LivingArea"].le(0).fillna(False).sum()),
        "positive longitude": int(df["Longitude"].gt(0).fillna(False).sum()),
    }
    zips = pd.to_numeric(df["PostalCode"].astype("string").str.slice(0, 5), errors="coerce")
    checks["non-CA zip"] = int((~zips.between(90001, 96162) & zips.notna()).sum())

    print("\n--- Verification (all should be 0) ---")
    for name, count in checks.items():
        status = "OK " if count == 0 else "FAIL"
        print(f"{status} {name}: {count}")
    return all(count == 0 for count in checks.values())


def main():
    df = load_data()
    df = filter_california(df)
    df = drop_empty_flag_columns(df)
    df = remove_invalid_close_price(df)
    df = fix_coordinates(df)
    df = remove_non_california_properties(df)
    df = repair_zip_codes(df)
    df = resolve_timeline_issues(df)
    df = clear_invalid_numerics(df)

    passed = verify(df)

    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved: {OUTPUT_FILE}")
    print(f"Final: {len(df):,} rows x {df.shape[1]} columns")
    if not passed:
        raise SystemExit("Verification failed — inspect the FAIL lines above.")


if __name__ == "__main__":
    main()
