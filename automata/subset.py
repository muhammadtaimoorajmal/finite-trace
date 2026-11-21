"""Step 3: subset construction (ε-NFA -> DFA). Every DFA state is a SET of NFA states."""
from .model import EPS, Automaton


def epsilon_closure(machine, states):
    """All states reachable from `states` using only ε-moves (including the states themselves)."""
    closure, stack = set(states), list(states)
    while stack:
        for q in machine.next(stack.pop(), EPS):
            if q not in closure:
                closure.add(q)
                stack.append(q)
    return frozenset(closure)


def move(machine, states, symbol):
    """States reachable from `states` by reading exactly one `symbol`."""
    return {q for p in states for q in machine.next(p, symbol)}


def subset_construction(nfa):
    """Returns (dfa, subsets, steps). subsets maps 'D0' -> its set of NFA states."""
    start = epsilon_closure(nfa, {nfa.start})
    names = {start: "D0"}   # NFA subset -> DFA state name
    queue = [start]         # subsets whose transitions are not computed yet
    dfa = Automaton([], nfa.alphabet, "D0", set())
    steps = []

    while queue:
        subset = queue.pop(0)
        for symbol in nfa.alphabet:
            moved = move(nfa, subset, symbol)
            target = epsilon_closure(nfa, moved)  # the empty set becomes the dead state
            if target not in names:
                names[target] = f"D{len(names)}"
                queue.append(target)
            dfa.add(names[subset], symbol, names[target])
            steps.append({"From": names[subset], "Symbol": symbol, "move": nfa.show(moved),
                          "ε-closure(move)": nfa.show(target), "To": names[target]})

    dfa.states = list(names.values())
    # A DFA state is final if its subset contains a final NFA state.
    dfa.finals = {name for subset, name in names.items() if subset & nfa.finals}
    subsets = {name: subset for subset, name in names.items()}
    return dfa, subsets, steps
