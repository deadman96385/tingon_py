"""Public API surface for the tingon_py package."""

from .ble.scan import parse_advertisement, scan
from .client import TingonClient
from .device import TingonDevice
from .exceptions import (
    TingonConnectionError,
    TingonDependencyError,
    TingonError,
    TingonProtocolError,
    TingonUnavailableError,
    TingonUnsupportedCapability,
)
from .intimates.status import IntimateStatus
from .models import ApplianceState, ScannedDevice
from .profiles import (
    DeviceProfile,
    DeviceType,
    ProfileInfo,
    ProtocolFamily,
    profile_info,
)


__all__ = [
    "ApplianceState",
    "DeviceProfile",
    "DeviceType",
    "IntimateStatus",
    "ProfileInfo",
    "ProtocolFamily",
    "ScannedDevice",
    "TingonClient",
    "TingonConnectionError",
    "TingonDependencyError",
    "TingonDevice",
    "TingonError",
    "TingonProtocolError",
    "TingonUnavailableError",
    "TingonUnsupportedCapability",
    "parse_advertisement",
    "profile_info",
    "scan",
]
