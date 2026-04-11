"""Low-level BLE transport: connection lifecycle and GATT I/O.

This module knows about Bleak, GATT characteristics, and notification
subscriptions. It does not know about TINGON protocol payload formats
or device-family-specific command semantics.

External consumers (Home Assistant integrations, the bundled CLI and
webapp) are all expected to hand in a ``BLEDevice`` they already
resolved. This module does not own scanning.
"""

from __future__ import annotations

import asyncio
import logging
from random import randint
from typing import Callable, Optional

from ..exceptions import (
    TingonConnectionError,
    TingonDependencyError,
    TingonUnavailableError,
)
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
    from bleak.exc import BleakError
except ImportError:  # pragma: no cover - import guard for optional bleak
    BleakClient = None  # type: ignore[assignment]
    BLEDevice = object  # type: ignore[assignment,misc]
    AdvertisementData = object  # type: ignore[assignment,misc]
    BleakError = Exception  # type: ignore[assignment,misc]

try:
    from bleak_retry_connector import (
        BleakClientWithServiceCache,
        BleakNotFoundError,
        establish_connection,
    )
except ImportError:  # pragma: no cover - import guard for optional dep
    BleakClientWithServiceCache = None  # type: ignore[assignment]
    BleakNotFoundError = Exception  # type: ignore[assignment,misc]
    establish_connection = None  # type: ignore[assignment]


LOGGER = logging.getLogger("tingon_py")


NotificationHandler = Callable[[object, bytearray], None]
DisconnectedCallback = Callable[[object], None]
BleDeviceCallback = Callable[[], "Optional[BLEDevice]"]


class BleTransport:
    """Thin async wrapper around a single ``BleakClientWithServiceCache``.

    Connection lifecycle is handled via
    :func:`bleak_retry_connector.establish_connection` so transient
    connection errors are retried with back-off and GATT services are
    cached across reconnects.
    """

    def __init__(self) -> None:
        self._client: "Optional[BleakClient]" = None
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
        if establish_connection is None:
            raise TingonDependencyError(
                "bleak-retry-connector is not installed. "
                "Install it with: pip install bleak-retry-connector"
            )

    async def connect(
        self,
        device: "BLEDevice",
        *,
        name: Optional[str] = None,
        disconnected_callback: Optional[DisconnectedCallback] = None,
        ble_device_callback: Optional[BleDeviceCallback] = None,
        max_attempts: int = 3,
    ) -> None:
        """Connect to a TINGON device via ``establish_connection``.

        ``device`` must be a Bleak ``BLEDevice``. Callers that only have
        a MAC address are responsible for resolving it — the CLI does
        this at its edge via ``BleakScanner.find_device_by_address``.
        """
        self.require_bleak()
        resolved_name = name or getattr(device, "name", None) or "Tingon"
        self._address = getattr(device, "address", None)

        try:
            self._client = await establish_connection(
                BleakClientWithServiceCache,
                device,
                resolved_name,
                disconnected_callback=disconnected_callback,
                max_attempts=max_attempts,
                ble_device_callback=ble_device_callback,
                use_services_cache=True,
            )
        except BleakNotFoundError as exc:
            raise TingonUnavailableError(
                f"device not found: {self._address or resolved_name}"
            ) from exc
        except BleakError as exc:
            raise TingonConnectionError(
                f"failed to connect to {self._address or resolved_name}: {exc}"
            ) from exc

        LOGGER.info("Connected to %s", self._address or resolved_name)

    async def disconnect(self) -> None:
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
            except BleakError as exc:
                LOGGER.warning("Error during disconnect from %s: %s", self._address, exc)
            else:
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
