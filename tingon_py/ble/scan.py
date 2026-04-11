"""BLE scanning and advertisement parsing for TINGON devices."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..crypto import TingonEncryption
from ..exceptions import TingonDependencyError
from ..models import ScannedDevice
from ..profiles import APPLIANCE_TYPE_TO_PROFILE, DeviceProfile, DeviceType

try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:  # pragma: no cover - import guard for optional bleak
    BleakScanner = None  # type: ignore[assignment]
    BLEDevice = object  # type: ignore[assignment,misc]
    AdvertisementData = object  # type: ignore[assignment,misc]


LOGGER = logging.getLogger("tingon_py")

XIYU_TYPE_TO_PROFILE: dict[int, DeviceProfile] = {
    0: DeviceProfile.M1,
    1: DeviceProfile.A1,
    2: DeviceProfile.N1,
    3: DeviceProfile.M2,
    4: DeviceProfile.N2,
}


def _infer_xiyu_profile(name: str, dev_type_byte: int, sub_version: int) -> DeviceProfile | None:
    if "xiyu" not in name.lower():
        return None
    if dev_type_byte == 0 and sub_version == 2:
        dev_type_byte = 3
    return XIYU_TYPE_TO_PROFILE.get(dev_type_byte)


def _parse_scan_result(device: "BLEDevice", adv: "AdvertisementData", name_filter: str) -> ScannedDevice | None:
    if name_filter and device.name and name_filter.lower() not in device.name.lower():
        return None
    if not device.name:
        return None

    scanned = ScannedDevice(
        address=device.address,
        name=device.name or "Unknown",
        rssi=adv.rssi,
    )

    if adv.manufacturer_data:
        for _company_id, mfr_data in adv.manufacturer_data.items():
            scanned.raw_manufacturer_data = mfr_data
            scanned.device_key = TingonEncryption.extract_device_key(mfr_data)
            if len(mfr_data) > 11:
                dev_type_byte = mfr_data[10]
                sub_version = mfr_data[11] if len(mfr_data) > 11 else 0
                scanned.profile = _infer_xiyu_profile(scanned.name, dev_type_byte, sub_version)
                if scanned.profile is None and dev_type_byte == 0 and sub_version == 2:
                    scanned.device_type = DeviceType.FJB_SECOND
                elif scanned.profile is None and dev_type_byte in (0, 1, 2, 3):
                    scanned.device_type = DeviceType(dev_type_byte)
            if len(mfr_data) >= 19:
                mac_bytes = mfr_data[13:19]
                scanned.mac_from_adv = ":".join(f"{b:02X}" for b in mac_bytes)
            break

    if scanned.profile is None and scanned.device_type is not None:
        scanned.profile = APPLIANCE_TYPE_TO_PROFILE[scanned.device_type]
    elif scanned.profile is None:
        scanned.profile = DeviceProfile.parse(scanned.name, fuzzy=True)

    return scanned


def _iter_discovered_devices(scanner: Any):
    discovered = getattr(scanner, "discovered_devices_and_advertisement_data", None)
    if isinstance(discovered, dict):
        for device, adv in discovered.values():
            yield device, adv


async def scan(
    *,
    scanner: Any = None,
    name_filter: str = "",
    timeout: float = 10.0,
) -> list[ScannedDevice]:
    """Scan for TINGON devices using an injected scanner or a local bleak scanner."""
    found: dict[str, ScannedDevice] = {}

    def callback(device: "BLEDevice", adv: "AdvertisementData") -> None:
        scanned = _parse_scan_result(device, adv, name_filter)
        if scanned is not None:
            found[device.address] = scanned

    unregister_callback = None

    if scanner is None:
        if BleakScanner is None:
            raise TingonDependencyError(
                "bleak is not installed. Install it with: pip install bleak"
            )
        scanner = BleakScanner(detection_callback=callback)
    else:
        register_callback = getattr(scanner, "register_detection_callback", None)
        if callable(register_callback):
            unregister_callback = register_callback(callback)

    start = getattr(scanner, "start", None)
    stop = getattr(scanner, "stop", None)
    if not callable(start) or not callable(stop):
        raise TypeError("scanner must provide async start() and stop() methods")

    await start()
    try:
        await asyncio.sleep(timeout)
    finally:
        await stop()
        if callable(unregister_callback):
            unregister_callback()

    for device, adv in _iter_discovered_devices(scanner):
        scanned = _parse_scan_result(device, adv, name_filter)
        if scanned is not None:
            found[device.address] = scanned

    LOGGER.debug("Scan complete with %s device(s)", len(found))
    return list(found.values())
