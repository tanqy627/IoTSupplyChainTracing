#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
overlap_analysis.py
===================

Overlap analysis for groups discovered by Dimension I, II, and retained
Dimension III groups.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Dict, Iterable, List

import pandas as pd


def parse_group(value: str) -> frozenset[str]:
    return frozenset(x.strip() for x in str(value).split("|") if x.strip())


def load_groups(path: str, devices_col: str = "Devices", retained_col: str | None = None) -> List[frozenset[str]]:
    df = pd.read_csv(path)
    if retained_col and retained_col in df.columns:
        df = df[df[retained_col].astype(str).str.lower().isin(["true", "1", "yes"])]
    return [parse_group(x) for x in df[devices_col]]


def recognized_by(group: frozenset[str], groups: Iterable[frozenset[str]]) -> bool:
    return any(group.issubset(other) for other in groups)


def run_overlap_analysis(dim1_csv: str, dim2_csv: str, dim3_csv: str, output_csv: str | None = None) -> pd.DataFrame:
    dim1_groups = load_groups(dim1_csv)
    dim2_groups = load_groups(dim2_csv)
    dim3_groups = load_groups(dim3_csv, retained_col="Retained")

    labeled = (
        [("D1", g) for g in dim1_groups] +
        [("D2", g) for g in dim2_groups] +
        [("D3", g) for g in dim3_groups]
    )

    rows = []
    for source, group in labeled:
        d1 = recognized_by(group, dim1_groups)
        d2 = recognized_by(group, dim2_groups)
        d3 = recognized_by(group, dim3_groups)

        if d1 and d2 and d3:
            category = "D1∩D2∩D3"
        elif d1 and d2 and not d3:
            category = "D1∩D2\\D3"
        elif d1 and d3 and not d2:
            category = "D1∩D3\\D2"
        elif d2 and d3 and not d1:
            category = "D2∩D3\\D1"
        elif d1 and not d2 and not d3:
            category = "D1_only"
        elif d2 and not d1 and not d3:
            category = "D2_only"
        elif d3 and not d1 and not d2:
            category = "D3_only"
        else:
            category = "Unclassified"

        rows.append(
            {
                "Source": source,
                "Category": category,
                "Num_Devices": len(group),
                "Devices": "|".join(sorted(group)),
            }
        )

    out = pd.DataFrame(rows)

    summary = (
        out.groupby("Category")
        .agg(Groups=("Devices", "count"), Devices=("Num_Devices", "sum"), Avg_Size=("Num_Devices", "mean"))
        .reset_index()
        .sort_values("Category")
    )
    print(summary.to_string(index=False))

    if output_csv:
        out.to_csv(output_csv, index=False, encoding="utf-8-sig")
        print(f"[+] detailed overlap rows -> {output_csv}")

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze overlap among Dimension I/II/III groups.")
    parser.add_argument("--dim1-csv", required=True)
    parser.add_argument("--dim2-csv", required=True)
    parser.add_argument("--dim3-csv", required=True)
    parser.add_argument("--output-csv", default=None)
    args = parser.parse_args()
    run_overlap_analysis(args.dim1_csv, args.dim2_csv, args.dim3_csv, args.output_csv)


if __name__ == "__main__":
    main()
