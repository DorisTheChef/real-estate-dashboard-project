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

## Script map by week

| Week | Script | Purpose |
| ---- | ------ | ------- |
| Week 0 | `crmls_listed.py` | Extract monthly listing data from the API |
| Week 0 | `crmls_sold.py` | Extract monthly sold data from the API |
| Week 1 | `combine_crmls_monthly.py` | Combine monthly raw CSVs and filter to Residential |
| Weeks 2-3 | `week2_3_sold_eda.py` | Generate sold dataset EDA summaries and outputs |
| Weeks 2-3 | `enrich_mortgage_rates.py` | Merge monthly FRED mortgage rates into sold and listing datasets |
| Weeks 4-5 | `week4_5_clean_sold_data.py` | Clean sold data, add quality flags, and save an analysis-ready CSV |
