"""Tests for the pure-function ``parse_advertisement`` HA entry point."""

from __future__ import annotations

import unittest

from tingon_py import DeviceProfile, parse_advertisement


def _mfr_blob(*, dev_type: int = 0, sub_version: int = 0) -> bytes:
    """Build a synthetic 20-byte manufacturer-data blob.

    Layout mirrors what ``parse_advertisement`` reads:
    * byte 10 — device type
    * byte 11 — sub-version (XiYu 0/2 → M2 quirk, FJB/FJB2 quirk)
    * bytes 13..18 — MAC from advertisement
    """
    buf = bytearray(20)
    buf[10] = dev_type
    buf[11] = sub_version
    buf[13:19] = bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF])
    return bytes(buf)


class ParseAdvertisementAppliance(unittest.TestCase):
    def test_missing_name_returns_none(self):
        self.assertIsNone(
            parse_advertisement(name=None, manufacturer_data=None)
        )
        self.assertIsNone(
            parse_advertisement(name="", manufacturer_data=None)
        )

    def test_fjb_dehumidifier_from_manufacturer_data(self):
        scanned = parse_advertisement(
            name="TINGON FJB",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=0, sub_version=0)},
        )
        self.assertIsNotNone(scanned)
        self.assertEqual(scanned.profile, DeviceProfile.FJB)

    def test_fjb_second_from_dev_type_zero_sub_two(self):
        # Non-XiYu name + dev_type=0 + sub_version=2 → 2nd-gen dehumidifier.
        scanned = parse_advertisement(
            name="TINGON Dehumidifier",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=0, sub_version=2)},
        )
        self.assertIsNotNone(scanned)
        self.assertEqual(scanned.profile, DeviceProfile.FJB2)

    def test_gs_water_heater(self):
        scanned = parse_advertisement(
            name="TINGON GS",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=1)},
        )
        self.assertEqual(scanned.profile, DeviceProfile.GS)

    def test_rj_water_heater(self):
        scanned = parse_advertisement(
            name="TINGON RJ",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=2)},
        )
        self.assertEqual(scanned.profile, DeviceProfile.RJ)

    def test_mac_pulled_from_adv_blob(self):
        scanned = parse_advertisement(
            name="TINGON GS",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=1)},
        )
        self.assertEqual(scanned.mac_from_adv, "AA:BB:CC:DD:EE:FF")


class ParseAdvertisementXiYu(unittest.TestCase):
    def test_xiyu_type_zero_is_m1(self):
        scanned = parse_advertisement(
            name="XiYu",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=0, sub_version=0)},
        )
        self.assertEqual(scanned.profile, DeviceProfile.M1)

    def test_xiyu_type_one_is_a1(self):
        scanned = parse_advertisement(
            name="XiYu",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=1)},
        )
        self.assertEqual(scanned.profile, DeviceProfile.A1)

    def test_xiyu_type_two_is_n1(self):
        scanned = parse_advertisement(
            name="XiYu",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=2)},
        )
        self.assertEqual(scanned.profile, DeviceProfile.N1)

    def test_xiyu_type_three_is_m2(self):
        scanned = parse_advertisement(
            name="XiYu",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=3)},
        )
        self.assertEqual(scanned.profile, DeviceProfile.M2)

    def test_xiyu_type_four_is_n2(self):
        scanned = parse_advertisement(
            name="XiYu",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=4)},
        )
        self.assertEqual(scanned.profile, DeviceProfile.N2)

    def test_xiyu_type_zero_sub_two_is_m2_quirk(self):
        scanned = parse_advertisement(
            name="XiYu",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=0, sub_version=2)},
        )
        self.assertEqual(scanned.profile, DeviceProfile.M2)


class ParseAdvertisementEdgeCases(unittest.TestCase):
    def test_name_filter_mismatch_returns_none(self):
        scanned = parse_advertisement(
            name="TINGON GS",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=1)},
            name_filter="m2",
        )
        self.assertIsNone(scanned)

    def test_name_filter_match_is_case_insensitive(self):
        scanned = parse_advertisement(
            name="TINGON GS",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=1)},
            name_filter="tingon",
        )
        self.assertIsNotNone(scanned)

    def test_short_mfr_blob_does_not_raise(self):
        # Blob shorter than index 11 — the parser should not explode.
        scanned = parse_advertisement(
            name="XiYu",
            manufacturer_data={0xFFFF: b"\x00\x01\x02"},
        )
        # Falls back to fuzzy name inference — XiYu alone isn't enough to
        # pin a profile, so the result may be ``None`` but must not raise.
        self.assertTrue(scanned is None or scanned.profile is None or scanned.profile in DeviceProfile)

    def test_empty_manufacturer_data_uses_fuzzy_name(self):
        scanned = parse_advertisement(
            name="TINGON M2",
            manufacturer_data=None,
        )
        self.assertIsNotNone(scanned)
        self.assertEqual(scanned.profile, DeviceProfile.M2)

    def test_unknown_name_and_empty_data_returns_device_without_profile(self):
        scanned = parse_advertisement(
            name="not-a-tingon",
            manufacturer_data=None,
        )
        # Fuzzy parse returns ``None`` on a totally unknown name, so the
        # ScannedDevice itself exists but without a profile.
        self.assertIsNotNone(scanned)
        self.assertIsNone(scanned.profile)

    def test_rssi_and_address_are_preserved(self):
        scanned = parse_advertisement(
            name="TINGON GS",
            manufacturer_data={0xFFFF: _mfr_blob(dev_type=1)},
            rssi=-42,
            address="11:22:33:44:55:66",
        )
        self.assertEqual(scanned.rssi, -42)
        self.assertEqual(scanned.address, "11:22:33:44:55:66")


if __name__ == "__main__":
    unittest.main()
