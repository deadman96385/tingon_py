"""`tingon status` command."""

from __future__ import annotations

from ..formatters import format_status
from ._common import add_profile_arg, connect_for_args


async def cmd_status(args) -> None:
    dev = await connect_for_args(args)
    try:
        if dev.is_intimate:
            # Intimate devices have no polling endpoint — the client's
            # status_dict helper returns the current locally-tracked state.
            status = dev.intimate_status_dict()
        else:
            await dev.update()
            state = dev.appliance_state
            status = state.as_dict() if state is not None else None

        if status:
            print("\nDevice Status:")
            print(format_status(status, dev.profile))
        else:
            print("Failed to get device status.")
    finally:
        await dev.disconnect()


def register(subparsers) -> None:
    parser = subparsers.add_parser("status", help="Query device status")
    parser.add_argument("address", help="Device BLE address")
    add_profile_arg(parser)
    parser.set_defaults(func=cmd_status)
