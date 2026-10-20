"""Training source ablation must keep preprocessing, budgets, and test sealing."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.mes_training_source import (check_sources, matched_samples,
                                        normal_background, evaluate)


def entry(offset=0, count=120):
    return {"X": np.arange(count * 2, dtype=float).reshape(count, 2) + offset,
            "keys": [("run", i + 8) for i in range(count)],
            "healthy_windows": np.array([True] * count)}


class TrainingSourceTests(unittest.TestCase):
    def test_matched_sampling_is_deterministic_equal_and_keeps_order(self):
        reference, aligned = {"EQ": entry()}, {"EQ": entry(3, 150)}
        samples, diagnostic = matched_samples(reference, aligned)
        self.assertEqual(len(samples["reference"]["EQ"]), 120)
        self.assertEqual(len(samples["aligned"]["EQ"]), 120)
        again, repeated = matched_samples(reference, aligned)
        np.testing.assert_array_equal(samples["aligned"]["EQ"], again["aligned"]["EQ"])
        self.assertEqual(diagnostic, repeated)
        self.assertEqual(diagnostic["EQ"]["aligned"]["selected_keys"],
                         sorted(diagnostic["EQ"]["aligned"]["selected_keys"]))
        self.assertGreater(diagnostic["EQ"]["aligned"]["selected_keys"][-1][1], 120)

    def test_only_all_healthy_windows_are_selected(self):
        a, b = {"EQ": entry(count=150)}, {"EQ": entry(count=150)}
        a["EQ"]["healthy_windows"][:20] = False
        samples, diagnostic = matched_samples(a, b)
        self.assertEqual(len(samples["reference"]["EQ"]), 130)
        self.assertGreaterEqual(diagnostic["EQ"]["reference"]["selected_keys"][0][1], 28)

    def test_bad_count_dimension_and_nonfinite_inputs_fail(self):
        with self.assertRaisesRegex(ValueError, "100"):
            matched_samples({"EQ": entry(count=99)}, {"EQ": entry()})
        bad = entry()
        bad["X"] = bad["X"][:, :1]
        with self.assertRaisesRegex(ValueError, "dimension"):
            matched_samples({"EQ": entry()}, {"EQ": bad})
        bad = entry()
        bad["X"][0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            matched_samples({"EQ": entry()}, {"EQ": bad})
        with self.assertRaisesRegex(ValueError, "equipment"):
            matched_samples({"EQ": entry()}, {"OTHER": entry()})

    def test_sources_reject_overlap_and_wrong_generator(self):
        def manifest(seed, profile="independent"):
            return {"profile": profile, "generator_version": 7, "response_scale": 1,
                    "runs": [{"run_id": str(seed), "seed": seed, "split": "train"}]}
        original, fresh = manifest(1, "pattern"), manifest(20)
        check_sources(original, fresh)
        with self.assertRaisesRegex(ValueError, "overlap"):
            check_sources(original, manifest(1))
        fresh["generator_version"] = 6
        with self.assertRaisesRegex(ValueError, "v7"):
            check_sources(original, fresh)

    def test_background_excludes_off_episodes_and_windows_after_fault(self):
        rows = []
        for i in range(1, 25):
            faults = ([{"intensity": 0}] if i == 10 else [])
            rows.append(({"sequence": i}, {"faults": faults}))
        runs = {"r": rows}
        alerts = {("r", i): {"EQ"} for i in range(1, 25)}
        result = normal_background(runs, alerts, {"EQ": {"keys": [("r", i) for i in range(8, 25)]}})
        self.assertEqual(result["healthy_window_alert_equipment_frames"], 9)
        self.assertEqual(result["prefault_alert_equipment_frames"], 2)
        self.assertEqual(result["by_equipment"]["EQ"], 9)

    def test_tiny_end_to_end_never_reads_poisoned_test_rows(self):
        from scripts.build_mes_fault_dataset import build_dataset
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("pattern", "full", "weak")]
            for path, profile, seed, scale in ((paths[0], "pattern", 31, 1),
                                               (paths[1], "independent", 1371, 1),
                                               (paths[2], "independent", 1371, .2)):
                manifest = build_dataset(path, runs_per_split=1, ticks=120,
                                         seed=seed, hazard=0, profile=profile,
                                         response_scale=scale)
                count = sum(r["frames"] for r in manifest["runs"] if r["split"] != "test")
                for field in ("feature_file", "private_label_file"):
                    target = path / manifest[field]
                    with target.open(encoding="utf-8") as source:
                        prefix = [source.readline() for _ in range(count)]
                    target.write_text("".join(prefix) + "UNREAD TEST ROW\n", encoding="utf-8")
            reference = {"diagnostics": {}}
            from scripts.evaluate_mes_fault_models import fit_normal
            from scripts.mes_validation_candidate_review import load_train_validation
            config, splits = load_train_validation(paths[0])
            specs, stats = fit_normal(splits["train"], config)
            # Same coverage rule as D12; no validation rows choose these masks.
            from scripts.evaluate_mes_fault_models import valid_values
            valid = [valid_values(f, specs) for rows in splits["train"].values() for f, l in rows]
            for eq in config.equipment:
                reference["diagnostics"][eq.equipment_id] = {"selected_channels": [
                    s.signal for s in eq.signals
                    if (eq.equipment_id, s.signal) in stats and
                    sum((eq.equipment_id, s.signal) in v for v in valid) / len(valid) >= .95]}
            ref_path = Path(directory) / "reference.json"
            ref_path.write_text(json.dumps(reference), encoding="utf-8")
            result = evaluate(*paths, ref_path)
            self.assertEqual(result["test_rows_read"], 0)
            self.assertFalse(result["final_test_evaluated"])
            self.assertEqual(result["preprocessing_refitted"], False)
            self.assertEqual(result["paired_background_identical"], True)
            self.assertEqual(result["arms"]["full"]["frames"], 120)
            self.assertEqual(len(result["training"]), 10)
            json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
