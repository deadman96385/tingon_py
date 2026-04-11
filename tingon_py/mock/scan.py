"""Deterministic mock scan results for supported profiles."""

from __future__ import annotations

from ..models import ScannedDevice
from ..profiles import DeviceProfile


def mock_device_catalog() -> list[tuple[DeviceProfile, str]]:
    return [
        (DeviceProfile.FJB, "XPOWER Dry 120"),
        (DeviceProfile.FJB2, "XPOWER Dry 220"),
        (DeviceProfile.GS, "Wanhe Heater GS"),
        (DeviceProfile.RJ, "Wanhe Heater RJ"),
        (DeviceProfile.A1, "TINGON A1"),
        (DeviceProfile.N1, "TINGON N1"),
        (DeviceProfile.N2, "TINGON N2"),
        (DeviceProfile.M1, "TINGON M1"),
        (DeviceProfile.M2, "TINGON M2"),
    ]


def mock_scan_devices(name_filter: str = "") -> list[ScannedDevice]:
    query = name_filter.lower().strip()
    devices: list[ScannedDevice] = []
    for index, (profile, device_name) in enumerate(mock_device_catalog(), start=1):
        if query and query not in device_name.lower() and query not in profile.value.lower():
            continue
        address = f"FA:KE:00:00:{index:02X}:{index + 16:02X}"
        devices.append(
            ScannedDevice(
                address=address,
                name=device_name,
                rssi=-32 - index * 4,
                profile=profile,
                mac_from_adv=address,
            )
        )
    return devices
