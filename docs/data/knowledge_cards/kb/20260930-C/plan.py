"""Fixed batch C slots. The seed fixes the plan, not generated prose."""
import json
from pathlib import Path

HERE = Path(__file__).parent
SEED = 20260930
ASSIGNMENTS = [(eq, "T2", None) for eq in ["HPU"] * 3 + ["CV"] * 3 + ["RT"] * 2 + ["GR"] * 2]
ASSIGNMENTS += [
    ("HPU", "T6", "maintenance_restart"),
    ("GR", "T6", "maintenance_restart"),
    ("CV", "T6", "maintenance_restart"),
    ("RT", "T6", "maintenance_restart"),
    ("CV", "T6", "abnormal_stop_restart"),
    ("GR", "T6", "abnormal_stop_restart"),
    ("RT", "T6", "abnormal_stop_restart"),
    ("HPU", "T6", "normal_stop_restart"),
    ("GR", "T6", "normal_stop_restart"),
]


def build():
    return {"batch_id": "KB-20260930-C", "seed": SEED, "generator": "plan.py",
            "slots": [{"slot": f"S{i:02d}", "card_id": f"K-{1200+i}",
                       "equipment": eq, "tacit_type": kind,
                       **({"restart_type": restart} if restart else {})}
                      for i, (eq, kind, restart) in enumerate(ASSIGNMENTS, 1)]}


if __name__ == "__main__":
    (HERE / "plan.json").write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n",
                                  encoding="utf-8", newline="\n")
    print("batch C: T2 10 + T6 9 slots; seed=20260930")
