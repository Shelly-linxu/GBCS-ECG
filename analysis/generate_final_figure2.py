from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_final_figure2(prediction_path: Path, output_path: Path) -> None:
    """Plot final Figure 2: ECG age and Heart Foundation Heart Age predictions."""
    pred = pd.read_csv(prediction_path)

    specs = [
        (
            "death10_allcause",
            "death10_allcause_ecg_age",
            "death10_allcause_heart_foundation_heart_age",
            "10-year all-cause mortality",
        ),
        (
            "death10_cvd",
            "death10_cvd_ecg_age",
            "death10_cvd_heart_foundation_heart_age",
            "10-year CVD mortality",
        ),
    ]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 12,
            "axes.titlesize": 17,
            "axes.labelsize": 13,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharex=True)
    for ax, (event_col, ecg_col, heart_col, title) in zip(axes, specs):
        sub = pred[[event_col, ecg_col, heart_col]].dropna().copy()
        sub["decile"] = pd.qcut(sub[ecg_col], 10, labels=False, duplicates="drop") + 1
        dec = sub.groupby("decile", as_index=False).agg(
            observed=(event_col, "mean"),
            ecg_age=(ecg_col, "mean"),
            heart_age=(heart_col, "mean"),
        )
        ax.bar(dec["decile"], dec["observed"] * 100, color="#bdbdbd", width=0.72, label="Observed")
        ax.plot(dec["decile"], dec["ecg_age"] * 100, marker="o", lw=2.0, color="#4C78A8", label="ECG age")
        ax.plot(
            dec["decile"],
            dec["heart_age"] * 100,
            marker="o",
            lw=2.0,
            color="#54A24B",
            label="Heart Foundation Heart Age",
        )
        ax.set_xlabel("Decile of ECG age-based predicted risk")
        ax.set_ylabel("10-year risk, %")
        ax.set_title(title)
        ax.set_xticks(range(1, 11))
        ax.grid(axis="y", color="#d9d9d9", linewidth=0.8, alpha=0.7)
        ax.set_axisbelow(True)

    axes[1].legend(frameon=False, fontsize=9, loc="upper left")
    fig.tight_layout(w_pad=2.0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Generate final manuscript Figure 2 from an analysis prediction CSV. "
            "The CSV should contain observed 10-year outcomes and predicted risks "
            "from the ECG-age and Heart Foundation Heart Age models."
        )
    )
    parser.add_argument(
        "--prediction-csv",
        required=True,
        type=Path,
        help=(
            "Path to the local derived prediction CSV. This individual-level file is "
            "not included in the repository."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "manuscript/figures/figure2_predicted_observed_risk_deciles.png",
        help="Output PNG path.",
    )
    args = parser.parse_args()

    plot_final_figure2(args.prediction_csv, args.output)
