"""Causal episode rearming around the fixed preserved Timestral hybrid."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rearm_preserve',ROOT/'scripts/mes_timestral_preserve.py')
preserve=importlib.util.module_from_spec(spec);spec.loader.exec_module(preserve)
utils=preserve.utils;base=preserve.base


def episode_alerts(keys,raw_z,ratio,baseline,equipment,resets,desired,params):
    raise NotImplementedError('episode rearming')


def choose(rows,current,baselines):
    raise NotImplementedError('preservation and EWMA-level duplicate selection')
