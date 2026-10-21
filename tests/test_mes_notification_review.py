import copy
import unittest

from scripts.mes_notification_review import group_notifications, review_notifications
from tests.test_mes_diagnostic_contract import frame, specs, fault


class NotificationTests(unittest.TestCase):
    def group(self, active, frames=None):
        frames = frames or [frame(i, {"S": 0}) for i in range(1, len(active)+1)]
        alerts = {("r", f["sequence"]): ({"S"} if on else set()) for f, on in zip(frames, active)}
        before = copy.deepcopy(alerts)
        result = group_notifications({"r": frames}, alerts, specs("S"), {"S": [("S", "x")]})
        self.assertEqual(alerts, before)
        return frames, alerts, result

    def test_two_quiet_seconds_merge_three_close(self):
        _, _, result = self.group([1, 0, 0, 1, 0, 0, 0, 1])
        self.assertEqual([r["sequence"] for r in result["notifications"]], [1, 8])
        self.assertEqual(result["eligible_short_gap_restarts"], 1)
        self.assertIn("resolved", [r["reason"] for r in result["closures"]])

    def test_unknown_is_not_quiet_and_continuous_partial_positive_does_not_storm(self):
        frames = [frame(i, {"S": 0}, "bad" if i in (2, 3, 4) else "good") for i in range(1, 6)]
        _, _, result = self.group([1, 1, 1, 0, 1], frames)
        self.assertEqual([r["sequence"] for r in result["notifications"]], [1, 5])
        self.assertEqual([r["reason"] for r in result["closures"]], ["unknown", "run_end"])

    def test_gap_and_mode_interrupt(self):
        frames = [frame(i, {"S": 0}) for i in (1, 3, 4, 5)]
        frames[2]["line_mode"] = "paused"
        _, _, result = self.group([1, 1, 0, 1], frames)
        self.assertEqual([r["sequence"] for r in result["notifications"]], [1, 3, 5])
        self.assertEqual([r["reason"] for r in result["closures"]], ["gap", "inactive", "run_end"])

    def test_missing_other_equipment_cannot_interrupt_local_incident(self):
        frames = [frame(i, {"S": 0, **({"D": 0} if i != 2 else {})}) for i in range(1, 5)]
        alerts = {("r", i): {"S"} if i in (1, 4) else set() for i in range(1, 5)}
        result = group_notifications({"r": frames}, alerts, specs("S", "D"),
                                     {"S": [("S", "x")], "D": [("D", "x")]})
        self.assertEqual([r["sequence"] for r in result["notifications"]], [1])

    def test_later_fault_notification_must_not_be_hidden_by_open_incident(self):
        frames, alerts, grouped = self.group([1, 0, 1])
        labels = [{"faults": [dict(fault(), id="first")]}, {"faults": []},
                  {"faults": [dict(fault(), id="second", start=3, end=5)]}]
        result = review_notifications({"r": list(zip(frames, labels))}, alerts, grouped)
        self.assertIn("individual source notification lost or delayed", result["failures"])
        self.assertEqual(result["lost_or_changed_events"][0]["fault_id"], "second")

    def test_same_episode_restarts_reduce_notifications_with_exact_event_timestamp(self):
        frames, alerts, grouped = self.group([1, 0, 1])
        runs = {"r": [(f, {"faults": [fault()]}) for f in frames]}
        result = review_notifications(runs, alerts, grouped)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["unmatched_notifications"], 0)
        self.assertEqual(result["removed_same_episode_duplicates"], 1)

    def test_trace_closes_at_run_end_and_corruption_is_rejected(self):
        frames, alerts, grouped = self.group([1, 0, 1])
        self.assertEqual(grouped["closures"][-1]["reason"], "run_end")
        grouped["transitions"] = []
        runs = {"r": [(f, {"faults": [fault()]}) for f in frames]}
        self.assertIn("invalid incident transition trace", review_notifications(runs, alerts, grouped)["failures"])

    def test_leading_false_alarm_cannot_hide_first_source_notification(self):
        frames, alerts, grouped = self.group([1, 0, 1])
        runs = {"r": [(f, {"faults": [dict(fault(), start=3)] if i == 3 else []})
                      for i, f in enumerate(frames, 1)]}
        result = review_notifications(runs, alerts, grouped)
        self.assertIn("individual source notification lost or delayed", result["failures"])

    def test_gap_reopening_cannot_increase_notifications_unnoticed(self):
        frames, alerts, grouped = self.group([1, 1], [frame(i, {"S": 0}) for i in (1, 3)])
        result = review_notifications({"r": [(f, {"faults": []}) for f in frames]}, alerts, grouped)
        self.assertIn("per-run equipment notifications increased", result["failures"])
        grouped["counts"][0]["notifications"] = 0
        self.assertIn("notification counts differ from trace",
                      review_notifications({"r": [(f, {"faults": []}) for f in frames]}, alerts, grouped)["failures"])

    def test_invalid_equipment_and_inactive_raw_positive_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "mask"):
            group_notifications({"r": [frame(1, {"S": 0})]}, {("r", 1): {"D"}}, specs("S"), {"S": [("S", "x")]})
        f = frame(1, {"S": 0})
        f["line_mode"] = "stopped"
        with self.assertRaisesRegex(ValueError, "inactive"):
            self.group([1], [f])


if __name__ == "__main__":
    unittest.main()
