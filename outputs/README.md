# Output Files

This directory contains the group-level results released for the three dimensions of the 3D-SCM pipeline. The release is intentionally limited to structured group-level outputs and does not include raw PCAPs, raw DNS logs, local paths, device IPs, timestamps, LLM raw responses, API logs, distance matrices, or flow-level payload sequences.

All list-valued fields use `|` as the separator. Empty optional fields are left blank.

## Files

### `documentary_groups.csv`

Dimension I result: 36 groups constructed from verified documentary evidence of cross-vendor connections.

Columns:

- `Cluster_ID`: Dimension I group identifier.
- `Tech_Link`: documented technical link or corporate affiliation defining the group.
- `Connection_Type`: connection category (`Technical Integration` or `Corporate Affiliation`).
- `Num_Vendors`, `Num_Devices`: numbers of vendors and devices in the group.
- `Vendors`, `Devices`: pipe-separated vendor and device lists.
- `provider`: provider associated with the documented connection, when applicable.
- `provider_role`: provider's role in the connection.
- `provider_subrole`: more specific provider role, when applicable.

### `endpoint_groups.csv`

Dimension II result: 69 groups of devices from multiple vendors that share one or more backend domains.

Columns:

- `Cluster_ID`: Dimension II group identifier.
- `Num_Vendors`, `Num_Devices`, `Num_Domains`: numbers of vendors, devices, and shared domains in the group.
- `Vendors`, `Devices`, `Domains`: pipe-separated vendor, device, and domain lists.
- `Domain_Types`: category or categories assigned to the shared domains.
- `Providers`: provider or providers associated with the shared domains.
- `Provider_Roles`: roles of the associated providers.
- `Provider_Subroles`: more specific provider roles, when applicable.
- `Annotation_Confidences`: confidence level or levels for the domain annotations.
- `Domain_Annotation_Notes`: semicolon-separated domain-level annotation notes.

For fields containing multiple annotation values, the values summarize the domains represented in the group; repeated identical values may be consolidated and therefore should not be interpreted as positionally aligned with `Domains`.

### `behavior_groups.csv`

Dimension III result: 81 cross-vendor groups identified from similar behavioral traffic patterns.

Columns:

- `Cluster_ID`: Dimension III group identifier.
- `Num_Vendors`, `Num_Devices`: numbers of vendors and devices in the group.
- `Num_Components`: number of connected components from which the group was derived.
- `Superset_Count`: number of supersets supporting the group.
- `Vendors`, `Devices`: pipe-separated vendor and device lists.
- `Device_Types`: pipe-separated device types represented in the group.
