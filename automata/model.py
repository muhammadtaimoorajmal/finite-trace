"""The one data structure used by all three machines (ε-NFA, DFA, minimized DFA)."""
from dataclasses import dataclass, field

EPS = "ε"  # label of an epsilon (empty) move


@dataclass
class Automaton:
    states: list   # state names in display order, e.g. ["q0", "q1", ...]
    alphabet: list  # input symbols, e.g. ["a", "b", "c", "d"]
    start: str
    finals: set
    delta: dict = field(default_factory=dict)  # (state, symbol) -> set of next states

    def add(self, src, symbol, dst):
        """Add the transition src --symbol--> dst."""
        self.delta.setdefault((src, symbol), set()).add(dst)

    def next(self, state, symbol):
        """All states reachable from `state` on `symbol` (empty set if none)."""
        return self.delta.get((state, symbol), set())

    def symbols(self):
        """Table columns: the alphabet, plus ε if the machine has ε-moves."""
        has_eps = any(symbol == EPS for _, symbol in self.delta)
        return self.alphabet + ([EPS] if has_eps else [])

    def edges(self):
        """Every transition as (src, symbol, dst), in a stable order."""
        for src in self.states:
            for symbol in self.symbols():
                for dst in self.sorted(self.next(src, symbol)):
                    yield src, symbol, dst

    def sorted(self, states):
        """Sort state names by their position in self.states (q2 before q10)."""
        return sorted(states, key=self.states.index)

    def show(self, states):
        """Format a set of states: 'q1' for one state, '{q1, q2}' for more, '∅' for none."""
        if not states:
            return "∅"
        names = self.sorted(states)
        return names[0] if len(names) == 1 else "{" + ", ".join(names) + "}"

    def table(self, extra=None):
        """Transition table rows. → marks the start state, * marks final states.

        `extra` can add a column, e.g. {"NFA subset": {"D0": "{q0, q1}"}}.
        """
        rows = []
        for state in self.states:
            mark = ("→ " if state == self.start else "") + ("* " if state in self.finals else "")
            row = {"State": mark + state}
            for column, values in (extra or {}).items():
                row[column] = values[state]
            for symbol in self.symbols():
                row[symbol] = self.show(self.next(state, symbol)) if self.next(state, symbol) else "—"
            rows.append(row)
        return rows
