# Dataset Sources and Acquisition

## Overview

The measurement pipeline uses seven publicly available IoT network traffic
datasets. The repository does not redistribute raw PCAP files. Instead, it
provides source links, input schemas, and code for processing
locally obtained datasets.

A machine-readable manifest is available at:

```text
data/dataset_manifest.csv
```

## Data Sources

| Dataset | Description | Source |
|---|---|---|
| UNSW | Long-term traffic traces from consumer IoT devices. | https://iotanalytics.unsw.edu.au/unsw-iotraffic.html |
| NCSU IoT Lab Datasets | Controlled traffic collected from common IoT devices in the USA for IoT device fingerprinting research. | https://privacy-datahub.csc.ncsu.edu/publication/ahmed-pets-2021/ |
| Mon(IoT)r | Measurement dataset of information exposure from consumer IoT devices in the USA and UK. | https://github.com/NEU-SNS/intl-iot |
| YourThings | Traffic data from home-based IoT deployments. | https://yourthings.info/data/ |
| IoT Sentinel | Device-type identification traces for consumer IoT devices. | https://github.com/andypitcher/IoT_Sentinel |
| IoTLS | TLS usage dataset for consumer IoT devices collected over a multi-year period. | https://github.com/NEU-SNS/IoTLS |
| IoT LifeCycle | Lifecycle-based traffic traces covering multiple consumer IoT device lifecycle phases. | https://github.com/NKUHack4FGroup/Lifecycle-Based-Traffic-Dataset |

## Acquisition Procedure

1. Download or request access to each dataset from its original source.
2. Follow the original license, data-use terms, and citation requirements.
3. Store the downloaded PCAP files under a local directory outside the GitHub
   repository, for example:

```text
/path/to/local_iot_datasets/
├── UNSW/
├── NCSU_2020/
├── NCSU_2021/
├── MonIoTr_US/
├── MonIoTr_UK/
├── YourThings/
├── IoT_Sentinel/
├── IoTLS/
└── IoT_LifeCycle/
```

4. Configure local dataset paths in `configs/default.yaml`, or provide them to
   the preprocessing CLI through `--root-dirs`.

## Device IP Mapping

The flow extraction script first attempts to infer the IoT device IP from the
PCAP filename. When this is unavailable, it uses a manual mapping file with the
following schema:

```csv
Full_Path,Manual_IP,Notes
/path/to/dataset/device/example_capture.pcap,192.168.1.10,"Example only."
```

This mapping file is a local-only input. It is not included in the public
repository because real mappings may expose absolute paths, local IP addresses,
or other environment-specific identifiers. If needed, create it locally and pass
it to the preprocessing script via `--manual-ip-csv`.

## Device Metadata

The repository includes metadata for the 247 devices in the traffic analysis:

```text
data/device_list.csv
data/device_type.csv
```

The device list maps devices to vendors, while the device-type file maps devices
to device categories.

## Non-Redistribution Policy

Raw PCAP files, full DNS query logs, device MAC addresses, local IP addresses,
absolute local file paths, model-output caches, and API keys are intentionally excluded from this
repository. Users should obtain raw datasets from the original sources and run
the preprocessing pipeline locally.
