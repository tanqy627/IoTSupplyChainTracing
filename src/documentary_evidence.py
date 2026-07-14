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
  - tech-link normalization helpers;
  - utilities for validating and normalizing released documentary groups.

The released Dimension I result is expected to use the group-level schema:

    Cluster_ID, Tech_Link, Connection_Type, Num_Vendors, Num_Devices,
    Vendors, Devices, Provider, Provider_Role, Provider_Subrole

It should not contain raw LLM responses, API logs, API keys, local paths, IP
addresses, or intermediate LLM cache files.
"""

from __future__ import annotations

import argparse
import os
import re
from typing import Dict, List, Sequence

import pandas as pd

try:
    from .device_names import canonicalize_device_name
except ImportError:
    from device_names import canonicalize_device_name


TECH_LINK_ALIASES = {
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
    "Cluster_ID",
    "Tech_Link",
    "Connection_Type",
    "Num_Vendors",
    "Num_Devices",
    "Vendors",
    "Devices",
    "Provider",
    "Provider_Role",
    "Provider_Subrole",
]

CONNECTION_TYPES = {"Technical Integration", "Corporate Affiliation"}

COLUMN_ALIASES = {
    "Group_ID": "Cluster_ID",
    "Platform": "Tech_Link",
    "Ecosystem_Link": "Tech_Link",
    "Relationship_Type": "Connection_Type",
    "provider": "Provider",
    "provider_role": "Provider_Role",
    "provider_subrole": "Provider_Subrole",
}

CONNECTION_TYPE_ALIASES = {
    "Ecosystem": "Technical Integration",
    "Parent/Subsidiary": "Corporate Affiliation",
}


PROMPT_STAGE1 = """You are an IoT supply chain analyst.

Vendor 1: "{vendor1}"
Vendor 2: "{vendor2}"

Do these two vendors have any publicly documented supply chain relationships?

Accepted connection types:
- Corporate Affiliation: the two vendors have a documented corporate-
  or brand-level affiliation, such as shared ownership, acquisition,
  sub-branding, or operation under the same corporate group.
- Technical Integration: the two vendors are connected through a
  documented technical relationship, such as a shared platform, SDK,
  cloud service, certification program, technology partnership,
  integration partnership, or product compatibility program. Both
  vendors remain independent, but their devices may depend on or
  interoperate through the same shared technical basis.

For a Technical Integration relationship, identify the specific shared
technical basis as the technical link. Examples include Amazon Alexa,
Google Home, Apple HomeKit, Matter, Tuya, a shared SDK, a shared cloud
service, a certification program, or a named technology partnership.

ACCEPT only if:
- The relationship is publicly documented, such as in an official
  website, press release, partnership announcement, certification
  list, product compatibility page, SDK/cloud documentation, or
  corporate filing.
- You are certain based on known public documentation.

REJECT if:
- No publicly documented evidence exists.
- The relationship is only a generic business partnership,
  reseller/channel relationship, marketing collaboration, or
  co-branding activity without evidence of concrete corporate
  affiliation or technical integration.
- You are uncertain or would need to speculate.

OUTPUT FORMAT (JSON):
{{
  "is_related": true or false,
  "connection_type": "Corporate Affiliation|Technical Integration|None",
  "technical_link": "specific technical link or None",
  "reason": "one sentence"
}}"""


PROMPT_STAGE2 = """You are an IoT supply chain analyst.

Vendor: "{vendor}"
Device type: {device_type}
Tech-link: "{technical_link}"

Does {vendor}'s {device_type} officially support, integrate with, depend
on, or interoperate through {technical_link}?

ACCEPT if:
- There is publicly documented evidence that this vendor's device type
  supports, integrates with, depends on, or interoperates through the
  given tech-link.
- Acceptable evidence includes certification lists, official partner
  pages, SDK/cloud documentation, product compatibility pages, press
  releases, product manuals, or official product listings.

REJECT if:
- The vendor has a general relationship with the tech-link, but there
  is no evidence that this specific device type supports, integrates
  with, depends on, or interoperates through it.
- The evidence only applies to a different device type from the same
  vendor.
- No publicly documented evidence exists.
- You are uncertain or would need to speculate.

OUTPUT FORMAT (JSON):
{{
  "is_related": true or false,
  "reason": "one sentence"
}}"""


def split_tech_links(tech_link: str) -> List[str]:
    """Split strings such as 'Amazon Alexa and Google Home' into tech-links."""
    if not tech_link or str(tech_link).lower() in {"none", "null", "nan", ""}:
        return []
    normalized = re.sub(r"\s+and\s+", "|", str(tech_link), flags=re.IGNORECASE)
    normalized = re.sub(r"\s*[,;/]\s*", "|", normalized)
    return [p.strip() for p in normalized.split("|") if p.strip()]


def normalize_tech_link(tech_link: str, aliases: Dict[str, str] = TECH_LINK_ALIASES) -> str:
    """Normalize common aliases for technical-link names."""
    if not tech_link or str(tech_link).lower() in {"none", "null", "nan", ""}:
        return ""
    value = str(tech_link).strip()
    return aliases.get(value, value)


# Backward-compatible helper aliases.
split_platforms = split_tech_links
normalize_platform = normalize_tech_link


def canonicalize_documentary_groups(df: pd.DataFrame) -> pd.DataFrame:
    """Convert supported legacy input names and values to the release schema."""
    df = df.copy().fillna("")
    for old_name, canonical_name in COLUMN_ALIASES.items():
        if canonical_name not in df.columns and old_name in df.columns:
            df = df.rename(columns={old_name: canonical_name})

    for optional in ["Provider", "Provider_Role", "Provider_Subrole"]:
        if optional not in df.columns:
            df[optional] = ""

    missing = [col for col in DOCUMENTARY_GROUP_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"documentary groups CSV missing columns: {missing}")

    out = df[DOCUMENTARY_GROUP_COLUMNS].copy()
    out["Connection_Type"] = out["Connection_Type"].map(
        lambda value: CONNECTION_TYPE_ALIASES.get(str(value).strip(), str(value).strip())
    )
    out["Devices"] = out["Devices"].map(
        lambda value: "|".join(
            canonicalize_device_name(device)
            for device in str(value).split("|")
            if device.strip()
        )
    )
    for col in ["Num_Vendors", "Num_Devices"]:
        out[col] = pd.to_numeric(out[col], errors="raise").astype(int)
    return out


def validate_documentary_groups(df: pd.DataFrame) -> None:
    """Validate schema and internal consistency without fixing release counts."""
    missing = [col for col in DOCUMENTARY_GROUP_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"documentary groups CSV missing columns: {missing}")
    if df["Cluster_ID"].duplicated().any():
        duplicates = sorted(df.loc[df["Cluster_ID"].duplicated(), "Cluster_ID"].unique())
        raise ValueError(f"duplicate Cluster_ID values: {duplicates}")

    invalid_types = sorted(set(df["Connection_Type"]) - CONNECTION_TYPES)
    if invalid_types:
        raise ValueError(f"unsupported Connection_Type values: {invalid_types}")

    for _, row in df.iterrows():
        vendors = {value.strip() for value in str(row["Vendors"]).split("|") if value.strip()}
        devices = {value.strip() for value in str(row["Devices"]).split("|") if value.strip()}
        if int(row["Num_Vendors"]) != len(vendors):
            raise ValueError(f"{row['Cluster_ID']}: Num_Vendors does not match Vendors")
        if int(row["Num_Devices"]) != len(devices):
            raise ValueError(f"{row['Cluster_ID']}: Num_Devices does not match Devices")
        if not str(row["Tech_Link"]).strip():
            raise ValueError(f"{row['Cluster_ID']}: Tech_Link is empty")


def normalize_documentary_groups(
    input_csv: str,
    output_csv: str,
    *,
    normalize_tech_link_names: bool = True,
) -> pd.DataFrame:
    """Validate and normalize a Dimension I group-level evidence file.

    Legacy field names and connection-type values are accepted as input. The
    output always uses the current release schema.
    """
    out = canonicalize_documentary_groups(pd.read_csv(input_csv, dtype=str))
    if normalize_tech_link_names:
        out["Tech_Link"] = out["Tech_Link"].map(normalize_tech_link)
    validate_documentary_groups(out)

    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    out.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"[+] documentary groups: {len(out):,} -> {output_csv}")
    return out


def load_documentary_groups(path: str) -> pd.DataFrame:
    """Load a released Dimension I group-level evidence CSV."""
    out = canonicalize_documentary_groups(pd.read_csv(path, dtype=str))
    validate_documentary_groups(out)
    return out


def export_prompts(output_md: str) -> None:
    """Export the Dimension I prompts to a Markdown file for transparency."""
    os.makedirs(os.path.dirname(output_md) or ".", exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write("# Dimension I LLM Prompts\n\n")
        f.write("These prompts document the LLM-assisted assessment used to produce ")
        f.write("verified Dimension I evidence. The main public pipeline consumes ")
        f.write("`outputs/documentary_groups.csv` and does not require rerunning the LLM.\n\n")
        f.write("## Stage 1: Vendor-Level Connection Identification\n\n```text\n")
        f.write(PROMPT_STAGE1)
        f.write("\n```\n\n## Stage 2: Device-Type Tech-Link Assessment\n\n```text\n")
        f.write(PROMPT_STAGE2)
        f.write("\n```\n")
    print(f"[+] prompts -> {output_md}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dimension I documentary evidence utilities.")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("normalize-groups", help="validate and normalize group-level documentary evidence")
    p1.add_argument("--input-csv", required=True)
    p1.add_argument("--output-csv", required=True)
    p1.add_argument(
        "--keep-tech-link-names", "--keep-platform-names",
        dest="keep_tech_link_names", action="store_true",
        help="do not apply tech-link alias normalization",
    )

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
            normalize_tech_link_names=not args.keep_tech_link_names,
        )
    elif args.command == "export-prompts":
        export_prompts(args.output_md)
    else:
        parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
