# Changelog

All notable changes to FiniteTrace are documented here. The project follows [semantic versioning](https://semver.org/).

## v1.0.0 — Initial stable release

The first public release.

### Features

- **Regular expressions to automata:** a formal regular-expression parser (union, concatenation, `*`, `+`, `?`, grouping, ε/λ, escaped operators) with positioned error messages, Thompson's construction of ε-NFAs, and NFA-to-DFA conversion by subset construction.
- **Other inputs:** structured language rules (starts with, ends with, contains, does not contain, does not end with, even/odd count of a symbol, exactly *k* occurrences), exact-string automata, and manually entered DFAs, NFAs and ε-NFAs, all with validation.
- **NFA to DFA Converter:** for regex-generated or manually entered NFAs, showing the initial ε-closure, every `move`/`ε-closure` step, the DFA-state mapping and the dead state.
- **State diagrams** for every automaton, drawn in the browser from Graphviz DOT, with an automatic layout choice and DOT downloads.
- **Transition tables** in state × symbol form (with ε columns for NFAs).
- **String simulation** for DFAs, NFAs and ε-NFAs, with Accepted/Rejected verdicts, explanations and a complete step-by-step trace.
- **Interactive playback:** play, pause, previous, next, reset, replay and a speed control, with active states and the transitions used highlighted on the diagram.

### Quality

- Over 700 automated tests, covering the algorithms, independent-oracle equivalence checks, randomized checks with fixed seeds, Streamlit interface tests and end-to-end workflows. Checked in a real Chrome browser.
- GitHub Actions continuous integration on Python 3.11 and 3.13.
- Public deployments show only generic messages for unexpected errors (`client.showErrorDetails = "none"`).

### Development history

FiniteTrace was built in ten stages before this release:

1. The project foundation and automaton model.
2. The regular-expression parser.
3. Thompson's construction.
4. Subset construction.
5. Language rules and manual input.
6. The simulator.
7. State diagrams.
8. Interactive playback.
9. Integration testing and hardening.
10. Release preparation.

There were no earlier public releases.
