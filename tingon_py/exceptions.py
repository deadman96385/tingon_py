class TingonError(Exception):
    """Base class for public tingon_py exceptions."""


class TingonDependencyError(TingonError):
    """Raised when an optional runtime dependency is unavailable."""


class TingonConnectionError(TingonError):
    """Raised when a BLE connection cannot be established."""


class TingonUnavailableError(TingonConnectionError):
    """Raised when the device cannot be reached.

    Distinct from ``TingonConnectionError`` so Home Assistant integrations
    can tell a temporarily unreachable device (stale ``BLEDevice``,
    ``BleakNotFoundError``, ``ble_device_callback`` returning ``None``)
    from a fundamentally broken connection.
    """


class TingonProtocolError(TingonError):
    """Raised when command or profile inputs are invalid."""


class TingonUnsupportedCapability(TingonError):
    """Raised when a profile does not support a requested capability."""
