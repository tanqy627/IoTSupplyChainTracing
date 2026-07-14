import pandas as pd

from src.behavior_clustering import export_dim3_behavior_groups


def test_export_dim3_behavior_groups_consolidates_components(tmp_path):
    rows = [
        {"Component_ID": "c1", "Device": "A", "Vendor": "v1", "device_type": "Camera"},
        {"Component_ID": "c1", "Device": "B", "Vendor": "v2", "device_type": "Plug"},
        {"Component_ID": "c2", "Device": "A", "Vendor": "v1", "device_type": "Camera"},
        {"Component_ID": "c2", "Device": "B", "Vendor": "v2", "device_type": "Plug"},
        {"Component_ID": "c3", "Device": "A", "Vendor": "v1", "device_type": "Camera"},
        {"Component_ID": "c3", "Device": "B", "Vendor": "v2", "device_type": "Plug"},
        {"Component_ID": "c3", "Device": "C", "Vendor": "v3", "device_type": "Unknown"},
        {"Component_ID": "c4", "Device": "D", "Vendor": "v4", "device_type": "Sensor"},
        {"Component_ID": "c4", "Device": "E", "Vendor": "v4", "device_type": "Sensor"},
    ]
    input_csv = tmp_path / "components.csv"
    output_csv = tmp_path / "groups.csv"
    pd.DataFrame(rows).to_csv(input_csv, index=False)

    result = export_dim3_behavior_groups(str(input_csv), str(output_csv))

    assert len(result) == 2
    by_devices = result.set_index("Devices")
    pair = "A_IoTLifeCycle|B_IoTLifeCycle"
    triple = "A_IoTLifeCycle|B_IoTLifeCycle|C_IoTLifeCycle"
    assert by_devices.loc[pair, "Num_Components"] == 2
    assert by_devices.loc[pair, "Superset_Count"] == 3
    assert by_devices.loc[triple, "Num_Components"] == 1
    assert by_devices.loc[triple, "Superset_Count"] == 1
    assert by_devices.loc[triple, "Device_Types"] == "Camera|Plug|Unknown"
    assert output_csv.exists()
