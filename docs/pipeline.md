# Pipeline Notes

The first-stage release follows the same high-level flow as the research code:

1. `flow_preprocessing.py`
   - reconstructs TCP/UDP flows from PCAPs;
   - extracts signed packet-length sequences;
   - maps remote IPs to DNS domains using timestamped DNS events;
   - filters non-routable endpoints, standardized protocol ports, and short flows.

2. `documentary_evidence.py`
   - records Dimension I prompts;
   - normalizes manually verified documentary evidence into device groups.

3. `endpoint_matching.py`
   - builds device-to-domain sets;
   - identifies device pairs and groups sharing backend domains.

4. `behavior_clustering.py` + `ps_dtw.py`
   - first clusters flows within each device and keeps medoid representatives;
   - then globally clusters medoids across devices using PS-DTW.

5. `corroboration.py`
   - applies Rule I through Rule IV to retain high-confidence Dimension III groups.

6. `overlap_analysis.py`
   - summarizes cross-dimension overlap.
