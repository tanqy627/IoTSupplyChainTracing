from src.device_names import canonicalize_device_name


def test_iot_lifecycle_device_names_are_canonicalized():
    assert canonicalize_device_name("Camera_selfdata") == "Camera_IoTLifeCycle"
    assert canonicalize_device_name("huawei_tv") == "huawei_tv_IoTLifeCycle"
    assert canonicalize_device_name("Camera_YT") == "Camera_YT"
    assert canonicalize_device_name("Camera_IoTLifeCycle") == "Camera_IoTLifeCycle"
