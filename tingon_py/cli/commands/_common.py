"""Shared helpers for CLI command modules."""

from __future__ import annotations

from ...client import TingonClient
from ...exceptions import TingonProtocolError
from ...profiles import DeviceProfile, profile_info


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


async def connect_for_args(args) -> TingonClient:
    dev = TingonClient()
    profile = resolve_profile_arg(args)
    meta = profile_info(profile)
    await dev.connect(args.address, device_type=meta.appliance_type, profile=profile)
    return dev
