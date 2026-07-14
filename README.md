# IoTSupplyChainTracing

This repository contains the public implementation and released group-level
results for 3D-SCM, a three-dimensional IoT supply-chain measurement framework.

The release focuses on the deterministic and reusable pipeline components:

1. traffic flow preprocessing,
2. Dimension I documentary relationship assessment and normalization,
3. Dimension II endpoint matching,
4. Dimension III PS-DTW behavioral clustering,
5. cross-dimensional overlap analysis.

The three dimensions operate independently, as described in the submitted
paper. Dimension III cross-vendor groups are final measurement results; they
are not filtered by evidence from Dimensions I or II.

Dimension II group construction is deterministic. Provider attribution,
provider roles, domain notes, and annotation confidence are
manually curated annotations layered on top of the generated groups.

Raw PCAPs and large derived flow files are not redistributed here. The code
uses explicit input/output paths rather than hard-coded local paths.

## Repository contents

```text
.
|-- README.md                          Project overview and execution guide
|-- LICENSE                            Repository license
|-- requirements.txt                   Python dependencies
|-- .gitignore                         Local caches and generated-file exclusions
|-- configs/
|   `-- default.yaml                   Paths, stage modes, and algorithm parameters
|-- scripts/
|   `-- run_pipeline.py                Unified stage runner
|-- src/
|   |-- flow_preprocessing.py          PCAP parsing, DNS matching, and flow filtering
|   |-- device_names.py                Canonical device-name normalization
|   |-- documentary_evidence.py        Dimension I prompts and result validation
|   |-- dim1_assessment.py             Optional two-stage LLM assessment and caching
|   |-- endpoint_matching.py           Dimension II shared-domain grouping
|   |-- ps_dtw.py                      PS-DTW distance and similarity functions
|   |-- behavior_clustering.py         Dimension III two-stage clustering and export
|   `-- overlap_analysis.py            Cross-dimensional Table VI analysis
|-- data/
|   |-- README.md                      Data-file descriptions
|   |-- dataset_manifest.csv           Original dataset sources and access links
|   |-- device_list.csv                Vendor metadata for 247 analyzed devices
|   |-- device_type.csv                Type metadata for 247 analyzed devices
|   `-- domain_level_annotation.csv    Dimension II provider annotations
|-- outputs/
|   |-- README.md                      Released-output schemas
|   |-- documentary_groups.csv         36 Dimension I groups
|   |-- endpoint_groups.csv            69 Dimension II groups
|   |-- behavior_groups.csv            81 Dimension III groups
|   |-- overlap_details.csv            186 per-group overlap classifications
|   `-- overlap_summary.csv            Seven Table VI category counts
|-- docs/
|   |-- dataset.md                     Dataset acquisition and local preparation
|   |-- input_schema.md                Input and released-output schemas
|   `-- pipeline.md                    Stage behavior and artifact flow
`-- tests/
    |-- test_device_names.py           Device-name normalization checks
    |-- test_documentary_evidence.py   Dimension I schema and 36-group regression
    |-- test_dim1_assessment.py        LLM candidate generation and cache checks
    |-- test_endpoint_matching.py      Dimension II grouping and annotation checks
    |-- test_ps_dtw.py                 PS-DTW numerical sanity check
    |-- test_behavior_clustering.py    Dimension III exporter checks
    `-- test_overlap_analysis.py       186-group and Table VI regression checks
```

## Installation

Python 3.10 or later is recommended.

```bash
python -m pip install -r requirements.txt
```

## Pipeline entry point

The unified runner supports `preprocess`, `dim1`, `dim2`, `dim3`, `overlap`,
and `all` stages:

```bash
python scripts/run_pipeline.py --config configs/default.yaml --stage dim1
python scripts/run_pipeline.py --config configs/default.yaml --stage dim3 --dry-run
```

Before running `preprocess` or `all`, set the local raw-PCAP directories in
`paths.dataset_roots` in `configs/default.yaml`. A dry run prints the commands
without executing them.

Dimension I has three modes in `configs/default.yaml`:

- `reuse` (default): validate and reuse the reviewed released groups;
- `run`: call Gemini with the appendix prompts and write unreviewed Stage 1,
  Stage 2, and candidate outputs under `outputs/dim1_assessment/`;
- `skip`: do not execute Dimension I.

`run` requires `GEMINI_API_KEY` in the environment. API keys must not be stored
in the configuration file. LLM candidates do not overwrite the reviewed
`outputs/documentary_groups.csv`; local API caches and candidate files are
excluded by `.gitignore`.

Individual module commands remain available:

```bash
# 1. Extract flows from PCAPs
python src/flow_preprocessing.py extract \
  --root-dirs /path/to/dataset \
  --manual-ip-csv <LOCAL_MANUAL_IP_CSV> \
  --device-type-csv data/device_type.csv \
  --output-pickle outputs/traffic_features.pkl \
  --checkpoint-log outputs/processed_files.log \
  --workers 16

# 2. Merge batch outputs
python src/flow_preprocessing.py merge \
  --batch-prefix outputs/traffic_features.pkl \
  --output-pickle outputs/Traffic_Cleaned_v2_merged.pkl

# 3. Filter flows
python src/flow_preprocessing.py filter \
  --input-pickle outputs/Traffic_Cleaned_v2_merged.pkl \
  --output-pickle outputs/Traffic_Cleaned_v3_Final.pkl \
  --device-list-csv data/device_list.csv

# 4. Dimension II endpoint matching
python src/endpoint_matching.py \
  --input-pickle outputs/Traffic_Cleaned_v3_Final.pkl \
  --pair-output-csv outputs/endpoint_pairs.csv \
  --summary-output-txt outputs/endpoint_summary.txt \
  --domain-annotation-csv data/domain_level_annotation.csv \
  --group-output-csv outputs/endpoint_groups.csv

# Alternatively, export groups from an existing pair-level result
python src/endpoint_matching.py \
  --pair-input-csv /path/to/endpoint_matching_result.csv \
  --domain-annotation-csv data/domain_level_annotation.csv \
  --group-output-csv outputs/endpoint_groups.csv

# 5. Dimension III in-device medoid extraction
python src/behavior_clustering.py in-device \
  --input-pickle outputs/Traffic_Cleaned_v3_Final.pkl \
  --output-pickle outputs/in_device_representatives.pkl \
  --checkpoint-pickle outputs/in_device_checkpoint.pkl

# 6. Dimension III global clustering
python src/behavior_clustering.py global \
  --input-pickle outputs/in_device_representatives.pkl \
  --output-csv outputs/global_components.csv \
  --device-type-csv data/device_type.csv \
  --matrix-cache outputs/global_distance_matrix.npy

# 7. Export final Dimension III cross-vendor behavioral groups
python src/behavior_clustering.py export-groups \
  --global-component-csv outputs/global_components.csv \
  --output-csv outputs/behavior_groups.csv

# 8. Analyze complementarity among the three independent dimensions
python src/overlap_analysis.py \
  --dim1-csv outputs/documentary_groups.csv \
  --dim2-csv outputs/endpoint_groups.csv \
  --dim3-csv outputs/behavior_groups.csv \
  --output-csv outputs/overlap_details.csv \
  --summary-output-csv outputs/overlap_summary.csv
```

## Notes

- Dimension I defaults to reusing and validating
  `outputs/documentary_groups.csv`; LLM execution is available through `run`
  mode but is not required.
- The PS-DTW implementation uses Numba when available and falls back to Python
  functions when Numba is unavailable.
- Large-scale clustering can require substantial memory because hierarchical
  clustering uses pairwise distance matrices.


## Data Sources

Raw PCAP files are not redistributed in this repository. The public dataset
sources and acquisition links are listed in `data/dataset_manifest.csv`, with
additional preparation notes in `docs/dataset.md`. The repository includes the
dataset source manifest, group-level released results, and code for processing
locally obtained datasets.
