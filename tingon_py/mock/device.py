"""In-memory mock device used for testing and the web UI demo mode."""

from __future__ import annotations

import json
from typing import Optional

from ..appliances.specs import BATHROOM_MODES
from ..intimates.protocol import IntimateProtocol
from ..profiles import (
    CAP_MOTOR1,
    CAP_MOTOR2,
    DeviceProfile,
    ProfileInfo,
    profile_info,
)


class MockTingonDevice:
    """Reusable in-memory controller for testing without BLE hardware.

    This mirrors the subset of the ``TingonDevice`` API that the CLI and
    webapp use, but keeps all state in memory rather than talking to a
    real BLE peripheral.
    """

    def __init__(self, address: str, profile: DeviceProfile, name: str) -> None:
        self._address = address
        self._profile = profile
        self._name = name
        self._status = default_mock_status(profile)

    @property
    def profile(self) -> DeviceProfile:
        return self._profile

    @property
    def profile_meta(self) -> ProfileInfo:
        return profile_info(self._profile)

    def has_capability(self, capability: str) -> bool:
        return capability in self.profile_meta.capabilities

    async def connect(self, _address: str, profile: Optional[DeviceProfile] = None) -> None:
        if profile is not None:
            self._profile = profile

    async def disconnect(self) -> None:
        return None

    async def get_status(self) -> dict:
        return json.loads(json.dumps(self._status))

    # Appliance actions
    async def set_power(self, on: bool) -> None:
        self._status["power"] = 1 if on else 0

    async def set_target_humidity(self, percent: int) -> None:
        self._status["target_hum"] = percent

    async def set_drainage(self, on: bool) -> None:
        self._status["drainage"] = 1 if on else 0

    async def set_dehumidification(self, on: bool) -> None:
        self._status["dehumidification"] = 1 if on else 0

    async def set_water_temperature(self, temp: int) -> None:
        self._status["setting_water_temp"] = temp
        self._status["outlet_water_temp"] = max(0, temp - 2)

    async def set_bathroom_mode(self, mode: int) -> None:
        self._status["bathroom_mode"] = mode
        if mode in BATHROOM_MODES and BATHROOM_MODES[mode][1] is not None:
            self._status["setting_water_temp"] = BATHROOM_MODES[mode][1]

    async def set_cruise_insulation_temp(self, temp: int) -> None:
        self._status["cruise_insulation_temp"] = temp

    async def set_zero_cold_water_mode(self, mode: int) -> None:
        self._status["zero_cold_water_mode"] = mode

    async def set_eco_cruise(self, on: bool) -> None:
        self._status["eco_cruise"] = 1 if on else 0

    async def set_water_pressurization(self, on: bool) -> None:
        self._status["water_pressurization"] = 1 if on else 0

    async def set_single_cruise(self, on: bool) -> None:
        self._status["single_cruise"] = 1 if on else 0

    async def set_diandong(self, on: bool) -> None:
        self._status["diandong"] = 1 if on else 0

    async def set_zero_cold_water(self, on: bool) -> None:
        self._status["zero_cold_water"] = 1 if on else 0

    async def set_timer(
        self,
        entries: "list[dict] | None" = None,
        *,
        timer_hex: Optional[str] = None,
        remind_hex: Optional[str] = None,
    ) -> None:
        if entries is None:
            entries = []
        self._status["timer_entries"] = [
            {
                "switch": 1 if entry.get("switch") else 0,
                "status": 1 if entry.get("status") else 0,
                "hours": int(entry.get("hours", 0)),
            }
            for entry in entries
        ]

    async def provision_wifi(self, ssid: str, password: str, config_url: str = "", encrypt: bool = True):
        return {"ok": True, "ssid": ssid, "mock": True}

    # Intimate actions
    async def intimate_play(self, play: bool, mode: Optional[int]) -> None:
        self._status["play"] = play
        if mode is not None:
            self._status["mode"] = mode
        if play and self._status.get("motor1", 0) == 0 and self.has_capability(CAP_MOTOR1):
            self._status["motor1"] = 50
        if not play:
            self._status["motor1"] = 0
            if self.has_capability(CAP_MOTOR2):
                self._status["motor2"] = 0

    async def intimate_set_mode(self, mode: int) -> None:
        self._status["mode"] = mode
        self._status["play"] = True
        self._status["custom_mode"] = None

    async def intimate_use_custom(self, slot_id: int) -> None:
        self._status["play"] = True
        self._status["mode"] = 0
        self._status["custom_mode"] = slot_id

    async def intimate_set_output(self, motor1: int, motor2: Optional[int]) -> None:
        self._status["motor1"] = motor1
        if motor2 is not None and self.has_capability(CAP_MOTOR2):
            self._status["motor2"] = motor2
        self._status["play"] = motor1 > 0 or self._status.get("motor2", 0) > 0
        self._status["mode"] = 0
        self._status["custom_mode"] = None

    async def intimate_set_position(self, position: str) -> None:
        self._status["position"] = position

    async def intimate_set_custom_range(self, start: int, end: int) -> None:
        start, end = IntimateProtocol.normalize_range(start, end)
        self._status["range_start"] = start
        self._status["range_end"] = end

    async def intimate_set_n2_mode(self, mode_name: str) -> None:
        self._status["n2_mode"] = mode_name

    async def intimate_query_custom(self, _slot_id: int):
        return None

    async def intimate_set_custom(self, slot_id: int, items: list[tuple[int, int]]) -> None:
        self._status[f"custom_{slot_id}"] = [
            {"mode": mode, "sec": sec} for mode, sec in items
        ]


def default_mock_status(profile: DeviceProfile) -> dict:
    if profile in {DeviceProfile.FJB, DeviceProfile.FJB2}:
        return {
            "power": 1,
            "target_hum": 55 if profile == DeviceProfile.FJB else 48,
            "drainage": 0,
            "dehumidification": 1,
            "air_intake_temp": 24,
            "air_intake_hum": 62,
            "air_outlet_temp": 28,
            "air_outlet_hum": 46,
            "eva_temp": 18,
            "wind_speed": 3,
            "compressor_status": 1,
            "error": 0,
            "defrost": 0,
            "work_time": 1380,
            "total_work_time": 22410,
            "timer_entries": [
                {"switch": 1, "status": 1, "hours": 2},
            ],
        }
    if profile in {DeviceProfile.GS, DeviceProfile.RJ}:
        return {
            "power": 1,
            "bathroom_mode": 1 if profile == DeviceProfile.GS else 2,
            "setting_water_temp": 50 if profile == DeviceProfile.GS else 42,
            "inlet_water_temp": 22,
            "outlet_water_temp": 48 if profile == DeviceProfile.GS else 40,
            "wind_status": 1,
            "discharge": 0,
            "water_status": 1,
            "fire_status": 1,
            "equipment_failure": 0,
            "cruise_insulation_temp": 45,
            "zero_cold_water_mode": 1,
            "eco_cruise": 0,
            "water_pressurization": 0,
            "single_cruise": 0,
            "diandong": 0,
            "zero_cold_water": 0,
        }
    base: dict = {
        "play": False,
        "mode": 1,
        "motor1": 0,
        "motor2": 0,
        "custom_mode": None,
    }
    if profile == DeviceProfile.M1:
        base.update({"play": True, "motor1": 65, "motor2": 28})
    elif profile == DeviceProfile.A1:
        base.update({"play": True, "motor1": 54})
    elif profile == DeviceProfile.N1:
        base.update({"play": True, "motor1": 36})
    elif profile == DeviceProfile.M2:
        base.update({"play": True, "motor1": 72, "position": "middle", "range_start": 12, "range_end": 78})
    elif profile == DeviceProfile.N2:
        base.update({"play": True, "motor1": 48, "motor2": 22, "n2_mode": "vibration"})
    for slot_id, items in {
        32: [{"mode": 1, "sec": 12}, {"mode": 4, "sec": 8}],
        33: [{"mode": 2, "sec": 10}, {"mode": 6, "sec": 6}, {"mode": 3, "sec": 9}],
        34: [{"mode": 5, "sec": 14}],
    }.items():
        base[f"custom_{slot_id}"] = items
    return base
