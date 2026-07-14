"""Canonical device naming shared by the 3D-SCM pipeline."""

from __future__ import annotations


DATASET_SUFFIXES = (
    "_Mon(uk)",
    "_Mon(us)",
    "_Our",
    "_Our2",
    "_UNSW",
    "_YT",
    "_IoTLS",
    "_IoT-Sentinel",
    "_IoTLifeCycle",
)


def canonicalize_device_name(value: str) -> str:
    """Use ``_IoTLifeCycle`` for self-collected or previously unsuffixed devices."""
    name = str(value).strip()
    if not name or name.lower() == "unknown":
        return name
    if name.endswith("_selfdata"):
        return name[: -len("_selfdata")] + "_IoTLifeCycle"
    if not name.endswith(DATASET_SUFFIXES):
        return name + "_IoTLifeCycle"
    return name
