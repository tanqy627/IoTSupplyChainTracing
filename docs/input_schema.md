# Input Schema

This document describes the expected input columns for running the core
pipeline locally, and the schema of the released group-level evidence files.
Raw PCAP files and large flow-level artifacts are not redistributed in this
repository.

## Cleaned flow pickle

Each cleaned flow record should be a dictionary with the following fields:

| Field | Description |
|---|---|
| `Device` | Device name used throughout the pipeline. |
| `Vendor` | Vendor/manufacturer/brand label. |
| `Device_IP` | Local IoT device IP address. This is required only during preprocessing and should not be included in released results. |
| `Remote_IP` | Remote endpoint IP address. This is required only during preprocessing and should not be included in released results. |
| `Protocol` | Transport protocol, such as `TCP` or `UDP`. |
| `Device_Port` | Device-side port. |
| `Server_Port` | Remote endpoint port. |
| `Flow_Start_TS` | Flow start timestamp. This should not be included in released results. |
| `Domain` | DNS-derived domain mapped to `Remote_IP`. |
| `Payload_Sequence` | Signed packet-length sequence; positive values represent device-to-remote packets and negative values represent remote-to-device packets. |
| `Pcap_Filename` | Source PCAP filename. This should be sanitized before release. |
| `Source_Full_Path` | Local source PCAP path. This is user-specific and should not be committed or released. |

## Device list CSV

Required columns:

```csv
Device_Name,Vendor
```

## Device type CSV

Required columns:

```csv
Device_Name,Type
```

## Optional manual IP CSV

If the IoT device IP cannot be inferred from the PCAP filename, users may
provide a local manual IP mapping file via `--manual-ip-csv`. This file is
user-specific and should not be committed to the repository.

Required columns:

```csv
Full_Path,Manual_IP
```

Example:

```csv
Full_Path,Manual_IP
<LOCAL_DATA_ROOT>/UNSW/example_device/example_capture.pcap,192.168.1.10
```

## Dimension I documentary groups CSV

Dimension I is released as verified, group-level documentary evidence. It is
used by the corroboration module as Rule I evidence. The released file is:

```text
outputs/documentary_groups.csv
```

Required columns:

```csv
Group_ID,Platform,Relationship_Type,Num_Vendors,Num_Devices,Vendors,Devices
```

| Field | Description |
|---|---|
| `Group_ID` | Dimension I group identifier. |
| `Platform` | Ecosystem link or platform name when applicable. For parent/subsidiary groups, this may be empty or contain the normalized corporate link depending on preprocessing. |
| `Relationship_Type` | Documented relationship type, e.g., `Ecosystem` or `Parent/Subsidiary`. |
| `Num_Vendors` | Number of distinct vendors in the group. |
| `Num_Devices` | Number of devices in the group. |
| `Vendors` | Pipe-separated vendor list. |
| `Devices` | Pipe-separated device list. |

The released Dimension I file does not contain raw LLM responses, API logs,
or intermediate LLM verification records.

## Dimension II endpoint groups CSV

The released Dimension II group-level result is:

```text
outputs/endpoint_groups.csv
```

Required columns:

```csv
Group_ID,Num_Vendors,Num_Devices,Num_Domains,Vendors,Devices,Domains,Domain_Types
```

## Dimension III candidate groups CSV

The released Dimension III candidate group file is intentionally minimal:

```text
outputs/dim3_candidate_groups.csv
```

Required columns:

```csv
Group_ID,Num_Vendors,Num_Devices,Vendors,Devices
```

Corroboration rule fields are intentionally excluded from this file and are
reported in `outputs/corroboration_results.csv`.

## Corroboration results CSV

The released corroboration file contains retained Dimension III groups and the
rule-level evidence explaining why each group is kept:

```text
outputs/corroboration_results.csv
```

Core columns include:

```csv
Group_ID,Num_Vendors,Num_Devices,Vendors,Devices,Rule_I,Rule_II,Rule_III,Rule_IV,Retained,Corroboration_Tier
```
