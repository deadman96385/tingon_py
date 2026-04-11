"""Entry point for the ``tingon`` command-line interface."""

from __future__ import annotations

import argparse
import asyncio

from .commands import appliance, intimate, provision, scan, status


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tingon",
        description="TINGON IoT BLE Device Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tingon scan
  tingon status AA:BB:CC:DD:EE:FF --profile fjb
  tingon humidity AA:BB:CC:DD:EE:FF 50 --profile fjb2
  tingon temp AA:BB:CC:DD:EE:FF 42 --profile gs
  tingon play AA:BB:CC:DD:EE:FF on --profile m2 --mode 1
  tingon motor AA:BB:CC:DD:EE:FF 70 30 --profile m1
  tingon position AA:BB:CC:DD:EE:FF front --profile m2
  tingon custom-set AA:BB:CC:DD:EE:FF 32 1:10 2:20 --profile n2
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    scan.register(subparsers)
    status.register(subparsers)
    appliance.register(subparsers)
    intimate.register(subparsers)
    provision.register(subparsers)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
