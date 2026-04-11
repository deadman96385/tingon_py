"""High-level appliance control API.

This controller speaks in meaningful domain methods (power, humidity,
temperature, bathroom mode, provisioning) and uses the BLE transport
together with the appliance protocol helpers to execute each action.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from ..ble.transport import BleTransport
from ..ble.uuids import CHR_CMD_NOTIFY, CHR_QUERY_NOTIFY, JUNK_DATA
from ..crypto import TingonEncryption
from ..profiles import DeviceType
from .protocol import TingonProtocol
from .specs import (
    DEHUMIDIFIER_QUERY_IDS,
    DEHUMIDIFIER_SIGNED_SPECS,
    DEHUMIDIFIER_SPECS,
    DEHUMIDIFIER_TYPES,
    WATER_HEATER_QUERY_IDS,
    WATER_HEATER_SIGNED_SPECS,
    WATER_HEATER_SPECS,
    WATER_HEATER_TYPES,
)


LOGGER = logging.getLogger("tingon_py")


class ApplianceController:
    """BLE controller for TINGON dehumidifier/water heater devices."""

    def __init__(
        self,
        transport: BleTransport,
        device_type: Optional[DeviceType] = None,
        device_key: str = "41",
    ) -> None:
        self._transport = transport
        self._device_type = device_type
        self._device_key = device_key
        self._response_data: str = ""
        self._response_event = asyncio.Event()
        self._query_data: str = ""
        self._query_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    @property
    def device_type(self) -> Optional[DeviceType]:
        return self._device_type

    def set_device_type(self, device_type: Optional[DeviceType]) -> None:
        self._device_type = device_type

    def set_device_key(self, device_key: str) -> None:
        self._device_key = device_key

    @property
    def is_dehumidifier(self) -> bool:
        return self._device_type in DEHUMIDIFIER_TYPES

    @property
    def is_water_heater(self) -> bool:
        return self._device_type in WATER_HEATER_TYPES

    @property
    def specs(self):
        if self.is_water_heater:
            return WATER_HEATER_SPECS
        return DEHUMIDIFIER_SPECS

    @property
    def query_ids(self) -> list[int]:
        if self.is_water_heater:
            return WATER_HEATER_QUERY_IDS
        return DEHUMIDIFIER_QUERY_IDS

    @property
    def signed_specs(self) -> set[int]:
        if self.is_water_heater:
            return WATER_HEATER_SIGNED_SPECS
        return DEHUMIDIFIER_SIGNED_SPECS

    # ------------------------------------------------------------------
    # Notification setup
    # ------------------------------------------------------------------

    async def setup_notifications(self) -> None:
        """Subscribe to the ee04 and cc03 notification characteristics."""
        try:
            await self._transport.start_notify(CHR_CMD_NOTIFY, self._cmd_notification_handler)
        except Exception:
            LOGGER.warning("Could not subscribe to command notifications (ee04)", exc_info=True)
        try:
            await self._transport.start_notify(CHR_QUERY_NOTIFY, self._query_notification_handler)
        except Exception:
            LOGGER.warning("Could not subscribe to query notifications (cc03)", exc_info=True)

    def _cmd_notification_handler(self, _characteristic, data: bytearray) -> None:
        hex_data = data.hex().upper()
        if hex_data == JUNK_DATA:
            return
        self._response_data += hex_data
        if len(data) < 20:
            self._response_event.set()

    def _query_notification_handler(self, _characteristic, data: bytearray) -> None:
        hex_data = data.hex().upper()
        self._query_data += hex_data
        if len(data) < 20:
            self._query_event.set()

    # ------------------------------------------------------------------
    # Low-level command plumbing
    # ------------------------------------------------------------------

    async def send_command(self, spec_id: int, value) -> Optional[dict]:
        """Send a single-property command and return parsed response."""
        hex_cmd = TingonProtocol.encode_command(spec_id, value)
        self._response_data = ""
        self._response_event.clear()

        await self._transport.write_cmd(TingonProtocol.hex_to_bytes(hex_cmd))

        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            LOGGER.warning("Command response timeout")
            return None

        return TingonProtocol.parse_response(self._response_data, self.signed_specs)

    async def send_multi_command(self, specs: dict) -> Optional[dict]:
        """Send a multi-property command and return parsed response."""
        hex_cmd = TingonProtocol.encode_multi_command(specs)
        self._response_data = ""
        self._response_event.clear()

        await self._transport.write_cmd(TingonProtocol.hex_to_bytes(hex_cmd))

        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            LOGGER.warning("Command response timeout")
            return None

        return TingonProtocol.parse_response(self._response_data, self.signed_specs)

    async def send_raw_hex(self, hex_str: str) -> None:
        """Send a raw hex string command."""
        await self._transport.write_cmd(TingonProtocol.hex_to_bytes(hex_str))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def query_all(self) -> Optional[dict]:
        """Query all device properties, returns {spec_id: value}."""
        return await self.query_specs(self.query_ids)

    async def query_specs(self, spec_ids: list[int]) -> Optional[dict]:
        """Query specific device properties."""
        query_bytes = TingonProtocol.build_query(spec_ids)
        self._query_data = ""
        self._query_event.clear()

        await self._transport.write_query(query_bytes)

        try:
            await asyncio.wait_for(self._query_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            LOGGER.warning("Query response timeout")
            return None

        return TingonProtocol.parse_response(self._query_data, self.signed_specs)

    async def get_status(self) -> Optional[dict]:
        """Query all properties and return a human-readable dict with named keys."""
        raw = await self.query_all()
        if raw is None:
            return None

        result: dict[str, object] = {}
        specs = self.specs
        for spec_id, value in raw.items():
            if spec_id in specs:
                result[specs[spec_id].name] = value
            else:
                result[f"spec_{spec_id}"] = value
        return result

    # ------------------------------------------------------------------
    # Convenience: power (both device types)
    # ------------------------------------------------------------------

    async def set_power(self, on: bool) -> Optional[dict]:
        return await self.send_command(1, 1 if on else 0)

    # ------------------------------------------------------------------
    # Convenience: dehumidifier
    # ------------------------------------------------------------------

    async def set_target_humidity(self, percent: int) -> Optional[dict]:
        return await self.send_command(5, percent)

    async def set_drainage(self, on: bool) -> Optional[dict]:
        return await self.send_command(3, 1 if on else 0)

    async def set_dehumidification(self, on: bool) -> Optional[dict]:
        return await self.send_command(4, 1 if on else 0)

    async def set_timer(self, timer_hex: str, remind_hex: str = "") -> Optional[dict]:
        specs = {2: timer_hex}
        if remind_hex:
            specs[18] = remind_hex
        return await self.send_multi_command(specs)

    # ------------------------------------------------------------------
    # Convenience: water heater
    # ------------------------------------------------------------------

    async def set_water_temperature(self, temp: int) -> Optional[dict]:
        return await self.send_command(7, temp)

    async def set_bathroom_mode(self, mode: int) -> Optional[dict]:
        """Set bathroom mode: 1=normal, 2=kitchen, 4=eco, 5=season."""
        return await self.send_command(2, format(mode, "02x"))

    async def set_cruise_insulation_temp(self, temp: int) -> Optional[dict]:
        return await self.send_command(105, temp)

    async def set_zero_cold_water_mode(self, mode: int) -> Optional[dict]:
        """Set zero-cold-water mode: 0=off, 1=on, 3=enhanced."""
        return await self.send_command(106, mode)

    async def set_eco_cruise(self, on: bool) -> Optional[dict]:
        return await self.send_command(107, 1 if on else 0)

    async def set_water_pressurization(self, on: bool) -> Optional[dict]:
        return await self.send_command(108, 1 if on else 0)

    # ------------------------------------------------------------------
    # WiFi Provisioning
    # ------------------------------------------------------------------

    async def provision_wifi(
        self,
        ssid: str,
        password: str,
        config_url: str = "",
        encrypt: bool = True,
    ) -> Optional[dict]:
        """Provision WiFi credentials via BLE (ff service)."""
        payload = {
            "CID": 30005,
            "PL": {"SSID": ssid, "Password": password},
            "URL": config_url,
        }
        json_str = json.dumps(payload, separators=(",", ":"))

        if encrypt:
            encrypted_hex = TingonEncryption.xor_encrypt(json_str, self._device_key)
            data = bytes.fromhex(encrypted_hex)
        else:
            data = json_str.encode("utf-8")

        response_hex = await self._transport.write_prov_chunked(data)
        if not response_hex:
            return None

        try:
            if encrypt:
                decrypted = TingonEncryption.xor_decrypt(response_hex.lower(), self._device_key)
                start = decrypted.index("{")
                end = decrypted.rindex("}") + 1
                json_str = decrypted[start:end]
            else:
                json_str = bytes.fromhex(response_hex).decode("utf-8", errors="replace")

            return json.loads(json_str)
        except (ValueError, json.JSONDecodeError):
            LOGGER.warning("Failed to parse provisioning response", exc_info=True)
            return None
