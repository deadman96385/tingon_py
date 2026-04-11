"""Public API surface for the tingon_py package."""

from .ble.scan import scan
from .client import TingonClient
from .exceptions import (
    TingonConnectionError,
    TingonDependencyError,
    TingonError,
    TingonProtocolError,
    TingonUnsupportedCapability,
)
from .models import ScannedDevice
from .profiles import (
    DeviceProfile,
    DeviceType,
    ProfileInfo,
    ProtocolFamily,
    profile_info,
)


__all__ = [
    "DeviceProfile",
    "DeviceType",
    "ProfileInfo",
    "ProtocolFamily",
    "ScannedDevice",
    "profile_info",
    "scan",
    "TingonClient",
    "TingonConnectionError",
    "TingonDependencyError",
    "TingonError",
    "TingonProtocolError",
    "TingonUnsupportedCapability",
]
