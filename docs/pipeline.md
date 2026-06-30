# Pipeline Notes

The first-stage release follows the same high-level flow as the research code,
while keeping raw PCAPs, raw DNS logs, LLM raw responses, and large intermediate
artifacts outside the public repository.

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
   - identifies device pairs and groups sharing backend domains.

4. `behavior_clustering.py` + `ps_dtw.py`
   - first clusters flows within each device and keeps medoid representatives;
   - then globally clusters medoids across devices using PS-DTW.

5. `corroboration.py`
   - uses `outputs/documentary_groups.csv` as Rule I evidence;
   - uses `outputs/endpoint_groups.csv` as Rule II evidence;
   - applies Rule I through Rule IV to retain high-confidence Dimension III groups.

6. `overlap_analysis.py`
   - summarizes cross-dimension overlap.

## Released result files

The group-level results currently released under `outputs/` are:

```text
outputs/documentary_groups.csv
outputs/endpoint_groups.csv
outputs/dim3_candidate_groups.csv
outputs/corroboration_results.csv
```

`dim3_candidate_groups.csv` contains all Dimension III candidates before
corroboration. `corroboration_results.csv` contains only retained Dimension III
groups together with the rule-level evidence fields.

## Local-only inputs

The preprocessing pipeline may require local dataset paths, local PCAP paths,
and a local manual IP mapping CSV. These files are user-specific and should not
be committed to the repository. See `docs/dataset.md` for the expected local
layout and optional `--manual-ip-csv` format.
