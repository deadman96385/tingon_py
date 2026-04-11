"""Top-level TINGON device orchestrator.

``TingonDevice`` is a thin coordinator that picks the right family-specific
controller based on the profile, wires it up with a BLE transport, and
exposes a stable surface for CLI and web callers.

It deliberately does not contain protocol or transport details of its own.
"""

from __future__ import annotations

import logging
from typing import Optional

from .appliances.controller import ApplianceController
from .ble.scan import scan as scan_devices
from .ble.transport import BleTransport
from .exceptions import TingonUnsupportedCapability
from .intimates.controller import IntimateController
from .models import ScannedDevice
from .profiles import (
    APPLIANCE_TYPE_TO_PROFILE,
    DeviceProfile,
    DeviceType,
    ProfileInfo,
    ProtocolFamily,
    profile_info,
)


LOGGER = logging.getLogger("tingon_py")


class TingonDevice:
    """Async BLE orchestrator for TINGON IoT devices."""

    def __init__(self) -> None:
        self._transport = BleTransport()
        self._profile: Optional[DeviceProfile] = None
        self._device_type: Optional[DeviceType] = None
        self._device_key: str = "41"
        self._appliance: Optional[ApplianceController] = None
        self._intimate: Optional[IntimateController] = None

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    @property
    def profile(self) -> Optional[DeviceProfile]:
        return self._profile

    @property
    def profile_meta(self) -> Optional[ProfileInfo]:
        return profile_info(self._profile) if self._profile else None

    @property
    def device_type(self) -> Optional[DeviceType]:
        return self._device_type

    @property
    def is_appliance(self) -> bool:
        return self.profile_meta is not None and self.profile_meta.family == ProtocolFamily.APPLIANCE

    @property
    def is_intimate(self) -> bool:
        return self.profile_meta is not None and self.profile_meta.family == ProtocolFamily.INTIMATE

    def has_capability(self, capability: str) -> bool:
        return self.profile_meta is not None and capability in self.profile_meta.capabilities

    def require_capability(self, capability: str) -> None:
        if not self.has_capability(capability):
            prof = self._profile.value if self._profile else "unknown"
            raise TingonUnsupportedCapability(
                f"Profile '{prof}' does not support '{capability}'"
            )

    # ------------------------------------------------------------------
    # Scanning (class-level helper for convenience)
    # ------------------------------------------------------------------

    @staticmethod
    async def scan(
        name_filter: str = "",
        timeout: float = 10.0,
        scanner=None,
    ) -> list[ScannedDevice]:
        """Scan for TINGON BLE devices."""
        return await scan_devices(scanner=scanner, name_filter=name_filter, timeout=timeout)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(
        self,
        address: str,
        device_type: Optional[DeviceType] = None,
        profile: Optional[DeviceProfile] = None,
    ) -> None:
        """Connect to a TINGON device and wire up the right controller."""
        self._profile = profile or (
            APPLIANCE_TYPE_TO_PROFILE[device_type] if device_type is not None else None
        )
        if self._profile is not None and self.profile_meta and self.profile_meta.appliance_type is not None:
            device_type = self.profile_meta.appliance_type
        self._device_type = device_type

        await self._transport.connect(address)

        if self.is_intimate:
            assert self._profile is not None
            self._intimate = IntimateController(self._transport, self._profile)
            await self._intimate.setup_notifications()
        else:
            # Appliance family, or unknown profile (fall back to appliance wiring)
            self._appliance = ApplianceController(
                self._transport, self._device_type, self._device_key
            )
            await self._appliance.setup_notifications()

        if self.profile_meta is not None:
            LOGGER.info(
                "Profile: %s (%s)",
                self.profile_meta.display_name,
                self.profile_meta.category,
            )
        elif self._device_type is not None:
            category = "Dehumidifier" if self._appliance and self._appliance.is_dehumidifier else "Water Heater"
            LOGGER.info("Device type: %s (%s)", self._device_type.name, category)

    async def disconnect(self) -> None:
        await self._transport.disconnect()
        self._appliance = None
        self._intimate = None

    # ------------------------------------------------------------------
    # Controller access
    # ------------------------------------------------------------------

    def _require_appliance(self) -> ApplianceController:
        if self._appliance is None:
            raise TingonUnsupportedCapability("No appliance controller is active")
        return self._appliance

    def _require_intimate(self) -> IntimateController:
        if self._intimate is None:
            raise TingonUnsupportedCapability("No intimate controller is active")
        return self._intimate

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self) -> Optional[dict]:
        if self.is_intimate:
            return self._require_intimate().get_status()
        return await self._require_appliance().get_status()

    # ------------------------------------------------------------------
    # Appliance actions
    # ------------------------------------------------------------------

    async def set_power(self, on: bool):
        return await self._require_appliance().set_power(on)

    async def set_target_humidity(self, percent: int):
        return await self._require_appliance().set_target_humidity(percent)

    async def set_drainage(self, on: bool):
        return await self._require_appliance().set_drainage(on)

    async def set_dehumidification(self, on: bool):
        return await self._require_appliance().set_dehumidification(on)

    async def set_water_temperature(self, temp: int):
        return await self._require_appliance().set_water_temperature(temp)

    async def set_bathroom_mode(self, mode: int):
        return await self._require_appliance().set_bathroom_mode(mode)

    async def provision_wifi(
        self,
        ssid: str,
        password: str,
        config_url: str = "",
        encrypt: bool = True,
    ):
        return await self._require_appliance().provision_wifi(
            ssid, password, config_url=config_url, encrypt=encrypt
        )

    # ------------------------------------------------------------------
    # Intimate actions
    # ------------------------------------------------------------------

    async def intimate_play(self, play: bool, mode: Optional[int] = None):
        await self._require_intimate().play(play, mode)

    async def intimate_set_mode(self, mode: int):
        await self._require_intimate().set_mode(mode)

    async def intimate_use_custom(self, slot_id: int):
        await self._require_intimate().use_custom(slot_id)

    async def intimate_set_output(self, motor1: int, motor2: Optional[int] = None):
        await self._require_intimate().set_output(motor1, motor2)

    async def intimate_set_position(self, position: str):
        await self._require_intimate().set_position(position)

    async def intimate_set_custom_range(self, start: int, end: int):
        await self._require_intimate().set_custom_range(start, end)

    async def intimate_set_n2_mode(self, mode_name: str):
        await self._require_intimate().set_n2_mode(mode_name)

    async def intimate_query_custom(self, slot_id: int):
        return await self._require_intimate().query_custom(slot_id)

    async def intimate_set_custom(self, slot_id: int, items: list[tuple[int, int]]):
        await self._require_intimate().set_custom(slot_id, items)

    # ------------------------------------------------------------------
    # Raw access (works for either family)
    # ------------------------------------------------------------------

    async def send_raw_hex(self, hex_str: str) -> None:
        if self._intimate is not None:
            await self._intimate.send_raw_hex(hex_str)
            return
        await self._require_appliance().send_raw_hex(hex_str)
