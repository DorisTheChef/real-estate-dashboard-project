# python

This folder contains Python data processing and analysis scripts for the Real Estate Dashboard Project.

Recommended contents:

- ETL scripts
- data preparation workflows
- exploratory data analysis notebooks or scripts
- automation utilities

## Combine monthly CRMLS files

Run this script from the project root to combine all monthly listing and sold CSVs
from January 2024 through April 2026:

```bash
python python/combine_crmls_monthly.py
```

The script reads files from `data/raw/`, filters both datasets to
`PropertyType == "Residential"`, and writes combined CSV outputs to
`data/processed/`.

Files ending in `_filled.csv` are preferred when present. Those files contain
two extra columns at the end, so the script drops the final two columns before
concatenating monthly files.
