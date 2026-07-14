#!/usr/bin/env python3
"""Unified stage runner for the public 3D-SCM pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dim1_assessment import make_gemini_caller, run_dim1_assessment
from src.documentary_evidence import load_documentary_groups


STAGES = ["preprocess", "dim1", "dim2", "dim3", "overlap"]


def load_config(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def run_command(command: List[str], dry_run: bool) -> None:
    print("$", " ".join(command))
    if not dry_run:
        subprocess.run(command, cwd=ROOT, check=True)


def run_dim1(config: Dict[str, Any], dry_run: bool) -> None:
    settings = config.get("dimension1", {})
    paths = config.get("paths", {})
    mode = settings.get("mode", "reuse")
    groups_csv = ROOT / settings.get("groups_csv", "outputs/documentary_groups.csv")

    if mode == "skip":
        print("[dim1] skipped")
        return
    if mode == "reuse":
        print(f"[dim1] validate and reuse {groups_csv}")
        if not dry_run:
            load_documentary_groups(str(groups_csv))
        return
    if mode != "run":
        raise ValueError("dimension1.mode must be run, reuse, or skip")

    print("[dim1] run LLM assessment; output is unreviewed candidates")
    if dry_run:
        return
    caller = make_gemini_caller(
        model=settings.get("model", "gemini-3.1-pro-preview"),
        api_key_env=settings.get("api_key_env", "GEMINI_API_KEY"),
        use_grounding=bool(settings.get("use_grounding", True)),
    )
    run_dim1_assessment(
        device_list_csv=str(ROOT / paths["device_list_csv"]),
        device_type_csv=str(ROOT / paths["device_type_csv"]),
        output_dir=str(ROOT / settings.get("assessment_output_dir", "outputs/dim1_assessment")),
        call_llm=caller,
        cache_dir=str(ROOT / settings.get("cache_dir", "outputs/dim1_cache")),
        max_retries=int(settings.get("max_retries", 3)),
    )


def commands_for_stage(stage: str, config: Dict[str, Any]) -> List[List[str]]:
    py = sys.executable
    paths = config.get("paths", {})
    outputs = paths.get("outputs_dir", "outputs")
    cleaned = paths.get("cleaned_flow_pickle", f"{outputs}/Traffic_Cleaned_v3_Final.pkl")

    if stage == "preprocess":
        roots = paths.get("dataset_roots", [])
        if not roots:
            raise ValueError("paths.dataset_roots is required for preprocess")
        flow = config.get("flow_preprocessing", {})
        extracted = f"{outputs}/traffic_features.pkl"
        merged = f"{outputs}/Traffic_Cleaned_v2_merged.pkl"
        extract = [
            py, "src/flow_preprocessing.py", "extract", "--root-dirs", *roots,
            "--device-type-csv", paths["device_type_csv"], "--output-pickle", extracted,
            "--checkpoint-log", f"{outputs}/processed_files.log",
            "--workers", str(flow.get("workers", 16)),
            "--flow-timeout", str(flow.get("flow_timeout", 120)),
            "--save-interval", str(flow.get("save_interval", 200)),
        ]
        if paths.get("manual_ip_csv"):
            extract.extend(["--manual-ip-csv", paths["manual_ip_csv"]])
        return [
            extract,
            [py, "src/flow_preprocessing.py", "merge", "--batch-prefix", extracted,
             "--output-pickle", merged],
            [py, "src/flow_preprocessing.py", "filter", "--input-pickle", merged,
             "--output-pickle", cleaned, "--device-list-csv", paths["device_list_csv"],
             "--min-packet-count", str(flow.get("min_packet_count", 5)),
             "--block-ports", *map(str, flow.get("standardized_protocol_ports", [37, 53, 123]))],
        ]
    if stage == "dim2":
        pair_input = paths.get("endpoint_pair_input_csv")
        if pair_input:
            return [[py, "src/endpoint_matching.py", "--pair-input-csv", pair_input,
                     "--domain-annotation-csv", paths["domain_annotation_csv"],
                     "--group-output-csv", f"{outputs}/endpoint_groups.csv"]]
        return [[py, "src/endpoint_matching.py", "--input-pickle", cleaned,
                 "--pair-output-csv", f"{outputs}/endpoint_pairs.csv",
                 "--domain-annotation-csv", paths["domain_annotation_csv"],
                 "--group-output-csv", f"{outputs}/endpoint_groups.csv"]]
    if stage == "dim3":
        global_input = paths.get("global_component_input_csv")
        if global_input:
            return [[py, "src/behavior_clustering.py", "export-groups",
                     "--global-component-csv", global_input,
                     "--output-csv", f"{outputs}/behavior_groups.csv"]]
        representatives = f"{outputs}/in_device_representatives.pkl"
        components = f"{outputs}/global_components.csv"
        ps_dtw = config.get("ps_dtw", {})
        shared_args = [
            "--sigma", str(ps_dtw.get("sigma", 35.0)),
            "--similarity-threshold", str(ps_dtw.get("similarity_threshold", 0.90)),
            "--max-seq-len", str(ps_dtw.get("max_seq_len", 100)),
        ]
        return [
            [py, "src/behavior_clustering.py", "in-device", "--input-pickle", cleaned,
             "--output-pickle", representatives, *shared_args,
             "--min-packet-count", str(config.get("flow_preprocessing", {}).get("min_packet_count", 5))],
            [py, "src/behavior_clustering.py", "global", "--input-pickle", representatives,
             "--output-csv", components, "--device-type-csv", paths["device_type_csv"],
             *shared_args],
            [py, "src/behavior_clustering.py", "export-groups",
             "--global-component-csv", components,
             "--output-csv", f"{outputs}/behavior_groups.csv"],
        ]
    if stage == "overlap":
        return [[py, "src/overlap_analysis.py",
                 "--dim1-csv", f"{outputs}/documentary_groups.csv",
                 "--dim2-csv", f"{outputs}/endpoint_groups.csv",
                 "--dim3-csv", f"{outputs}/behavior_groups.csv",
                 "--output-csv", f"{outputs}/overlap_details.csv",
                 "--summary-output-csv", f"{outputs}/overlap_summary.csv"]]
    raise ValueError(f"unknown stage: {stage}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run 3D-SCM pipeline stages.")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--stage", choices=STAGES + ["all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    selected = STAGES if args.stage == "all" else [args.stage]

    for stage in selected:
        print(f"\n== {stage} ==")
        if stage == "dim1":
            run_dim1(config, args.dry_run)
        else:
            for command in commands_for_stage(stage, config):
                run_command(command, args.dry_run)


if __name__ == "__main__":
    main()
