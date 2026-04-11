"""Shared data models used across the tingon_py package.

These are intentionally small, plain dataclasses so they can be imported
anywhere without pulling in BLE, protocol, or UI dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .profiles import DeviceProfile, DeviceType


@dataclass
class SpecDef:
    """Definition of a single appliance spec/property."""

    name: str
    data_type: str   # "01"=bool, "02"=int, "04"=status, "05"=error, "00"=raw
    length: int      # value length in bytes
    writable: bool = False


@dataclass
class ScannedDevice:
    """A BLE scan result paired with TINGON-specific metadata."""

    address: str
    name: str
    rssi: int
    device_type: Optional[DeviceType] = None
    profile: Optional[DeviceProfile] = None
    mac_from_adv: Optional[str] = None
    device_key: str = "41"
    raw_manufacturer_data: Optional[bytes] = None
