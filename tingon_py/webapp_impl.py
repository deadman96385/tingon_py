"""
Local web UI for TINGON appliance and intimate BLE devices.

Run with:
    python webapp.py

Then open:
    http://127.0.0.1:8765
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import random
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .appliances.specs import BATHROOM_MODE_NAME_TO_VALUE, bathroom_mode_options
from .ble.scan import scan as ble_scan_devices
from .client import TingonClient
from .intimates.protocol import IntimateProtocol
from .mock.device import MockTingonDevice
from .mock.scan import mock_scan_devices
from .models import ScannedDevice
from .profiles import (
    CAP_BATHROOM_MODE,
    CAP_CRUISE_TEMP,
    CAP_CUSTOM,
    CAP_CUSTOM_RANGE,
    CAP_DEHUM,
    CAP_DIANDONG,
    CAP_DRAINAGE,
    CAP_ECO_CRUISE,
    CAP_HUMIDITY,
    CAP_MOTOR2,
    CAP_N2_MODE,
    CAP_PLAY,
    CAP_POSITION,
    CAP_POWER,
    CAP_PRESET_MODE,
    CAP_PROVISION,
    CAP_SINGLE_CRUISE,
    CAP_STATUS,
    CAP_TIMER,
    CAP_WATER_PRESSURIZATION,
    CAP_WATER_TEMP,
    CAP_ZERO_COLD_WATER,
    CAP_ZERO_COLD_WATER_MODE,
    DeviceProfile,
    INTIMATE_PLAYBACK_BEHAVIORS,
    ProtocolFamily,
    intimate_custom_step_limit,
    intimate_mode_count,
    intimate_mode_labels,
    profile_info,
)


WEB_ROOT = Path(__file__).parent / "web"
DEFAULT_MOCK_MODE = os.environ.get("TINGON_WEB_MOCK", "").lower() in {"1", "true", "yes", "on"}


def _web_profiles() -> list[DeviceProfile]:
    return [
        DeviceProfile.FJB,
        DeviceProfile.FJB2,
        DeviceProfile.GS,
        DeviceProfile.RJ,
        DeviceProfile.A1,
        DeviceProfile.N1,
        DeviceProfile.N2,
        DeviceProfile.M1,
        DeviceProfile.M2,
    ]
def profile_ui(profile: DeviceProfile) -> dict:
    meta = profile_info(profile)
    capabilities = meta.capabilities
    bathroom_modes = []
    if profile in {DeviceProfile.GS, DeviceProfile.RJ}:
        bathroom_modes = bathroom_mode_options()
    hero_asset = profile.value
    if profile in {DeviceProfile.FJB, DeviceProfile.FJB2}:
        hero_asset = "xpower.png"
    elif profile in {DeviceProfile.GS, DeviceProfile.RJ}:
        hero_asset = "wanhe.png"
    mode_labels = intimate_mode_labels(profile)
    return {
        "profile": profile.value,
        "display_name": meta.display_name,
        "category": meta.category,
        "family": meta.family.value,
        "supports_power": CAP_POWER in capabilities,
        "supports_status_query": CAP_STATUS in capabilities,
        "supports_humidity": CAP_HUMIDITY in capabilities,
        "supports_drainage": CAP_DRAINAGE in capabilities,
        "supports_dehumidification": CAP_DEHUM in capabilities,
        "supports_water_temperature": CAP_WATER_TEMP in capabilities,
        "supports_bathroom_mode": CAP_BATHROOM_MODE in capabilities,
        "supports_cruise_insulation_temp": CAP_CRUISE_TEMP in capabilities,
        "supports_zero_cold_water_mode": CAP_ZERO_COLD_WATER_MODE in capabilities,
        "supports_eco_cruise": CAP_ECO_CRUISE in capabilities,
        "supports_water_pressurization": CAP_WATER_PRESSURIZATION in capabilities,
        "supports_single_cruise": CAP_SINGLE_CRUISE in capabilities,
        "supports_diandong": CAP_DIANDONG in capabilities,
        "supports_zero_cold_water": CAP_ZERO_COLD_WATER in capabilities,
        "supports_timer": CAP_TIMER in capabilities,
        "supports_provision": CAP_PROVISION in capabilities,
        "supports_play": CAP_PLAY in capabilities,
        "supports_preset_mode": CAP_PRESET_MODE in capabilities,
        "supports_second_motor": CAP_MOTOR2 in capabilities,
        "supports_position": CAP_POSITION in capabilities,
        "supports_n2_mode": CAP_N2_MODE in capabilities,
        "supports_custom_slots": CAP_CUSTOM in capabilities,
        "supports_custom_range": CAP_CUSTOM_RANGE in capabilities,
        "mode_count": intimate_mode_count(profile),
        "mode_labels": mode_labels,
        "mode_cards": [
            {
                "id": index + 1,
                "label": label,
                "icon": f"mode{index + 1}.png",
                "active_icon": f"mode{index + 1}_on.png",
            }
            for index, label in enumerate(mode_labels)
        ],
        "mode_options": bathroom_modes,
        "custom_step_limit": intimate_custom_step_limit(profile),
        "playback_behaviors": list(INTIMATE_PLAYBACK_BEHAVIORS),
        "hero_asset": hero_asset,
    }


def serialize_scan(device: ScannedDevice) -> dict:
    info = profile_info(device.profile) if device.profile is not None else None
    supported = info is not None and info.family in {ProtocolFamily.INTIMATE, ProtocolFamily.APPLIANCE}
    return {
        "address": device.address,
        "name": device.name,
        "rssi": device.rssi,
        "profile": device.profile.value if device.profile else None,
        "display_name": info.display_name if info else device.name,
        "family": info.family.value if info else None,
        "supported": supported,
        "mac_from_adv": device.mac_from_adv,
    }


@dataclass
class SessionRecord:
    address: str
    name: str
    profile: DeviceProfile


class EventHub:
    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, event: str, payload: dict):
        message = {"event": event, "payload": payload}
        stale: list[WebSocket] = []
        async with self._lock:
            websockets = list(self._connections)
        for websocket in websockets:
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        if stale:
            async with self._lock:
                for websocket in stale:
                    self._connections.discard(websocket)


class DeviceSessionManager:
    def __init__(self, events: EventHub, mock_mode: bool = False):
        self._events = events
        self._lock = asyncio.Lock()
        self._device: Optional[TingonClient | MockTingonDevice] = None
        self._session: Optional[SessionRecord] = None
        self._scan_cache: dict[str, ScannedDevice] = {}
        self._poll_task: Optional[asyncio.Task] = None
        self._last_status_json = ""
        self._mock_mode = mock_mode
        self._playback_behavior = "loop"
        self._next_mode_change_at: Optional[float] = None
        self._range_presets = [{"start": 0, "end": 92} for _ in range(6)]
        self._active_range_preset = 0

    def set_mock_mode(self, enabled: bool):
        self._mock_mode = enabled

    @property
    def mock_mode(self) -> bool:
        return self._mock_mode

    def _mock_scan(self, name: str) -> list[ScannedDevice]:
        return mock_scan_devices(name)

    async def close(self):
        async with self._lock:
            await self._disconnect_locked()

    async def scan(self, timeout: float, name: str = "") -> list[dict]:
        await self._events.broadcast("scan_started", {"timeout": timeout, "name": name})
        if self._mock_mode:
            await asyncio.sleep(min(timeout, 0.35))
            devices = self._mock_scan(name)
        else:
            devices = await ble_scan_devices(name_filter=name, timeout=timeout)
        self._scan_cache = {device.address: device for device in devices}
        result = [serialize_scan(device) for device in devices]
        await self._events.broadcast("scan_completed", {"devices": result})
        return result

    async def connect(self, address: str, raw_profile: Optional[str] = None) -> dict:
        async with self._lock:
            await self._disconnect_locked()

            scanned = self._scan_cache.get(address)
            profile = DeviceProfile.parse(raw_profile) if raw_profile else None
            if profile is None and scanned is not None:
                profile = scanned.profile
            if profile is None:
                raise HTTPException(status_code=400, detail="Unable to infer profile for device")

            meta = profile_info(profile)

            if self._mock_mode:
                device = MockTingonDevice(address, profile, scanned.name if scanned is not None else meta.display_name)
                try:
                    await device.connect(address, profile=profile)
                except Exception as exc:
                    raise HTTPException(status_code=400, detail=f"Mock connect failed: {exc}") from exc
            else:
                device = TingonClient()
                try:
                    await device.connect(address, profile=profile)
                except Exception as exc:
                    raise HTTPException(status_code=400, detail=f"BLE connect failed: {exc}") from exc

            self._device = device
            self._session = SessionRecord(
                address=address,
                name=scanned.name if scanned is not None else meta.display_name,
                profile=profile,
            )

            await self._maybe_refresh_custom_locked()
            session = await self._session_payload_locked()
            self._start_poll_locked()

        await self._events.broadcast("session", session)
        return session

    async def disconnect(self) -> dict:
        async with self._lock:
            await self._disconnect_locked()
            payload = self._empty_session()
        await self._events.broadcast("session", payload)
        return payload

    async def get_session(self) -> dict:
        async with self._lock:
            return await self._session_payload_locked()

    async def refresh_status(self) -> dict:
        async with self._lock:
            self._require_device_locked(CAP_STATUS)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_power(self, on: bool) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_POWER)
            await device.set_power(on)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_humidity(self, percent: int) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_HUMIDITY)
            await device.set_target_humidity(percent)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_drainage(self, on: bool) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_DRAINAGE)
            await device.set_drainage(on)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_dehumidification(self, on: bool) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_DEHUM)
            await device.set_dehumidification(on)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_water_temperature(self, temp: int) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_WATER_TEMP)
            await device.set_water_temperature(temp)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_bathroom_mode(self, mode_name: str) -> dict:
        mode = BATHROOM_MODE_NAME_TO_VALUE.get(mode_name.lower())
        if mode is None:
            raise HTTPException(status_code=400, detail=f"Unknown bathroom mode '{mode_name}'")
        async with self._lock:
            device = self._require_device_locked(CAP_BATHROOM_MODE)
            await device.set_bathroom_mode(mode)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_cruise_insulation_temp(self, temp: int) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_CRUISE_TEMP)
            await device.set_cruise_insulation_temp(temp)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_zero_cold_water_mode(self, mode: int) -> dict:
        if mode not in (0, 1, 3):
            raise HTTPException(status_code=400, detail="Zero cold water mode must be 0 (off), 1 (on), or 3 (enhanced)")
        async with self._lock:
            device = self._require_device_locked(CAP_ZERO_COLD_WATER_MODE)
            await device.set_zero_cold_water_mode(mode)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_eco_cruise(self, on: bool) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_ECO_CRUISE)
            await device.set_eco_cruise(on)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_water_pressurization(self, on: bool) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_WATER_PRESSURIZATION)
            await device.set_water_pressurization(on)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_single_cruise(self, on: bool) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_SINGLE_CRUISE)
            await device.set_single_cruise(on)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_diandong(self, on: bool) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_DIANDONG)
            await device.set_diandong(on)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_zero_cold_water(self, on: bool) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_ZERO_COLD_WATER)
            await device.set_zero_cold_water(on)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_timer(self, entries: list[dict]) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_TIMER)
            await device.set_timer(entries)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def provision_wifi(self, ssid: str, password: str, config_url: str, encrypt: bool) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_PROVISION)
            if isinstance(device, MockTingonDevice):
                return {"ok": True, "mock": True, "ssid": ssid}
            try:
                result = await device.provision_wifi(
                    ssid, password, config_url=config_url, encrypt=encrypt
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Provisioning failed: {exc}") from exc
        return {"ok": True, "mock": False, "ssid": ssid, "response": result}

    async def set_play(self, play: bool, mode: Optional[int]) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_PLAY)
            await device.intimate_play(play, mode)
            self._reset_playback_clock_locked(enabled=play)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_mode(self, mode: int) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_PRESET_MODE)
            await device.intimate_set_mode(mode)
            self._reset_playback_clock_locked(enabled=mode > 0)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_motor(self, motor1: int, motor2: Optional[int]) -> dict:
        async with self._lock:
            device = self._require_device_locked()
            await device.intimate_set_output(motor1, motor2)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_position(self, position: str) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_POSITION)
            await device.intimate_set_position(position)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_n2_mode(self, mode_name: str) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_N2_MODE)
            await device.intimate_set_n2_mode(mode_name)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_playback_behavior(self, behavior: str) -> dict:
        normalized = behavior.strip().lower()
        if normalized not in INTIMATE_PLAYBACK_BEHAVIORS:
            raise HTTPException(status_code=400, detail=f"Unknown playback behavior '{behavior}'")
        async with self._lock:
            self._require_device_locked(CAP_PRESET_MODE)
            self._playback_behavior = normalized
            status = await self._device.get_status()
            self._reset_playback_clock_locked(enabled=bool(status and status.get("play")))
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def get_custom(self) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_CUSTOM)
            await self._refresh_custom_locked(device)
            return await self._session_payload_locked()

    async def set_custom(self, slot_id: int, items: list[tuple[int, int]]) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_CUSTOM)
            self._validate_custom_items_locked(items)
            await device.intimate_set_custom(slot_id, items)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def use_custom(self, slot_id: int) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_CUSTOM)
            await device.intimate_use_custom(slot_id)
            self._reset_playback_clock_locked(enabled=True)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def set_range(self, start: int, end: int) -> dict:
        async with self._lock:
            device = self._require_device_locked(CAP_CUSTOM_RANGE)
            await device.intimate_set_custom_range(start, end)
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def save_range_preset(self, slot_id: int, start: int, end: int) -> dict:
        if slot_id not in range(1, 7):
            raise HTTPException(status_code=400, detail="Range presets must be 1 through 6")
        normalized_start, normalized_end = IntimateProtocol.normalize_range(start, end)
        async with self._lock:
            self._require_device_locked(CAP_CUSTOM_RANGE)
            self._range_presets[slot_id - 1] = {"start": normalized_start, "end": normalized_end}
            self._active_range_preset = slot_id - 1
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    async def use_range_preset(self, slot_id: int) -> dict:
        if slot_id not in range(1, 7):
            raise HTTPException(status_code=400, detail="Range presets must be 1 through 6")
        async with self._lock:
            device = self._require_device_locked(CAP_CUSTOM_RANGE)
            preset = self._range_presets[slot_id - 1]
            await device.intimate_set_custom_range(preset["start"], preset["end"])
            self._active_range_preset = slot_id - 1
            payload = await self._session_payload_locked()
        await self._events.broadcast("session", payload)
        return payload

    def _empty_session(self) -> dict:
        return {"connected": False, "device": None}

    def _require_device_locked(self, capability: Optional[str] = None) -> TingonClient | MockTingonDevice:
        if self._device is None or self._session is None:
            raise HTTPException(status_code=400, detail="No active device session")
        if capability and not self._device.has_capability(capability):
            raise HTTPException(status_code=400, detail=f"Profile '{self._session.profile.value}' does not support '{capability}'")
        return self._device

    async def _disconnect_locked(self):
        if self._poll_task is not None:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None
        if self._device is not None:
            with contextlib.suppress(Exception):
                await self._device.disconnect()
        self._device = None
        self._session = None
        self._last_status_json = ""
        self._next_mode_change_at = None

    async def _refresh_custom_locked(self, device: Optional[TingonClient | MockTingonDevice] = None):
        device = device or self._require_device_locked(CAP_CUSTOM)
        if not device.has_capability(CAP_CUSTOM):
            return
        for slot_id in (32, 33, 34):
            with contextlib.suppress(Exception):
                await device.intimate_query_custom(slot_id)

    async def _maybe_refresh_custom_locked(self):
        if self._device is None or not self._device.has_capability(CAP_CUSTOM):
            return
        await self._refresh_custom_locked(self._device)

    async def _session_payload_locked(self) -> dict:
        if self._device is None or self._session is None:
            return self._empty_session()

        status = await self._device.get_status()
        profile = self._session.profile
        control_state = None
        if profile_info(profile).family == ProtocolFamily.INTIMATE:
            control_state = {
                "playback_behavior": self._playback_behavior,
            }
            if CAP_CUSTOM_RANGE in profile_info(profile).capabilities:
                control_state["range_presets"] = list(self._range_presets)
                control_state["active_range_preset"] = self._active_range_preset + 1
        payload = {
            "connected": True,
            "device": {
                "address": self._session.address,
                "name": self._session.name,
                "profile": profile.value,
                "profile_ui": profile_ui(profile),
                "status": status,
                "control_state": control_state,
            },
        }
        self._last_status_json = json.dumps(payload["device"]["status"], sort_keys=True)
        return payload

    def _start_poll_locked(self):
        self._poll_task = asyncio.create_task(self._poll_status())

    async def _poll_status(self):
        while True:
            await asyncio.sleep(0.75)
            try:
                async with self._lock:
                    if self._device is None or self._session is None:
                        return
                    status = await self._device.get_status()
                    status = await self._advance_playback_locked(status)
                    status_json = json.dumps(status, sort_keys=True)
                    if status_json == self._last_status_json:
                        continue
                    self._last_status_json = status_json
                    payload = {
                        "connected": True,
                        "device": {
                            "address": self._session.address,
                            "name": self._session.name,
                            "profile": self._session.profile.value,
                            "profile_ui": profile_ui(self._session.profile),
                            "status": status,
                            "control_state": (
                                {
                                    "playback_behavior": self._playback_behavior,
                                    "range_presets": list(self._range_presets),
                                    "active_range_preset": self._active_range_preset + 1,
                                }
                                if self._session.profile == DeviceProfile.M2
                                else {"playback_behavior": self._playback_behavior}
                            ),
                        },
                    }
                await self._events.broadcast("session", payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                continue

    def _validate_custom_items_locked(self, items: list[tuple[int, int]]):
        if self._session is None:
            return
        mode_count = intimate_mode_count(self._session.profile)
        step_limit = intimate_custom_step_limit(self._session.profile)
        if len(items) > step_limit:
            raise HTTPException(status_code=400, detail=f"This profile supports up to {step_limit} custom steps")
        for mode, sec in items:
            if mode < 1 or mode > mode_count:
                raise HTTPException(status_code=400, detail=f"Mode must be between 1 and {mode_count}")
            if sec not in (10, 20, 30, 40, 50, 60):
                raise HTTPException(status_code=400, detail="Duration must be one of 10, 20, 30, 40, 50, or 60 seconds")

    def _reset_playback_clock_locked(self, *, enabled: bool):
        if enabled and self._playback_behavior in {"random", "sequence"}:
            self._next_mode_change_at = time.monotonic() + 30.0
        else:
            self._next_mode_change_at = None

    async def _advance_playback_locked(self, status: Optional[dict]) -> Optional[dict]:
        if not status or self._session is None:
            return status
        if self._playback_behavior not in {"random", "sequence"}:
            self._next_mode_change_at = None
            return status
        if not status.get("play"):
            self._next_mode_change_at = None
            return status
        if status.get("custom_mode"):
            self._next_mode_change_at = None
            return status
        if self._next_mode_change_at is None:
            self._next_mode_change_at = time.monotonic() + 30.0
            return status
        if time.monotonic() < self._next_mode_change_at:
            return status

        mode_count = intimate_mode_count(self._session.profile)
        current_mode = int(status.get("mode") or 1)
        if self._playback_behavior == "random":
            next_mode = current_mode
            if mode_count > 1:
                while next_mode == current_mode:
                    next_mode = random.randint(1, mode_count)
        else:
            next_mode = (current_mode % mode_count) + 1

        await self._device.intimate_set_mode(next_mode)
        self._next_mode_change_at = time.monotonic() + 30.0
        return await self._device.get_status()


class ScanRequest(BaseModel):
    timeout: float = Field(default=6.0, ge=1.0, le=30.0)
    name: str = ""


class ConnectRequest(BaseModel):
    address: str
    profile: Optional[str] = None


class PlayRequest(BaseModel):
    play: bool
    mode: Optional[int] = Field(default=None, ge=0, le=20)


class ModeRequest(BaseModel):
    mode: int = Field(ge=0, le=20)


class MotorRequest(BaseModel):
    motor1: int = Field(ge=0, le=100)
    motor2: Optional[int] = Field(default=None, ge=0, le=100)


class PositionRequest(BaseModel):
    position: str


class N2ModeRequest(BaseModel):
    name: str


class PlaybackBehaviorRequest(BaseModel):
    behavior: str


class PowerRequest(BaseModel):
    on: bool


class HumidityRequest(BaseModel):
    percent: int = Field(ge=0, le=100)


class WaterTemperatureRequest(BaseModel):
    temp: int = Field(ge=0, le=100)


class BathroomModeRequest(BaseModel):
    name: str


class CruiseTempRequest(BaseModel):
    temp: int = Field(ge=0, le=100)


class ZeroColdWaterModeRequest(BaseModel):
    mode: int = Field(description="0=off, 1=on, 3=enhanced")


class ProvisionRequest(BaseModel):
    ssid: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=0, max_length=128)
    config_url: str = ""
    encrypt: bool = True


class TimerEntry(BaseModel):
    switch: int = Field(ge=0, le=1, description="1=on-timer, 0=off-timer")
    status: int = Field(ge=0, le=1, description="1=enabled, 0=disabled")
    hours: int = Field(ge=0, le=23)


class TimerRequest(BaseModel):
    entries: list[TimerEntry] = Field(default_factory=list, max_length=6)


class CustomStep(BaseModel):
    mode: int = Field(ge=0, le=20)
    sec: int = Field(ge=0, le=255)


class CustomSetRequest(BaseModel):
    items: list[CustomStep]


class RangeRequest(BaseModel):
    start: int = Field(ge=0, le=92)
    end: int = Field(ge=0, le=92)


events = EventHub()
manager = DeviceSessionManager(events, mock_mode=DEFAULT_MOCK_MODE)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await manager.close()


app = FastAPI(title="TINGON Local Web UI", version="1.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")


@app.get("/")
async def root():
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/api/profiles")
async def get_profiles():
    return {
        "profiles": [profile_ui(profile) for profile in _web_profiles()],
        "positions": list(IntimateProtocol.POSITION_BYTES.keys()),
        "n2_modes": list(IntimateProtocol.N2_MODE_LABELS.values()),
        "playback_behaviors": list(INTIMATE_PLAYBACK_BEHAVIORS),
        "custom_slots": [32, 33, 34],
        "mock_mode": manager.mock_mode,
    }


@app.post("/api/scan")
async def scan_devices(request: ScanRequest):
    devices = await manager.scan(timeout=request.timeout, name=request.name)
    return {"devices": devices}


@app.post("/api/connect")
async def connect_device(request: ConnectRequest):
    return await manager.connect(request.address, request.profile)


@app.post("/api/disconnect")
async def disconnect_device():
    return await manager.disconnect()


@app.get("/api/session")
async def get_session():
    return await manager.get_session()


@app.get("/api/appliance/status")
async def appliance_status():
    return await manager.refresh_status()


@app.post("/api/appliance/power")
async def appliance_power(request: PowerRequest):
    return await manager.set_power(request.on)


@app.post("/api/appliance/humidity")
async def appliance_humidity(request: HumidityRequest):
    return await manager.set_humidity(request.percent)


@app.post("/api/appliance/drainage")
async def appliance_drainage(request: PowerRequest):
    return await manager.set_drainage(request.on)


@app.post("/api/appliance/dehumidification")
async def appliance_dehumidification(request: PowerRequest):
    return await manager.set_dehumidification(request.on)


@app.post("/api/appliance/water-temperature")
async def appliance_water_temperature(request: WaterTemperatureRequest):
    return await manager.set_water_temperature(request.temp)


@app.post("/api/appliance/bathroom-mode")
async def appliance_bathroom_mode(request: BathroomModeRequest):
    return await manager.set_bathroom_mode(request.name)


@app.post("/api/appliance/cruise-temp")
async def appliance_cruise_temp(request: CruiseTempRequest):
    return await manager.set_cruise_insulation_temp(request.temp)


@app.post("/api/appliance/zero-cold-water-mode")
async def appliance_zero_cold_water_mode(request: ZeroColdWaterModeRequest):
    return await manager.set_zero_cold_water_mode(request.mode)


@app.post("/api/appliance/eco-cruise")
async def appliance_eco_cruise(request: PowerRequest):
    return await manager.set_eco_cruise(request.on)


@app.post("/api/appliance/water-pressurization")
async def appliance_water_pressurization(request: PowerRequest):
    return await manager.set_water_pressurization(request.on)


@app.post("/api/appliance/single-cruise")
async def appliance_single_cruise(request: PowerRequest):
    return await manager.set_single_cruise(request.on)


@app.post("/api/appliance/diandong")
async def appliance_diandong(request: PowerRequest):
    return await manager.set_diandong(request.on)


@app.post("/api/appliance/zero-cold-water")
async def appliance_zero_cold_water(request: PowerRequest):
    return await manager.set_zero_cold_water(request.on)


@app.post("/api/appliance/timer")
async def appliance_timer(request: TimerRequest):
    entries = [entry.model_dump() for entry in request.entries]
    return await manager.set_timer(entries)


@app.post("/api/appliance/provision")
async def appliance_provision(request: ProvisionRequest):
    return await manager.provision_wifi(
        request.ssid, request.password, request.config_url, request.encrypt
    )


@app.post("/api/intimate/play")
async def intimate_play(request: PlayRequest):
    return await manager.set_play(request.play, request.mode)


@app.post("/api/intimate/mode")
async def intimate_mode(request: ModeRequest):
    return await manager.set_mode(request.mode)


@app.post("/api/intimate/motor")
async def intimate_motor(request: MotorRequest):
    return await manager.set_motor(request.motor1, request.motor2)


@app.post("/api/intimate/position")
async def intimate_position(request: PositionRequest):
    return await manager.set_position(request.position)


@app.post("/api/intimate/n2-mode")
async def intimate_n2_mode(request: N2ModeRequest):
    return await manager.set_n2_mode(request.name)


@app.post("/api/intimate/playback-behavior")
async def intimate_playback_behavior(request: PlaybackBehaviorRequest):
    return await manager.set_playback_behavior(request.behavior)


@app.get("/api/intimate/custom")
async def intimate_custom_get():
    return await manager.get_custom()


@app.post("/api/intimate/custom/{slot_id}")
async def intimate_custom_set(slot_id: int, request: CustomSetRequest):
    if slot_id not in (32, 33, 34):
        raise HTTPException(status_code=400, detail="Custom slots must be 32, 33, or 34")
    items = [(item.mode, item.sec) for item in request.items]
    return await manager.set_custom(slot_id, items)


@app.post("/api/intimate/custom/{slot_id}/use")
async def intimate_custom_use(slot_id: int):
    if slot_id not in (32, 33, 34):
        raise HTTPException(status_code=400, detail="Custom slots must be 32, 33, or 34")
    return await manager.use_custom(slot_id)


@app.post("/api/intimate/range")
async def intimate_range(request: RangeRequest):
    return await manager.set_range(request.start, request.end)


@app.post("/api/intimate/range/preset/{slot_id}/save")
async def intimate_range_save(slot_id: int, request: RangeRequest):
    return await manager.save_range_preset(slot_id, request.start, request.end)


@app.post("/api/intimate/range/preset/{slot_id}/use")
async def intimate_range_use(slot_id: int):
    return await manager.use_range_preset(slot_id)


@app.websocket("/api/events")
async def websocket_events(websocket: WebSocket):
    await events.connect(websocket)
    try:
        await websocket.send_json({"event": "session", "payload": await manager.get_session()})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await events.disconnect(websocket)
    except Exception:
        await events.disconnect(websocket)


def main():
    import uvicorn

    parser = argparse.ArgumentParser(prog="tingon-web", description="TINGON local web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    parser.add_argument("--mock", action="store_true", help="Use mock devices instead of live BLE")
    args = parser.parse_args()
    manager.set_mock_mode(args.mock)
    if args.mock:
        os.environ["TINGON_WEB_MOCK"] = "1"

    uvicorn.run(app, host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
