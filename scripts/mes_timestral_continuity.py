"""Observation-only continuity filters with framewise source-display preservation."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('continuity_previous',ROOT/'scripts/mes_timestral_rearm.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
preserve=previous.preserve;utils=previous.utils;base=previous.base


def continuity_alerts(keys,raw_z,ratio,baseline,equipment,resets,current,params):
    raise NotImplementedError('source display continuity')


def coverage_loss(keys,positive,before,after):
    raise NotImplementedError('framewise coverage loss')


def choose(rows,current,baselines):
    raise NotImplementedError('coverage-preserving selection')
