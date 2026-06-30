# IoTSupplyChainTracing Core

This repository contains a first-stage public release of the core code for
3D-SCM: a three-dimensional IoT supply-chain measurement framework.

The release focuses on the deterministic and reusable pipeline components:

1. traffic flow preprocessing,
2. Dimension I documentary evidence normalization,
3. Dimension II endpoint matching,
4. Dimension III PS-DTW behavioral clustering,
5. corroboration and overlap analysis.

Raw PCAPs and large derived flow files are not redistributed here. The code
uses explicit input/output paths rather than hard-coded local paths.

## Directory

```text
src/
  flow_preprocessing.py       PCAP parsing, DNS timestamp matching, flow filtering
  documentary_evidence.py     Dimension I prompts/evidence normalization
  endpoint_matching.py        Dimension II shared-domain matching
  ps_dtw.py                   PS-DTW distance/similarity functions
  behavior_clustering.py      Dimension III two-stage clustering
  corroboration.py            Rule I-IV corroboration
  overlap_analysis.py         Cross-dimension overlap analysis

configs/
  default.yaml                Example configuration

docs/
  pipeline.md                 Pipeline command examples
  input_schema.md             Required input/result columns

outputs/
  documentary_groups.csv      Dimension I verified documentary groups
  endpoint_groups.csv         Dimension II endpoint-sharing groups
  dim3_candidate_groups.csv   Dimension III candidate groups before corroboration
  corroboration_results.csv   Retained Dimension III groups with rule evidence
```

## Minimal pipeline

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

# 7. Export Dim III candidate groups
python src/behavior_clustering.py export-groups \
  --global-component-csv outputs/global_components.csv \
  --output-csv outputs/dim3_candidate_groups.csv

# 8. Corroboration
python src/corroboration.py \
  --global-component-csv outputs/global_components.csv \
  --dim3-groups-csv outputs/dim3_candidate_groups.csv \
  --dim1-groups-csv outputs/documentary_groups.csv \
  --dim2-groups-csv outputs/endpoint_groups.csv \
  --output-csv outputs/corroboration_results.csv
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
