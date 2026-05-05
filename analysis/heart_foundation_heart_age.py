from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import argparse
from pathlib import Path
import json
import re

import numpy as np
import pandas as pd


APP_SOURCE_URL = (
    "https://heartagecalculator.heartfoundation.org.au/"
    "_next/static/chunks/app/page-50683d3beafce369.js"
)

TABLE_VARIABLES = {
    "age": "S",
    "smoke": "E",
    "history": "H",
    "diabetes": "K",
    "med": "_",
    "final": "B",
    "cholesterol": "Y",
    "cholesterolAvg": "O",
    "hdl": "q",
    "hdlAvg": "I",
    "sbp": "W",
    "sbpAvg": "G",
}


def _extract_js_object(script: str, var_name: str, start: int = 34000) -> str:
    marker = f",{var_name}="
    marker_index = script.find(marker, start)
    if marker_index == -1:
        raise ValueError(f"Could not find lookup table {var_name} in Heart Age app JavaScript.")
    object_start = script.find("{", marker_index)
    if object_start == -1:
        raise ValueError(f"Could not find object start for lookup table {var_name}.")

    depth = 0
    in_string = False
    escaped = False
    for index in range(object_start, len(script)):
        char = script[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return script[object_start : index + 1]
    raise ValueError(f"Could not find object end for lookup table {var_name}.")


def _parse_js_numeric_object(raw_object: str) -> dict[str, float]:
    quoted_keys = re.sub(
        r"([,{])([A-Za-z_][A-Za-z0-9_]*|-?\d+(?:\.\d+)?):",
        lambda match: f'{match.group(1)}"{match.group(2)}":',
        raw_object,
    )
    normalized_numbers = re.sub(
        r"(?<=[:\[,])(-?)\.(\d+)",
        lambda match: f"{match.group(1)}0.{match.group(2)}",
        quoted_keys,
    )
    parsed = json.loads(normalized_numbers)
    return {str(key): value for key, value in parsed.items()}


def load_lookup_tables(app_js_path: Path) -> dict[str, dict[str, float]]:
    script = app_js_path.read_text(encoding="utf-8")
    tables = {}
    for table_name, var_name in TABLE_VARIABLES.items():
        tables[table_name] = _parse_js_numeric_object(_extract_js_object(script, var_name))
    return tables


def completed_years(age: float) -> int | None:
    if pd.isna(age):
        return None
    return int(np.floor(float(age)))


def calculator_sex(sex_value: float) -> str | None:
    if pd.isna(sex_value):
        return None
    if int(sex_value) == 1:
        return "Male"
    if int(sex_value) == 0:
        return "Female"
    return None


def calculator_group(sex_name: str, age_years: int) -> str:
    if sex_name == "Male":
        if age_years <= 44:
            return "Male-1"
        if age_years <= 59:
            return "Male-2"
        return "Male-3"
    if sex_name == "Female":
        if age_years <= 44:
            return "Female-4"
        if age_years <= 59:
            return "Female-5"
        return "Female-6"
    raise ValueError(f"Unsupported calculator sex: {sex_name}")


def yes_no_key(group: str, value: bool) -> str:
    return f"{group}-{'Yes' if value else 'No'}"


def half_up(value: float, digits: int = 0) -> float:
    if pd.isna(value):
        return np.nan
    quant = Decimal("1") if digits == 0 else Decimal("1").scaleb(-digits)
    return float(Decimal(str(float(value))).quantize(quant, rounding=ROUND_HALF_UP))


def one_decimal_key(group: str, value: float) -> str:
    rounded = Decimal(str(float(value))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{group}-{rounded:.1f}"


def score_key(score: float) -> str:
    if float(score).is_integer():
        return str(int(score))
    return f"{score:.1f}"


def score_row(row: pd.Series, tables: dict[str, dict[str, float]], family_history: bool = False) -> dict[str, float | int | str | bool]:
    age_years = completed_years(row.get("agec"))
    sex_name = calculator_sex(row.get("sex"))
    eligible = age_years is not None and 35 <= age_years <= 75 and sex_name is not None
    if not eligible:
        return {
            "heart_age_eligible": False,
            "heart_age_age_years": age_years,
            "heart_age_sex": sex_name,
            "heart_age_score": np.nan,
            "heart_age_official": np.nan,
            "heart_age_used_sbp_average": np.nan,
            "heart_age_used_cholesterol_average": np.nan,
        }

    group = calculator_group(sex_name, age_years)
    smoke = bool(pd.to_numeric(row.get("smk"), errors="coerce") > 0)
    diabetes = bool(pd.to_numeric(row.get("diab"), errors="coerce") == 1)
    bp_med = bool(pd.to_numeric(row.get("bpdrug"), errors="coerce") == 1)

    age_points = tables["age"].get(str(age_years), 0)
    smoke_points = tables["smoke"].get(yes_no_key(group, smoke), 0)
    history_points = tables["history"].get(yes_no_key(group, family_history), 0)
    diabetes_points = tables["diabetes"].get(yes_no_key(group, diabetes), 0)
    med_points = tables["med"].get(yes_no_key(group, bp_med), 0)

    sbp = pd.to_numeric(row.get("sbp"), errors="coerce")
    sbp_rounded = half_up(sbp, 0)
    if pd.notna(sbp_rounded) and 70 <= sbp_rounded <= 228:
        sbp_key = f"{group}-{int(sbp_rounded)}"
        used_sbp_average = False
    else:
        sbp_average = tables["sbpAvg"].get(f"{sex_name}-{age_years}")
        sbp_key = f"{group}-{int(sbp_average)}"
        used_sbp_average = True
    sbp_points = tables["sbp"].get(sbp_key, 0)

    tchol = pd.to_numeric(row.get("tchol"), errors="coerce")
    hdl = pd.to_numeric(row.get("hdl"), errors="coerce")
    cholesterol_valid = pd.notna(tchol) and pd.notna(hdl) and 2 <= tchol <= 10.5 and 0.1 <= hdl <= 6.4
    if cholesterol_valid:
        cholesterol_key = one_decimal_key(group, tchol)
        hdl_key = one_decimal_key(group, hdl)
        used_cholesterol_average = False
    else:
        cholesterol_average = tables["cholesterolAvg"].get(f"{sex_name}-{age_years}")
        hdl_average = tables["hdlAvg"].get(f"{sex_name}-{age_years}")
        cholesterol_key = one_decimal_key(group, cholesterol_average)
        hdl_key = one_decimal_key(group, hdl_average)
        used_cholesterol_average = True
    cholesterol_points = tables["cholesterol"].get(cholesterol_key, 0)
    hdl_points = tables["hdl"].get(hdl_key, 0)

    score = half_up(
        age_points
        + smoke_points
        + history_points
        + diabetes_points
        + med_points
        + sbp_points
        + cholesterol_points
        + hdl_points,
        1,
    )
    score = round(score * 2) / 2
    heart_age = tables["final"].get(score_key(score), np.nan)

    return {
        "heart_age_eligible": True,
        "heart_age_age_years": age_years,
        "heart_age_sex": sex_name,
        "heart_age_group": group,
        "heart_age_smoking_yes": smoke,
        "heart_age_family_history_yes": family_history,
        "heart_age_diabetes_yes": diabetes,
        "heart_age_bp_med_yes": bp_med,
        "heart_age_used_sbp_average": used_sbp_average,
        "heart_age_used_cholesterol_average": used_cholesterol_average,
        "heart_age_points_age": age_points,
        "heart_age_points_smoke": smoke_points,
        "heart_age_points_history": history_points,
        "heart_age_points_diabetes": diabetes_points,
        "heart_age_points_bp_med": med_points,
        "heart_age_points_sbp": sbp_points,
        "heart_age_points_total_cholesterol": cholesterol_points,
        "heart_age_points_hdl": hdl_points,
        "heart_age_score": score,
        "heart_age_official": heart_age,
    }


def add_heart_age_columns(df: pd.DataFrame, app_js_path: Path, family_history: bool = False) -> pd.DataFrame:
    tables = load_lookup_tables(app_js_path)
    scored = pd.DataFrame([score_row(row, tables, family_history=family_history) for _, row in df.iterrows()])
    return pd.concat([df.reset_index(drop=True), scored.reset_index(drop=True)], axis=1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Add Australian Heart Foundation Heart Age calculator outputs to a local "
            "ECG-age prediction CSV. Cohort-level input/output files are not included "
            "in this repository."
        )
    )
    parser.add_argument("--input-csv", required=True, type=Path, help="Local ECG-age prediction CSV.")
    parser.add_argument("--app-js", required=True, type=Path, help="Downloaded Heart Age app JavaScript bundle.")
    parser.add_argument("--output-csv", required=True, type=Path, help="Output CSV with Heart Age columns.")
    args = parser.parse_args()

    df = pd.read_csv(args.input_csv)
    out = add_heart_age_columns(df, app_js_path=args.app_js)
    columns = [
        "standard_obje_id",
        "agec",
        "sex",
        "smk",
        "diab",
        "bpdrug",
        "sbp",
        "tchol",
        "hdl",
        "heart_age_eligible",
        "heart_age_age_years",
        "heart_age_sex",
        "heart_age_group",
        "heart_age_smoking_yes",
        "heart_age_family_history_yes",
        "heart_age_diabetes_yes",
        "heart_age_bp_med_yes",
        "heart_age_used_sbp_average",
        "heart_age_used_cholesterol_average",
        "heart_age_score",
        "heart_age_official",
    ]
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    out[columns].to_csv(args.output_csv, index=False)
    print(
        {
            "source_url": APP_SOURCE_URL,
            "output": str(args.output_csv),
            "rows": int(len(out)),
            "eligible_rows": int(out["heart_age_eligible"].fillna(False).sum()),
            "family_history_assumption": "No for all participants unless a cohort variable is added later.",
        }
    )


if __name__ == "__main__":
    main()
