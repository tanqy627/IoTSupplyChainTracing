# Dataset Sources and Local Preparation

## Overview

The measurement uses seven publicly available IoT network-traffic datasets.
Raw PCAPs are not redistributed. The machine-readable source list is
`data/dataset_manifest.csv`; users should follow each source's license,
data-use terms, citation requirements, and access procedure.

## Sources

| Dataset | Description | Source |
|---|---|---|
| UNSW | Long-term consumer-IoT traffic traces. | https://iotanalytics.unsw.edu.au/unsw-iotraffic.html |
| NCSU IoT Lab Datasets | Controlled US IoT-device fingerprinting traffic. | https://privacy-datahub.csc.ncsu.edu/publication/ahmed-pets-2021/ |
| Mon(IoT)r | US and UK consumer-IoT information-exposure measurements. | https://github.com/NEU-SNS/intl-iot |
| YourThings | Traffic from home-based IoT deployments. | https://yourthings.info/data/ |
| IoT Sentinel | Consumer-IoT device-type identification traces. | https://github.com/andypitcher/IoT_Sentinel |
| IoTLS | Multi-year TLS-usage traces from consumer IoT devices. | https://github.com/NEU-SNS/IoTLS |
| IoT LifeCycle | Traffic covering multiple device lifecycle phases. | https://github.com/NKUHack4FGroup/Lifecycle-Based-Traffic-Dataset |

## Local layout

Store the downloaded captures outside this repository. One possible layout is:

```text
/path/to/local_iot_datasets/
|-- UNSW/
|-- NCSU_2020/
|-- NCSU_2021/
|-- MonIoTr_US/
|-- MonIoTr_UK/
|-- YourThings/
|-- IoT_Sentinel/
|-- IoTLS/
`-- IoT_LifeCycle/
```

Set these directories in `paths.dataset_roots` in `configs/default.yaml`, or
pass them to `flow_preprocessing.py extract` through `--root-dirs`.

## Device IP mapping

Flow extraction first attempts to infer the IoT device IP from the PCAP
filename. When this is unavailable, supply a local mapping:

```csv
Full_Path,Manual_IP
/path/to/dataset/device/example_capture.pcap,192.168.1.10
```

Pass the file with `--manual-ip-csv` or set `paths.manual_ip_csv`. It is a
local-only input and must not be committed.

## Device metadata

`data/device_list.csv` and `data/device_type.csv` cover the same 247 analyzed
devices and use the canonical names consumed by all three dimensions. Their
schemas are defined in `docs/input_schema.md`.

## Excluded sensitive or large artifacts

The public repository excludes raw PCAPs, full DNS logs, MAC addresses, local
IPs, absolute paths, flow-level payload sequences, distance matrices, LLM/API
caches, and API keys. These are either locally derived or potentially
environment-sensitive.
