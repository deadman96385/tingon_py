"""`tingon` intimate-family commands (play, motor, position, n2-mode, custom)."""

from __future__ import annotations

import json

from ...intimates.protocol import IntimateProtocol
from ._common import add_profile_arg, connect_for_args


async def cmd_play(args) -> None:
    dev = await connect_for_args(args)
    try:
        await dev.intimate_play(args.state == "on", args.mode)
        print(f"Playback {'started' if args.state == 'on' else 'stopped'}")
    finally:
        await dev.disconnect()


async def cmd_motor(args) -> None:
    dev = await connect_for_args(args)
    try:
        await dev.intimate_set_output(args.motor1, args.motor2)
        print(f"Output updated: motor1={args.motor1}, motor2={args.motor2}")
    finally:
        await dev.disconnect()


async def cmd_position(args) -> None:
    dev = await connect_for_args(args)
    try:
        await dev.intimate_set_position(args.position)
        print(f"Position set to {args.position}")
    finally:
        await dev.disconnect()


async def cmd_n2_mode(args) -> None:
    dev = await connect_for_args(args)
    try:
        await dev.intimate_set_n2_mode(args.name)
        print(f"N2 selector set to {args.name}")
    finally:
        await dev.disconnect()


async def cmd_custom_get(args) -> None:
    dev = await connect_for_args(args)
    try:
        items = await dev.intimate_query_custom(args.slot)
        print(json.dumps(items, indent=2))
    finally:
        await dev.disconnect()


async def cmd_custom_set(args) -> None:
    dev = await connect_for_args(args)
    try:
        items = []
        for item in args.items:
            mode_raw, sec_raw = item.split(":", 1)
            items.append((int(mode_raw), int(sec_raw)))
        await dev.intimate_set_custom(args.slot, items)
        print(f"Custom slot {args.slot} updated with {len(items)} step(s)")
    finally:
        await dev.disconnect()


def register(subparsers) -> None:
    p_play = subparsers.add_parser("play", help="Start or stop intimate playback")
    p_play.add_argument("address", help="Device BLE address")
    p_play.add_argument("state", choices=["on", "off"], help="Playback state")
    p_play.add_argument("--mode", type=int, default=None, help="Mode to use when starting playback")
    add_profile_arg(p_play)
    p_play.set_defaults(func=cmd_play)

    p_motor = subparsers.add_parser("motor", help="Set intimate manual output")
    p_motor.add_argument("address", help="Device BLE address")
    p_motor.add_argument("motor1", type=int, help="Primary output 0-100")
    p_motor.add_argument("motor2", type=int, nargs="?", default=None, help="Secondary output 0-100")
    add_profile_arg(p_motor)
    p_motor.set_defaults(func=cmd_motor)

    p_position = subparsers.add_parser("position", help="Set M2 position selector")
    p_position.add_argument("address", help="Device BLE address")
    p_position.add_argument(
        "position",
        choices=sorted(IntimateProtocol.POSITION_BYTES.keys()),
        help="Position selector",
    )
    add_profile_arg(p_position)
    p_position.set_defaults(func=cmd_position)

    p_n2 = subparsers.add_parser("n2-mode", help="Set the local N2 selector")
    p_n2.add_argument("address", help="Device BLE address")
    p_n2.add_argument(
        "name",
        choices=list(IntimateProtocol.N2_MODE_LABELS.values()),
        help="N2 selector",
    )
    add_profile_arg(p_n2)
    p_n2.set_defaults(func=cmd_n2_mode)

    p_cget = subparsers.add_parser("custom-get", help="Read intimate custom slot")
    p_cget.add_argument("address", help="Device BLE address")
    p_cget.add_argument("slot", type=int, choices=[32, 33, 34], help="Custom slot ID")
    add_profile_arg(p_cget)
    p_cget.set_defaults(func=cmd_custom_get)

    p_cset = subparsers.add_parser("custom-set", help="Write intimate custom slot")
    p_cset.add_argument("address", help="Device BLE address")
    p_cset.add_argument("slot", type=int, choices=[32, 33, 34], help="Custom slot ID")
    p_cset.add_argument("items", nargs="+", help="Sequence of mode:sec pairs")
    add_profile_arg(p_cset)
    p_cset.set_defaults(func=cmd_custom_set)
