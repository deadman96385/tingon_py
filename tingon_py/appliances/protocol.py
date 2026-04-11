"""Appliance packet construction and parsing (TLV protocol)."""

from __future__ import annotations

import json
import time
from typing import Optional


class TingonProtocol:
    """Encode commands and decode responses for the TINGON appliance BLE protocol."""

    @staticmethod
    def _pad(hex_str: str, width: int) -> str:
        return hex_str.zfill(width)

    @staticmethod
    def _get_spec_encoding(spec_id: int) -> tuple[str, int]:
        """Return (data_type, value_length) for a given spec ID."""
        if spec_id in (1, 3, 4, 17) or (spec_id in range(102, 112) and spec_id not in (104, 105, 106)):
            return ("01", 1)
        if spec_id in (5, 27, 105, 106) or spec_id in range(10, 16):
            return ("02", 1)
        if spec_id in (6, 7):
            return ("02", 4)
        if spec_id in (8, 9):
            return ("04", 1)
        if spec_id in (16, 104):
            return ("05", 1)
        if spec_id in (2, 18):
            return ("00", 0)  # variable
        # Fallback: treat as 1-byte int
        return ("02", 1)

    @staticmethod
    def encode_command(spec_id: int, value) -> str:
        """Encode a single-property command as a hex string."""
        data_type, val_len = TingonProtocol._get_spec_encoding(spec_id)
        spec_hex = TingonProtocol._pad(format(spec_id, "x"), 4)

        if data_type == "00":
            # Raw/variable: value is already a hex string
            val_hex = str(value)
            length_hex = TingonProtocol._pad(format(len(val_hex) // 2, "x"), 4)
        else:
            val_hex = TingonProtocol._pad(format(int(value), "x"), val_len * 2)
            length_hex = TingonProtocol._pad(format(val_len, "x"), 4)

        return f"01{spec_hex}{data_type}{length_hex}{val_hex}"

    @staticmethod
    def encode_multi_command(specs: dict) -> str:
        """Encode a multi-property command. specs = {spec_id: value, ...}"""
        items = list(specs.items())
        if len(items) == 1:
            return TingonProtocol.encode_command(items[0][0], items[0][1])

        count = TingonProtocol._pad(format(len(items), "x"), 2)
        parts = []
        for _i, (spec_id, value) in enumerate(items):
            data_type, val_len = TingonProtocol._get_spec_encoding(spec_id)
            spec_hex = TingonProtocol._pad(format(spec_id, "x"), 4)

            if data_type == "00":
                val_hex = str(value)
                length_hex = TingonProtocol._pad(format(len(val_hex) // 2, "x"), 4)
            else:
                val_hex = TingonProtocol._pad(format(int(value), "x"), val_len * 2)
                length_hex = TingonProtocol._pad(format(val_len, "x"), 4)

            parts.append(f"{spec_hex}{data_type}{length_hex}{val_hex}")

        return count + "".join(parts)

    @staticmethod
    def build_query(spec_ids: list[int]) -> bytes:
        """Build a query JSON payload for the cc service."""
        payload = {
            "time": int(time.time() * 1000),
            "data": spec_ids,
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def parse_response(hex_str: str, signed_specs: Optional[set[int]] = None) -> dict:
        """Parse a TLV hex response into {spec_id: value}."""
        if not hex_str or len(hex_str) < 4:
            return {}

        result: dict[int, object] = {}
        pos = 2  # skip header (2 hex chars = 1 byte)

        while pos + 10 <= len(hex_str):  # need at least specId(4) + type(2) + length(4)
            spec_id = int(hex_str[pos:pos + 4], 16)
            data_type = hex_str[pos + 4:pos + 6]
            data_len = int(hex_str[pos + 6:pos + 10], 16)
            pos += 10

            data_end = pos + data_len * 2
            if data_end > len(hex_str):
                break

            data_hex = hex_str[pos:data_end]
            pos = data_end

            if data_type == "00":
                # Raw value (timer data) - keep as hex string
                result[spec_id] = data_hex
            else:
                raw_val = int(data_hex, 16) if data_hex else 0
                if signed_specs and spec_id in signed_specs:
                    raw_val = TingonProtocol.signed_value(raw_val, data_len * 8)
                result[spec_id] = raw_val

        return result

    @staticmethod
    def signed_value(raw: int, bits: int = 16) -> int:
        """Convert unsigned int to signed using two's complement."""
        if raw >= (1 << (bits - 1)):
            raw -= (1 << bits)
        return raw

    @staticmethod
    def hex_to_bytes(hex_str: str) -> bytes:
        """Convert hex string to bytes."""
        hex_str = hex_str.replace(" ", "")
        return bytes.fromhex(hex_str)

    @staticmethod
    def bytes_to_hex(data: bytes) -> str:
        """Convert bytes to uppercase hex string."""
        return data.hex().upper()
