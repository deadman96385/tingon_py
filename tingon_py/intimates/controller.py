"""High-level intimate-device control API."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from ..ble.transport import BleTransport
from ..ble.uuids import CHR_CMD_NOTIFY, JUNK_DATA
from ..exceptions import TingonProtocolError
from ..profiles import (
    CAP_CUSTOM,
    CAP_CUSTOM_RANGE,
    CAP_MOTOR1,
    CAP_MOTOR2,
    CAP_N2_MODE,
    CAP_PLAY,
    CAP_POSITION,
    CAP_PRESET_MODE,
    DeviceProfile,
    profile_info,
)
from .protocol import IntimateProtocol
from .status import IntimateStatus


LOGGER = logging.getLogger("tingon_py")


class IntimateController:
    """BLE controller for TINGON intimate devices."""

    def __init__(self, transport: BleTransport, profile: DeviceProfile) -> None:
        self._transport = transport
        self._profile = profile
        self._status = IntimateStatus()
        self._response_data: str = ""
        self._response_event = asyncio.Event()
        self._listeners: list[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    def register_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a zero-arg listener; returns an unregister function."""
        self._listeners.append(callback)

        def _unregister() -> None:
            try:
                self._listeners.remove(callback)
            except ValueError:
                pass

        return _unregister

    def _notify_listeners(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:  # pragma: no cover - defensive
                LOGGER.exception("Intimate state listener raised")

    @property
    def profile(self) -> DeviceProfile:
        return self._profile

    @property
    def status(self) -> IntimateStatus:
        return self._status

    # ------------------------------------------------------------------
    # Notification setup
    # ------------------------------------------------------------------

    async def setup_notifications(self) -> None:
        try:
            await self._transport.start_notify(CHR_CMD_NOTIFY, self._cmd_notification_handler)
        except Exception:
            LOGGER.warning("Could not subscribe to command notifications (ee04)", exc_info=True)

    def _cmd_notification_handler(self, _characteristic, data: bytearray) -> None:
        hex_data = data.hex().upper()
        if hex_data == JUNK_DATA:
            return
        self._response_data += hex_data
        parsed = IntimateProtocol.parse_notify(hex_data, self._profile)
        mutated = False
        if "mode" in parsed:
            self._status.mode = parsed["mode"]
            self._status.play = parsed["mode"] != 0
            mutated = True
        if "motor1" in parsed:
            self._status.motor1 = parsed["motor1"]
            self._status.play = self._status.motor1 > 0 or self._status.motor2 > 0
            mutated = True
        if "motor2" in parsed:
            self._status.motor2 = parsed["motor2"]
            self._status.play = self._status.motor1 > 0 or self._status.motor2 > 0
            mutated = True
        if len(data) < 20:
            self._response_event.set()
        if mutated:
            self._notify_listeners()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _has_capability(self, capability: str) -> bool:
        return capability in profile_info(self._profile).capabilities

    def _require_capability(self, capability: str) -> None:
        from ..exceptions import TingonUnsupportedCapability

        if not self._has_capability(capability):
            raise TingonUnsupportedCapability(
                f"Profile '{self._profile.value}' does not support '{capability}'"
            )

    async def _send_hex(self, hex_str: str) -> None:
        await self._transport.write_cmd(bytes.fromhex(hex_str.replace(" ", "")))

    async def send_raw_hex(self, hex_str: str) -> None:
        await self._send_hex(hex_str)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status_dict(self) -> dict:
        """Return the current locally-tracked status as a plain dict.

        Includes label-mapping for N2 mode and expands custom slots into
        per-slot keys. This is a *display helper* — there is no BLE
        round-trip. Consumers that want raw structured access should
        read :attr:`status` directly.
        """
        result: dict[str, object] = {
            "play": self._status.play,
            "mode": self._status.mode,
            "motor1": self._status.motor1,
            "motor2": self._status.motor2,
            "custom_mode": self._status.custom_mode,
        }
        if self._has_capability(CAP_POSITION):
            result["position"] = self._status.position
            result["range_start"] = self._status.range_start
            result["range_end"] = self._status.range_end
        if self._has_capability(CAP_N2_MODE):
            result["n2_mode"] = IntimateProtocol.N2_MODE_LABELS.get(
                self._status.n2_mode,
                self._status.n2_mode,
            )
        for slot_id, items in self._status.custom_slots.items():
            result[f"custom_{slot_id}"] = items
        return result

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def play(self, play: bool, mode: Optional[int] = None) -> None:
        self._require_capability(CAP_PLAY)
        current_mode = mode if mode is not None else max(self._status.mode, 1)
        await self._send_hex(IntimateProtocol.encode_play(play, current_mode))
        self._status.play = play
        if not play:
            self._status.mode = 0
            self._status.custom_mode = None
        self._notify_listeners()

    async def set_mode(self, mode: int) -> None:
        self._require_capability(CAP_PRESET_MODE)
        await self._send_hex(IntimateProtocol.encode_mode(mode))
        self._status.mode = int(mode)
        self._status.play = mode != 0
        self._status.custom_mode = None
        self._status.motor1 = 0
        self._status.motor2 = 0
        self._notify_listeners()

    async def use_custom(self, slot_id: int) -> None:
        self._require_capability(CAP_CUSTOM)
        if slot_id not in (32, 33, 34):
            raise TingonProtocolError("Custom slots must be 32, 33, or 34")
        await self._send_hex(IntimateProtocol.encode_mode(slot_id))
        self._status.play = True
        self._status.mode = 0
        self._status.custom_mode = int(slot_id)
        self._status.motor1 = 0
        self._status.motor2 = 0
        self._notify_listeners()

    async def set_output(self, motor1: int, motor2: Optional[int] = None) -> None:
        self._require_capability(CAP_MOTOR1)
        if self._profile == DeviceProfile.M2:
            await self._send_hex(
                IntimateProtocol.encode_position_speed(self._status.position, motor1)
            )
            self._status.motor1 = int(motor1)
        elif self._profile == DeviceProfile.M1:
            self._require_capability(CAP_MOTOR2)
            if motor2 is None:
                motor2 = self._status.motor2
            await self._send_hex(
                IntimateProtocol.encode_dual_output(motor1, motor2, quantized=True)
            )
            self._status.motor1 = int(motor1)
            self._status.motor2 = int(motor2)
        elif self._profile == DeviceProfile.N2:
            if motor2 is not None:
                await self._send_hex(
                    IntimateProtocol.encode_dual_output(motor1, motor2, quantized=False)
                )
                self._status.motor2 = int(motor2)
            else:
                await self._send_hex(IntimateProtocol.encode_single_output(motor1))
            self._status.motor1 = int(motor1)
        else:
            await self._send_hex(IntimateProtocol.encode_single_output(motor1))
            self._status.motor1 = int(motor1)

        self._status.play = self._status.motor1 > 0 or self._status.motor2 > 0
        self._status.mode = 0
        self._status.custom_mode = None
        self._notify_listeners()

    async def set_position(self, position: str) -> None:
        self._require_capability(CAP_POSITION)
        normalized = position.lower().replace("-", "_")
        if normalized not in IntimateProtocol.POSITION_BYTES:
            raise TingonProtocolError(f"Unknown position '{position}'")
        self._status.position = normalized
        await self._send_hex(
            IntimateProtocol.encode_position_speed(normalized, self._status.motor1)
        )
        self._notify_listeners()

    async def set_custom_range(self, start: int, end: int) -> None:
        self._require_capability(CAP_CUSTOM_RANGE)
        normalized_start, normalized_end = IntimateProtocol.normalize_range(start, end)
        await self._send_hex(IntimateProtocol.encode_custom_range(normalized_start, normalized_end))
        self._status.range_start = normalized_start
        self._status.range_end = normalized_end
        self._notify_listeners()

    async def set_n2_mode(self, mode_name: str) -> None:
        self._require_capability(CAP_N2_MODE)
        lookup = {label: idx for idx, label in IntimateProtocol.N2_MODE_LABELS.items()}
        if mode_name not in lookup:
            raise TingonProtocolError(f"Unknown N2 selector '{mode_name}'")
        self._status.n2_mode = lookup[mode_name]
        self._notify_listeners()

    async def query_custom(self, slot_id: int) -> list[dict[str, int]]:
        self._require_capability(CAP_CUSTOM)
        if slot_id not in (32, 33, 34):
            raise TingonProtocolError("Custom slots must be 32, 33, or 34")
        self._response_data = ""
        self._response_event.clear()
        await self._send_hex(IntimateProtocol.encode_query_custom(slot_id))
        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            return self._status.custom_slots[slot_id]

        if self._response_data.startswith("0A04") and len(self._response_data) >= 8:
            payload_len = int(self._response_data[6:8], 16) * 2
            body = self._response_data[8:8 + payload_len]
            self._status.custom_slots[slot_id] = IntimateProtocol.decode_custom_hex(body)
            self._notify_listeners()
        return self._status.custom_slots[slot_id]

    async def set_custom(self, slot_id: int, items: list[tuple[int, int]]) -> None:
        self._require_capability(CAP_CUSTOM)
        if slot_id not in (32, 33, 34):
            raise TingonProtocolError("Custom slots must be 32, 33, or 34")
        await self._send_hex(IntimateProtocol.encode_custom(slot_id, items))
        self._status.custom_slots[slot_id] = [
            {"mode": int(mode), "sec": int(sec)} for mode, sec in items
        ]
        self._notify_listeners()
