"""Bounded incremental execution of frozen v14c, without a neural runtime.

One instance consumes one ordered source stream. Restart/run/gap requires the
same 64 preceding running frames as the research reference. Nothing is sent to
MES or PDA. The original batch implementation remains the regression oracle.
"""
from collections import deque
from datetime import datetime
import math

import numpy as np
from scripts.mes_causal_schema import metadata, signals


class _Notices:
    """The v11 source-aware latch, retained between frames."""
    def __init__(self, indexes, channels, patience):
        self.indexes = indexes
        self.patience = patience
        self.on = np.zeros(len(indexes), bool)
        self.high = np.zeros(len(indexes), int)
        self.low = self.high.copy()
        self.process_sources = np.zeros((len(indexes), channels), bool)
        self.flat_sources = self.process_sources.copy()

    def step(self, process, flat, known, flat_known, reset, hold):
        if reset:
            self.on[:] = False
            self.high[:] = self.low[:] = 0
            self.process_sources[:] = self.flat_sources[:] = False
        if hold:
            self.high[:] = self.low[:] = 0
            return np.zeros(len(self.indexes), bool)
        result = np.zeros(len(self.indexes), bool)
        for j, ix in enumerate(self.indexes):
            p, f = process[ix], flat[ix]
            # Saturation preserves decisions without unbounded counter growth.
            self.high[j] = min(self.high[j] + 1, self.patience) if p.any() else 0
            observed = known[self.process_sources[j]].all() and flat_known[self.flat_sources[j]].all()
            self.low[j] = 0 if p.any() or f.any() or not observed else min(self.low[j] + 1, 5)
            if self.low[j] >= 5:
                self.on[j] = False
                self.process_sources[j] = self.flat_sources[j] = False
            if not self.on[j] and (self.high[j] >= self.patience or f.any()):
                result[j] = self.on[j] = True
            if self.on[j]:
                self.process_sources[j, ix] |= p
                self.flat_sources[j, ix] |= f
        return result


class OnlineDetector:
    """Consume canonical frames; return first-notice equipment IDs only.

    Rejected contracts raise before mutation; duplicate/old frames return an
    empty set with accepted=False. Bad/stale individual measurements are NaN,
    never healthy evidence. State is process-local, not a durable alarm journal.
    """
    def __init__(self, settings):
        base = settings['base']
        specs = signals()
        self.channels = [tuple(c) for c in base['channels']]
        if not self.channels or len(set(self.channels)) != len(self.channels) or any(c not in specs for c in self.channels):
            raise ValueError('unique schema channels required')
        n = len(self.channels)
        stats = {(e, s): (m, a) for e, s, m, a in base['stats']}
        try:
            self.center, self.scale = np.asarray([stats[c] for c in self.channels], float).T
        except (KeyError, ValueError) as exc:
            raise ValueError('channel statistics required') from exc
        self.variable = np.asarray(base['variable'], bool).copy()
        self.tolerance = np.asarray(base['tolerance'], float).copy()
        self.limits = np.asarray(settings['limits'], float).copy()
        self.equipment = sorted({e for e, _ in self.channels})
        self.thermal_limits = np.asarray(settings['thermal_rise_limits'], float).copy()
        for name, value, size, positive in (
            ('variable', self.variable, n, False), ('tolerance', self.tolerance, n, False),
            ('limits', self.limits, n, True), ('thermal', self.thermal_limits, len(self.equipment), True),
            ('scale', self.scale, n, True), ('center', self.center, n, False)):
            if value.shape != (size,) or not np.isfinite(value).all() or (positive and np.any(value <= 0)):
                raise ValueError('finite correctly shaped ' + name + ' required')
        if np.any(self.tolerance < 0):
            raise ValueError('nonnegative tolerance required')
        # The legacy settings key identifies the frozen statistical ablation.
        params = base['selected']['no_timestral']['params']
        self.width, self.patience = params['width'], params['patience']
        if type(self.width) is not int or self.width != 5 or type(self.patience) is not int or self.patience < 1:
            raise ValueError('frozen width=5 and positive integer patience required')
        self.canonical = list(specs)
        self.units = [specs[c]['unit'] for c in self.canonical]
        self.positions = [self.canonical.index(c) for c in self.channels]
        self.config_id = metadata()['config_id']
        self.indexes = [np.array([j for j, c in enumerate(self.channels) if c[0] == e], int) for e in self.equipment]
        self.thermal = np.array(['temp' in c[1] for c in self.channels])
        self.temp_indexes = [ix[self.thermal[ix] & self.variable[ix]] for ix in self.indexes]
        self.aug_indexes = [np.r_[ix, n + j] for j, ix in enumerate(self.indexes)]
        self.aug_thermal = np.r_[self.thermal, np.ones(len(self.equipment), bool)]
        self.aug_limits = np.r_[self.limits, np.ones(len(self.equipment))]
        self.run = self.sequence = self.at = None
        self.last_status = {'accepted': False, 'ready': False}
        self._restart()

    def _restart(self):
        n = len(self.channels)
        self.warm = 0
        self.was_ready = False
        self.previous_raw = None
        self.median = deque(maxlen=self.width)
        self.flat = deque(maxlen=16)
        self.thermal_history = deque(maxlen=37)
        self.ewma = np.zeros(n)
        self.ewma_valid = np.zeros(n, bool)
        self.machines = [_Notices(ix, size, self.patience) for ix, size in (
            (self.indexes, n), (self.indexes, n),
            (self.aug_indexes, n + len(self.equipment)), (self.aug_indexes, n + len(self.equipment)))]

    @property
    def history_sizes(self):
        return dict(median=len(self.median), flat=len(self.flat), thermal=len(self.thermal_history))

    def _validate(self, frame):
        if not isinstance(frame.get('run_id'), str) or not frame['run_id']:
            raise ValueError('nonempty run_id required')
        seq = frame.get('sequence')
        if type(seq) is not int or seq < 0:
            raise ValueError('nonnegative integer sequence required')
        if frame.get('config_id') != self.config_id:
            raise ValueError('config_id mismatch')
        if frame.get('line_mode') not in ('running', 'paused', 'stopped', 'recovering', 'quality_hold'):
            raise ValueError('known line_mode required')
        try:
            at = datetime.fromisoformat(frame['simulated_at'].replace('Z', '+00:00'))
            if at.utcoffset() is None:
                raise ValueError('timezone required')
        except (KeyError, AttributeError, TypeError, ValueError) as exc:
            raise ValueError('timezone-aware simulated_at required') from exc
        measurements = frame.get('measurements')
        if not isinstance(measurements, list) or len(measurements) != len(self.canonical):
            raise ValueError('canonical measurement order and count required')
        raw = np.full(len(measurements), np.nan)
        for j, m in enumerate(measurements):
            if (m.get('equipment_id'), m.get('signal')) != self.canonical[j]:
                raise ValueError('canonical measurement order required')
            if m.get('unit') != self.units[j]:
                raise ValueError('measurement unit mismatch')
            v = m.get('value')
            if m.get('quality') == 'good' and m.get('observed_at') == frame['simulated_at'] and isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v):
                raw[j] = v
        return at, raw[self.positions]

    def _scores(self, raw, reset, hold, ready):
        if reset or hold:
            self.median.clear()
            self.flat.clear()
            self.thermal_history.clear()
            self.ewma[:] = 0
            self.ewma_valid[:] = False
        z = (raw - self.center) / self.scale
        median = np.full(len(raw), np.nan)
        if not hold:
            self.median.append(z)
            self.thermal_history.append(z)
            if len(self.median) == self.width:
                x = np.asarray(self.median)
                good = np.isfinite(x).all(axis=0)
                median[good] = np.median(x[:, good], axis=0)
        finite = np.isfinite(median)
        self.ewma = np.where(finite, np.where(self.ewma_valid, .4 * median + .6 * self.ewma, median), 0.)
        self.ewma_valid = finite
        level = np.where(finite, np.abs(self.ewma), np.nan)
        if not ready or hold:
            level[:] = np.nan
        level[~self.variable] = 0.
        self.flat.append(np.full(len(raw), np.nan) if hold else raw)
        x = np.asarray(self.flat)
        finite = np.isfinite(x)
        spread = np.max(np.where(finite, x, -np.inf), axis=0) - np.min(np.where(finite, x, np.inf), axis=0)
        moving = (finite.sum(axis=0) >= 2) & (spread > self.tolerance)
        complete = len(self.flat) == 16 and finite.all(axis=0)
        flat = self.variable & complete & (spread <= self.tolerance)
        flat_known = self.variable & np.isfinite(raw) & (flat | moving)
        flat &= ready and not hold
        flat_known &= ready and not hold
        rise = np.full(len(self.equipment), np.nan)
        if ready and not hold and len(self.thermal_history) == 37:
            x = np.asarray(self.thermal_history)
            for k, ix in enumerate(self.temp_indexes):
                good = [j for j in ix if np.isfinite(x[-1, j]) and np.isfinite(x[-5:, j]).sum() >= 4 and np.isfinite(x[:-5, j]).sum() >= 24]
                if len(good) >= 2:
                    change = np.nanmedian(x[-5:, good], axis=0) - np.nanmedian(x[:-5, good], axis=0)
                    rise[k] = np.sort(change)[-2]
        return level, flat, flat_known, np.maximum(rise, 0) / self.thermal_limits

    def step(self, frame):
        at, raw = self._validate(frame)
        run, seq = frame['run_id'], frame['sequence']
        if run == self.run and (seq <= self.sequence or at <= self.at):
            self.last_status = dict(accepted=False, ready=self.was_ready, reason='old_or_duplicate')
            return set()
        discontinuity = run != self.run or seq != self.sequence + 1 or (at - self.at).total_seconds() != 1
        if discontinuity:
            self._restart()
        self.run, self.sequence, self.at = run, seq, at
        running = frame['line_mode'] == 'running'
        ready = running and self.warm == 64
        reset = seq == 0 or not ready or ready != self.was_ready
        self.was_ready = ready
        self.warm = min(64, self.warm + 1) if running else 0
        if reset:
            self.previous_raw = None
        hold = False
        if self.previous_raw is not None:
            good = self.variable & np.isfinite(raw) & np.isfinite(self.previous_raw)
            hold = bool(good.sum() >= 4 and np.sum(good & (raw == self.previous_raw)) >= .8 * good.sum())
        self.previous_raw = raw
        level, flat, flat_known, rise = self._scores(raw, reset, hold, ready)
        known = np.isfinite(level) & self.variable & ready & (not hold)
        process = known & (level > self.limits)
        independent = np.array([flat[ix].any() or process[ix[~self.thermal[ix]]].any() for ix in self.indexes])
        recovered = known & (~self.thermal | (level <= self.limits * (2 / 3)))
        original = self.machines[0].step(process, flat, known, flat_known, reset, hold)
        base = self.machines[1].step(process, flat, recovered, flat_known, reset, hold) | (original & independent)
        aug_level = np.r_[level, rise]
        aug_known = np.r_[known, np.isfinite(rise) & ready & (not hold)]
        aug_process = aug_known & (aug_level > self.aug_limits)
        aug_flat = np.r_[flat, np.zeros(len(rise), bool)]
        aug_flat_known = np.r_[flat_known, np.zeros(len(rise), bool)]
        aug_recovered = aug_known & (~self.aug_thermal | (aug_level <= self.aug_limits * (2 / 3)))
        original_aug = self.machines[2].step(aug_process, aug_flat, aug_known, aug_flat_known, reset, hold)
        augmented = self.machines[3].step(aug_process, aug_flat, aug_recovered, aug_flat_known, reset, hold) | (original_aug & independent)
        notices = augmented | (base & independent)
        self.last_status = dict(accepted=True, ready=ready, hold=hold, reset=reset, discontinuity=discontinuity)
        return {eq for eq, emitted in zip(self.equipment, notices) if emitted}
