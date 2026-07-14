#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-dimensional overlap analysis for 3D-SCM.

The three dimensions are independent. For every group produced by any
dimension, a dimension recognizes the group when all its devices are contained
in at least one group produced by that dimension. This is the criterion used
for Table VI of the submitted paper.
"""

from __future__ import annotations

import argparse
from typing import Iterable, List

import pandas as pd


CATEGORY_ORDER = [
    "D1&D2&D3",
    "D1&D2\\D3",
    "D1&D3\\D2",
    "D2&D3\\D1",
    "D1_only",
    "D2_only",
    "D3_only",
]


def parse_group(value: str) -> frozenset[str]:
    return frozenset(x.strip() for x in str(value).split("|") if x.strip())


def load_groups(path: str, devices_col: str = "Devices") -> List[frozenset[str]]:
    df = pd.read_csv(path)
    if devices_col not in df.columns:
        raise ValueError(f"{path} is missing required column: {devices_col}")
    return [parse_group(x) for x in df[devices_col]]


def recognized_by(group: frozenset[str], groups: Iterable[frozenset[str]]) -> bool:
    return any(group.issubset(other) for other in groups)


def classify_group(d1: bool, d2: bool, d3: bool) -> str:
    mapping = {
        (True, True, True): "D1&D2&D3",
        (True, True, False): "D1&D2\\D3",
        (True, False, True): "D1&D3\\D2",
        (False, True, True): "D2&D3\\D1",
        (True, False, False): "D1_only",
        (False, True, False): "D2_only",
        (False, False, True): "D3_only",
    }
    return mapping[(d1, d2, d3)]


def summarize_overlap(details: pd.DataFrame) -> pd.DataFrame:
    """Return the seven Table VI overlap categories in a stable order."""
    return (
        details.groupby("Category")
        .agg(Groups=("Devices", "count"))
        .reindex(CATEGORY_ORDER, fill_value=0)
        .reset_index()
    )


def run_overlap_analysis(
    dim1_csv: str,
    dim2_csv: str,
    dim3_csv: str,
    output_csv: str | None = None,
    summary_output_csv: str | None = None,
) -> pd.DataFrame:
    dim1_groups = load_groups(dim1_csv)
    dim2_groups = load_groups(dim2_csv)
    dim3_groups = load_groups(dim3_csv)

    labeled = (
        [("D1", group) for group in dim1_groups]
        + [("D2", group) for group in dim2_groups]
        + [("D3", group) for group in dim3_groups]
    )

    rows = []
    for source, group in labeled:
        d1 = recognized_by(group, dim1_groups)
        d2 = recognized_by(group, dim2_groups)
        d3 = recognized_by(group, dim3_groups)
        rows.append(
            {
                "Source": source,
                "Category": classify_group(d1, d2, d3),
                "Num_Devices": len(group),
                "Devices": "|".join(sorted(group)),
            }
        )

    out = pd.DataFrame(rows)
    summary = summarize_overlap(out)
    print(summary.to_string(index=False))

    if output_csv:
        out.to_csv(output_csv, index=False, encoding="utf-8-sig")
        print(f"[+] detailed overlap rows -> {output_csv}")
    if summary_output_csv:
        summary.to_csv(summary_output_csv, index=False, encoding="utf-8-sig")
        print(f"[+] overlap summary -> {summary_output_csv}")

    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze overlap among independent Dimension I/II/III groups."
    )
    parser.add_argument("--dim1-csv", required=True)
    parser.add_argument("--dim2-csv", required=True)
    parser.add_argument("--dim3-csv", required=True)
    parser.add_argument("--output-csv", default=None)
    parser.add_argument("--summary-output-csv", default=None)
    args = parser.parse_args()
    run_overlap_analysis(
        args.dim1_csv,
        args.dim2_csv,
        args.dim3_csv,
        args.output_csv,
        args.summary_output_csv,
    )


if __name__ == "__main__":
    main()
