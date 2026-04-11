"""Low-level BLE transport: connection lifecycle and GATT I/O.

This module knows about Bleak, GATT characteristics, and notification
subscriptions. It does not know about TINGON protocol payload formats
or device-family-specific command semantics.
"""

from __future__ import annotations

import asyncio
import logging
from random import randint
from typing import Callable, Optional

from ..exceptions import TingonConnectionError, TingonDependencyError
from .uuids import (
    CHR_CMD_WRITE,
    CHR_PROV_NOTIFY,
    CHR_PROV_WRITE,
    CHR_QUERY_WRITE,
    WRITE_DELAY,
)

try:
    from bleak import BleakClient
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:  # pragma: no cover - import guard for optional bleak
    BleakClient = None  # type: ignore[assignment]
    BLEDevice = object  # type: ignore[assignment,misc]
    AdvertisementData = object  # type: ignore[assignment,misc]


LOGGER = logging.getLogger("tingon_py")


NotificationHandler = Callable[[object, bytearray], None]


class BleTransport:
    """Thin async wrapper around a single BleakClient connection."""

    def __init__(self) -> None:
        self._client: Optional["BleakClient"] = None
        self._address: Optional[str] = None

    @property
    def address(self) -> Optional[str]:
        return self._address

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @staticmethod
    def require_bleak() -> None:
        if BleakClient is None:
            raise TingonDependencyError(
                "bleak is not installed. Install it with: pip install bleak"
            )

    async def connect(self, address: str) -> None:
        self.require_bleak()
        self._address = address
        self._client = BleakClient(address)
        try:
            await self._client.connect()
        except Exception as exc:
            raise TingonConnectionError(f"Failed to connect to {address}") from exc
        LOGGER.info("Connected to %s", address)

    async def disconnect(self) -> None:
        if self._client and self._client.is_connected:
            await self._client.disconnect()
            LOGGER.info("Disconnected from %s", self._address or "device")
        self._client = None

    async def start_notify(self, characteristic: str, handler: NotificationHandler) -> None:
        assert self._client is not None
        await self._client.start_notify(characteristic, handler)

    async def stop_notify(self, characteristic: str) -> None:
        if self._client is None:
            return
        await self._client.stop_notify(characteristic)

    async def write_gatt_char(self, characteristic: str, data: bytes, *, response: bool = True) -> None:
        assert self._client is not None
        await self._client.write_gatt_char(characteristic, data, response=response)

    async def write_cmd(self, data: bytes) -> None:
        """Write to the ee02 command characteristic."""
        await self.write_gatt_char(CHR_CMD_WRITE, data, response=True)
        await asyncio.sleep(WRITE_DELAY)

    async def write_query(self, data: bytes) -> None:
        """Write to the cc02 query characteristic."""
        await self.write_gatt_char(CHR_QUERY_WRITE, data, response=True)
        await asyncio.sleep(WRITE_DELAY)

    async def write_prov_chunked(self, data: bytes) -> Optional[str]:
        """Write chunked data to the ff03 provisioning characteristic.

        Returns the concatenated notification response as an uppercase hex string,
        or None if the response did not arrive before the timeout.
        """
        chunk_size = 18
        chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        packet_id = randint(0, 255)

        prov_data = ""
        prov_event = asyncio.Event()

        def prov_handler(_char, recv_data: bytearray) -> None:
            nonlocal prov_data
            prov_data += recv_data.hex().upper()
            if len(recv_data) < 20:
                prov_event.set()

        await self.start_notify(CHR_PROV_NOTIFY, prov_handler)

        try:
            for i, chunk in enumerate(chunks):
                packet = bytes([packet_id, i + 1]) + chunk
                await self.write_gatt_char(CHR_PROV_WRITE, packet, response=True)
                await asyncio.sleep(WRITE_DELAY)

            # Send terminator if last chunk was exactly 18 bytes
            if chunks and len(chunks[-1]) == chunk_size:
                terminator = bytes([packet_id, len(chunks) + 1])
                await self.write_gatt_char(CHR_PROV_WRITE, terminator, response=True)

            try:
                await asyncio.wait_for(prov_event.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                LOGGER.warning("Provisioning response timeout")
                return None
        finally:
            await self.stop_notify(CHR_PROV_NOTIFY)

        return prov_data
