"""Shared data models used across the tingon_py package.

These are intentionally small, plain dataclasses so they can be imported
anywhere without pulling in BLE, protocol, or UI dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

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


@dataclass(frozen=True)
class ApplianceState:
    """Typed snapshot of an appliance's current state.

    Known spec names (see ``appliances/specs.py``) are promoted to typed
    fields; anything not recognised goes into ``extras`` so future
    firmware additions are not silently dropped.

    Consumers that need a flat ``dict`` (webapp JSON, CLI formatters)
    call :meth:`as_dict`.
    """

    device_type: Optional[DeviceType] = None
    power: Optional[bool] = None
    target_humidity: Optional[int] = None
    current_humidity: Optional[int] = None
    water_temperature: Optional[int] = None
    bathroom_mode: Optional[int] = None
    error_code: Optional[int] = None
    extras: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a flat dict merging typed fields with extras.

        ``None`` typed fields are omitted so the result mirrors the
        pre-refactor ``get_status()`` output shape. Dehumidifiers and
        water heaters use different spec names for the same concepts;
        we emit under the original spec name for backward compatibility
        with the webapp and CLI renderers.
        """
        is_water_heater = self.device_type in {DeviceType.GS, DeviceType.RJ}

        out: dict[str, Any] = {}
        if self.power is not None:
            out["power"] = 1 if self.power else 0
        if self.target_humidity is not None:
            out["target_hum"] = self.target_humidity
        if self.current_humidity is not None:
            out["air_intake_hum"] = self.current_humidity
        if self.water_temperature is not None:
            out["setting_water_temp"] = self.water_temperature
        if self.bathroom_mode is not None:
            out["bathroom_mode"] = self.bathroom_mode
        if self.error_code is not None:
            out["equipment_failure" if is_water_heater else "error"] = self.error_code
        out.update(self.extras)
        return out
