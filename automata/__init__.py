"""RE -> ε-NFA -> DFA -> minimized DFA for Project 29: (b + bbb + bb)* cc + ad + bbd."""
from .minimize import table_filling
from .regex import PROJECT_RE, to_postfix
from .subset import subset_construction
from .thompson import thompson


def build_all(regex=PROJECT_RE):
    """Run the whole pipeline (call regex.validate first) and return every intermediate result."""
    postfix = to_postfix(regex)
    nfa, nfa_steps = thompson(postfix)
    dfa, subsets, subset_steps = subset_construction(nfa)
    min_dfa, groups, marked = table_filling(dfa)
    return {
        "postfix": postfix, "nfa": nfa, "nfa_steps": nfa_steps,
        "dfa": dfa, "subsets": subsets, "subset_steps": subset_steps,
        "min_dfa": min_dfa, "groups": groups, "marked": marked,
    }
