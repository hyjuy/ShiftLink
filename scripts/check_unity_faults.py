"""Replay the saved Jetson configuration without changing the live MES."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shiftlink.mes.configuration import from_payload
from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine

def main():
    source = Path(sys.argv[1])
    out = Path(sys.argv[2])
    payload = json.loads(source.read_text(encoding="utf-8"))["config"]
    config = from_payload(payload)
    states = []
    for index, scenario in enumerate([None, *config.scenarios]):
        engine = MesEngine(Run(str(index), 42, datetime(2026, 10, 7, tzinfo=timezone.utc)), config)
        engine.start()
        if scenario: engine.set_scenario(scenario.scenario_id)
        for _ in range(3): engine.tick()
        state = engine.snapshot.as_dict()
        state["config_id"] = payload["config_id"]
        state["symptom_diagnostics"] = engine.symptom_diagnostics()
        states.append(state)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"config": payload, "states": states}, ensure_ascii=False, indent=2, default=lambda x: x.isoformat()), encoding="utf-8")
    print(f"Replayed {len(states)-1} scenarios plus normal: {out}")

if __name__ == "__main__": main()
