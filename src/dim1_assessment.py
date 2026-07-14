"""Optional LLM execution pipeline for Dimension I candidate generation."""

from __future__ import annotations

import hashlib
import json
import os
import time
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Dict, List

import pandas as pd

from .documentary_evidence import (
    DOCUMENTARY_GROUP_COLUMNS,
    PROMPT_STAGE1,
    PROMPT_STAGE2,
    normalize_tech_link,
    validate_documentary_groups,
)


STAGE1_SCHEMA = {
    "type": "object",
    "properties": {
        "is_related": {"type": "boolean"},
        "connection_type": {
            "type": "string",
            "enum": ["Corporate Affiliation", "Technical Integration", "None"],
        },
        "technical_link": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["is_related", "connection_type", "technical_link", "reason"],
}

STAGE2_SCHEMA = {
    "type": "object",
    "properties": {
        "is_related": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["is_related", "reason"],
}


def _cache_path(cache_dir: str, stage: str, key: Dict[str, str]) -> Path:
    digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
    return Path(cache_dir) / stage / f"{digest}.json"


def _cached_call(
    call_llm: Callable[[str, Dict[str, Any]], Dict[str, Any]],
    prompt: str,
    schema: Dict[str, Any],
    cache_dir: str,
    stage: str,
    key: Dict[str, str],
    max_retries: int,
) -> Dict[str, Any]:
    path = _cache_path(cache_dir, stage, key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            result = call_llm(prompt, schema)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result
        except Exception as exc:  # network/provider errors are retried and recorded by caller
            error = exc
            if attempt < max_retries:
                time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"LLM call failed after {max_retries + 1} attempts") from error


def make_gemini_caller(
    model: str,
    api_key_env: str = "GEMINI_API_KEY",
    use_grounding: bool = True,
) -> Callable[[str, Dict[str, Any]], Dict[str, Any]]:
    """Create a Gemini Interactions API caller with structured JSON output."""
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"missing environment variable: {api_key_env}")
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("Dimension I run mode requires the google-genai package") from exc

    client = genai.Client(api_key=api_key)

    def call(prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "model": model,
            "input": prompt,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": schema,
            },
        }
        if use_grounding:
            kwargs["tools"] = [{"type": "google_search"}, {"type": "url_context"}]
        response = client.interactions.create(**kwargs)
        try:
            provider_response = response.model_dump(mode="json")
        except (AttributeError, TypeError):
            provider_response = {"output_text": response.output_text}
        return {
            "parsed": json.loads(response.output_text),
            "raw_text": response.output_text,
            # Preserve grounding/citation metadata when exposed by the SDK.
            "provider_response": provider_response,
            "model": model,
            "timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        }

    return call


def run_dim1_assessment(
    device_list_csv: str,
    device_type_csv: str,
    output_dir: str,
    call_llm: Callable[[str, Dict[str, Any]], Dict[str, Any]],
    cache_dir: str,
    max_retries: int = 3,
) -> pd.DataFrame:
    """Run both appendix prompts and export unreviewed Dimension I candidates."""
    vendors_df = pd.read_csv(device_list_csv, dtype=str)
    types_df = pd.read_csv(device_type_csv, dtype=str)
    metadata = vendors_df.merge(types_df, on="Device_Name", validate="one_to_one")
    vendors = sorted(metadata["Vendor"].dropna().unique(), key=str.lower)

    stage1_rows: List[Dict[str, Any]] = []
    for vendor1, vendor2 in combinations(vendors, 2):
        key = {"vendor1": vendor1, "vendor2": vendor2}
        result = _cached_call(
            call_llm, PROMPT_STAGE1.format(**key), STAGE1_SCHEMA,
            cache_dir, "stage1", key, max_retries,
        )
        stage1_rows.append({**key, **result["parsed"], "model": result.get("model", "")})

    stage1 = pd.DataFrame(stage1_rows)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    stage1.to_csv(Path(output_dir) / "dim1_stage1_assessments.csv", index=False, encoding="utf-8-sig")

    technical = stage1[
        stage1["is_related"].astype(bool)
        & (stage1["connection_type"] == "Technical Integration")
    ].copy()
    vendor_links: Dict[str, set[str]] = {}
    for _, row in technical.iterrows():
        link = normalize_tech_link(row["technical_link"])
        for vendor in (row["vendor1"], row["vendor2"]):
            vendor_links.setdefault(vendor, set()).add(link)

    stage2_rows: List[Dict[str, Any]] = []
    for vendor, links in sorted(vendor_links.items()):
        device_types = sorted(metadata.loc[metadata["Vendor"] == vendor, "Type"].unique())
        for technical_link in sorted(links):
            for device_type in device_types:
                key = {
                    "vendor": vendor,
                    "device_type": device_type,
                    "technical_link": technical_link,
                }
                result = _cached_call(
                    call_llm, PROMPT_STAGE2.format(**key), STAGE2_SCHEMA,
                    cache_dir, "stage2", key, max_retries,
                )
                stage2_rows.append({**key, **result["parsed"], "model": result.get("model", "")})

    stage2 = pd.DataFrame(stage2_rows)
    stage2.to_csv(Path(output_dir) / "dim1_stage2_assessments.csv", index=False, encoding="utf-8-sig")

    candidates: List[Dict[str, Any]] = []
    affiliations = stage1[
        stage1["is_related"].astype(bool)
        & (stage1["connection_type"] == "Corporate Affiliation")
    ]
    for _, row in affiliations.iterrows():
        member_vendors = sorted([row["vendor1"], row["vendor2"]])
        devices = sorted(metadata.loc[metadata["Vendor"].isin(member_vendors), "Device_Name"])
        candidates.append({
            "Tech_Link": f"Corporate Affiliation ({'/'.join(member_vendors)})",
            "Connection_Type": "Corporate Affiliation",
            "Vendors": "|".join(member_vendors),
            "Devices": "|".join(devices),
            "Provider": "",
            "Provider_Role": "Corporate Affiliation",
            "Provider_Subrole": "",
        })

    if not stage2.empty:
        accepted = stage2[stage2["is_related"].astype(bool)]
        for link, group in accepted.groupby("technical_link"):
            member_vendors = sorted(group["vendor"].unique())
            if len(member_vendors) < 2:
                continue
            approved = {(row.vendor, row.device_type) for row in group.itertuples()}
            devices = sorted(
                row.Device_Name for row in metadata.itertuples()
                if (row.Vendor, row.Type) in approved
            )
            candidates.append({
                "Tech_Link": link,
                "Connection_Type": "Technical Integration",
                "Vendors": "|".join(member_vendors),
                "Devices": "|".join(devices),
                "Provider": "",
                "Provider_Role": "",
                "Provider_Subrole": "",
            })

    candidates.sort(key=lambda row: (row["Connection_Type"], row["Tech_Link"]))
    for index, row in enumerate(candidates, 1):
        row["Cluster_ID"] = f"D1_CAND_{index:04d}"
        row["Num_Vendors"] = len(set(row["Vendors"].split("|")))
        row["Num_Devices"] = len(set(row["Devices"].split("|"))) if row["Devices"] else 0
    out = pd.DataFrame(candidates, columns=DOCUMENTARY_GROUP_COLUMNS)
    if not out.empty:
        validate_documentary_groups(out)
    out.to_csv(Path(output_dir) / "dim1_candidates.csv", index=False, encoding="utf-8-sig")
    return out
