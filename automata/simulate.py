"""Step 3: run a string on the NFA or the DFA.

Keep the SET of current states. After each symbol, the new set is every state reachable
on that symbol. For the DFA the set always holds exactly one state.
"""


def check_word(machine, word):
    """Return an error message if the word uses a symbol outside the alphabet, else None."""
    for ch in word:
        if ch not in machine.alphabet:
            return (f"String Rejected: '{word}' contains '{ch}', which is not in the alphabet "
                    f"{{{', '.join(machine.alphabet)}}}.")
    return None


def run(machine, word):
    """Sets of current states: before reading anything, then after each symbol."""
    current = {machine.start}
    history = [current]
    for symbol in word:
        current = {q for p in current for q in machine.next(p, symbol)}
        history.append(current)
    return history


def accepts(machine, word):
    """True if a final state is reached at the end of the word."""
    return bool(run(machine, word)[-1] & machine.finals)


def trace(machine, word, history):
    """Steps like 'q0 --a--> q4'. lines[0] = start, lines[i] = step i, lines[-1] = verdict."""
    order = lambda states: sorted(states, key=machine.states.index)
    lines = [f"Start: {machine.start}"]
    for i, symbol in enumerate(word):
        step = []
        for p in order(history[i]):
            targets = order(machine.next(p, symbol))
            step += [f"{p} --{symbol}--> {q}" for q in targets] or [f"{p} --{symbol}--> φ (this branch dies)"]
        lines.append("\n".join(step) or f"φ --{symbol}--> φ (no branch left)")

    last = order(history[-1])
    finals = [s for s in last if s in machine.finals]
    if finals:
        lines.append(f"{', '.join(finals)} is Final State → String Accepted")
    elif not last:
        lines.append("All branches died → String Rejected")
    else:
        lines.append(f"{', '.join(last)} is not a Final State → String Rejected")
    return lines
