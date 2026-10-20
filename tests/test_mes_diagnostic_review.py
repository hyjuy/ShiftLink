import copy
import unittest
from types import SimpleNamespace

from tests.test_mes_diagnostic_contract import frame
from scripts.mes_diagnostic_review import fit_baselines, pair_audit, review_signed


class DiagnosticReviewTests(unittest.TestCase):
    def test_fit_uses_only_complete_normal_windows_and_current_channels(self):
        signal = SimpleNamespace(signal="x", unit="A", normal_min=-10, normal_max=10)
        config = SimpleNamespace(equipment=[SimpleNamespace(equipment_id="S", active=True, signals=[signal])])
        rows = [(frame(i, {"S": (i%11)/10}), {"faults": []}) for i in range(1, 131)]
        rows[-1][1]["faults"] = [{"equipment_id": "S", "intensity": 1}]
        rows[-1][0]["measurements"][0]["value"] = 9999
        bundle, robust, diagnostic = fit_baselines({"r": rows}, config)
        self.assertEqual(diagnostic["S"]["healthy_windows"], 122)
        self.assertLess(bundle["stats"]["S", "x"][0], 1)
        self.assertEqual(bundle["masks"], {"S": [("S", "x")]})
        self.assertEqual(set(bundle["models"]["isolation_forest"]), {"S"})

    def test_pair_checks_schedule_but_reports_postfault_measurement_divergence(self):
        fault = {"id": "f", "equipment_id": "S", "intensity": 1}
        full = {"r": [(frame(1, {"S": 0}), {"faults": []}),
                      (frame(2, {"S": 1}), {"faults": [fault]}),
                      (frame(3, {"S": 2}), {"faults": []})]}
        weak = copy.deepcopy(full)
        weak["r"][-1][0]["measurements"][0]["value"] = .2
        self.assertEqual(pair_audit(full, weak)["label_free_measurement_differences"], 1)
        weak["r"][0][0]["measurements"][0]["value"] = .2
        with self.assertRaisesRegex(ValueError, "prefault"):
            pair_audit(full, weak)

    def test_no_improvement_cannot_promote_an_identical_candidate(self):
        runs = {"r": [(frame(i, {"S": 0}), {"faults": []}) for i in range(1, 3)]}
        alerts = {("r", i): set() for i in range(1, 3)}
        result = review_signed(runs, alerts, alerts, [])
        self.assertIn("no strict improvement", result["failures"])


if __name__ == "__main__":
    unittest.main()
