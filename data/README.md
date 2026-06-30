# Data

This repository does **not** redistribute raw PCAP files. The original traffic
captures used in the paper should be obtained from their original public
sources, following the corresponding licenses, data-use terms, or access-request
procedures.

## Files Provided in This Repository

```text
data/
├── README.md
├── dataset_manifest.csv
└── files_with_suggested_ips.schema.csv
```

`dataset_manifest.csv` records dataset names, collection campaigns, short
descriptions, original sources, acquisition links, and redistribution status.

`files_with_suggested_ips.schema.csv` documents the format of the optional
manual device-IP mapping file used during PCAP preprocessing. It contains only
placeholder paths and must not be replaced by a real mapping file in the public
repository if that file exposes local paths, local IP addresses, or other
environment-specific identifiers.

## Raw Traffic Preparation

After obtaining the raw datasets from the original sources, organize the PCAP
files under a local data directory and configure the paths in `configs/default.yaml`
or pass them through command-line arguments.

The preprocessing code expects each PCAP to be associated with the IoT device IP.
When the device IP cannot be inferred from the filename, provide it through a
local file following the schema in:

```text
data/files_with_suggested_ips.schema.csv
```
