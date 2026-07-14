#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
behavior_clustering.py
======================

Dimension III: traffic-behavior clustering.

This is a repository-friendly consolidation of the original two-stage scripts:
  1. in-device flow clustering: reduce each device's flows to medoid exemplars;
  2. global flow clustering: cluster exemplars across devices.

The heavy PS-DTW distance computation is implemented in ``ps_dtw.py``.
"""

from __future__ import annotations

import argparse
import gc
import os
import pickle
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd

try:
    from .device_names import canonicalize_device_name
except ImportError:
    from device_names import canonicalize_device_name

try:
    from .ps_dtw import PSDTWConfig, pairwise_distance_matrix_from_signed_sequences
except ImportError:
    from ps_dtw import PSDTWConfig, pairwise_distance_matrix_from_signed_sequences


def load_pickle_records(path: str) -> List[Dict[str, Any]]:
    try:
        obj = pd.read_pickle(path)
    except Exception:
        with open(path, "rb") as f:
            obj = pickle.load(f)

    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        records: List[Dict[str, Any]] = []
        for value in obj.values():
            records.extend(value if isinstance(value, list) else [value])
        return records
    if hasattr(obj, "to_dict"):
        return obj.to_dict(orient="records")
    raise ValueError(f"Unsupported pickle format: {type(obj)!r}")


def save_pickle(obj: Any, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(obj, f)


def light_check(flow: Dict[str, Any], min_packet_count: int = 5) -> bool:
    seq = flow.get("Payload_Sequence", [])
    up = sum(1 for x in seq if x > 0)
    down = sum(1 for x in seq if x < 0)
    return up >= min_packet_count and down >= min_packet_count


def medoid_representatives(
    flows: Sequence[Dict[str, Any]],
    config: PSDTWConfig,
    distance_threshold: float,
) -> List[Dict[str, Any]]:
    """
    Cluster flows within one device and return one medoid per cluster.

    The medoid is the member with the smallest average intra-cluster distance.
    """
    flows = list(flows)
    n = len(flows)
    if n <= 1:
        return flows

    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    seqs = [f.get("Payload_Sequence", []) for f in flows]
    condensed = pairwise_distance_matrix_from_signed_sequences(seqs, config)

    labels = fcluster(linkage(condensed, method="complete"), t=distance_threshold, criterion="distance")
    dist_matrix = squareform(condensed)

    groups: Dict[int, List[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        groups[int(label)].append(idx)

    representatives: List[Dict[str, Any]] = []
    for idxs in groups.values():
        if len(idxs) == 1:
            representatives.append(flows[idxs[0]])
            continue

        idx_arr = np.asarray(idxs)
        sub_matrix = dist_matrix[np.ix_(idx_arr, idx_arr)]
        medoid_local = int(np.argmin(sub_matrix.mean(axis=1)))
        representatives.append(flows[idxs[medoid_local]])

    return representatives


def run_in_device_clustering(
    input_pickle: str,
    output_pickle: str,
    checkpoint_pickle: str | None = None,
    sigma: float = 35.0,
    similarity_threshold: float = 0.90,
    max_seq_len: int = 100,
    min_packet_count: int = 5,
) -> List[Dict[str, Any]]:
    """
    Stage 1: cluster flows within each device and keep medoid exemplars.
    """
    from tqdm import tqdm

    config = PSDTWConfig(sigma=sigma, max_seq_len=max_seq_len)
    distance_threshold = 1.0 - similarity_threshold

    all_flows = load_pickle_records(input_pickle)
    by_device: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for flow in all_flows:
        device = canonicalize_device_name(flow.get("Device", "Unknown"))
        if light_check(flow, min_packet_count=min_packet_count):
            by_device[device].append(flow)

    processed: Dict[str, List[Dict[str, Any]]] = {}
    if checkpoint_pickle and os.path.exists(checkpoint_pickle):
        with open(checkpoint_pickle, "rb") as f:
            processed = pickle.load(f)

    for device, flows in tqdm(sorted(by_device.items()), desc="In-device clustering"):
        if device in processed:
            continue
        try:
            processed[device] = medoid_representatives(flows, config, distance_threshold)
        except Exception as exc:
            print(f"[WARN] {device}: clustering failed ({exc}); falling back to all flows")
            processed[device] = list(flows)

        if checkpoint_pickle:
            save_pickle(processed, checkpoint_pickle)

    representatives: List[Dict[str, Any]] = []
    for reps in processed.values():
        representatives.extend(reps)

    save_pickle(representatives, output_pickle)
    print(f"[+] representatives: {len(representatives):,} -> {output_pickle}")
    return representatives


def run_global_clustering(
    input_pickle: str,
    output_csv: str,
    device_type_csv: str | None = None,
    matrix_cache: str | None = None,
    sigma: float = 35.0,
    similarity_threshold: float = 0.90,
    max_seq_len: int = 100,
) -> pd.DataFrame:
    """
    Stage 2: cluster all medoid exemplars across devices and export components.
    """
    from scipy.cluster.hierarchy import fcluster, linkage

    config = PSDTWConfig(sigma=sigma, max_seq_len=max_seq_len)
    distance_threshold = 1.0 - similarity_threshold

    exemplars = load_pickle_records(input_pickle)
    if len(exemplars) < 2:
        raise ValueError("Need at least two exemplars for global clustering")

    if matrix_cache and os.path.exists(matrix_cache):
        condensed = np.load(matrix_cache)
    else:
        seqs = [x.get("Payload_Sequence", []) for x in exemplars]
        condensed = pairwise_distance_matrix_from_signed_sequences(seqs, config)
        if matrix_cache:
            os.makedirs(os.path.dirname(matrix_cache) or ".", exist_ok=True)
            np.save(matrix_cache, condensed)

    labels = fcluster(linkage(condensed, method="complete"), t=distance_threshold, criterion="distance")

    device_type_map: Dict[str, str] = {}
    if device_type_csv and os.path.exists(device_type_csv):
        type_df = pd.read_csv(device_type_csv, dtype=str)
        device_type_map = dict(zip(type_df["Device_Name"], type_df["Type"]))

    rows: List[Dict[str, Any]] = []
    for idx, (label, flow) in enumerate(zip(labels, exemplars)):
        device = canonicalize_device_name(flow.get("Device", "Unknown"))
        vendor = str(flow.get("Vendor", "unknown"))
        rows.append(
            {
                "Component_ID": int(label),
                "Flow_Index": idx,
                "Device": device,
                "Vendor": vendor,
                "Device_Type": device_type_map.get(device, "Unknown"),
                "Domain": flow.get("Domain", ""),
                "Remote_IP": flow.get("Remote_IP", ""),
                "Server_Port": flow.get("Server_Port", ""),
                "Payload_Sequence": flow.get("Payload_Sequence", []),
            }
        )

    df = pd.DataFrame(rows)

    # Enrich component-level statistics.
    comp_stats = []
    for comp_id, group in df.groupby("Component_ID"):
        vendors = sorted(set(str(v) for v in group["Vendor"]))
        devices = sorted(set(str(d) for d in group["Device"]))
        comp_stats.append(
            {
                "Component_ID": comp_id,
                "Num_Flows": len(group),
                "Num_Devices": len(devices),
                "Num_Vendors": len(set(v.lower() for v in vendors)),
                "Devices": "|".join(devices),
                "Vendors": "|".join(vendors),
                "vendor_state": 1 if len(set(v.lower() for v in vendors)) > 1 else 0,
                "Major_Device_Type": Counter(group["Device_Type"]).most_common(1)[0][0],
            }
        )

    stats_df = pd.DataFrame(comp_stats)
    df = df.merge(stats_df, on="Component_ID", how="left")

    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"[+] global components -> {output_csv}")
    return df


def export_dim3_behavior_groups(global_component_csv: str, output_csv: str) -> pd.DataFrame:
    """
    Consolidate cross-vendor components into final Dimension III groups.

    Components with exactly the same device set represent the same behavioral
    group and are merged. ``Num_Components`` records their multiplicity, while
    ``Superset_Count`` records how many cross-vendor components contain all
    devices in the group (including exact matches).

    The function accepts both the repository-generated schema (``Device_Type``)
    and the research intermediate schema (``device_type``).
    """
    df = pd.read_csv(global_component_csv)
    required = {"Component_ID", "Device", "Vendor"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"global component CSV missing columns: {missing}")

    type_col = "Device_Type" if "Device_Type" in df.columns else "device_type" if "device_type" in df.columns else None

    components: List[Dict[str, Any]] = []
    for comp_id, group in df.groupby("Component_ID", sort=False):
        devices = frozenset(group["Device"].dropna().astype(str).map(canonicalize_device_name))
        vendors = frozenset(group["Vendor"].dropna().astype(str))
        normalized_vendors = frozenset(v.strip().lower() for v in vendors if v.strip())
        if len(devices) < 2 or len(normalized_vendors) < 2:
            continue

        device_types = frozenset()
        if type_col:
            device_types = frozenset(
                value.strip()
                for value in group[type_col].dropna().astype(str)
                if value.strip() and value.strip().lower() != "nan"
            )

        components.append(
            {
                "component_id": str(comp_id),
                "devices": devices,
                "vendors": normalized_vendors,
                "device_types": device_types,
            }
        )

    consolidated: Dict[frozenset[str], Dict[str, Any]] = {}
    for component in components:
        devices = component["devices"]
        if devices not in consolidated:
            consolidated[devices] = {
                "component_ids": [],
                "vendors": set(),
                "device_types": set(),
            }
        consolidated[devices]["component_ids"].append(component["component_id"])
        consolidated[devices]["vendors"].update(component["vendors"])
        consolidated[devices]["device_types"].update(component["device_types"])

    group_records: List[Dict[str, Any]] = []
    for devices, metadata in consolidated.items():
        superset_count = sum(devices.issubset(component["devices"]) for component in components)
        group_records.append(
            {
                "Num_Vendors": len(metadata["vendors"]),
                "Num_Devices": len(devices),
                "Num_Components": len(metadata["component_ids"]),
                "Superset_Count": superset_count,
                "Vendors": "|".join(sorted(metadata["vendors"])),
                "Devices": "|".join(sorted(devices)),
                "Device_Types": "|".join(sorted(metadata["device_types"])),
            }
        )

    group_records.sort(
        key=lambda row: (
            -row["Num_Devices"],
            -row["Num_Vendors"],
            row["Devices"],
        )
    )
    for index, row in enumerate(group_records, start=1):
        row["Cluster_ID"] = f"D3_C{index:04d}"

    columns = [
        "Cluster_ID",
        "Num_Vendors",
        "Num_Devices",
        "Num_Components",
        "Superset_Count",
        "Vendors",
        "Devices",
        "Device_Types",
    ]
    out = pd.DataFrame(group_records, columns=columns)
    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    out.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"[+] cross-vendor components: {len(components):,}")
    print(f"[+] unique behavioral groups: {len(out):,} -> {output_csv}")
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dimension III behavioral clustering.")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("in-device")
    p1.add_argument("--input-pickle", required=True)
    p1.add_argument("--output-pickle", required=True)
    p1.add_argument("--checkpoint-pickle", default=None)
    p1.add_argument("--sigma", type=float, default=35.0)
    p1.add_argument("--similarity-threshold", type=float, default=0.90)
    p1.add_argument("--max-seq-len", type=int, default=100)
    p1.add_argument("--min-packet-count", type=int, default=5)

    p2 = sub.add_parser("global")
    p2.add_argument("--input-pickle", required=True)
    p2.add_argument("--output-csv", required=True)
    p2.add_argument("--device-type-csv", default=None)
    p2.add_argument("--matrix-cache", default=None)
    p2.add_argument("--sigma", type=float, default=35.0)
    p2.add_argument("--similarity-threshold", type=float, default=0.90)
    p2.add_argument("--max-seq-len", type=int, default=100)

    p3 = sub.add_parser("export-groups")
    p3.add_argument("--global-component-csv", required=True)
    p3.add_argument("--output-csv", required=True)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "in-device":
        run_in_device_clustering(
            args.input_pickle, args.output_pickle, args.checkpoint_pickle,
            args.sigma, args.similarity_threshold, args.max_seq_len, args.min_packet_count,
        )
    elif args.command == "global":
        run_global_clustering(
            args.input_pickle, args.output_csv, args.device_type_csv, args.matrix_cache,
            args.sigma, args.similarity_threshold, args.max_seq_len,
        )
    elif args.command == "export-groups":
        export_dim3_behavior_groups(args.global_component_csv, args.output_csv)


if __name__ == "__main__":
    main()
