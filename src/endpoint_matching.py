#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
endpoint_matching.py
====================

Dimension II: backend endpoint matching by shared DNS domains.

Input
-----
A pickle produced by ``flow_preprocessing.py filter``. The input can be:
  - list[dict]
  - pandas.DataFrame

Required flow fields:
  Device, Vendor, Domain

Output
------
1. Pair-level endpoint matches:
   Device1, Vendor1, Device2, Vendor2, Same_Vendor,
   Shared_Domain_Count, Shared_Domains
2. Optional group-level results generated from cross-vendor domain device sets.
"""

from __future__ import annotations

import argparse
import os
import pickle
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

import pandas as pd

try:
    from .device_names import canonicalize_device_name
except ImportError:
    from device_names import canonicalize_device_name


def load_records(path: str) -> List[Dict[str, Any]]:
    with open(path, "rb") as f:
        obj = pickle.load(f)
    if isinstance(obj, list):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict(orient="records")
    if isinstance(obj, dict):
        records: List[Dict[str, Any]] = []
        for value in obj.values():
            records.extend(value if isinstance(value, list) else [value])
        return records
    raise ValueError(f"Unsupported pickle format: {type(obj)!r}")


def normalize_domain(value: Any) -> str:
    if value is None:
        return ""
    domain = str(value).strip()
    if domain.lower() in {"", "none", "nan", "null"}:
        return ""
    return domain.rstrip(".").lower()


def build_device_domain_sets(records: Iterable[Dict[str, Any]]) -> Tuple[Dict[str, Set[str]], Dict[str, str]]:
    device_domains: Dict[str, Set[str]] = defaultdict(set)
    device_vendor: Dict[str, str] = {}

    for record in records:
        device = canonicalize_device_name(record.get("Device", ""))
        if not device:
            continue

        vendor = str(record.get("Vendor", "unknown")).strip() or "unknown"
        domain = normalize_domain(record.get("Domain"))

        device_vendor[device] = vendor
        if domain:
            device_domains[device].add(domain)

    return dict(device_domains), device_vendor


def compute_pair_matches(
    device_domains: Dict[str, Set[str]],
    device_vendor: Dict[str, str],
    min_shared_domains: int = 1,
    cross_vendor_only: bool = False,
) -> List[Dict[str, Any]]:
    devices = sorted(device_domains.keys())
    rows: List[Dict[str, Any]] = []

    for d1, d2 in combinations(devices, 2):
        v1 = device_vendor.get(d1, "unknown")
        v2 = device_vendor.get(d2, "unknown")
        same_vendor = v1.lower() == v2.lower()

        if cross_vendor_only and same_vendor:
            continue

        shared = device_domains[d1] & device_domains[d2]
        if len(shared) < min_shared_domains:
            continue

        rows.append(
            {
                "Device1": d1,
                "Vendor1": v1,
                "Device2": d2,
                "Vendor2": v2,
                "Same_Vendor": same_vendor,
                "Shared_Domain_Count": len(shared),
                "Shared_Domains": "|".join(sorted(shared)),
            }
        )

    rows.sort(key=lambda r: (r["Same_Vendor"], -r["Shared_Domain_Count"], r["Device1"], r["Device2"]))
    return rows


def build_domain_groups(pair_rows: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    """Build the final Dimension II groups from pair-level matches.

    First, reconstruct the complete device set observed for each domain using
    both same-vendor and cross-vendor pairs. Domain device sets involving at
        least two vendors define the group device sets. Identical device sets are
    consolidated, and every domain shared by all devices in a group is retained.
    """
    domain_devices: Dict[str, Set[str]] = defaultdict(set)
    device_vendor: Dict[str, str] = {}

    for row in pair_rows:
        d1 = canonicalize_device_name(row["Device1"])
        d2 = canonicalize_device_name(row["Device2"])
        device_vendor[d1] = row.get("Vendor1", "unknown")
        device_vendor[d2] = row.get("Vendor2", "unknown")
        for domain in str(row.get("Shared_Domains", "")).split("|"):
            domain = normalize_domain(domain)
            if domain:
                domain_devices[domain].update((d1, d2))

    device_sets: Set[frozenset[str]] = set()
    for devices in domain_devices.values():
        vendors = {device_vendor.get(device, "unknown").strip().lower() for device in devices}
        if len(vendors) >= 2:
            device_sets.add(frozenset(devices))

    groups: List[Dict[str, Any]] = []
    for devices in device_sets:
        domains = sorted(
            domain for domain, observed_devices in domain_devices.items()
            if devices.issubset(observed_devices)
        )
        vendors = sorted({device_vendor.get(device, "unknown").strip().lower() for device in devices})
        groups.append(
            {
                "Num_Vendors": len(vendors),
                "Num_Devices": len(devices),
                "Num_Domains": len(domains),
                "Vendors": "|".join(vendors),
                "Devices": "|".join(sorted(devices)),
                "Domains": "|".join(domains),
            }
        )

    groups.sort(key=lambda row: (-row["Num_Devices"], -row["Num_Vendors"], row["Devices"]))
    for index, row in enumerate(groups, start=1):
        row["Cluster_ID"] = f"C{index:04d}"

    columns = [
        "Cluster_ID", "Num_Vendors", "Num_Devices", "Num_Domains",
        "Vendors", "Devices", "Domains",
    ]
    return pd.DataFrame(groups, columns=columns)


def enrich_domain_groups(group_df: pd.DataFrame, annotation_csv: str) -> pd.DataFrame:
    """Attach manually curated domain-level annotations to Dimension II groups."""
    annotations = pd.read_csv(annotation_csv, dtype=str).fillna("")
    required = {
        "Domain", "Provider", "Provider_Role", "Provider_Subrole",
        "Annotation_Note",
    }
    missing = sorted(required - set(annotations.columns))
    if missing:
        raise ValueError(f"domain annotation CSV missing columns: {missing}")

    annotation_map = annotations.set_index("Domain").to_dict(orient="index")

    cluster_id_by_domains: Dict[frozenset[str], str] = {}
    if "Cluster_IDs" in annotations.columns:
        cluster_domains: Dict[str, Set[str]] = defaultdict(set)
        for _, annotation in annotations.iterrows():
            for cluster_id in str(annotation["Cluster_IDs"]).split("|"):
                if cluster_id:
                    cluster_domains[cluster_id].add(str(annotation["Domain"]))
        cluster_id_by_domains = {
            frozenset(domains): cluster_id for cluster_id, domains in cluster_domains.items()
        }

    def collect(domains: Sequence[str], column: str, split_values: bool = False) -> str:
        values: Set[str] = set()
        for domain in domains:
            value = str(annotation_map[domain].get(column, ""))
            candidates = value.split("|") if split_values else [value]
            values.update(candidate.strip() for candidate in candidates if candidate.strip())
        return "|".join(sorted(values))

    rows: List[Dict[str, Any]] = []
    for _, row in group_df.iterrows():
        domains = [domain for domain in str(row["Domains"]).split("|") if domain]
        missing_domains = [domain for domain in domains if domain not in annotation_map]
        if missing_domains:
            raise ValueError(f"domains missing annotations: {missing_domains}")

        enriched = row.to_dict()
        released_cluster_id = cluster_id_by_domains.get(frozenset(domains))
        if released_cluster_id:
            enriched["Cluster_ID"] = released_cluster_id
        enriched["Providers"] = collect(domains, "Provider")
        enriched["Provider_Roles"] = collect(domains, "Provider_Role")
        enriched["Provider_Subroles"] = collect(domains, "Provider_Subrole")

        confidence_col = next(
            (name for name in ("Annotation_Confidence", "Annotation_Confidences") if name in annotations.columns),
            None,
        )
        if confidence_col:
            enriched["Annotation_Confidences"] = collect(domains, confidence_col)
        enriched["Domain_Annotation_Notes"] = "; ".join(
            f"{domain}: {annotation_map[domain]['Annotation_Note']}" for domain in domains
        )
        rows.append(enriched)

    out = pd.DataFrame(rows)
    if cluster_id_by_domains:
        out = out.sort_values("Cluster_ID").reset_index(drop=True)
    return out


def write_summary(path: str, pair_rows: Sequence[Dict[str, Any]], device_domains: Dict[str, Set[str]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cross_vendor = [r for r in pair_rows if not bool(r["Same_Vendor"])]
    same_vendor = [r for r in pair_rows if bool(r["Same_Vendor"])]

    domain_pair_count = Counter()
    for row in pair_rows:
        for domain in str(row.get("Shared_Domains", "")).split("|"):
            if domain:
                domain_pair_count[domain] += 1

    lines = []
    lines.append("=" * 60)
    lines.append("Endpoint matching summary")
    lines.append("=" * 60)
    lines.append(f"Devices with DNS domains       : {len(device_domains):,}")
    lines.append(f"Unique domains                 : {len(set().union(*device_domains.values())) if device_domains else 0:,}")
    lines.append(f"Pairs with shared domains      : {len(pair_rows):,}")
    lines.append(f"  Cross-vendor pairs           : {len(cross_vendor):,}")
    lines.append(f"  Same-vendor pairs            : {len(same_vendor):,}")
    lines.append("")
    lines.append("Top shared domains:")
    for domain, count in domain_pair_count.most_common(20):
        lines.append(f"  {domain:<60} {count:>6}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_endpoint_matching(
    input_pickle: str,
    pair_output_csv: str,
    summary_output_txt: str | None = None,
    group_output_csv: str | None = None,
    domain_annotation_csv: str | None = None,
    min_shared_domains: int = 1,
    cross_vendor_only: bool = False,
) -> None:
    if group_output_csv and cross_vendor_only:
        raise ValueError(
            "group construction requires same-vendor and cross-vendor pairs; "
            "do not use --cross-vendor-only with --group-output-csv"
        )
    records = load_records(input_pickle)
    device_domains, device_vendor = build_device_domain_sets(records)
    pair_rows = compute_pair_matches(
        device_domains,
        device_vendor,
        min_shared_domains=min_shared_domains,
        cross_vendor_only=cross_vendor_only,
    )

    os.makedirs(os.path.dirname(pair_output_csv) or ".", exist_ok=True)
    pd.DataFrame(pair_rows).to_csv(pair_output_csv, index=False, encoding="utf-8-sig")

    if summary_output_txt:
        write_summary(summary_output_txt, pair_rows, device_domains)

    if group_output_csv:
        group_df = build_domain_groups(pair_rows)
        if domain_annotation_csv:
            group_df = enrich_domain_groups(group_df, domain_annotation_csv)
        os.makedirs(os.path.dirname(group_output_csv) or ".", exist_ok=True)
        group_df.to_csv(group_output_csv, index=False, encoding="utf-8-sig")

    print(f"[+] pairs : {len(pair_rows):,} -> {pair_output_csv}")
    if group_output_csv:
        print(f"[+] groups: {len(pd.read_csv(group_output_csv)):,} -> {group_output_csv}")


def export_groups_from_pair_csv(
    pair_input_csv: str,
    group_output_csv: str,
    domain_annotation_csv: str | None = None,
) -> pd.DataFrame:
    """Export Dimension II groups from an existing pair-level result."""
    pair_rows = pd.read_csv(pair_input_csv).fillna("").to_dict(orient="records")
    group_df = build_domain_groups(pair_rows)
    if domain_annotation_csv:
        group_df = enrich_domain_groups(group_df, domain_annotation_csv)
    os.makedirs(os.path.dirname(group_output_csv) or ".", exist_ok=True)
    group_df.to_csv(group_output_csv, index=False, encoding="utf-8-sig")
    print(f"[+] pair rows: {len(pair_rows):,}")
    print(f"[+] groups   : {len(group_df):,} -> {group_output_csv}")
    return group_df


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dimension II endpoint matching by shared domains.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-pickle")
    source.add_argument("--pair-input-csv")
    parser.add_argument("--pair-output-csv")
    parser.add_argument("--summary-output-txt", default=None)
    parser.add_argument("--group-output-csv", default=None)
    parser.add_argument("--domain-annotation-csv", default=None)
    parser.add_argument("--min-shared-domains", type=int, default=1)
    parser.add_argument("--cross-vendor-only", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.pair_input_csv:
        if not args.group_output_csv:
            raise SystemExit("--pair-input-csv requires --group-output-csv")
        export_groups_from_pair_csv(
            pair_input_csv=args.pair_input_csv,
            group_output_csv=args.group_output_csv,
            domain_annotation_csv=args.domain_annotation_csv,
        )
        return

    if not args.pair_output_csv:
        raise SystemExit("--input-pickle requires --pair-output-csv")
    run_endpoint_matching(
        input_pickle=args.input_pickle,
        pair_output_csv=args.pair_output_csv,
        summary_output_txt=args.summary_output_txt,
        group_output_csv=args.group_output_csv,
        domain_annotation_csv=args.domain_annotation_csv,
        min_shared_domains=args.min_shared_domains,
        cross_vendor_only=args.cross_vendor_only,
    )


if __name__ == "__main__":
    main()
