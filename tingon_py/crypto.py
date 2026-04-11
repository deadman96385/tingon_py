"""XOR encryption and checksum helpers for TINGON BLE provisioning."""

from __future__ import annotations

from random import randint


# XOR key dictionary used by the WiFi provisioning protocol.
KEY_DICTIONARY = [
    226, 103,  87, 132,  63,  66,  59,  88, 176, 241, 188, 194, 123, 228, 209,  42,
     19, 100, 195, 219, 189, 176, 198,  24, 138, 237, 115, 187,  61, 152,  67, 146,
    176, 179, 140,  48, 182, 156,  17, 161, 183,  69, 137, 207,  17,  23,  47, 211,
     70, 177, 182, 141, 226,   4,  93, 106, 105,  24, 226,   2,  50,  89, 176, 161,
     51, 178, 182, 145, 201, 170, 180, 158, 158, 113, 175,  58,  94, 208, 239, 254,
     88, 147,  56,  27, 161, 254,  17,  48, 108, 109, 230,   7, 134, 147, 109, 130,
     12,  54,  36,   0,  61,   0,  41, 219, 129, 210, 119, 239,  42, 201,  35, 244,
     80, 133,  85,   7, 146,  55,  24, 124, 199, 165,  95,  11, 231, 161,  95, 149,
    192, 141,  35,   3, 129, 126,  45,  82,  50, 254, 114, 183, 222,   1, 163,  73,
    121,  75,   4, 181, 179, 196, 195, 200, 176, 113, 144,  44, 110, 181,  15,  76,
     19,  24, 231, 190, 104, 161, 131, 175,  47, 194, 186,  64, 156,  88,  37,  26,
     80,  53,  90, 165,  78, 228, 119, 240, 253, 144, 192,  67, 109,  14,  38, 145,
    139, 187, 101, 250, 179, 191,  68, 217,  46, 165, 120, 198,  52, 175, 106,  95,
      3,  99,  78,  16, 226, 248, 217, 149, 230, 131,   1, 203,  57,  11,  49, 216,
     92, 242, 131, 189,  53,  76,  93, 152,  33,  18, 138, 156, 246,   1, 227,  81,
    167,  20,  19, 209, 253, 243,  65, 104,  80,   2,   3, 148, 129, 167, 114, 187,
]

DEFAULT_ENCRYPTION_KEY = "gwin0801"


class TingonEncryption:
    """XOR encryption/decryption for WiFi provisioning."""

    @staticmethod
    def xor_encrypt(plaintext: str, device_key: str) -> str:
        """XOR-encrypt a plaintext string, return lowercase hex."""
        data = plaintext.encode("utf-8")
        rand_byte = randint(0, 255)
        idx = int(device_key, 16) ^ rand_byte

        encrypted = bytearray(len(data))
        for i in range(len(data)):
            if idx >= len(KEY_DICTIONARY):
                idx = 0
            encrypted[i] = KEY_DICTIONARY[idx] ^ data[i]
            idx += 1

        return format(rand_byte, "02x") + encrypted.hex()

    @staticmethod
    def xor_decrypt(encrypted_hex: str, device_key: str) -> str:
        """XOR-decrypt an encrypted hex string, return plaintext."""
        rand_byte = int(encrypted_hex[:2], 16)
        ciphertext = bytes.fromhex(encrypted_hex[2:])
        idx = int(device_key, 16) ^ rand_byte

        decrypted = bytearray(len(ciphertext))
        for i in range(len(ciphertext)):
            if idx >= len(KEY_DICTIONARY):
                idx = 0
            decrypted[i] = KEY_DICTIONARY[idx] ^ ciphertext[i]
            idx += 1

        return decrypted.decode("utf-8", errors="replace")

    @staticmethod
    def extract_device_key(manufacturer_data: bytes) -> str:
        """Extract the 2-char hex encryption key from manufacturer advertisement data."""
        hex_str = manufacturer_data.hex()
        if len(hex_str) >= 8:
            return hex_str[-8:-6]
        return "41"  # default fallback

    @staticmethod
    def crc_xmodem(data: bytes) -> int:
        """CRC-XModem checksum."""
        crc = 0
        for byte in data:
            for bit in range(8):
                xor_flag = ((byte >> (7 - bit)) & 1) == 1
                crc_msb = ((crc >> 15) & 1) == 1
                crc <<= 1
                if xor_flag ^ crc_msb:
                    crc ^= 0x1021
        return crc & 0xFFFF
