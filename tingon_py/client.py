"""Thin public client wrapping the TingonDevice orchestrator."""

from __future__ import annotations

from typing import Optional

from .ble.scan import scan as scan_devices
from .device import TingonDevice
from .profiles import DeviceProfile, DeviceType, ProfileInfo


class TingonClient:
    """Canonical async client for TINGON BLE devices."""

    def __init__(self) -> None:
        self._device = TingonDevice()

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

    def has_capability(self, capability: str) -> bool:
        return self._device.has_capability(capability)

    def require_capability(self, capability: str) -> None:
        self._device.require_capability(capability)

    async def connect(
        self,
        address: str,
        device_type: Optional[DeviceType] = None,
        profile: Optional[DeviceProfile] = None,
    ) -> None:
        await self._device.connect(address, device_type=device_type, profile=profile)

    async def disconnect(self) -> None:
        await self._device.disconnect()

    async def get_status(self):
        return await self._device.get_status()

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
