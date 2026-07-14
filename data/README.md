# Data Files

This directory contains public metadata and annotations used by the pipeline.
Raw PCAP files are not redistributed; obtain them from their original sources
under the corresponding licenses and access terms.

## Contents

```text
data/
|-- README.md                     This file
|-- dataset_manifest.csv          Dataset sources, links, and redistribution status
|-- device_list.csv               Device-to-vendor metadata
|-- device_type.csv               Device-to-type metadata
`-- domain_level_annotation.csv   Dimension II provider annotations
```

- `dataset_manifest.csv` records the seven source datasets, collection
  campaigns, descriptions, original links, and redistribution status.
- `device_list.csv` maps the 247 analyzed devices to vendors.
- `device_type.csv` maps the same 247 canonical device names to device types.
- `domain_level_annotation.csv` contains the manually curated Provider-based
  annotations for the 87 domains used in the released Dimension II groups.
  `Cluster_IDs`, `Num_Clusters`, `Num_Vendors_Observed`, and
  `Num_Devices_Observed` are derived traceability fields.

Detailed column definitions are provided in `docs/input_schema.md`.

## Local raw data

Store downloaded PCAPs outside the repository and configure their directories
in `configs/default.yaml`. If a device IP cannot be inferred from a filename,
provide a local `Full_Path,Manual_IP` mapping with `--manual-ip-csv`. Do not
commit this local mapping because it may contain absolute paths and local IPs.
See `docs/dataset.md` for preparation instructions.
