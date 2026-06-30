#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
documentary_evidence.py
=======================

Dimension I: documented inter-vendor relationship evidence.

This module keeps the deterministic parts of the original LLM-assisted
pipeline:
  - platform name splitting and normalization,
  - loading device/vendor/type metadata,
  - converting manually verified LLM evidence into device groups.

The actual LLM query stage is intentionally optional for the initial public
release. Store verified results as CSV/JSON and use this module to normalize
them into ``vendor_corroboration_clusters.csv``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from itertools import combinations
from typing import Any, Dict, Iterable, List, Sequence, Set

import pandas as pd


DEFAULT_NON_IOT_TYPES = {
    "Hub", "Phone", "Computer", "Gateway",
    "Tablet", "Router", "Game Console", "Unknown",
}

PLATFORM_ALIASES = {
    "Alexa": "Amazon Alexa",
    "Works with Alexa": "Amazon Alexa",
    "Works with Ring": "Ring",
    "AWS IoT": "AWS",
    "Google Assistant": "Google Home",
    "Samsung SmartThings": "SmartThings",
    "Apple Home": "Apple HomeKit",
    "Apple HealthKit": "Apple Health",
    "Apple AirPlay 2": "Apple AirPlay",
    "Huawei HiLink": "HarmonyOS Connect",
    "HarmonyOS": "HarmonyOS Connect",
    "Huawei HarmonyOS": "HarmonyOS Connect",
    "HarmonyOS Connect (Huawei HiLink)": "HarmonyOS Connect",
    "Mijia": "Xiaomi Mi Home",
    "Mi Home": "Xiaomi Mi Home",
    "Xiaomi Home": "Xiaomi Mi Home",
    "Xiaomi Mijia": "Xiaomi Mi Home",
    "Xiaomi": "Xiaomi Mi Home",
    "Tianmao (Tmall Genie)": "Tmall Genie",
    "Tmall Genie (Tianmao)": "Tmall Genie",
    "Tianmao Genie": "Tmall Genie",
    "Xiaodu": "DuerOS",
    "Xiaodu (DuerOS)": "DuerOS",
    "Joylink": "JD Joylink",
    "Joylink (JD Smart)": "JD Joylink",
    "GeForce NOW": "NVIDIA GeForce NOW",
    "Ring App": "Ring",
    "Works with Sonos": "Sonos",
    "Roku TV Ready": "Roku TV",
}


PROMPT_STAGE1 = """You are an IoT supply chain analyst.

Vendor 1: "{vendor1}"
Vendor 2: "{vendor2}"

Do these two vendors have ANY documented supply chain relationship?

Accepted relationship types:
- Ecosystem: two vendors have a documented technical association,
  including platform certifications (e.g., Works with Alexa, Apple
  HomeKit, Google Home), shared third-party platform SDKs (e.g.,
  Tuya, Matter), or publicly announced partnerships or
  interoperability agreements. Both parties remain independent
  vendors.
- Parent/Subsidiary: one vendor directly owns or controls the other,
  as documented in corporate filings or acquisition announcements.

ACCEPT only if:
- The relationship is PUBLICLY DOCUMENTED, such as in a press
  release, partnership announcement, platform certification list,
  official partner page, product documentation, corporate filing,
  or acquisition announcement.
- You are CERTAIN -- do NOT speculate.

REJECT if uncertain or if no publicly documented evidence exists.

Important decision rules:
- If the relationship is Ecosystem, extract the specific ecosystem
  link that connects the two vendors. This link will be used in
  Stage 2 device-type verification.
- If the relationship is Parent/Subsidiary, use ecosystem_link =
  "None" because shared ownership is handled directly during group
  construction and does not proceed to Stage 2.
- If there is no documented connection, set relationship_type to
  "None", ecosystem_link to "None", and is_related to false.

Respond with ONLY valid JSON:
{{
  "is_related": true or false,
  "relationship_type": "Ecosystem | Parent/Subsidiary | None",
  "ecosystem_link": "specific ecosystem name or None",
  "reason": "one sentence"
}}"""


PROMPT_STAGE2 = """You are an IoT supply chain analyst.

Vendor: "{vendor}"
Device type: "{device_type}"
Ecosystem link: "{ecosystem_link}"

Does {vendor}'s {device_type} officially support or integrate with
{ecosystem_link}?

ACCEPT if there is publicly documented evidence, such as a platform
certification list, official partner page, press release, product
listing, official product documentation, or compatibility page.

REJECT if:
- No publicly documented evidence exists.
- You are uncertain.
- The vendor participates in the ecosystem only at a general
  company level, but there is no evidence that this specific device
  type integrates with the ecosystem link.

Respond with ONLY valid JSON:
{{
  "is_related": true or false,
  "reason": "one sentence"
}}"""


def split_platforms(platform: str) -> List[str]:
    """Split strings such as 'Amazon Alexa and Google Home' into platforms."""
    if not platform or str(platform).lower() in {"none", "null", "nan", ""}:
        return []
    normalized = re.sub(r"\s+and\s+", "|", str(platform), flags=re.IGNORECASE)
    normalized = re.sub(r"\s*[,;/]\s*", "|", normalized)
    return [p.strip() for p in normalized.split("|") if p.strip()]


def normalize_platform(platform: str, aliases: Dict[str, str] = PLATFORM_ALIASES) -> str:
    if not platform or str(platform).lower() in {"none", "null", "nan", ""}:
        return ""
    return aliases.get(str(platform).strip(), str(platform).strip())


def load_device_metadata(
    device_list_csv: str,
    device_type_csv: str,
    non_iot_types: Set[str] = DEFAULT_NON_IOT_TYPES,
) -> tuple[Dict[str, str], Dict[str, str], Dict[str, Set[str]], Dict[str, Set[str]]]:
    device_list_df = pd.read_csv(device_list_csv, dtype=str)
    device_type_df = pd.read_csv(device_type_csv, dtype=str)

    device_vendor = dict(zip(device_list_df["Device_Name"], device_list_df["Vendor"]))
    device_type = dict(zip(device_type_df["Device_Name"], device_type_df["Type"]))

    vendor_devices: Dict[str, Set[str]] = defaultdict(set)
    vendor_types: Dict[str, Set[str]] = defaultdict(set)

    for device, vendor in device_vendor.items():
        dtype = device_type.get(device)
        if dtype and dtype not in non_iot_types and vendor and vendor != "Unknown":
            vendor_devices[vendor].add(device)
            vendor_types[vendor].add(dtype)

    return device_vendor, device_type, vendor_devices, vendor_types


def canonicalize_evidence_columns(evidence: pd.DataFrame) -> pd.DataFrame:
    """Normalize common Dimension-I evidence column names.

    The paper uses ``ecosystem_link`` in the LLM prompt, while early
    internal scripts used ``Platform``.  For repository compatibility,
    this function maps both forms to ``Platform`` before group building.
    """
    rename_map = {
        "vendor1": "Vendor1",
        "vendor2": "Vendor2",
        "relationship_type": "Relationship_Type",
        "is_related": "Is_Related",
        "ecosystem_link": "Platform",
        "Ecosystem_Link": "Platform",
        "platform": "Platform",
        "vendor": "Vendor",
        "device_type": "Device_Type",
    }
    existing = {c: rename_map[c] for c in evidence.columns if c in rename_map}
    return evidence.rename(columns=existing)


def build_groups_from_verified_evidence(
    verified_csv: str,
    device_list_csv: str,
    device_type_csv: str,
    output_csv: str,
) -> pd.DataFrame:
    """
    Build Dimension I device groups from verified documentary evidence.

    Expected verified evidence columns for Stage 1:
      Vendor1, Vendor2, Relationship_Type, Ecosystem_Link, Is_Related

    Expected verified evidence columns for Stage 2:
      Vendor, Device_Type, Ecosystem_Link, Is_Related

    For compatibility, the ecosystem-link column may also be named
    Platform, platform, or ecosystem_link.
    """
    evidence = canonicalize_evidence_columns(pd.read_csv(verified_csv, dtype=str).fillna(""))
    _, device_type, vendor_devices, _ = load_device_metadata(device_list_csv, device_type_csv)

    groups: List[Dict[str, Any]] = []
    gid = 0

    # Parent/Subsidiary evidence directly groups all IoT devices from two vendors.
    if {"Vendor1", "Vendor2", "Relationship_Type", "Is_Related"}.issubset(evidence.columns):
        for _, row in evidence.iterrows():
            if str(row["Is_Related"]).lower() not in {"true", "1", "yes"}:
                continue
            relationship = row["Relationship_Type"]
            if relationship != "Parent/Subsidiary":
                continue
            v1, v2 = row["Vendor1"], row["Vendor2"]
            devices = sorted(vendor_devices.get(v1, set()) | vendor_devices.get(v2, set()))
            if len(devices) < 2:
                continue
            gid += 1
            groups.append(
                {
                    "Cluster_ID": f"D1_{gid:04d}",
                    "Relationship_Type": relationship,
                    "Platform": "",
                    "Num_Devices": len(devices),
                    "Num_Vendors": len({v1.lower(), v2.lower()}),
                    "Devices": "|".join(devices),
                    "Vendors": "|".join(sorted({v1, v2})),
                }
            )

    # Ecosystem/platform evidence groups all related vendors/devices by normalized platform.
    platform_to_devices: Dict[str, Set[str]] = defaultdict(set)
    platform_to_vendors: Dict[str, Set[str]] = defaultdict(set)

    if {"Vendor", "Platform", "Device_Type", "Is_Related"}.issubset(evidence.columns):
        for _, row in evidence.iterrows():
            if str(row["Is_Related"]).lower() not in {"true", "1", "yes"}:
                continue
            vendor = row["Vendor"]
            platform = normalize_platform(row["Platform"])
            dtype = row["Device_Type"]
            if not platform:
                continue
            for device in vendor_devices.get(vendor, set()):
                if device_type.get(device) == dtype:
                    platform_to_devices[platform].add(device)
                    platform_to_vendors[platform].add(vendor)

    for platform, devices_set in sorted(platform_to_devices.items()):
        vendors = platform_to_vendors[platform]
        if len(devices_set) < 2 or len(vendors) < 2:
            continue
        gid += 1
        groups.append(
            {
                "Cluster_ID": f"D1_{gid:04d}",
                "Relationship_Type": "Ecosystem",
                "Platform": platform,
                "Num_Devices": len(devices_set),
                "Num_Vendors": len(vendors),
                "Devices": "|".join(sorted(devices_set)),
                "Vendors": "|".join(sorted(vendors)),
            }
        )

    out = pd.DataFrame(groups)
    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    out.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"[+] documentary groups: {len(out):,} -> {output_csv}")
    return out


def export_prompts(output_md: str) -> None:
    os.makedirs(os.path.dirname(output_md) or ".", exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write("# Dimension I LLM Prompts\n\n")
        f.write("## Stage 1: Inter-Vendor Connection Identification\n\n```text\n")
        f.write(PROMPT_STAGE1)
        f.write("\n```\n\n## Stage 2: Device-Level Ecosystem Verification\n\n```text\n")
        f.write(PROMPT_STAGE2)
        f.write("\n```\n")
    print(f"[+] prompts -> {output_md}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dimension I documentary evidence utilities.")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("build-groups")
    p1.add_argument("--verified-csv", required=True)
    p1.add_argument("--device-list-csv", required=True)
    p1.add_argument("--device-type-csv", required=True)
    p1.add_argument("--output-csv", required=True)

    p2 = sub.add_parser("export-prompts")
    p2.add_argument("--output-md", required=True)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "build-groups":
        build_groups_from_verified_evidence(
            args.verified_csv,
            args.device_list_csv,
            args.device_type_csv,
            args.output_csv,
        )
    elif args.command == "export-prompts":
        export_prompts(args.output_md)


if __name__ == "__main__":
    main()
