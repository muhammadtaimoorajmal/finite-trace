"""Step 1: the NFA for (b + bbb + bb)* cc + ad + bbd.

Built like in class: start state A, one branch for each part of the union (+),
and all three branches end in the same final state G.

  Branch 1  (b + bbb + bb)* cc :  A -b-> B (B loops on b), A or B -c-> C -c-> G
            Any mix of b, bb and bbb is just "any number of b's", so B loops on b.
            The loop has its own state B (not A) because it belongs only to cc:
            a loop on A would also accept "bad" and "bbbd", which are wrong.
  Branch 2  ad  :  A -a-> D -d-> G
  Branch 3  bbd :  A -b-> E -b-> F -d-> G
"""
from .model import Automaton

TRANSITIONS = [
    # Branch 1: (b + bbb + bb)* cc
    ("A", "b", "B"), ("B", "b", "B"),  # the b's (B loops on b)
    ("A", "c", "C"), ("B", "c", "C"),  # first c, after zero or more b's
    ("C", "c", "G"),                   # second c -> final state G
    # Branch 2: ad
    ("A", "a", "D"), ("D", "d", "G"),
    # Branch 3: bbd
    ("A", "b", "E"), ("E", "b", "F"), ("F", "d", "G"),
]


def build_nfa():
    """Return the NFA: states A..G, start A, final G."""
    nfa = Automaton(list("ABCDEFG"), ["a", "b", "c", "d"], "A", {"G"})
    for src, symbol, dst in TRANSITIONS:
        nfa.add(src, symbol, dst)
    return nfa
