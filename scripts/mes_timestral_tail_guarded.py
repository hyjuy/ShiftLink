"""Separate stage5 notification candidate; no detector or runtime integration."""
from datetime import datetime

import numpy as np

from scripts import mes_timestral_evidence as evidence


def notifications(data, display, original, params):
    keys, equipment = evidence.validate(data, display)
    assert set(original) == set(display)
    z, stable = 2, 2
    normal_count, cooldown, quiet_off = (params[k] for k in ('normal_count', 'cooldown', 'quiet_off'))
    assert 1 <= normal_count <= 12 and cooldown >= 1 and quiet_off >= 1
    assert np.shape(data['signed_z']) == (len(keys), len(data['channels']))
    signatures, magnitudes = [], []
    for eq in equipment:
        ix = np.array([j for j, c in enumerate(data['channels']) if c[0] == eq])
        assert len(ix)
        values = data['signed_z'][:, ix]
        absolute = np.where(np.isfinite(values), np.abs(values), -np.inf)
        dom = np.argmax(absolute, axis=1)
        signed = values[np.arange(len(keys)), dom]
        signatures.append(ix[dom] * 2 + (signed < 0))
        magnitudes.append(absolute[np.arange(len(keys)), dom])
    signatures, magnitudes = np.array(signatures).T, np.array(magnitudes).T
    state = {}
    last = None
    out = {}
    for i, (key, observation) in enumerate(zip(keys, data['observations'])):
        at = datetime.fromisoformat(observation['at'])
        if (data['resets'][i] or last is None or key[0] != last[0][0]
                or key[1] != last[0][1] + 1 or (at - last[1]).total_seconds() != 1
                or observation['inactive']):
            state = {}
        emitted = set()
        if not observation['inactive']:
            for j, eq in enumerate(equipment):
                s = state.setdefault(eq, dict(seen=set(), normal=0, off=0, armed=False,
                                              sent=None, on=False, dominant=None, stable=0))
                valid = np.isfinite(data['raw_z'][i, j]) and np.isfinite(data['ratio'][i, j])
                normal = valid and data['raw_z'][i, j] <= 1.5
                s['normal'] = min(s['normal'] + 1, normal_count + 1) if normal else 0
                if s['normal'] == normal_count:
                    s['armed'] = True
                    s['seen'].clear()
                s['off'] = s['off'] + 1 if eq not in original[key] else 0
                if s['off'] == quiet_off:
                    s['armed'] = True
                    s['seen'].clear()
                sig = int(signatures[i, j]) if magnitudes[i, j] >= z and valid else None
                s['stable'] = min(s['stable'] + 1, stable) if sig is not None and sig == s['dominant'] else int(sig is not None)
                s['dominant'] = sig
                current = eq in display[key]
                novel = sig is not None and s['stable'] >= stable and sig not in s['seen']
                candidate = current and not s['on']
                if candidate and (s['sent'] is None or s['armed'] or novel or (at - s['sent']).total_seconds() >= cooldown):
                    emitted.add(eq)
                    s['sent'] = at
                    s['armed'] = False
                    if sig is not None:
                        s['seen'].add(sig)
                # Learn only the first emerging symptom; keep later symptoms novel.
                if not s['seen'] and eq not in original[key] and sig is not None and s['sent'] is not None and (at - s['sent']).total_seconds() <= 8:
                    s['seen'].add(sig)
                s['on'] = current
        out[key] = emitted
        last = key, at
    return out
