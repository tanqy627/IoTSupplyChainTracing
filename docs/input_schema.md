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

The device-list and device-type files must contain the same canonical set of
247 `Device_Name` values.

## Dimension II domain annotation CSV

The public annotation file is `data/domain_level_annotation.csv`.

Required annotation columns:

```csv
Domain,Provider,Provider_Role,Provider_Subrole,Annotation_Confidence,Annotation_Note
```

| Field | Description |
|---|---|
| `Domain` | Domain represented in a Dimension II group. |
| `Provider` | Attributed service, platform, infrastructure, or content provider. |
| `Provider_Role` | Provider's primary role. |
| `Provider_Subrole` | More specific role, when applicable. |
| `Annotation_Confidence` | Confidence assigned to the annotation. |
| `Annotation_Note` | Short explanation of the attribution. |

The released file also includes derived traceability columns:
`Cluster_IDs`, `Num_Clusters`, `Num_Vendors_Observed`, and
`Num_Devices_Observed`.

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

Dimension I is released as verified, group-level documentary evidence. The
released file is:

```text
outputs/documentary_groups.csv
```

Required columns:

```csv
Cluster_ID,Tech_Link,Connection_Type,Num_Vendors,Num_Devices,Vendors,Devices,Provider,Provider_Role,Provider_Subrole
```

| Field | Description |
|---|---|
| `Cluster_ID` | Dimension I group identifier. |
| `Tech_Link` | Documented technical link or corporate affiliation defining the group. |
| `Connection_Type` | `Technical Integration` or `Corporate Affiliation`. |
| `Num_Vendors` | Number of distinct vendors in the group. |
| `Num_Devices` | Number of devices in the group. |
| `Vendors` | Pipe-separated vendor list. |
| `Devices` | Pipe-separated device list. |
| `Provider` | Provider associated with the connection, when applicable. |
| `Provider_Role` | Provider role associated with the connection. |
| `Provider_Subrole` | More specific provider role, when applicable. |

Legacy input names such as `Group_ID`, `Platform`, `Relationship_Type`, and
lowercase provider fields are accepted by the normalization utility, but all
released output uses the schema above.

The released Dimension I file does not contain raw LLM responses, API logs,
or intermediate LLM verification records.

## Dimension II endpoint groups CSV

The released Dimension II group-level result is:

```text
outputs/endpoint_groups.csv
```

Required columns:

```csv
Cluster_ID,Num_Vendors,Num_Devices,Num_Domains,Vendors,Devices,Domains,Providers,Provider_Roles,Provider_Subroles,Annotation_Confidences,Domain_Annotation_Notes
```

## Dimension III behavioral groups CSV

The released Dimension III result contains the final cross-vendor groups
produced by behavioral clustering:

```text
outputs/behavior_groups.csv
```

Required columns:

```csv
Cluster_ID,Num_Vendors,Num_Devices,Num_Components,Superset_Count,Vendors,Devices,Device_Types
```

Dimension III groups are not filtered using Dimension I or Dimension II. The
overlap analysis compares the three independent outputs afterward.

## Cross-dimensional overlap CSVs

`outputs/overlap_details.csv` contains one row for each of the 186 source
groups:

```csv
Source,Category,Num_Devices,Devices
```

`outputs/overlap_summary.csv` contains the seven Table VI categories:

```csv
Category,Groups
```

For a source group, a dimension recognizes it when the source group's device
set is a subset of at least one group produced by that dimension.
