# FiniteTrace v1.0.0 — Initial Stable Release

FiniteTrace is an interactive tool for building, visualizing, converting and simulating finite automata (DFA, NFA and ε-NFA), written in Python with a Streamlit interface. All automata algorithms are implemented directly in the project.

## Highlights

- **Regular expression to ε-NFA:** a formal regex parser (union, concatenation, `*`, `+`, `?`, grouping, ε/λ, escaped operators) with positioned error messages, and Thompson's construction.
- **NFA-to-DFA subset construction:** showing the initial ε-closure, every `move`/`ε-closure` step, the DFA-state-to-NFA-subset mapping and the dead state.
- **Structured language rules:** starts with, ends with, contains, does not contain, does not end with, even/odd number of a symbol, and exactly *k* occurrences.
- **Exact-string automata**, including the empty string.
- **Manual DFA/NFA/ε-NFA definitions** with line-numbered validation, convertible to DFAs.
- **State diagrams** with initial arrows, double-circle accepting states, dashed ε-transitions and self-loops; automatic layout; DOT downloads.
- **Transition tables** in state × symbol form.
- **DFA and NFA string simulation** with Accepted/Rejected verdicts, explanations and a full step-by-step trace.
- **Interactive playback** with play, pause, previous, next, reset, replay and speed control, highlighting active states and the transitions used.

## Quality

- **Tests:** 729 collected, 728 passed and 1 skipped. The skipped test is optional and needs the Graphviz `dot` executable.
- **Coverage of the suite:** algorithm tests; checks of NFAs and DFAs against independent oracles on every short string; fixed-seed randomized tests; Streamlit `AppTest` interface tests; and end-to-end workflows.
- **Browser checks:** every input mode, the converter, simulation and playback were verified in a real Chrome browser.
- **CI:** GitHub Actions runs the suite on Python 3.11 and 3.13.

## Installation

See the [README](https://github.com/muhammadtaimoorajmal/finite-trace#quick-start). In short: clone the repository, install `requirements.txt` into a virtual environment, and run `python -m streamlit run app.py`.

## Supported Python versions

Python 3.11 and 3.13 are tested in CI. Development used Python 3.13.

## Known limitations

- Formal regular-expression syntax only, not Python/PCRE regex (no character classes, counted repetition, anchors, wildcard `.`, backreferences or lookarounds).
- Structured language rules rather than free-form natural-language input.
- No automatic DFA minimization; subset construction gives an equivalent but not necessarily minimal DFA.
- Documented limits:
  - regular expressions of up to 512 characters
  - 1,500 ε-NFA states and 512 DFA states
  - test strings of up to 1,000 characters
  - diagrams of up to 80 states / 250 transitions (larger automata keep their tables, traces and DOT download)
- The Graphviz `dot` command-line program is optional; it is only needed to render downloaded `.dot` files outside the app.

## License

MIT.
