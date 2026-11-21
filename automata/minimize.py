"""Step 4: DFA minimization with the Table-Filling (Myhill-Nerode) method.

1. Mark every pair (final, non-final): they are distinguishable.
2. Repeat: mark (p, q) if some symbol takes them to a pair that is already marked.
3. Pairs never marked are equivalent; their states merge into one state.
"""
from .model import Automaton


def table_filling(dfa):
    """Returns (min_dfa, groups, marked). marked maps a pair to (round, reason)."""
    states = dfa.states

    def pair(p, q):  # one fixed order for each pair: (later state, earlier state)
        return (p, q) if states.index(p) > states.index(q) else (q, p)

    def goes(p, symbol):  # the single DFA successor
        return next(iter(dfa.next(p, symbol)))

    pairs = [(p, q) for i, p in enumerate(states) for q in states[:i]]
    marked = {}

    # Round 0: final vs non-final.
    for p, q in pairs:
        if (p in dfa.finals) != (q in dfa.finals):
            marked[(p, q)] = (0, "one is final, the other is not")

    # Rounds 1, 2, ...: use only pairs marked in earlier rounds.
    round_no, changed = 0, True
    while changed:
        round_no, changed = round_no + 1, False
        for p, q in pairs:
            if (p, q) in marked:
                continue
            for symbol in dfa.alphabet:
                p2, q2 = goes(p, symbol), goes(q, symbol)
                if p2 != q2 and marked.get(pair(p2, q2), (round_no,))[0] < round_no:
                    marked[(p, q)] = (round_no, f"on '{symbol}' they go to ({p2}, {q2}), which is marked")
                    changed = True
                    break

    # Unmarked pairs are equivalent: collect them into groups.
    groups, done = [], set()
    for s in states:
        if s not in done:
            group = [t for t in states if t == s or (t not in done and pair(s, t) not in marked)]
            done.update(group)
            groups.append(group)

    # One new state Mi per group; take transitions from any member (they all agree).
    group_of = {s: f"M{i}" for i, group in enumerate(groups) for s in group}
    min_dfa = Automaton([f"M{i}" for i in range(len(groups))], dfa.alphabet,
                        group_of[dfa.start], {group_of[f] for f in dfa.finals})
    for group in groups:
        for symbol in dfa.alphabet:
            min_dfa.add(group_of[group[0]], symbol, group_of[goes(group[0], symbol)])
    return min_dfa, groups, marked
