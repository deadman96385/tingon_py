"""Shared helpers for CLI command modules."""

from __future__ import annotations

from ...client import TingonClient
from ...exceptions import TingonDependencyError, TingonProtocolError, TingonUnavailableError
from ...profiles import DeviceProfile, profile_info

try:
    from bleak import BleakScanner
except ImportError:  # pragma: no cover - import guard for optional bleak
    BleakScanner = None  # type: ignore[assignment]


def add_profile_arg(parser, required: bool = True) -> None:
    parser.add_argument(
        "--profile",
        required=required,
        help="Profile: fjb, fjb2, gs, rj, a1, n1, n2, m1, m2",
    )


def resolve_profile_arg(args) -> DeviceProfile:
    profile = DeviceProfile.parse(getattr(args, "profile", None))
    if profile is None:
        raise TingonProtocolError("--profile is required")
    return profile


async def _resolve_ble_device(address: str):
    if BleakScanner is None:
        raise TingonDependencyError(
            "bleak is not installed. Install it with: pip install bleak"
        )
    ble_device = await BleakScanner.find_device_by_address(address, timeout=10.0)
    if ble_device is None:
        raise TingonUnavailableError(f"device not found: {address}")
    return ble_device


async def connect_for_args(args) -> TingonClient:
    dev = TingonClient()
    profile = resolve_profile_arg(args)
    meta = profile_info(profile)
    ble_device = await _resolve_ble_device(args.address)
    await dev.connect(ble_device, device_type=meta.appliance_type, profile=profile)
    return dev
