"""Step 5: run a string on any of the three machines.

One function works for all three: keep the SET of active states, and after each
symbol take ε-closure(move(active, symbol)). For a DFA the set always has one state.
"""
from .subset import epsilon_closure, move


def check_word(machine, word):
    """Return an error message if the word uses a symbol outside the alphabet, else None."""
    for ch in word:
        if ch not in machine.alphabet:
            return f"'{word}' contains '{ch}', which is not in the alphabet {{{', '.join(machine.alphabet)}}}."
    return None


def run(machine, word):
    """Active-state sets: before reading anything, then after each symbol."""
    active = epsilon_closure(machine, {machine.start})
    history = [active]
    for symbol in word:
        active = epsilon_closure(machine, move(machine, active, symbol))
        history.append(active)
    return history


def accepts(machine, word):
    """True if the machine ends in (or its active set contains) a final state."""
    return bool(run(machine, word)[-1] & machine.finals)


def trace(machine, word, history):
    """Readable steps like 'q0 --a--> q1' and the final verdict."""
    show = machine.show
    lines = [f"Start: {show(history[0])}"]
    lines += [f"{show(history[i])} --{word[i]}--> {show(history[i + 1])}" for i in range(len(word))]
    last = history[-1]
    finals = last & machine.finals
    if len(last) == 1 and finals:
        lines.append(f"{show(last)} is Final State → String Accepted")
    elif finals:
        lines.append(f"Active set contains final state {show(finals)} → String Accepted")
    elif len(last) == 1:
        lines.append(f"{show(last)} is not a Final State → String Rejected")
    else:
        lines.append("No final state in the active set → String Rejected")
    return lines
