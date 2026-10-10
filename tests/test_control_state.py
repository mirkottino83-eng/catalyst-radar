import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from apply_control import ACTIONS, apply_issue
from control_state import load_control

class TestControls(unittest.TestCase):
    def test_owner_can_toggle_and_other_setting_persists(self):
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/"control.json"
            target.write_text('{"monitoring_enabled":true,"notifications_enabled":true}',encoding="utf-8")
            apply_issue("Catalyst Radar control: disable-monitoring","owner","owner",target)
            self.assertFalse(load_control(target)["monitoring_enabled"])
            self.assertTrue(load_control(target)["notifications_enabled"])
            apply_issue("Catalyst Radar control: disable-notifications","owner","owner",target)
            self.assertFalse(load_control(target)["notifications_enabled"])
            apply_issue("Catalyst Radar control: enable-monitoring","owner","owner",target)
            self.assertTrue(load_control(target)["monitoring_enabled"])
            self.assertFalse(load_control(target)["notifications_enabled"])

    def test_reject_non_owner_and_unknown_command(self):
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/"control.json"
            original='{"monitoring_enabled":true,"notifications_enabled":true}'
            target.write_text(original,encoding="utf-8")
            with self.assertRaises(PermissionError):
                apply_issue("Catalyst Radar control: disable-monitoring","attacker","owner",target)
            with self.assertRaises(ValueError):
                apply_issue("random comment","owner","owner",target)
            self.assertEqual(target.read_text(encoding="utf-8"),original)

    def test_invalid_data_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/"control.json"
            target.write_text('{"monitoring_enabled":"false","notifications_enabled":true}',encoding="utf-8")
            self.assertFalse(load_control(target)["monitoring_enabled"])
            with self.assertRaises(ValueError):
                apply_issue("Catalyst Radar control: enable-monitoring","owner","owner",target)

if __name__ == "__main__":
    unittest.main()
