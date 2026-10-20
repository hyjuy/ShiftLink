"""Disjoint diagnostic context must reconcile with the untouched strict score."""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from scripts.mes_diagnostic_contract import (classify_alarms, compare_pair,
                                            predict_signed_ewma)


AT = datetime(2026, 10, 21, tzinfo=timezone.utc)


def frame(sequence, values, quality="good"):
    at = (AT + timedelta(seconds=sequence)).isoformat()
    return {"sequence": sequence, "simulated_at": at, "line_mode": "running",
            "equipment_operating_states": [], "measurements": [
                {"equipment_id": eq, "signal": "x", "value": value,
                 "unit": "A", "quality": quality, "observed_at": at}
                for eq, value in values.items()]}


def specs(*equipment):
    return {(eq, "x"): SimpleNamespace(unit="A") for eq in equipment}


def fault(eq="S", intensity=1, end=4):
    return {"id": "f", "equipment_id": eq, "intensity": intensity,
            "start": 1, "end": end, "pattern_id": "fixture"}


class DiagnosticContractTests(unittest.TestCase):
    def test_source_response_off_recovery_and_background_are_disjoint(self):
        source = [({"S": 5, "D": 2}, [fault()]),
                  ({"S": 0, "D": 0}, [fault(intensity=0)]),
                  ({"S": 0, "D": 0}, []),
                  ({"S": 0, "D": 0}, []),
                  ({"S": 0, "D": 0}, [])]
        sequences = [1, 2, 4, 12, 13]
        runs = {"r": [(frame(i, values), {"faults": labels})
                       for i, (values, labels) in zip(sequences, source)]}
        clean = {"r": [(frame(i, {"S": 0, "D": 0}), label)
                        for i, (_, label) in zip(sequences, runs["r"])]}
        alerts = {("r", i): {"S", "D"} for i in sequences}
        summary, records = classify_alarms(runs, alerts, clean, specs("S", "D"), {})
        labels = {(r["sequence"], r["equipment_id"]): r["context"] for r in records}
        self.assertEqual(labels[1, "S"], "source_active")
        self.assertEqual(labels[1, "D"], "other_source_response")
        self.assertEqual(labels[2, "S"], "episode_off")
        self.assertEqual(labels[4, "S"], "local_post_end")
        self.assertEqual(labels[12, "S"], "unchanged_background")
        self.assertEqual(summary["alarm_equipment_seconds"], 26)
        self.assertEqual(sum(v["alarm_equipment_seconds"] for v in summary["contexts"].values()), 26)
        from scripts.evaluate_mes_fault_models import score
        strict = score(runs, alerts)
        self.assertEqual(summary["strict_wrong_equipment_seconds"], strict["wrong_alert_equipment_seconds"])
        self.assertEqual(summary["strict_wrong_union_seconds"], strict["wrong_alert_seconds"])

    def test_valid_set_mismatch_is_not_silently_equal_and_zero_source_is_not_active(self):
        f = frame(1, {"S": 0, "D": 0})
        c = frame(1, {"S": 0})
        runs = {"r": [(f, {"faults": [fault(intensity=0)]})]}
        summary, records = classify_alarms(runs, {("r", 1): {"S", "D"}},
                                          {"r": [(c, {"faults": []})]}, specs("S", "D"), {})
        self.assertEqual({r["equipment_id"]: r["context"] for r in records},
                         {"S": "episode_off", "D": "incomparable"})
        self.assertEqual(summary["source_positive_equipment_seconds"], 0)

    def test_numeric_pair_uses_keys_not_measurement_order_or_metadata(self):
        f, c = frame(1, {"A": 0, "B": 2}), frame(1, {"B": 2, "A": 0})
        result = compare_pair(f, c, specs("A", "B"), {})
        self.assertFalse(result["A"]["changed"])
        self.assertFalse(result["B"]["changed"])
        c["measurements"][0]["value"] = 2.000001
        self.assertTrue(compare_pair(f, c, specs("A", "B"), {})["B"]["changed"])
        c["measurements"][0]["quality"] = "bad"
        self.assertFalse(compare_pair(f, c, specs("A", "B"), {})["B"]["comparable"])

    def test_incomparable_source_positive_is_kept_in_cross_tab(self):
        f, c = frame(1, {"S": 0}, "bad"), frame(1, {"S": 0})
        result, _ = classify_alarms({"r": [(f, {"faults": [fault()]})]},
                                    {("r", 1): {"S"}}, {"r": [(c, {})]}, specs("S"), {})
        self.assertEqual(result["contexts"]["incomparable"]["source_positive_equipment_seconds"], 1)
        self.assertEqual(result["strict_wrong_equipment_seconds"], 0)

    def test_signed_subset_and_opposite_direction_delay_counterexample(self):
        from scripts.evaluate_mes_fault_models import predict_ewma
        values = [6.25, -4, -4, -4, -4]
        runs = {"r": [(frame(i, {"S": v}), {"faults": []}) for i, v in enumerate(values, 1)]}
        stats = {("S", "x"): (0, 1)}
        original = predict_ewma(runs, specs("S"), stats, 3)
        candidate = predict_signed_ewma(runs, specs("S"), stats, 3)
        self.assertIn("S", original["r", 2])
        self.assertNotIn("S", candidate["r", 2])
        self.assertIn("S", candidate["r", 5])
        self.assertTrue(all(candidate[key] <= original[key] for key in candidate))

    def test_signed_does_not_use_labels_future_and_resets_between_runs(self):
        runs = {"r": [(frame(i, {"S": 8}), {"faults": []}) for i in range(1, 4)]}
        stats = {("S", "x"): (0, 1)}
        first = predict_signed_ewma(runs, specs("S"), stats, 3)
        altered = copy.deepcopy(runs)
        for _, label in altered["r"]:
            label["faults"] = [fault()]
        altered["r"][-1][0]["measurements"][0]["value"] = -100
        after = predict_signed_ewma(altered, specs("S"), stats, 3)
        self.assertEqual(first["r", 1], after["r", 1])
        self.assertEqual(first["r", 2], after["r", 2])
        self.assertEqual(first, predict_signed_ewma({"r": runs["r"]}, specs("S"), stats, 3))


if __name__ == "__main__":
    unittest.main()
