"""Top-level TINGON device orchestrator.

``TingonDevice`` is a thin coordinator that picks the right family-specific
controller based on the profile, wires it up with a BLE transport, and
exposes a stable surface for CLI, webapp, and Home Assistant callers.

It deliberately does not contain protocol or transport details of its own.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

from .appliances.controller import ApplianceController
from .ble.scan import scan as scan_devices
from .ble.transport import BleTransport
from .exceptions import TingonUnsupportedCapability
from .intimates.controller import IntimateController
from .intimates.status import IntimateStatus
from .models import ApplianceState, ScannedDevice
from .profiles import (
    APPLIANCE_TYPE_TO_PROFILE,
    DeviceProfile,
    DeviceType,
    ProfileInfo,
    ProtocolFamily,
    profile_info,
)

if TYPE_CHECKING:  # pragma: no cover
    from bleak.backends.device import BLEDevice


LOGGER = logging.getLogger("tingon_py")


Callback = Callable[[], None]
BleDeviceCallback = Callable[[], "Optional[BLEDevice]"]


class TingonDevice:
    """Async BLE orchestrator for TINGON IoT devices.

    ``TingonDevice`` takes a Bleak ``BLEDevice`` and delegates to the
    right family-specific controller. It exposes a callback registry so
    Home Assistant ``DataUpdateCoordinator`` listeners (and other
    consumers) can subscribe to state changes without polling.
    """

    def __init__(self) -> None:
        self._transport = BleTransport()
        self._profile: Optional[DeviceProfile] = None
        self._device_type: Optional[DeviceType] = None
        self._device_key: str = "41"
        self._appliance: Optional[ApplianceController] = None
        self._intimate: Optional[IntimateController] = None
        self._available: bool = False
        self._listeners: list[Callback] = []

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

    @property
    def available(self) -> bool:
        """True after a successful connect, False after disconnect or stale error."""
        return self._available

    @property
    def appliance_state(self) -> Optional[ApplianceState]:
        """Cached appliance snapshot (``None`` until the first ``update()``)."""
        return self._appliance.state if self._appliance is not None else None

    @property
    def intimate_status(self) -> Optional[IntimateStatus]:
        """Locally-tracked intimate device status.

        Intimate devices have no polling endpoint — this is populated
        from BLE notifications and mirrors the last-known state.
        """
        return self._intimate.status if self._intimate is not None else None

    def has_capability(self, capability: str) -> bool:
        return self.profile_meta is not None and capability in self.profile_meta.capabilities

    def require_capability(self, capability: str) -> None:
        if not self.has_capability(capability):
            prof = self._profile.value if self._profile else "unknown"
            raise TingonUnsupportedCapability(
                f"Profile '{prof}' does not support '{capability}'"
            )

    # ------------------------------------------------------------------
    # Callback registry
    # ------------------------------------------------------------------

    def register_callback(self, callback: Callback) -> Callback:
        """Register a zero-arg listener; returns an unregister function.

        Listeners fire on:

        - a command response that updates cached state,
        - an intimate notification that updates ``intimate_status``,
        - a BLE disconnect.

        The registered callback should be cheap and non-blocking. It
        runs in whatever loop the BLE event originated on.
        """
        self._listeners.append(callback)

        def _unregister() -> None:
            try:
                self._listeners.remove(callback)
            except ValueError:
                pass

        return _unregister

    def _fire_callbacks(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:  # pragma: no cover - defensive
                LOGGER.exception("Tingon listener raised")

    # ------------------------------------------------------------------
    # Scanning (class-level helper for convenience)
    # ------------------------------------------------------------------

    @staticmethod
    async def scan(
        name_filter: str = "",
        timeout: float = 10.0,
        scanner=None,
    ) -> list[ScannedDevice]:
        """Scan for TINGON BLE devices.

        Convenience for the CLI and webapp. Home Assistant integrations
        should use their own shared scanner and call ``parse_advertisement``.
        """
        return await scan_devices(scanner=scanner, name_filter=name_filter, timeout=timeout)

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
        """Connect to a TINGON device and wire up the right controller.

        ``device`` is a Bleak ``BLEDevice``. Callers that only have a
        MAC address resolve it at their own edge (the CLI does this via
        ``BleakScanner.find_device_by_address``; a Home Assistant
        integration calls ``async_ble_device_from_address``).

        ``disconnected_callback`` fires when the BLE link drops. It is
        called after internal cleanup — ``available`` is already
        ``False`` and registered listeners have already been notified.

        ``ble_device_callback`` is forwarded to
        :func:`bleak_retry_connector.establish_connection` and used to
        obtain a fresh ``BLEDevice`` on retry if the cached one is stale.
        """
        self._profile = profile or (
            APPLIANCE_TYPE_TO_PROFILE[device_type] if device_type is not None else None
        )
        if self._profile is not None and self.profile_meta and self.profile_meta.appliance_type is not None:
            device_type = self.profile_meta.appliance_type
        self._device_type = device_type

        def _on_disconnect(_client: object) -> None:
            self._handle_disconnect(disconnected_callback)

        await self._transport.connect(
            device,
            disconnected_callback=_on_disconnect,
            ble_device_callback=ble_device_callback,
            max_attempts=max_attempts,
        )

        if self.is_intimate:
            assert self._profile is not None
            self._intimate = IntimateController(self._transport, self._profile)
            self._intimate.register_listener(self._fire_callbacks)
            await self._intimate.setup_notifications()
        else:
            # Appliance family, or unknown profile (fall back to appliance wiring)
            self._appliance = ApplianceController(
                self._transport, self._device_type, self._device_key
            )
            self._appliance.register_listener(self._fire_callbacks)
            await self._appliance.setup_notifications()

        self._available = True

        if self.profile_meta is not None:
            LOGGER.info(
                "Profile: %s (%s)",
                self.profile_meta.display_name,
                self.profile_meta.category,
            )
        elif self._device_type is not None:
            category = "Dehumidifier" if self._appliance and self._appliance.is_dehumidifier else "Water Heater"
            LOGGER.info("Device type: %s (%s)", self._device_type.name, category)

    def _handle_disconnect(self, consumer_callback: Optional[Callback]) -> None:
        """Internal disconnect hook — runs inside Bleak's callback thread."""
        self._available = False
        self._fire_callbacks()
        if consumer_callback is not None:
            try:
                consumer_callback()
            except Exception:  # pragma: no cover - defensive
                LOGGER.exception("Consumer disconnected_callback raised")

    async def disconnect(self) -> None:
        await self._transport.disconnect()
        self._appliance = None
        self._intimate = None
        if self._available:
            self._available = False
            self._fire_callbacks()

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
    # Polling update (coordinator-friendly)
    # ------------------------------------------------------------------

    async def update(self) -> None:
        """Refresh cached state.

        For appliances this issues a full query and updates
        ``appliance_state``. Intimate devices are push-only — ``update``
        is a no-op and state is already current via notifications.
        """
        if self.is_intimate:
            return
        await self._require_appliance().query_all()

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

    async def set_cruise_insulation_temp(self, temp: int):
        return await self._require_appliance().set_cruise_insulation_temp(temp)

    async def set_zero_cold_water_mode(self, mode: int):
        return await self._require_appliance().set_zero_cold_water_mode(mode)

    async def set_eco_cruise(self, on: bool):
        return await self._require_appliance().set_eco_cruise(on)

    async def set_water_pressurization(self, on: bool):
        return await self._require_appliance().set_water_pressurization(on)

    async def set_single_cruise(self, on: bool):
        return await self._require_appliance().set_single_cruise(on)

    async def set_diandong(self, on: bool):
        return await self._require_appliance().set_diandong(on)

    async def set_zero_cold_water(self, on: bool):
        return await self._require_appliance().set_zero_cold_water(on)

    async def set_timer(
        self,
        entries: "list[dict] | None" = None,
        *,
        timer_hex: Optional[str] = None,
        remind_hex: Optional[str] = None,
    ):
        return await self._require_appliance().set_timer(
            entries, timer_hex=timer_hex, remind_hex=remind_hex
        )

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

    def intimate_status_dict(self) -> Optional[dict]:
        """Return the intimate controller's locally-tracked status as a dict.

        Intimate devices have no polling endpoint — this returns the
        last-known state assembled from BLE notifications and local
        mutations, with profile-aware label mapping applied.
        """
        if self._intimate is None:
            return None
        return self._intimate.status_dict()

    def status_dict(self) -> Optional[dict]:
        """Return the current device status as a dict.

        Unified view for display/serialisation: for appliance devices
        this returns ``appliance_state.as_dict()``; for intimate
        devices it returns the locally-tracked status with profile
        aware label mapping. Callers that need a refreshed appliance
        snapshot should ``await update()`` first.
        """
        if self.is_intimate:
            return self.intimate_status_dict()
        state = self.appliance_state
        return state.as_dict() if state is not None else None

    # ------------------------------------------------------------------
    # Raw access (works for either family)
    # ------------------------------------------------------------------

    async def send_raw_hex(self, hex_str: str) -> None:
        if self._intimate is not None:
            await self._intimate.send_raw_hex(hex_str)
            return
        await self._require_appliance().send_raw_hex(hex_str)
