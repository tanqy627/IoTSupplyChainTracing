# Input Schema

## Cleaned flow pickle

Each record should be a dictionary with the following fields:

| Field | Description |
|---|---|
| `Device` | device name |
| `Vendor` | vendor/manufacturer/brand label |
| `Device_IP` | local IoT device IP |
| `Remote_IP` | remote endpoint IP |
| `Protocol` | TCP or UDP |
| `Device_Port` | local device-side port |
| `Server_Port` | remote endpoint port |
| `Flow_Start_TS` | flow start timestamp |
| `Domain` | DNS-derived domain mapped to `Remote_IP` |
| `Payload_Sequence` | signed packet length sequence |
| `Pcap_Filename` | source pcap filename |
| `Source_Full_Path` | source pcap path |

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

## Manual IP CSV

Required columns:

```csv
Full_Path,Manual_IP
```

## Dimension I verified evidence CSV

For parent/subsidiary evidence:

```csv
Vendor1,Vendor2,Relationship_Type,Platform,Is_Related
```

For platform/device-type evidence:

```csv
Vendor,Platform,Device_Type,Is_Related
```
