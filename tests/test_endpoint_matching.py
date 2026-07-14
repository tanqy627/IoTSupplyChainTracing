import pandas as pd

from src.endpoint_matching import build_domain_groups, enrich_domain_groups


def test_domain_groups_use_domain_device_sets_not_connected_components(tmp_path):
    pair_rows = [
        {
            "Device1": "A", "Vendor1": "v1", "Device2": "B", "Vendor2": "v2",
            "Same_Vendor": False, "Shared_Domains": "d1.example|d2.example",
        },
        {
            "Device1": "A", "Vendor1": "v1", "Device2": "C", "Vendor2": "v1",
            "Same_Vendor": True, "Shared_Domains": "d1.example",
        },
        {
            "Device1": "B", "Vendor1": "v2", "Device2": "C", "Vendor2": "v1",
            "Same_Vendor": False, "Shared_Domains": "d1.example",
        },
    ]

    result = build_domain_groups(pair_rows).set_index("Devices")

    assert set(result.index) == {
        "A_IoTLifeCycle|B_IoTLifeCycle",
        "A_IoTLifeCycle|B_IoTLifeCycle|C_IoTLifeCycle",
    }
    assert result.loc["A_IoTLifeCycle|B_IoTLifeCycle", "Domains"] == "d1.example|d2.example"
    assert result.loc["A_IoTLifeCycle|B_IoTLifeCycle|C_IoTLifeCycle", "Domains"] == "d1.example"


def test_enrich_domain_groups_adds_provider_annotations(tmp_path):
    groups = pd.DataFrame(
        [{
            "Cluster_ID": "C0001", "Num_Vendors": 2, "Num_Devices": 2,
            "Num_Domains": 1, "Vendors": "v1|v2", "Devices": "A|B",
            "Domains": "d1.example",
        }]
    )
    annotations = pd.DataFrame(
        [{
            "Domain": "d1.example", "Provider": "Provider A",
            "Provider_Role": "IoT Platform Provider", "Provider_Subrole": "",
            "Annotation_Note": "Example platform endpoint",
            "Annotation_Confidence": "High",
        }]
    )
    annotation_csv = tmp_path / "annotations.csv"
    annotations.to_csv(annotation_csv, index=False)

    result = enrich_domain_groups(groups, str(annotation_csv)).iloc[0]

    assert result["Providers"] == "Provider A"
    assert result["Provider_Roles"] == "IoT Platform Provider"
    assert result["Annotation_Confidences"] == "High"
    assert result["Domain_Annotation_Notes"] == "d1.example: Example platform endpoint"
