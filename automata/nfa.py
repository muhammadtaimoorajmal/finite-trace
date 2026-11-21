"""Step 1: the NFA for (b + bbb + bb)* cc + ad + bbd.

Built like in class: one start state q0, and one branch for each part of the union (+).

  Branch 1  (b + bbb + bb)* cc
            Any mix of b, bb and bbb is just "any number of b's", so q1 loops on b.
            The loop gets its own state q1 (not q0): it belongs only to cc.
            If q0 had the loop, the NFA would also accept "bad" and "bbbd", which are wrong.
  Branch 2  ad
  Branch 3  bbd
"""
from .model import Automaton

TRANSITIONS = [
    # Branch 1: (b + bbb + bb)* cc
    ("q0", "b", "q1"), ("q1", "b", "q1"),  # the b's (loop)
    ("q0", "c", "q2"), ("q1", "c", "q2"),  # first c, after zero or more b's
    ("q2", "c", "q3"),                     # second c -> q3 is final
    # Branch 2: ad
    ("q0", "a", "q4"), ("q4", "d", "q5"),  # q5 is final
    # Branch 3: bbd
    ("q0", "b", "q6"), ("q6", "b", "q7"), ("q7", "d", "q8"),  # q8 is final
]


def build_nfa():
    """Return the NFA: states q0..q8, start q0, finals q3, q5, q8."""
    nfa = Automaton([f"q{i}" for i in range(9)], ["a", "b", "c", "d"], "q0", {"q3", "q5", "q8"})
    for src, symbol, dst in TRANSITIONS:
        nfa.add(src, symbol, dst)
    return nfa
