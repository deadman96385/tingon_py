"""Thin public client wrapping the TingonDevice orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from .ble.scan import scan as scan_devices
from .device import TingonDevice
from .intimates.status import IntimateStatus
from .models import ApplianceState
from .profiles import DeviceProfile, DeviceType, ProfileInfo

if TYPE_CHECKING:  # pragma: no cover
    from bleak.backends.device import BLEDevice


Callback = Callable[[], None]
BleDeviceCallback = Callable[[], "Optional[BLEDevice]"]


class TingonClient:
    """Canonical async client for TINGON BLE devices.

    Takes a Bleak ``BLEDevice`` at connect time — callers that only
    have a MAC address are responsible for resolving it (CLI: via
    ``BleakScanner.find_device_by_address``; Home Assistant: via
    ``bluetooth.async_ble_device_from_address``).
    """

    def __init__(self) -> None:
        self._device = TingonDevice()

    # ------------------------------------------------------------------
    # Metadata passthrough
    # ------------------------------------------------------------------

    @property
    def profile(self) -> Optional[DeviceProfile]:
        return self._device.profile

    @property
    def profile_meta(self) -> Optional[ProfileInfo]:
        return self._device.profile_meta

    @property
    def is_appliance(self) -> bool:
        return self._device.is_appliance

    @property
    def is_intimate(self) -> bool:
        return self._device.is_intimate

    @property
    def available(self) -> bool:
        return self._device.available

    @property
    def appliance_state(self) -> Optional[ApplianceState]:
        return self._device.appliance_state

    @property
    def intimate_status(self) -> Optional[IntimateStatus]:
        return self._device.intimate_status

    def has_capability(self, capability: str) -> bool:
        return self._device.has_capability(capability)

    def require_capability(self, capability: str) -> None:
        self._device.require_capability(capability)

    def register_callback(self, callback: Callback) -> Callback:
        """Register a zero-arg listener; returns an unregister function."""
        return self._device.register_callback(callback)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(
        self,
        device: "BLEDevice",
        *,
        device_type: Optional[DeviceType] = None,
        profile: Optional[DeviceProfile] = None,
        disconnected_callback: Optional[Callback] = None,
        ble_device_callback: Optional[BleDeviceCallback] = None,
        max_attempts: int = 3,
    ) -> None:
        await self._device.connect(
            device,
            device_type=device_type,
            profile=profile,
            disconnected_callback=disconnected_callback,
            ble_device_callback=ble_device_callback,
            max_attempts=max_attempts,
        )

    async def disconnect(self) -> None:
        await self._device.disconnect()

    async def update(self) -> None:
        """Refresh cached state (appliance query; no-op for intimates)."""
        await self._device.update()

    # ------------------------------------------------------------------
    # Appliance actions
    # ------------------------------------------------------------------

    async def set_power(self, on: bool):
        return await self._device.set_power(on)

    async def set_target_humidity(self, percent: int):
        return await self._device.set_target_humidity(percent)

    async def set_drainage(self, on: bool):
        return await self._device.set_drainage(on)

    async def set_dehumidification(self, on: bool):
        return await self._device.set_dehumidification(on)

    async def set_water_temperature(self, temp: int):
        return await self._device.set_water_temperature(temp)

    async def set_bathroom_mode(self, mode: int):
        return await self._device.set_bathroom_mode(mode)

    async def set_cruise_insulation_temp(self, temp: int):
        return await self._device.set_cruise_insulation_temp(temp)

    async def set_zero_cold_water_mode(self, mode: int):
        return await self._device.set_zero_cold_water_mode(mode)

    async def set_eco_cruise(self, on: bool):
        return await self._device.set_eco_cruise(on)

    async def set_water_pressurization(self, on: bool):
        return await self._device.set_water_pressurization(on)

    async def set_single_cruise(self, on: bool):
        return await self._device.set_single_cruise(on)

    async def set_diandong(self, on: bool):
        return await self._device.set_diandong(on)

    async def set_zero_cold_water(self, on: bool):
        return await self._device.set_zero_cold_water(on)

    async def set_timer(
        self,
        entries: "list[dict] | None" = None,
        *,
        timer_hex: Optional[str] = None,
        remind_hex: Optional[str] = None,
    ):
        return await self._device.set_timer(
            entries, timer_hex=timer_hex, remind_hex=remind_hex
        )

    # ------------------------------------------------------------------
    # Intimate actions
    # ------------------------------------------------------------------

    async def intimate_play(self, play: bool, mode: Optional[int] = None):
        await self._device.intimate_play(play, mode)

    async def intimate_set_mode(self, mode: int):
        await self._device.intimate_set_mode(mode)

    async def intimate_use_custom(self, slot_id: int):
        await self._device.intimate_use_custom(slot_id)

    async def intimate_set_output(self, motor1: int, motor2: Optional[int] = None):
        await self._device.intimate_set_output(motor1, motor2)

    async def intimate_set_position(self, position: str):
        await self._device.intimate_set_position(position)

    async def intimate_set_custom_range(self, start: int, end: int):
        await self._device.intimate_set_custom_range(start, end)

    async def intimate_set_n2_mode(self, mode_name: str):
        await self._device.intimate_set_n2_mode(mode_name)

    async def intimate_query_custom(self, slot_id: int):
        return await self._device.intimate_query_custom(slot_id)

    async def intimate_set_custom(self, slot_id: int, items: list[tuple[int, int]]):
        await self._device.intimate_set_custom(slot_id, items)

    def intimate_status_dict(self) -> Optional[dict]:
        """Return the intimate controller's locally-tracked status as a dict."""
        return self._device.intimate_status_dict()

    def status_dict(self) -> Optional[dict]:
        """Unified status-as-dict view for both families."""
        return self._device.status_dict()

    async def provision_wifi(
        self,
        ssid: str,
        password: str,
        config_url: str = "",
        encrypt: bool = True,
    ):
        return await self._device.provision_wifi(
            ssid, password, config_url=config_url, encrypt=encrypt
        )

    async def send_raw_hex(self, hex_str: str) -> None:
        await self._device.send_raw_hex(hex_str)

    @staticmethod
    async def scan(*, scanner=None, name_filter: str = "", timeout: float = 10.0):
        return await scan_devices(scanner=scanner, name_filter=name_filter, timeout=timeout)
