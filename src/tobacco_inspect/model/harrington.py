"""Harrington-style state-dependent enforcement.

A retailer caught selling to minors moves to a higher-inspection state, raising its prize next
period. The deterrence effect is an ASSUMPTION encoded in these parameters (docs/assumptions.md).

TODO: implement state transitions and delta_deterrence.
"""


def deterrence_gain(state):
    raise NotImplementedError
