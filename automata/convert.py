"""Step 2: NFA -> DFA by subset construction (the method from class).

1. Start with the set {A}; it becomes DFA state q0.
2. For each new set and each symbol, the next set is the union of the NFA moves
   of all its states.
3. A set not seen before becomes a new DFA state q1, q2, ... in the order found.
   The empty set (no move possible) becomes the trap (dead) state qT.
4. A DFA state is final if its set contains the NFA final state G.
"""
from .model import Automaton, set_name

TRAP = "qT"


def move(nfa, states, symbol):
    """Union of the NFA moves of every state in `states` on `symbol`."""
    return frozenset(q for p in states for q in nfa.next(p, symbol))


def nfa_to_dfa(nfa):
    """Return (dfa, rows, subsets).

    rows[i] explains how row i of the DFA table was found;
    subsets maps each DFA state name to its set of NFA states, e.g. "q2" -> "{B,E}".
    """
    start = frozenset({nfa.start})
    names = {start: "q0"}  # NFA set -> DFA state name
    queue = [start]        # sets whose row is not done yet
    dfa = Automaton([], nfa.alphabet, "q0", set(), is_dfa=True)
    rows = []

    while queue:
        current = queue.pop(0)
        row = {"state": names[current], "work": [], "new": []}
        for symbol in nfa.alphabet:
            target = move(nfa, current, symbol)
            if target not in names:  # Step 3: a new DFA state
                names[target] = f"q{sum(1 for s in names if s)}" if target else TRAP
                queue.append(target)
                row["new"].append(names[target])
            dfa.add(names[current], symbol, names[target])
            # e.g.  δ({B,E}, b) = δ(B,b) ∪ δ(E,b) = {B} ∪ {F} = {B,F} → q5
            parts = sorted(current, key=nfa.states.index)
            row["work"].append(
                f"δ({set_name(current, nfa.states)}, {symbol}) = "
                + " ∪ ".join(f"δ({p},{symbol})" for p in parts) + " = "
                + " ∪ ".join(nfa.show(nfa.next(p, symbol)) for p in parts)
                + f" = {set_name(target, nfa.states)}  → {names[target]}")
        rows.append(row)

    dfa.states = list(names.values())
    dfa.finals = {name for s, name in names.items() if s & nfa.finals}  # Step 4
    subsets = {name: set_name(s, nfa.states) for s, name in names.items()}
    return dfa, rows, subsets


def partial(dfa, rows, k):
    """The DFA as it looks after the first k rows are done (for the step-by-step animation)."""
    shown = [dfa.start] + [s for row in rows[:k] for s in row["new"]]
    part = Automaton(shown, dfa.alphabet, dfa.start, dfa.finals & set(shown), is_dfa=True)
    for row in rows[:k]:
        for symbol in dfa.alphabet:
            for dst in dfa.next(row["state"], symbol):
                part.add(row["state"], symbol, dst)
    return part
