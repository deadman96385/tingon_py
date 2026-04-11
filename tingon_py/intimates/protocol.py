"""Intimate-device packet construction and notification parsing."""

from __future__ import annotations

from ..profiles import DeviceProfile


class IntimateProtocol:
    """Encode commands and parse notifications for TINGON intimate devices."""

    POSITION_BYTES: dict[str, str] = {
        "front": "60",
        "middle": "61",
        "back": "62",
        "front_middle": "63",
        "middle_back": "64",
        "all": "65",
    }

    N2_MODE_LABELS: dict[int, str] = {
        0: "vibration",
        1: "electric_shock",
        2: "vibration_and_electric_shock",
    }

    @staticmethod
    def pad(hex_str: str, width: int = 2) -> str:
        return hex_str.zfill(width)

    @staticmethod
    def normalize_slider(value: int) -> int:
        value = max(0, min(100, int(value)))
        if value == 0:
            return 0
        if value <= 17:
            return 5
        if value <= 35:
            return 6
        if value <= 51:
            return 7
        if value <= 68:
            return 8
        if value <= 86:
            return 9
        return 10

    @staticmethod
    def encode_play(play: bool, mode: int = 1) -> str:
        return "0A0100" if not play else f"0A01{IntimateProtocol.pad(format(mode, 'x'))}"

    @staticmethod
    def encode_mode(mode: int) -> str:
        return f"0A01{IntimateProtocol.pad(format(mode, 'x'))}"

    @staticmethod
    def encode_dual_output(motor1: int, motor2: int, *, quantized: bool = False) -> str:
        if quantized:
            left = IntimateProtocol.normalize_slider(motor1)
            right = IntimateProtocol.normalize_slider(motor2)
        else:
            left = max(0, min(10, int(motor1) // 10))
            right = max(0, min(10, int(motor2) // 10))
        return (
            f"0A0240{IntimateProtocol.pad(format(left, 'x'))}"
            f"41{IntimateProtocol.pad(format(right, 'x'))}"
        )

    @staticmethod
    def encode_single_output(motor1: int) -> str:
        value = max(0, min(10, int(motor1) // 10))
        return f"0A0240{IntimateProtocol.pad(format(value, 'x'))}"

    @staticmethod
    def encode_position_speed(position: str, speed: int) -> str:
        pos_byte = IntimateProtocol.POSITION_BYTES[position]
        value = max(0, min(10, int(speed) // 10))
        return f"0A0202{pos_byte}{IntimateProtocol.pad(format(value, 'x'))}"

    @staticmethod
    def clamp_range_point(value: int) -> int:
        return max(0, min(92, int(value)))

    @staticmethod
    def normalize_range(start: int, end: int) -> tuple[int, int]:
        left = IntimateProtocol.clamp_range_point(start)
        right = IntimateProtocol.clamp_range_point(end)
        if left > right:
            left, right = right, left
        return left, right

    @staticmethod
    def divide_range(start: int, end: int, segments: int = 3) -> list[tuple[int, int]]:
        left, right = IntimateProtocol.normalize_range(start, end)
        span = (right - left) / float(segments)
        ranges: list[tuple[int, int]] = []
        for index in range(segments):
            seg_start = int(left + index * span)
            seg_end = int(left + (index + 1) * span)
            ranges.append((seg_start, seg_end))
        return ranges

    @staticmethod
    def encode_custom_range(start: int, end: int) -> str:
        parts = []
        for base, (seg_start, seg_end) in zip((0x50, 0x52, 0x54), IntimateProtocol.divide_range(start, end)):
            parts.append(f"{base:02X}{seg_start:02X}{base + 1:02X}{seg_end:02X}")
        return f"0A060C{''.join(parts)}"

    @staticmethod
    def encode_query_custom(slot_id: int) -> str:
        return f"0B02{IntimateProtocol.pad(format(slot_id, 'x'))}"

    @staticmethod
    def encode_custom(slot_id: int, items: list[tuple[int, int]]) -> str:
        body = "".join(
            f"{IntimateProtocol.pad(format(int(mode), 'x'))}"
            f"{IntimateProtocol.pad(format(int(sec), 'x'))}"
            for mode, sec in items
        )
        return (
            f"0A04{IntimateProtocol.pad(format(slot_id, 'x'))}"
            f"{IntimateProtocol.pad(format(len(body) // 2, 'x'))}{body}"
        )

    @staticmethod
    def decode_custom_hex(hex_str: str) -> list[dict[str, int]]:
        items: list[dict[str, int]] = []
        for idx in range(0, len(hex_str), 4):
            chunk = hex_str[idx:idx + 4]
            if len(chunk) == 4:
                items.append({"mode": int(chunk[:2], 16), "sec": int(chunk[2:], 16)})
        return items

    @staticmethod
    def parse_notify(hex_str: str, profile: DeviceProfile) -> dict[str, int]:
        if not hex_str.startswith("02") or len(hex_str) < 4:
            return {}
        code = hex_str[2:4]
        if code == "40":
            if profile == DeviceProfile.M1 and len(hex_str) >= 10 and hex_str[6:8] == "41":
                return {
                    "motor1": int(hex_str[4:6], 16) * 10,
                    "motor2": int(hex_str[8:10], 16) * 10,
                }
            return {"motor1": int(hex_str[4:6], 16) * 10}
        if code == "41":
            return {"motor2": int(hex_str[4:6], 16) * 10}
        return {"mode": int(code, 16)}
