# Pipeline Notes

The first-stage release follows the same high-level flow as the research code,
while keeping raw PCAPs, raw DNS logs, LLM raw responses, and large intermediate
artifacts outside the public repository.

The unified entry point is:

```bash
python scripts/run_pipeline.py --config configs/default.yaml --stage <stage>
```

Supported stages are `preprocess`, `dim1`, `dim2`, `dim3`, `overlap`, and
`all`. Dimension I supports `run`, `reuse`, and `skip`; `run` writes cached,
unreviewed LLM assessments and candidates without replacing the reviewed
release result.

1. `flow_preprocessing.py`
   - reconstructs TCP/UDP flows from PCAPs;
   - extracts signed packet-length sequences;
   - maps remote IPs to DNS domains using timestamped DNS events;
   - filters non-routable endpoints, standardized protocol ports, and short flows.

2. `documentary_evidence.py`
   - records the Dimension I prompts used for documented inter-vendor evidence;
   - normalizes verified group-level documentary evidence;
   - does not require users to rerun the LLM assessment in the main pipeline.

3. `endpoint_matching.py`
   - builds device-to-domain sets;
   - identifies device pairs sharing backend domains;
   - reconstructs each domain's complete device set using both same-vendor and
     cross-vendor pairs;
   - consolidates identical cross-vendor device sets into the final Dimension II
     groups and optionally attaches manually curated domain-level annotations.

The grouping algorithm produces cluster IDs, vendors, devices, and shared
domains. The manually curated domain-level table supplies provider,
provider-role, provider-subrole, annotation-confidence, and annotation-note
fields.

4. `behavior_clustering.py` + `ps_dtw.py`
   - first clusters flows within each device and keeps medoid representatives;
   - then globally clusters medoids across devices using PS-DTW.

5. `overlap_analysis.py`
   - treats the three dimensions as independent measurement outputs;
   - classifies all Dimension I, II, and III groups into the seven overlap
     categories reported in Table VI of the paper.

## Released result files

The group-level results currently released under `outputs/` are:

```text
outputs/documentary_groups.csv
outputs/endpoint_groups.csv
outputs/behavior_groups.csv
outputs/overlap_details.csv
outputs/overlap_summary.csv
```

`behavior_groups.csv` contains the 81 final cross-vendor behavioral groups from
Dimension III. These groups are not filtered using Dimension I or Dimension II;
the dimensions are compared only in the subsequent overlap analysis.

`overlap_details.csv` classifies all 186 released groups by dimensional
coverage. `overlap_summary.csv` contains the seven aggregate categories
reported in Table VI.

## Local-only inputs

The preprocessing pipeline may require local dataset paths, local PCAP paths,
and a local manual IP mapping CSV. These files are user-specific and should not
be committed to the repository. See `docs/dataset.md` for the expected local
layout and optional `--manual-ip-csv` format.
