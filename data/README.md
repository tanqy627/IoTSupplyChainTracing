# Data

This repository does **not** redistribute raw PCAP files. The original traffic
captures used in the paper should be obtained from their original public
sources, following the corresponding licenses, data-use terms, or access-request
procedures.

## Files Provided in This Repository

```text
data/
├── README.md
└── dataset_manifest.csv
```

`dataset_manifest.csv` records dataset names, collection campaigns, short
descriptions, original sources, acquisition links, and redistribution status.

## Raw Traffic Preparation

After obtaining the raw datasets from the original sources, organize the PCAP
files under a local data directory and configure the paths in `configs/default.yaml`
or pass them through command-line arguments.

The preprocessing code expects each PCAP to be associated with the IoT device IP.
When the device IP cannot be inferred from the filename, provide it through a
local manual IP mapping CSV via `--manual-ip-csv`. This local file is
user-specific and should not be committed to the public repository. Its required
columns are documented in `docs/input_schema.md` and `docs/dataset.md`.
