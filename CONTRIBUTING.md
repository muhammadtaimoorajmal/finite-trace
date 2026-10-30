# Contributing to FiniteTrace

Thanks for your interest in improving FiniteTrace. This guide covers setting up a development copy, running the app and tests, and what a good contribution looks like.

## Set up

Requires Python 3.11 or newer and Git.

```bash
git clone https://github.com/muhammadtaimoorajmal/finite-trace.git
cd finite-trace
python -m venv .venv

# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt
# macOS / Linux
.venv/bin/python -m pip install -r requirements.txt
```

## Run the app

```bash
# Windows
.venv\Scripts\python.exe -m streamlit run app.py
# macOS / Linux
.venv/bin/python -m streamlit run app.py
```

Then open http://localhost:8501. No system Graphviz installation is needed; diagrams are drawn in the browser.

## Run the tests

```bash
# Windows
.venv\Scripts\python.exe -m pytest
# macOS / Linux
.venv/bin/python -m pytest
```

The suite runs in well under a minute. One optional test renders DOT with the Graphviz `dot` executable and is skipped if it is not installed. GitHub Actions runs the same suite on Python 3.11 and 3.13 for every push and pull request to `main`.

## Code organization

- `core/`: the automaton model and all algorithms. Plain Python, no Streamlit imports, so everything here can be tested directly.
- `ui/` and `app.py`: the Streamlit interface. It collects input, calls `core/`, and displays results.
- `tests/`: unit tests per module, Streamlit `AppTest` interface tests (`test_*_app.py`), and integration and robustness tests.
- `docs/`: user, architecture, code and demo guides.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pieces fit together and [docs/CODE_WALKTHROUGH.md](docs/CODE_WALKTHROUGH.md) for a tour of the code.

## Contribution guidelines

- **Keep it readable.** Prefer small functions, clear names, sets and dictionaries, and comments that explain *why*. The code is meant to be understandable by people learning automata theory.
- **Keep algorithms in `core/`** and presentation in `ui/`. Every automaton should be a `FiniteAutomaton`, so the converter, simulator and diagrams keep working with it.
- **Add tests with every change.** For algorithms, prefer checks against an independent oracle (for example, a plain Python description of the language on all short strings) over checks of state counts alone. For interface changes, add an `AppTest` test.
- **Run the full test suite** before opening a pull request, and keep it passing.
- **Stay in scope.** FiniteTrace covers finite automata and formal regular expressions; pushdown automata, Turing machines and full PCRE regex syntax are out of scope.

## Reporting a bug

Open an issue at https://github.com/muhammadtaimoorajmal/finite-trace/issues with:

1. What you entered (the expression, rule, manual definition or test string).
2. What you expected and what FiniteTrace showed (an error message or a screenshot helps).
3. Your Python version and operating system, if the problem is about installation.

For a wrong accept/reject result, the smallest input that shows the problem is the most useful report.
