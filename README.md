# IoTSupplyChainTracing

This repository contains a first-stage public release of the core code for
3D-SCM: a three-dimensional IoT supply-chain measurement framework.

The release focuses on the deterministic and reusable pipeline components:

1. traffic flow preprocessing,
2. Dimension I documentary evidence normalization,
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

## Directory

```text
src/
  flow_preprocessing.py       PCAP parsing, DNS timestamp matching, flow filtering
  documentary_evidence.py     Dimension I prompts/evidence normalization
  dim1_assessment.py          Optional Dimension I LLM assessment and caching
  endpoint_matching.py        Dimension II shared-domain matching
  ps_dtw.py                   PS-DTW distance/similarity functions
  behavior_clustering.py      Dimension III two-stage clustering
  overlap_analysis.py         Cross-dimension overlap analysis

configs/
  default.yaml                Example configuration

data/
  device_list.csv             Vendor metadata for 247 analyzed devices
  device_type.csv             Type metadata for 247 analyzed devices

docs/
  pipeline.md                 Pipeline command examples
  input_schema.md             Required input/result columns

outputs/
  documentary_groups.csv      Dimension I verified documentary groups
  endpoint_groups.csv         Dimension II endpoint-sharing groups
  behavior_groups.csv         Dimension III behavioral groups
  overlap_details.csv         Per-group cross-dimensional classification
  overlap_summary.csv         Seven Table VI overlap categories
```

## Minimal pipeline

The unified runner supports `preprocess`, `dim1`, `dim2`, `dim3`, `overlap`,
and `all` stages:

```bash
python scripts/run_pipeline.py --config configs/default.yaml --stage dim1
python scripts/run_pipeline.py --config configs/default.yaml --stage dim3 --dry-run
```

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

- Dimension I is released as verified group-level documentary evidence in
  `outputs/documentary_groups.csv`; the main pipeline does not require users
  to rerun the LLM assessment.
- The PS-DTW implementation uses Numba when available and falls back to Python
  functions when Numba is unavailable.
- Large-scale clustering can require substantial memory because hierarchical
  clustering uses pairwise distance matrices.


## Data Sources

Raw PCAP files are not redistributed in this repository. The public dataset
sources and acquisition links are listed in `data/dataset_manifest.csv`, with
additional preparation notes in `docs/dataset.md`. The repository includes the dataset source manifest, group-level released
results, and code for processing locally obtained datasets.
