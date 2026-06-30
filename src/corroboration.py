#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corroboration.py
================

Corroboration step for Dimension III candidate groups.

Rules
-----
Rule I   Documentary corroboration:
         G is a subset of a Dimension I documented group.

Rule II  Endpoint corroboration:
         G is a subset of a Dimension II endpoint group.

Rule III Multi-cluster co-occurrence:
         The same device set appears in multiple behavior components, or appears
         as a subset of a larger behavior component.

Rule IV  Anchor-based corroboration:
         At least a threshold fraction of devices in G are anchored by at least
         one verified pair. A pair is verified if it is same-vendor, in a
         Dimension I pair, or in a Dimension II pair.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from itertools import combinations
from typing import Dict, Iterable, List, Sequence, Set, Tuple

import pandas as pd


DeviceGroup = frozenset[str]


def parse_device_group(value: str) -> DeviceGroup:
    return frozenset(x.strip() for x in str(value).split("|") if x.strip())


def load_groups_csv(path: str, devices_col: str = "Devices") -> List[DeviceGroup]:
    df = pd.read_csv(path)
    return [parse_device_group(row[devices_col]) for _, row in df.iterrows()]


def groups_to_pairs(groups: Iterable[DeviceGroup]) -> Set[Tuple[str, str]]:
    pairs: Set[Tuple[str, str]] = set()
    for group in groups:
        for d1, d2 in combinations(sorted(group), 2):
            pairs.add((d1, d2))
            pairs.add((d2, d1))
    return pairs


def is_subset_of_any(group: DeviceGroup, groups: Iterable[DeviceGroup]) -> bool:
    return any(group.issubset(other) for other in groups)


def rule1_documentary(group: DeviceGroup, dim1_groups: Sequence[DeviceGroup]) -> bool:
    return is_subset_of_any(group, dim1_groups)


def rule2_endpoint(group: DeviceGroup, dim2_groups: Sequence[DeviceGroup]) -> bool:
    return is_subset_of_any(group, dim2_groups)


def build_behavior_combo_index(global_component_df: pd.DataFrame) -> Tuple[Dict[DeviceGroup, Set[str]], List[DeviceGroup]]:
    combo_component_count: Dict[DeviceGroup, Set[str]] = defaultdict(set)
    all_combos: List[DeviceGroup] = []

    cross_df = global_component_df
    if "vendor_state" in cross_df.columns:
        cross_df = cross_df[cross_df["vendor_state"].astype(str).isin(["1", "True", "true"])]

    for comp_id, group in cross_df.groupby("Component_ID"):
        devices = frozenset(str(x) for x in group["Device"].dropna().unique())
        if len(devices) < 2:
            continue
        all_combos.append(devices)
        combo_component_count[devices].add(str(comp_id))

    return combo_component_count, all_combos


def rule3_multi_cluster(
    group: DeviceGroup,
    combo_component_count: Dict[DeviceGroup, Set[str]],
    all_behavior_combos: Sequence[DeviceGroup],
) -> Tuple[bool, int, int]:
    num_components = len(combo_component_count.get(group, set()))
    superset_count = sum(1 for other in all_behavior_combos if group.issubset(other) and other != group)
    return (num_components + superset_count) > 1, num_components, superset_count


def is_verified_pair(
    d1: str,
    d2: str,
    device_vendor: Dict[str, str],
    dim1_pairs: Set[Tuple[str, str]],
    dim2_pairs: Set[Tuple[str, str]],
) -> Tuple[bool, str | None]:
    v1 = device_vendor.get(d1, "unknown")
    v2 = device_vendor.get(d2, "unknown")
    if v1 == v2 and v1 != "unknown":
        return True, "same_vendor"
    if (d1, d2) in dim1_pairs or (d2, d1) in dim1_pairs:
        return True, "dim1_verified"
    if (d1, d2) in dim2_pairs or (d2, d1) in dim2_pairs:
        return True, "dim2_verified"
    return False, None


def rule4_anchor_based(
    group: DeviceGroup,
    device_vendor: Dict[str, str],
    dim1_pairs: Set[Tuple[str, str]],
    dim2_pairs: Set[Tuple[str, str]],
    threshold: float = 0.5,
) -> Tuple[bool, float, int, List[str], str]:
    devices = list(group)
    verified_devices: Set[str] = set()
    verified_pairs_info: List[str] = []
    anchor_types: Set[str] = set()

    for d1, d2 in combinations(devices, 2):
        ok, verification_type = is_verified_pair(d1, d2, device_vendor, dim1_pairs, dim2_pairs)
        if ok:
            verified_devices.add(d1)
            verified_devices.add(d2)
            verified_pairs_info.append(f"{d1}|{d2}|{verification_type}")
            if verification_type:
                anchor_types.add(verification_type)

    ratio = len(verified_devices) / len(group) if group else 0.0
    return ratio >= threshold, ratio, len(verified_devices), verified_pairs_info, "|".join(sorted(anchor_types))


def run_corroboration(
    global_component_csv: str,
    dim3_groups_csv: str,
    dim1_groups_csv: str,
    dim2_groups_csv: str,
    output_csv: str,
    anchor_threshold: float = 0.5,
) -> pd.DataFrame:
    comp_df = pd.read_csv(global_component_csv)
    dim3_df = pd.read_csv(dim3_groups_csv)

    dim1_groups = load_groups_csv(dim1_groups_csv)
    dim2_groups = load_groups_csv(dim2_groups_csv)
    dim1_pairs = groups_to_pairs(dim1_groups)
    dim2_pairs = groups_to_pairs(dim2_groups)

    device_vendor = dict(zip(comp_df["Device"].astype(str), comp_df["Vendor"].astype(str)))
    combo_component_count, all_behavior_combos = build_behavior_combo_index(comp_df)

    rows = []
    for _, row in dim3_df.iterrows():
        group = parse_device_group(row["Devices"])

        r1 = rule1_documentary(group, dim1_groups)
        r2 = rule2_endpoint(group, dim2_groups)
        tier1 = r1 or r2

        r3, num_components, superset_count = rule3_multi_cluster(
            group, combo_component_count, all_behavior_combos
        )
        r4, r4_ratio, r4_count, r4_pairs, r4_anchor_types = rule4_anchor_based(
            group, device_vendor, dim1_pairs, dim2_pairs, threshold=anchor_threshold
        )

        retained = tier1 or r3 or r4
        if tier1:
            tier = "1"
        elif r3:
            tier = "2a"
        elif r4:
            tier = "2b"
        else:
            tier = "None"

        rows.append(
            {
                "Cluster_ID": row.get("Cluster_ID", ""),
                "Num_Vendors": row.get("Num_Vendors", len({device_vendor.get(d, 'unknown') for d in group})),
                "Num_Devices": row.get("Num_Devices", len(group)),
                "Vendors": row.get("Vendors", "|".join(sorted({device_vendor.get(d, 'unknown') for d in group}))),
                "Devices": row["Devices"],
                "Rule_I": r1,
                "Rule_II": r2,
                "Rule_III": r3,
                "Num_Components": num_components,
                "Superset_Count": superset_count,
                "Rule_IV": r4,
                "Rule_IV_Verified_Ratio": round(r4_ratio, 3),
                "Rule_IV_Verified_Count": r4_count,
                "Rule_IV_Verified_Pairs": ";".join(r4_pairs),
                "Rule_IV_Anchor_Types": r4_anchor_types,
                "Retained": retained,
                "Corroboration_Tier": tier,
            }
        )

    out = pd.DataFrame(rows)
    out.to_csv(output_csv, index=False, encoding="utf-8-sig")

    print("[+] corroboration results")
    print(f"    candidate groups: {len(out):,}")
    print(f"    retained        : {int(out['Retained'].sum()):,}")
    print(f"    tier 1          : {int((out['Corroboration_Tier'] == '1').sum()):,}")
    print(f"    tier 2a         : {int((out['Corroboration_Tier'] == '2a').sum()):,}")
    print(f"    tier 2b         : {int((out['Corroboration_Tier'] == '2b').sum()):,}")
    print(f"    output          : {output_csv}")
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run corroboration rules for Dim III groups.")
    parser.add_argument("--global-component-csv", required=True)
    parser.add_argument("--dim3-groups-csv", required=True)
    parser.add_argument("--dim1-groups-csv", required=True)
    parser.add_argument("--dim2-groups-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--anchor-threshold", type=float, default=0.5)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_corroboration(
        args.global_component_csv,
        args.dim3_groups_csv,
        args.dim1_groups_csv,
        args.dim2_groups_csv,
        args.output_csv,
        args.anchor_threshold,
    )


if __name__ == "__main__":
    main()
