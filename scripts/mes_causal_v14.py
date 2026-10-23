"""Causal thermal-rise evidence; original v13 remains unchanged."""
import numpy as np
from scripts import mes_causal_v13 as previous


def thermal_rise(args,window=32):
    raise NotImplementedError('RED: thermal rise not implemented')


def predict(*args):
    return previous.predict(*args)
