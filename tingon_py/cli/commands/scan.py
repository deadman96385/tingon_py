"""`tingon scan` command."""

from __future__ import annotations

from ...ble.scan import scan as scan_devices


async def cmd_scan(args) -> None:
    print(f"Scanning for TINGON devices ({args.timeout}s)...")
    devices = await scan_devices(name_filter=args.name or "", timeout=args.timeout)
    if not devices:
        print("No devices found.")
        return

    print(f"\nFound {len(devices)} device(s):\n")
    for d in devices:
        type_str = f" [{d.profile.value}]" if d.profile is not None else ""
        mac_str = f" (ADV MAC: {d.mac_from_adv})" if d.mac_from_adv else ""
        print(f"  {d.address}  {d.name}  RSSI: {d.rssi}{type_str}{mac_str}")


def register(subparsers) -> None:
    parser = subparsers.add_parser("scan", help="Scan for TINGON devices")
    parser.add_argument("--name", default="", help="Filter by device name")
    parser.add_argument("--timeout", type=float, default=10.0, help="Scan timeout in seconds")
    parser.set_defaults(func=cmd_scan)
