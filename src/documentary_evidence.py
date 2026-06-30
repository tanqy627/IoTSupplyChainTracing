#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
documentary_evidence.py
=======================

Dimension I: documented inter-vendor relationship evidence.

The first-stage public release treats Dimension I as verified group-level
external evidence rather than a mandatory LLM execution pipeline. This module
therefore provides:
  - the prompts used for the documentary assessment;
  - platform/ecosystem-link normalization helpers;
  - utilities for validating and normalizing released documentary groups.

The released Dimension I result is expected to use the group-level schema:

    Group_ID, Platform, Relationship_Type, Num_Vendors, Num_Devices, Vendors, Devices

It should not contain raw LLM responses, API logs, API keys, local paths, IP
addresses, or intermediate LLM cache files.
"""

from __future__ import annotations

import argparse
import os
import re
from typing import Dict, List, Sequence

import pandas as pd


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

DOCUMENTARY_GROUP_COLUMNS = [
    "Group_ID",
    "Platform",
    "Relationship_Type",
    "Num_Vendors",
    "Num_Devices",
    "Vendors",
    "Devices",
]


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
    """Normalize common aliases for platform/ecosystem-link names."""
    if not platform or str(platform).lower() in {"none", "null", "nan", ""}:
        return ""
    value = str(platform).strip()
    return aliases.get(value, value)


def normalize_documentary_groups(
    input_csv: str,
    output_csv: str,
    *,
    normalize_platform_names: bool = True,
) -> pd.DataFrame:
    """Validate and normalize a Dimension I group-level evidence file.

    The input may use `Cluster_ID` instead of `Group_ID`. The output always
    uses the released schema defined in `DOCUMENTARY_GROUP_COLUMNS`.
    """
    df = pd.read_csv(input_csv, dtype=str).fillna("")
    df = df.rename(columns={"Cluster_ID": "Group_ID", "Ecosystem_Link": "Platform"})

    missing = [col for col in DOCUMENTARY_GROUP_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"documentary groups CSV missing columns: {missing}")

    out = df[DOCUMENTARY_GROUP_COLUMNS].copy()
    if normalize_platform_names:
        out["Platform"] = out["Platform"].map(normalize_platform)

    for col in ["Num_Vendors", "Num_Devices"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)

    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    out.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"[+] documentary groups: {len(out):,} -> {output_csv}")
    return out


def load_documentary_groups(path: str) -> pd.DataFrame:
    """Load a released Dimension I group-level evidence CSV."""
    df = pd.read_csv(path, dtype=str).fillna("")
    df = df.rename(columns={"Cluster_ID": "Group_ID", "Ecosystem_Link": "Platform"})
    missing = [col for col in DOCUMENTARY_GROUP_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"documentary groups CSV missing columns: {missing}")
    return df[DOCUMENTARY_GROUP_COLUMNS].copy()


def export_prompts(output_md: str) -> None:
    """Export the Dimension I prompts to a Markdown file for transparency."""
    os.makedirs(os.path.dirname(output_md) or ".", exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write("# Dimension I LLM Prompts\n\n")
        f.write("These prompts document the LLM-assisted assessment used to produce ")
        f.write("verified Dimension I evidence. The main public pipeline consumes ")
        f.write("`outputs/documentary_groups.csv` and does not require rerunning the LLM.\n\n")
        f.write("## Stage 1: Inter-Vendor Connection Identification\n\n```text\n")
        f.write(PROMPT_STAGE1)
        f.write("\n```\n\n## Stage 2: Device-Level Ecosystem Verification\n\n```text\n")
        f.write(PROMPT_STAGE2)
        f.write("\n```\n")
    print(f"[+] prompts -> {output_md}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dimension I documentary evidence utilities.")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("normalize-groups", help="validate and normalize group-level documentary evidence")
    p1.add_argument("--input-csv", required=True)
    p1.add_argument("--output-csv", required=True)
    p1.add_argument("--keep-platform-names", action="store_true", help="do not apply platform alias normalization")

    p2 = sub.add_parser("export-prompts", help="export Dimension I prompts")
    p2.add_argument("--output-md", required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "normalize-groups":
        normalize_documentary_groups(
            args.input_csv,
            args.output_csv,
            normalize_platform_names=not args.keep_platform_names,
        )
    elif args.command == "export-prompts":
        export_prompts(args.output_md)
    else:
        parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
