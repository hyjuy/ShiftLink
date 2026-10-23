"""Shared measurement metadata only; no process or fault equations."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANUAL = {'fluid_viscosity', 'gr_oil_water_content', 'hpu_return_submergence', 'hpu_suction_head'}


@lru_cache(maxsize=1)
def metadata():
    value = json.loads((ROOT / 'docs/data/reference/mes-causal-v8-signals.json').read_text(encoding='utf-8'))
    value.update(schema='causal-sensor-mes-v8', manual_sample_interval_seconds=30, lift_events='unavailable')
    value['config_id'] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    return value


@lru_cache(maxsize=1)
def signals():
    return {(e['equipment_id'], s['signal']): s for e in metadata()['equipment'] for s in e['signals']}


def units(value):
    low, high = value['normal_min'], value['normal_max']
    center = ((low or 0) + (high or 0)) / 2
    return center, max((high or 0) - (low or 0), abs(center) * .02, .01)
