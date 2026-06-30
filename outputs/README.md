# Output Files

This directory contains group-level results released for the core 3D-SCM pipeline. The files are intentionally limited to structured group-level outputs and do not include raw PCAPs, raw DNS logs, local paths, device IPs, timestamps, LLM raw responses, API logs, distance matrices, or flow-level payload sequences.

## Files

### `documentary_groups.csv`

Dimension I result: groups derived from verified documentary evidence.

Core columns:

- `Group_ID`: group identifier.
- `Platform`: ecosystem link or platform when applicable.
- `Relationship_Type`: documented relationship type, such as `Ecosystem` or `Parent/Subsidiary`.
- `Num_Vendors`, `Num_Devices`: group size statistics.
- `Vendors`, `Devices`: pipe-separated vendor and device lists.

### `endpoint_groups.csv`

Dimension II result: group-level endpoint sharing results.

Core columns:

- `Group_ID`: group identifier.
- `Num_Vendors`, `Num_Devices`, `Num_Domains`: group size statistics.
- `Vendors`, `Devices`: pipe-separated vendor and device lists.
- `Domains`: shared backend domains supporting the group.
- `Domain_Types`: domain categories used in analysis.

### `dim3_candidate_groups.csv`

Dimension III candidate groups before corroboration. This file is intentionally kept minimal and contains only candidate group membership information.

Core columns:

- `Group_ID`: Dimension III candidate group identifier.
- `Num_Vendors`, `Num_Devices`: group size statistics.
- `Vendors`, `Devices`: pipe-separated vendor and device lists.

Corroboration rule outputs are not included in this file. They are reported in `corroboration_results.csv`.

### `corroboration_results.csv`

Retained Dimension III groups after the corroboration step. This file contains the retained groups and the evidence fields used to explain why each group was kept.

Core columns include:

- `Group_ID`, `Num_Vendors`, `Num_Devices`, `Vendors`, `Devices`.
- `Rule_I`, `Rule_II`, `Rule_III`, `Rule_IV`: whether the group passed each corroboration rule.
- `Num_Components`, `Superset_Count`: statistics used by Rule III.
- `Rule_IV_Verified_Ratio`, `Rule_IV_Verified_Count`, `Rule_IV_Verified_Pairs`, `Rule_IV_Anchor_Types`: statistics and pair-level evidence used by Rule IV.
- `Retained`: retained flag. In this released file, all rows are retained groups.
- `Corroboration_Tier`: retained evidence tier.
