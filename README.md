# FiniteTrace

**Visualize. Convert. Simulate.**

FiniteTrace is an open-source, interactive tool for building, visualizing, converting and simulating finite automata: Deterministic Finite Automata (DFA) and Nondeterministic Finite Automata (NFA), including ε-NFAs. It is written in plain Python with a Streamlit interface. All automata algorithms are implemented from scratch so the code doubles as a readable reference.

> **Status:** early development. Module 01 of 10 (the project foundation) is complete. The builder, converter and simulator screens are layout placeholders only and do not produce results yet.

## Objectives

- Make regular languages and finite automata easy to explore visually.
- Show each algorithm step by step (ε-closures, subset construction, simulation traces) rather than only final answers.
- Keep the codebase small, typed and understandable for people learning Python and automata theory.

## Technology stack

| Purpose | Tool |
| --- | --- |
| Language | Python 3.11+ (developed on 3.13) |
| Web interface | [Streamlit](https://streamlit.io) |
| Graph rendering | [Graphviz](https://graphviz.org) (Python package + system `dot` executable) |
| Testing | pytest, Streamlit `AppTest` |
| Automata algorithms | Implemented in this repository (no automata libraries) |

## Planned functionality

- Parse regular expressions and build equivalent ε-NFAs (Thompson's construction).
- Define languages through structured rules or as a single exact string.
- Enter DFA/NFA transition definitions manually.
- Convert NFAs to DFAs with subset construction, showing ε-closures and state subsets.
- Generate state diagrams and transition tables.
- Simulate test strings on DFAs and NFAs with play, pause, step and reset controls.
- Report whether a string is accepted or rejected.

## Current implementation status

**Implemented (Module 01)**

- Project structure and Streamlit application shell with branding and tabbed navigation.
- Shared `FiniteAutomaton` data model (`core/automata.py`) usable for DFAs and NFAs, with epsilon transitions stored as `None`.
- Structural validation with specific error messages (unknown states, invalid symbols, DFA nondeterminism, DFA epsilon moves, incomplete DFAs).
- Unit tests for the data model and smoke tests for the app.

**Not implemented yet:** regex parsing, NFA construction, NFA-to-DFA conversion, simulation, diagrams and transition tables.

## Installation

Requirements: Python 3.11 or newer, and Git.

```bash
git clone https://github.com/muhammadtaimoorajmal/finite-trace.git
cd finite-trace
python -m venv .venv
```

Install dependencies using the virtual environment's interpreter:

```bash
# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt

# macOS / Linux
.venv/bin/python -m pip install -r requirements.txt
```

### Graphviz system package

The `graphviz` Python package needs the Graphviz `dot` executable to render diagrams. Diagrams arrive in a later module, so the app runs without it today, but installing it now is recommended:

- **Windows:** `winget install --id Graphviz.Graphviz -e` (or the installer from graphviz.org), then make sure `C:\Program Files\Graphviz\bin` is on your `PATH`.
- **macOS:** `brew install graphviz`
- **Debian/Ubuntu:** `sudo apt install graphviz`

Check with `dot -V`.

## Running the app

```bash
# Windows
.venv\Scripts\python.exe -m streamlit run app.py

# macOS / Linux
.venv/bin/python -m streamlit run app.py
```

Then open http://localhost:8501.

## Running the tests

```bash
# Windows
.venv\Scripts\python.exe -m pytest

# macOS / Linux
.venv/bin/python -m pytest
```

## Project structure

```text
finite-trace/
├── app.py                 # Streamlit entry point
├── core/
│   ├── automata.py        # Shared DFA/NFA data model and validation
│   ├── regex_parser.py    # Regular expression parser (planned)
│   ├── converter.py       # NFA-to-DFA conversion (planned)
│   └── simulator.py       # String simulation engine (planned)
├── ui/
│   └── visualizer.py      # Graphviz diagrams and tables (planned)
├── tests/
│   ├── test_automata.py   # Data model tests
│   └── test_app.py        # Streamlit smoke tests
├── .streamlit/config.toml # Theme configuration
├── requirements.txt
├── LICENSE
└── README.md
```

## Roadmap

| Module | Focus | Status |
| --- | --- | --- |
| 01 | Project foundation & architecture | Done |
| 02 | Regular expression parser | Planned |
| 03 | Dynamic NFA construction | Planned |
| 04 | NFA-to-DFA conversion | Planned |
| 05 | Language rules & manual input | Planned |
| 06 | DFA & NFA simulation engine | Planned |
| 07 | State diagrams & transition tables | Planned |
| 08 | Interactive interface & animation | Planned |
| 09 | Integration, robustness & testing | Planned |
| 10 | Release, documentation & final verification | Planned |

## License

Released under the [MIT License](LICENSE).
