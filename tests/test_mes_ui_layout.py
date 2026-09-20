"""Accessible DOM contract shared by the MES layout and controller."""
from html.parser import HTMLParser
from pathlib import Path
import unittest


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids = {}
        self.labels = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            if attrs["id"] in self.ids:
                raise AssertionError(f"Duplicate id: {attrs['id']}")
            self.ids[attrs["id"]] = (tag, attrs)
        if tag == "label" and "for" in attrs:
            self.labels.add(attrs["for"])


class MesLayoutTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.dom = Elements((root / "shiftlink/mes/web/index.html").read_text(encoding="utf-8"))

    def test_operator_can_find_labeled_replay_and_sensor_controls(self):
        for identifier in ("view-mode", "replay-run", "replay-sequence", "signal-select"):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, self.dom.ids)
                self.assertIn(identifier, self.dom.labels)
        for identifier in ("replay-refresh", "replay-play", "export-jsonl", "export-csv", "sensor-trends"):
            self.assertIn(identifier, self.dom.ids)

    def test_configuration_manager_can_find_configuration_controls(self):
        for identifier in ("config-file", "config-reason", "config-actor"):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, self.dom.ids)
        for identifier in ("config-validate", "config-apply", "config-errors", "config-message", "config-panel"):
            self.assertIn(identifier, self.dom.ids)

    def test_frequently_updated_map_is_not_a_live_announcement_region(self):
        self.assertNotEqual(self.dom.ids["line-map"][1].get("aria-live"), "polite")
        self.assertEqual(self.dom.ids["control-message"][1].get("aria-live"), "polite")

    def test_workspace_tabs_show_only_flow_initially(self):
        for key in ("flow", "detail", "history", "setup"):
            tab = self.dom.ids[f"tab-{key}"][1]
            panel = self.dom.ids[f"workspace-{key}"][1]
            self.assertEqual(tab["role"], "tab")
            self.assertEqual(tab["aria-controls"], f"workspace-{key}")
            self.assertEqual(tab["aria-selected"], str(key == "flow").lower())
            self.assertEqual(panel["role"], "tabpanel")
            self.assertEqual(panel["aria-labelledby"], f"tab-{key}")
            self.assertEqual("hidden" in panel, key != "flow")


if __name__ == "__main__":
    unittest.main()
