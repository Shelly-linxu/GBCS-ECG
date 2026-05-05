# GBCS-ECG

ECG-derived age prediction and mortality risk analysis in the Guangzhou Biobank Cohort Study.

This repository contains code and shareable analysis artifacts for the final ECG-age manuscript version.

## Repository Contents

- `analysis/`: analysis and helper scripts for ECG-age model construction, Heart Foundation Heart Age implementation, final figure generation, and calculator cleanup.
- `manuscript/`: final manuscript DOCX and final ECG-age figures.
- `supplementary/calculator/`: ECG-age-only supplementary calculator workbook.
- `supplementary/model_metadata/`: model validation and feature metadata needed to audit the ECG-age model and calculator.

## Data Availability

Individual-level cohort data and raw ECG files are not included in this repository. The analysis scripts expect local cohort files with the same harmonized variable names used in the manuscript analysis.

## Software

The ECG-age analysis artifact records Python 3.9.6. Key Python packages used for model development included pandas, NumPy, scikit-learn, XGBoost, LightGBM, lifelines, statsmodels, matplotlib, openpyxl, and joblib.

## Supplementary Calculator

The final supplementary workbook is:

`supplementary/calculator/ecg_age_score_calculator.xlsx`

It calculates ECG age from 174 structured ECG variables using the exported LightGBM tree formulas. Residual ECG-age acceleration outputs are excluded from this final workbook.
