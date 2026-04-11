import unittest

import tingon_py
from tingon_py import (
    ApplianceState,
    DeviceProfile,
    IntimateStatus,
    TingonClient,
    TingonDevice,
    TingonProtocolError,
    TingonUnavailableError,
    TingonUnsupportedCapability,
    parse_advertisement,
)
from tingon_py.profiles import CAP_WATER_TEMP


class PublicApiTests(unittest.TestCase):
    def test_package_root_exports_curated_api(self):
        self.assertIs(tingon_py.TingonClient, TingonClient)
        self.assertIs(tingon_py.TingonDevice, TingonDevice)
        self.assertIs(tingon_py.ApplianceState, ApplianceState)
        self.assertIs(tingon_py.IntimateStatus, IntimateStatus)
        self.assertIs(tingon_py.TingonUnavailableError, TingonUnavailableError)
        self.assertIs(tingon_py.parse_advertisement, parse_advertisement)
        self.assertFalse(hasattr(tingon_py, "MockTingonDevice"))

    def test_unknown_profile_raises_typed_error(self):
        with self.assertRaises(TingonProtocolError):
            DeviceProfile.parse("not-a-real-profile")

    def test_client_capability_checks_raise_typed_error(self):
        client = TingonClient()
        client._device._profile = DeviceProfile.A1

        with self.assertRaises(TingonUnsupportedCapability):
            client.require_capability(CAP_WATER_TEMP)
