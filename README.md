# FiniteTrace

**Visualize. Convert. Simulate.**

FiniteTrace is an open-source, interactive tool for building, visualizing, converting and simulating finite automata: Deterministic Finite Automata (DFA) and Nondeterministic Finite Automata (NFA), including ε-NFAs. It is written in plain Python with a Streamlit interface. All automata algorithms are implemented from scratch so the code doubles as a readable reference.

> **Status:** early development. Modules 01–02 of 10 are complete: the project foundation and the regular expression parser. Regular expressions can be validated and parsed in the app; automaton generation, conversion and simulation are not available yet.

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

### Implemented (Module 01)

- Project structure and Streamlit application shell with branding and tabbed navigation.
- Shared `FiniteAutomaton` data model (`core/automata.py`) usable for DFAs and NFAs, with epsilon transitions stored as `None`.
- Structural validation with specific error messages (unknown states, invalid symbols, DFA nondeterminism, DFA epsilon moves, incomplete DFAs).
- Unit tests for the data model and smoke tests for the app.

### Implemented (Module 02)

- Regular expression parser (`core/regex_parser.py`): tokenizer, syntax validation with positioned error messages, implicit-concatenation insertion, and Shunting-Yard conversion to postfix tokens.
- Alphabet extraction (epsilon is never part of the alphabet).
- **Validate & Parse** in the Automata Builder tab, showing the alphabet, explicit-concatenation form, postfix expression and a token table.

**Not implemented yet:** NFA construction, NFA-to-DFA conversion, simulation, diagrams and transition tables. A parsed expression cannot yet be turned into an automaton.

## Regular expression syntax

FiniteTrace uses formal regular expressions, not the Python/PCRE regex dialect.

| Feature | Syntax | Meaning |
| --- | --- | --- |
| Literal symbol | `a`, `Z`, `0`, `_` | Match that symbol (ASCII letters, digits, underscore) |
| Union | `a\|b` | Either expression |
| Concatenation | `ab` or `a.b` | `a` followed by `b` |
| Kleene star | `a*` | Zero or more repetitions |
| Kleene plus | `a+` | One or more repetitions |
| Optional | `a?` | Zero or one occurrence |
| Grouping | `(ab)` | Group an expression; groups may be nested |
| Epsilon | `ε` or `λ` | The empty string |
| Escape | `\|`, `\*`, `\+`, `\?`, `\(`, `\)`, `\.`, `\\` | The character itself as a literal symbol |

**Precedence** (highest first): parentheses, then the postfix operators `*` `+` `?`, then concatenation, then union. Concatenation and union are left-associative. So `a|bc` means `a|(bc)`, `ab*` means `a(b*)`, and `(ab)*` repeats the whole sequence `ab`.

**Implicit concatenation.** Writing two expressions side by side concatenates them. The parser inserts an explicit `.` wherever an operand (a symbol, `ε`, `)` or a postfix operator) is followed by the start of another operand (a symbol, `ε` or `(`): `(a|b)*abb` becomes `(a|b)*.a.b.b`. An unescaped `.` therefore always means concatenation, never "any character".

**Epsilon.** `ε` and `λ` both denote the empty string and never appear in the alphabet. The letter `e` is an ordinary symbol. An empty input is an error; write `ε` for the empty-string language.

**Escaping.** A backslash makes the reserved characters `| . * + ? ( ) \ [ ] { } ^ $` literal symbols, shown escaped in parser output (for example `a\|b` gives the postfix `a\|.b.`, which is different from `ab|`). Other escapes such as `\d` are rejected, as are escaped whitespace and `\ε` / `\λ`.

**Whitespace** between tokens is ignored (`a | b` equals `a|b`). Whitespace cannot be an alphabet symbol.

**Repeated postfix operators** such as `a**`, `a++` or `a+?` are rejected to avoid confusion with other regex dialects (`+?` is not a lazy quantifier here). Use parentheses for nested repetition: `(a*)*`, `(a+)?`.

**Not supported:** character classes `[a-z]`, counted repetition `{2,4}`, anchors `^` `$`, wildcard `.`, backreferences, lookarounds and flags. These produce an error instead of being misinterpreted.

**Maximum length:** 512 characters, including whitespace. Longer input is rejected, never truncated.

**Error positions** count characters from 1, including whitespace.

### Examples

| Expression | Alphabet | Explicit concatenation | Postfix |
| --- | --- | --- | --- |
| `(a\|b)*abb` | {a, b} | `(a\|b)*.a.b.b` | `ab\|*a.b.b.` |
| `(0\|1)*01` | {0, 1} | `(0\|1)*.0.1` | `01\|*0.1.` |
| `a(b\|c)*` | {a, b, c} | `a.(b\|c)*` | `abc\|*.` |
| `(ab)+` | {a, b} | `(a.b)+` | `ab.+` |
| `(a\|ε)b` | {a, b} | `(a\|ε).b` | `aε\|b.` |

| Invalid input | Error |
| --- | --- |
| `a\|\|b` | Unexpected '\|' at position 3: it directly follows '\|' at position 2; an expression is required between them. |
| `(ab` | Unmatched '(' at position 1: missing closing ')'. |
| `[ab]` | Unsupported '[' at position 1: character classes are not supported. Use explicit union, such as (a\|b). |
| `a**` | Unexpected '*' at position 3: repeated postfix operators such as '**' are not supported. Use parentheses, such as (a*)*. |

### Using Validate & Parse

1. Open the **Automata Builder** tab.
2. Type an expression into **Regular expression** and press **Validate & Parse**.
3. A valid expression shows its alphabet, explicit-concatenation form, postfix expression and a step-by-step token table. An invalid one shows an error with a marker under the offending character.

In code, `parse_regex("(a|b)*abb")` returns a `ParsedRegex` whose `postfix` is a tuple of typed `Token` objects, ready for the stack-based NFA construction planned in Module 03.

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

Then open <http://localhost:8501>.

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
│   ├── regex_parser.py    # Regular expression parser
│   ├── converter.py       # NFA-to-DFA conversion (planned)
│   └── simulator.py       # String simulation engine (planned)
├── ui/
│   └── visualizer.py      # Graphviz diagrams and tables (planned)
├── tests/
│   ├── test_automata.py   # Data model tests
│   ├── test_regex_parser.py # Parser tests
│   └── test_app.py        # Streamlit smoke tests
├── .streamlit/config.toml # Theme configuration
├── requirements.txt
├── LICENSE
└── README.md
```

## Roadmap

| Module | Focus | Status |
| --- | --- | --- |
| 01 | Project foundation & architecture | Complete |
| 02 | Regular expression parser | Complete |
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
