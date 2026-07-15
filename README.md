# Real Estate Dashboard Project
# CRMLS Market Analytics

## Overview

This project is part of the IDX Exchange Data Analyst Internship Program. The objective is to analyze California real estate market trends using CRMLS (California Regional Multiple Listing Service) data and develop automated reporting workflows and interactive Tableau dashboards.

The project focuses on understanding the complete analytics pipeline, from data acquisition and preparation to visualization and reporting.

---

## Objectives

* Explore and understand CRMLS listing and sales datasets
* Analyze key California real estate market trends
* Build automated data preparation workflows using Python
* Practice SQL-based data analysis and reporting
* Develop Tableau dashboards for market intelligence and performance reporting
* Recreate and understand production reporting workflows used by IDX Exchange

---

## Data Source

This project uses data obtained from the California Regional Multiple Listing Service (CRMLS).

**Note:** Raw source data files are not included in this repository.

---

## Technologies

* Python
* SQL
* Tableau
* Git & GitHub
* FileZilla
* CRMLS Real Estate Data

---

## Repository Structure

```text
real-estate-dashboard-project/

├── README.md
├── data/              # Local only; ignored by Git
├── notebooks/
├── python/
├── sql/
├── tableau/
└── screenshots/
```

### Folder Description

| Folder      | Description                                 |
| ----------- | ------------------------------------------- |
| data        | Local raw, processed, and report CSV files; not committed |
| notebooks   | Jupyter notebooks for EDA and analysis      |
| python      | Data processing and analysis scripts        |
| sql         | SQL queries used for reporting and analysis |
| tableau     | Tableau workbooks and dashboard resources   |
| screenshots | Dashboard screenshots and visual outputs    |

---

## Current Progress

### Week 0

* Reviewed the IDX Exchange internship handbook and Week 0 requirements
* Downloaded CRMLS monthly listing and sold CSV files from the provided FTP source
* Reviewed the monthly CRMLS file naming pattern:
  * `CRMLSListingYYYYMM.csv`
  * `CRMLSSoldYYYYMM.csv`
* Reviewed API extraction scripts for listing and sold data

### Week 1

* Built a monthly concatenation workflow in `python/combine_crmls_monthly.py`
* Combined listing and sold CSVs from January 2024 through June 2026
* Preferred `_filled.csv` files when available and dropped the two extra filled columns
* Filtered both combined datasets to `PropertyType == "Residential"`
* Saved combined residential listing and sold datasets to `data/processed/`

### Weeks 2-3

* Created EDA notebooks for sold and listing datasets:
  * `notebooks/week2_3_sold_eda.ipynb`
  * `notebooks/week2_3_listing_eda.ipynb`
* Reviewed dataset shape, column data types, property types, and missing values
* Flagged columns with more than 90% missing values
* Created numeric summaries and outlier checks for key fields such as price, living area, bedrooms, bathrooms, days on market, and year built
* Answered EDA questions about property type share, close prices, days on market, sale-to-list outcomes, date consistency, and county median prices
* Enriched listing and sold datasets with monthly 30-year fixed mortgage rates from FRED using `python/enrich_mortgage_rates.py`
* Created `notebooks/mortgage_rate_vs_sales_volume.ipynb` to explore the relationship between mortgage rates and residential sold volume

### Weeks 4-5

* Created `python/week4_5_clean_sold_data.py` to prepare an analysis-ready sold dataset
* Converted date fields and numeric fields to analysis-friendly data types
* Dropped columns with more than 90% missing values
* Dropped unnecessary metadata fields while retaining fields useful for Market Analysis and Competitive Analysis
* Added invalid numeric, date consistency, and geographic quality flag columns
* Saved the cleaned sold dataset and cleaning summary reports to local `data/` folders
* Created `notebooks/week4_5_flagged_rows_investigation.ipynb` to investigate and resolve every flagged category:
  * Filtered out non-California records, including mislabeled properties in Mexico, Arizona, and Nevada found by cross-checking city, county, zip code, and coordinates
  * Repaired corrupted coordinates (sign-flip recovery) and zip codes (typo correction plus reverse geocoding), and fixed year typos in contract dates
  * Set impossible values to missing instead of guessing: zero living areas, negative days on market, and dates that violate the listing-purchase-close timeline
  * Kept price and size outliers flagged for review since they represent valid luxury and multi-unit sales
  * Saved the final analysis-ready dataset (447,954 rows) with a per-flag decision log documenting every transformation

---

## Key Project Files

| Week | File | Purpose |
| ---- | ---- | ------- |
| Week 0 | `python/crmls_listed.py` | Extract monthly listing data from the API |
| Week 0 | `python/crmls_sold.py` | Extract monthly sold data from the API |
| Week 1 | `python/combine_crmls_monthly.py` | Combine monthly CRMLS listing and sold CSVs |
| Weeks 2-3 | `python/week2_3_sold_eda.py` | Script version of sold dataset EDA |
| Weeks 2-3 | `python/enrich_mortgage_rates.py` | Add FRED 30-year mortgage rates to MLS data |
| Weeks 2-3 | `notebooks/week2_3_sold_eda.ipynb` | Sold dataset EDA notebook |
| Weeks 2-3 | `notebooks/week2_3_listing_eda.ipynb` | Listing dataset EDA notebook |
| Weeks 2-3 | `notebooks/week2_3_sold_eda_questions.ipynb` | Sold dataset EDA question notebook |
| Weeks 2-3 | `notebooks/week2_3_listing_raw_eda_questions.ipynb` | Listing raw data EDA question notebook |
| Weeks 2-3 | `notebooks/mortgage_rate_vs_sales_volume.ipynb` | Mortgage rate vs. sold volume analysis |
| Weeks 4-5 | `python/week4_5_clean_sold_data.py` | Clean sold data and create analysis-ready output |
| Weeks 4-5 | `notebooks/week4_5_flagged_rows_investigation.ipynb` | Investigate and resolve all data quality flags, produce the final dataset |

---

## Key Metrics

Examples of metrics analyzed in this project include:

* Median Sales Price
* Homes Sold
* Days on Market
* Price per Square Foot
* Year-over-Year Growth
* Listing Agent Performance
* Office Performance
* Regional Market Trends

---

## Future Work

* Recreate market analysis dashboards from scratch
* Develop additional visualizations and reporting features
* Automate data refresh workflows
* Build reproducible reporting pipelines
* Compare market performance across California regions

---

## Author

Baixue Zhang

Data Analyst Intern | IDX Exchange
