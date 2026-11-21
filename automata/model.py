"""The data structure used by both machines (NFA and DFA)."""
from dataclasses import dataclass, field

DEAD = "φ"  # the empty set = dead (trap) state


@dataclass
class Automaton:
    states: list    # state names in display order
    alphabet: list  # input symbols: ["a", "b", "c", "d"]
    start: str
    finals: set
    is_dfa: bool = False  # a DFA has exactly one next state for every (state, symbol)
    delta: dict = field(default_factory=dict)  # (state, symbol) -> set of next states

    def add(self, src, symbol, dst):
        """Add the transition src --symbol--> dst."""
        self.delta.setdefault((src, symbol), set()).add(dst)

    def next(self, state, symbol):
        """All states reachable from `state` on `symbol` (empty set if none)."""
        return self.delta.get((state, symbol), set())

    def edges(self):
        """Every transition as (src, symbol, dst)."""
        for src in self.states:
            for symbol in self.alphabet:
                for dst in sorted(self.next(src, symbol), key=self.states.index):
                    yield src, symbol, dst

    def show(self, states):
        """A set of states as text: {q1,q6}, or φ for the empty set."""
        return set_name(states, self.states)

    def table(self):
        """Transition table rows. → marks the start state, * marks final states."""
        rows = []
        for state in self.states:
            mark = ("→ " if state == self.start else "") + ("* " if state in self.finals else "")
            row = {"State": mark + state}
            for symbol in self.alphabet:
                targets = self.next(state, symbol)
                # DFA cell: the one next state.  NFA cell: the set of next states.
                row[symbol] = next(iter(targets)) if self.is_dfa else self.show(targets)
            rows.append(row)
        return rows


def set_name(states, order):
    """Name of a set of states, e.g. {q1,q6}; the empty set is φ."""
    if not states:
        return DEAD
    return "{" + ",".join(sorted(states, key=order.index)) + "}"
