# python

This folder contains Python data processing and analysis scripts for the Real Estate Dashboard Project.

Recommended contents:

- ETL scripts
- data preparation workflows
- exploratory data analysis notebooks or scripts
- automation utilities

## Combine monthly CRMLS files

Run this script from the project root to combine all monthly listing and sold CSVs
from January 2024 through June 2026:

```bash
python python/combine_crmls_monthly.py
```

The script reads files from `data/raw/`, filters both datasets to
`PropertyType == "Residential"`, and writes combined CSV outputs to
`data/processed/`.

Files ending in `_filled.csv` are preferred when present. Those files contain
two extra columns at the end, so the script drops the final two columns before
concatenating monthly files.

## Enrich with mortgage rates

Run this script from the project root to fetch the FRED `MORTGAGE30US` series,
average weekly observations to monthly rates, and merge the monthly rate onto
the combined sold and listings datasets:

```bash
python python/enrich_mortgage_rates.py
```

Sold data is joined by `CloseDate`; listing data is joined by
`ListingContractDate`.

## Resolve quality flags

Run this script from the project root after `week4_5_clean_sold_data.py` to
apply every flag resolution decided in the Week 4-5 investigation notebook
(state filter, verified non-CA deletions, coordinate and zip repairs, date
fixes, and missing-value replacements), verify the resulting invariants, and
save the final analysis-ready dataset:

```bash
python python/week4_5_resolve_flags.py
```

The full pipeline from raw monthly CSVs to the final dataset is:

```bash
python python/combine_crmls_monthly.py
python python/enrich_mortgage_rates.py
python python/week4_5_clean_sold_data.py
python python/week4_5_resolve_flags.py
```

## Feature engineering

Run this script from the project root after `week4_5_resolve_flags.py` to
engineer the market metrics (sale-to-list ratio, close-to-original-list
ratio, price per square foot, close year/month/YrMo, listing-to-contract and
contract-to-close days), assign school districts by spatial join, and build
the segment summary tables:

```bash
python python/week6_feature_engineering.py
```

This step requires GeoPandas and the California School District Areas 2024-25
shapefile in `data/raw/school_districts/`. It saves the feature dataset to
`data/processed/` and segment summaries to `data/reports/week6_feature_engineering/`.

## Script map by week

| Week | Script | Purpose |
| ---- | ------ | ------- |
| Week 0 | `crmls_listed.py` | Extract monthly listing data from the API |
| Week 0 | `crmls_sold.py` | Extract monthly sold data from the API |
| Week 1 | `combine_crmls_monthly.py` | Combine monthly raw CSVs and filter to Residential |
| Weeks 2-3 | `week2_3_sold_eda.py` | Generate sold dataset EDA summaries and outputs |
| Weeks 2-3 | `enrich_mortgage_rates.py` | Merge monthly FRED mortgage rates into sold and listing datasets |
| Weeks 4-5 | `week4_5_clean_sold_data.py` | Clean sold data, add quality flags, and save an analysis-ready CSV |
| Weeks 4-5 | `week4_5_resolve_flags.py` | Resolve every quality flag (repairs, missing values, verified deletions) and save the final dataset |
| Week 6 | `week6_feature_engineering.py` | Engineer market metrics, assign school districts via spatial join, and build segment summaries |
