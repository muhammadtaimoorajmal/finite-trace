# FiniteTrace User Guide

This guide explains every part of the FiniteTrace interface and the exact input formats it accepts. For how the algorithms work internally, see [ARCHITECTURE.md](ARCHITECTURE.md); for a code-level tour, see [CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md).

**Contents**

1. [A quick tour](#a-quick-tour)
2. [Regular expression syntax](#regular-expression-syntax)
3. [Language rules, exact strings and manual automata](#language-rules-exact-strings-and-manual-automata)
4. [Generating ε-NFAs and DFAs, and the NFA to DFA Converter](#generating-ε-nfas-and-dfas-and-the-nfa-to-dfa-converter)
5. [String simulation](#string-simulation)
6. [State diagrams, transition tables and DOT downloads](#state-diagrams)
7. [Interactive simulation & animation](#interactive-simulation--animation)

## A quick tour

FiniteTrace has three tabs:

| Tab | What it does |
| --- | --- |
| **Automata Builder** | Builds an automaton from one of four inputs: a regular expression, a language rule, an exact string, or a manual DFA/NFA definition. Shows its state diagram, summary and transition table. |
| **String Simulator** | Runs a test string through an automaton, reports Accepted or Rejected, and replays the run step by step on the diagram. |
| **NFA to DFA Converter** | Converts an NFA (from a regular expression or a manual definition) to a DFA and shows every subset-construction step. |

The sidebar holds a short description and the **Diagram layout** setting (Automatic, Left to right, Top to bottom).

**Build a DFA from a regular expression.** Enter `(a|b)*abb` and press **Generate DFA**:

![Automata Builder showing the 5-state DFA for (a|b)*abb with its diagram and summary](images/automata-builder-dfa.png)

**Build an ε-NFA.** **Generate ε-NFA** shows the Thompson construction for the same expression, with ε-transitions as dashed arrows:

![Thompson ε-NFA for (a|b)*abb with 14 states and 11 ε-transitions](images/thompson-epsilon-nfa.png)

**Use a language rule.** In **Language Rule**, choose *Ends with*, alphabet `0,1`, pattern `01`:

![Language Rule mode generating the 3-state DFA for binary strings ending with 01](images/language-rule-builder.png)

**Enter your own automaton.** In **Manual Automaton**, choose NFA and enter its transitions:

![Manual ε-NFA with two ε-branches from q0 and its transition table](images/manual-epsilon-nfa.png)

**Convert an NFA to a DFA.** In the converter, enter `(0|1)*01`:

![Subset construction for (0|1)*01: the DFA-state mapping, every conversion step and the converted DFA](images/nfa-to-dfa-conversion.png)

**Simulate a string.** In the String Simulator, `(a|b)*abb` as a DFA accepts `aabb`; stepping to the end highlights the accepting state D4 and the transition just used:

![Simulation of aabb ending in the accepting state D4](images/simulation-accepted.png)

The same DFA rejects `abab`, which ends in D3:

![Simulation of abab ending in the non-accepting state D3](images/simulation-rejected.png)

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

In code, `parse_regex("(a|b)*abb")` returns a `ParsedRegex` whose `postfix` is a tuple of typed `Token` objects, which Thompson's construction consumes directly.

## Language rules, exact strings and manual automata

The Automata Builder has four input modes, shown as tabs: **Regular Expression**, **Language Rule**, **Exact String** and **Manual Automaton**. Each mode keeps its own inputs and result. A result is only shown while the inputs that produced it are unchanged.

**Alphabets** are entered as comma-separated single characters, such as `a,b` or `0, 1`. Spaces around symbols are ignored. Symbols cannot be whitespace, `,`, `ε` or `λ`, and at most 20 are allowed.

### Language rules

Language rules are **structured choices**, not free-form English. "Binary strings that end with 01" is entered as alphabet `0,1`, rule *Ends with*, pattern `01`. Each rule is built by a general algorithm from its parameters, and the result is a complete DFA with states `q0, q1, …`:

| Rule | Parameters | Construction |
| --- | --- | --- |
| Starts with | pattern | A chain of states counts how much of the prefix has matched. A wrong symbol goes to a dead state, and the final state loops on every symbol. |
| Ends with | pattern | Pattern-matching states (below). Accepting only while the input currently ends with the pattern. |
| Contains substring | pattern | The same states, but the full-match state is absorbing. |
| Does not contain substring | pattern | Complement of *contains*: accepting and non-accepting states are swapped. |
| Does not end with | pattern | Complement of *ends with*. |
| Even / odd number of a symbol | symbol | Two parity states. The chosen symbol toggles parity; other symbols leave it unchanged. |
| Exactly *k* occurrences | symbol, *k* (0–100) | States count occurrences 0…*k*, plus one overflow state for more than *k*. |

**Pattern-matching states.** State *i* means "the last *i* symbols read are the first *i* symbols of the pattern". After reading *x*, the next state is the length of the longest prefix of the pattern that is a suffix of `pattern[:i] + x`. This is the idea behind the Knuth–Morris–Pratt automaton. It handles overlapping patterns correctly, so *contains* `aba` accepts `ababa`. Patterns may be up to 50 characters.

**Complements** are only taken of complete DFAs. Every string ends in exactly one state of a complete DFA, so swapping acceptance gives exactly the complement language.

The table in the app has a *Meaning* column explaining each state, such as "matched 'ab'". A state that can never be reached is left out; for example, *starts with* `aa` over `{a}` needs no dead state.

### Exact strings

*Exact String* builds a DFA accepting one string and nothing else: a chain of states, one per character, then a dead state for anything extra or different. The string is taken **literally**. With `|` in the alphabet, `a|b` is the three characters `a`, `|`, `b`, not a choice. Leaving the string empty builds the automaton that accepts only ε. Strings may be up to 100 characters.

| Mode | Input | Accepts |
| --- | --- | --- |
| Exact string | `aabb` | only `aabb` |
| Regular expression | `(a\|b)*aabb` | every string ending in `aabb` |

### DFA or NFA output

Language rules and exact strings can be shown as a **DFA** or an **NFA**. Every DFA is also an NFA, one whose transitions each have exactly one destination and no ε-moves, so the NFA output is the same machine labelled as an NFA. It is a separate copy, not the original object. It is not a Thompson ε-NFA; use the Regular Expression mode for that.

### Manual DFA / NFA definitions

| Field | Example | Notes |
| --- | --- | --- |
| Machine type | `DFA` or `NFA` | |
| Alphabet | `0,1` | |
| States | `q0,q1` | letters, digits, `_ . - '`; no spaces; at most 40 characters each, 150 states |
| Initial state | `q0` | must be one of the states |
| Accepting states | `q0` | may be empty (the automaton accepts nothing) |
| Transitions | one `source,symbol,destination` per line | at most 2,000 lines |

Example DFA (binary strings with an even number of `0`s):

```text
q0,0,q1
q0,1,q0
q1,0,q0
q1,1,q1
```

Example ε-NFA (accepts exactly `a` or `b`; alphabet `a,b`, states `q0,q1,q2,q3`, initial `q0`, accepting `q3`):

```text
q0,ε,q1
q0,ε,q2
q1,a,q3
q2,b,q3
```

**Rules:**

- Use `ε` (or `λ`) as the symbol for an epsilon transition. It is stored internally as `None`, and the letter `e` is always an ordinary symbol.
- Repeating a source and symbol with a different destination makes an NFA nondeterministic, so `q0,a,q1` and `q0,a,q2` together give δ(q0, a) = {q1, q2}.
- Identical lines are merged. Blank lines and lines starting with `#` are ignored.
- A **DFA** must be complete and deterministic. It cannot use ε, conflicting destinations are reported with both line numbers, and every missing (state, symbol) pair is listed. FiniteTrace never adds a dead state silently.
- An **NFA** may have missing transitions, several destinations, ε-moves, ε-cycles and any number of accepting states.

Errors name the field or transition line, for example:

```text
Transitions line 2: a DFA allows one destination per state and symbol, but (q0, 0) already goes to 'q1' on line 1.
Incomplete DFA: missing transition for state 'q1' on symbol '1'.
Transitions line 1: symbol '2' is not in the alphabet.
```

The **Example** selector in the format help fills the form with a sample DFA or NFA. You can replace it with any automaton.

### Converting a manual NFA

1. In **Manual Automaton**, choose NFA, enter the definition and press **Validate & Build**.
2. In **NFA to DFA Converter**, open **From Manual NFA** and press **Convert NFA to DFA**.

The same subset-construction engine is used, with any state names. If the manual inputs change after building, the converter asks you to build again instead of using the old automaton. A manual DFA is already deterministic, so it is not offered for conversion.

### Language rules and manual automata in code

```python
from core.language_builder import ENDS_WITH, as_nfa, build_exact_string_dfa, build_language_dfa
from core.manual_builder import parse_and_build, build_manual_automaton
from core.converter import convert_nfa_to_dfa

dfa = build_language_dfa(ENDS_WITH, {"0", "1"}, pattern="01")
nfa_view = as_nfa(dfa)
exact = build_exact_string_dfa("aabb", {"a", "b"})
nfa = build_manual_automaton("NFA", {"q0", "q1"}, {"a"}, "q0", {"q1"}, [("q0", "a", "q1"), ("q0", None, "q1")])
dfa_from_manual = convert_nfa_to_dfa(nfa).dfa
```

## Generating ε-NFAs and DFAs, and the NFA to DFA Converter

In **Automata Builder → Regular Expression**:

- **Validate & Parse** checks the expression and shows its alphabet, the form with explicit concatenation, the postfix form and a token table. It does not build an automaton.
- **Generate ε-NFA** builds the Thompson ε-NFA and shows its diagram, a summary, every transition (one row per arrow) and the construction steps.
- **Generate DFA** builds the ε-NFA and converts it to a DFA in one step. It shows the DFA diagram, a summary, the DFA-state-to-NFA-subset mapping and the DFA transition table.

Neither generate button needs the other to be pressed first.

The **NFA to DFA Converter** tab has two sources:

- **From Regular Expression:** enter an expression and press **Convert NFA to DFA**. Section A shows the source ε-NFA, section B the subset construction (initial ε-closure, the DFA-state mapping and every `move` / `ε-closure` step), and section C the converted DFA.
- **From Manual NFA:** converts the NFA you built in **Manual Automaton** (see [Converting a manual NFA](#converting-a-manual-nfa)).

How these algorithms work is explained in [ARCHITECTURE.md](ARCHITECTURE.md).

## String simulation

`simulate(automaton, text)` runs a test string on any `FiniteAutomaton`, whatever produced it: a regular expression, language rule, exact string, manual definition or conversion.

**How it works.** The simulator keeps a **set of active states**:

1. **Step 0:** `active = ε-closure({initial state})`. No input is consumed.
2. For each character `x`, left to right: `active = ε-closure(move(active, x))`.
3. After the whole input: **accepted** if `active` contains at least one accepting state, otherwise **rejected**.

- **DFA:** the DFA must be complete, so the active set always holds exactly one state, its current state, and each step follows its single transition.
- **NFA:** the set holds every state some path could be in, so all paths are followed at once without listing them. If no active state has a move for a character, the set becomes empty and the string is rejected. Later characters are still recorded with no active states, so the trace always covers the whole input.
- **ε-transitions** never consume input. They are followed during ε-closure, which reuses the converter's `epsilon_closure` and is safe on ε-cycles.
- **Empty string:** leave the test string empty. It is accepted exactly when the starting active set contains an accepting state. For example, `a*` accepts it, `a+` rejects it, and `ε` accepts it.

**Input checking.** Test strings are read literally: no trimming, case-sensitive, with punctuation and digits as ordinary symbols. Every character must be in the automaton's alphabet. Otherwise the simulator reports an *invalid test string* rather than a rejection, for example:

```text
Invalid test string: symbol 'c' at position 3 is not in the alphabet {a, b}.
```

Positions count from 1. A typed `ε` is an ordinary character, not the empty string. Test strings may be up to 1,000 characters; the automaton itself is validated first, and an incomplete DFA is reported, never repaired.

**Trace.** `SimulationResult.steps` holds one `SimulationStep` per configuration:

| Field | Meaning |
| --- | --- |
| `index`, `position`, `symbol` | step number, 1-based input position and character read (`None` for step 0) |
| `active_before` | active states before reading the character |
| `symbol_edges` | transitions followed on that character, as `(source, symbol, destination)` |
| `moved_to` | `move(active_before, symbol)` |
| `epsilon_edges` | ε-transitions inside the closure, as `(source, None, destination)` |
| `active_after` | the active states after ε-closure |
| `explanation` | a one-line summary |

The String Simulator's playback (below) draws each of these records as one frame.

### Simulation example

`(a|b)*abb` converted to a DFA, on `aabb`:

| Step | Read | From | To |
| --- | --- | --- | --- |
| 0 | Start | — | D0 |
| 1 | a | D0 | D1 |
| 2 | a | D1 | D1 |
| 3 | b | D1 | D3 |
| 4 | b | D3 | D4 |

**Accepted:** the entire input was consumed and the final state D4 is accepting. On `abab` the same DFA visits D0, D1, D3, D1, D3 and ends in D3, which is not accepting, so the string is **rejected**.

### Using the String Simulator

The tab has three sources, each with its own test string and **Simulate String** button:

- **Regular Expression:** type an expression, choose **NFA** (Thompson's ε-NFA) or **DFA** (converted by subset construction), and simulate. No need to visit the Builder first.
- **Builder Automaton:** any current Automata Builder result, such as a regex ε-NFA or DFA, a language rule, an exact string or a manual DFA/NFA.
- **Converted DFA:** any current result from the NFA to DFA Converter.

The result shows **Accepted** or **Rejected** with an explanation, a summary, and a step-by-step trace table. DFAs show *From → To*; NFAs show active sets, `move`, the ε-transitions used, and the ε-closure.

Results are tied to the inputs that produced them. Editing the test string, the machine type, the selected automaton or the automaton's definition hides the old verdict. A Builder or Converter result whose inputs were edited afterwards is no longer offered.

### Simulation in code

```python
from core.thompson import regex_to_nfa
from core.simulator import accepts, simulate

automaton = regex_to_nfa("(a|b)*abb")
result = simulate(automaton, "aabb")

print(result.accepted)       # True
print(result.explanation)    # Accepted: ... contains accepting state q13.
print(accepts(automaton, "abab"))  # False (same engine)
```

## State diagrams

Every generated or entered automaton is drawn as a state diagram, built from the automaton's own data:

| Notation | Meaning |
| --- | --- |
| circle | a state |
| double circle | an accepting state |
| arrow from a small dot | the initial state (a state can be both initial and accepting) |
| arrow labelled `a` | a transition on `a`; an NFA may have several arrows with the same label from one state |
| dashed arrow labelled `ε` | an ε-transition, which moves without reading input |
| arrow back to the same state | a self-loop |

Every transition `(source, symbol, destination)` is drawn as its own arrow, including the dead state's self-loops in a complete DFA. Nothing is merged, added or left out. Missing NFA transitions stay missing, and no dead state is added to an NFA. Colours only reinforce the notation (cyan initial state, green accepting states, purple ε-arrows); shapes and labels carry the meaning.

**Where diagrams appear:**

- **Automata Builder:** with every generated ε-NFA, DFA, language-rule, exact-string and manual automaton.
- **NFA to DFA Converter:** the source NFA in section A and the converted DFA in section C. DFA states are drawn by their short names (`D0`, `D1`, …); the NFA subsets they stand for are in the mapping table in section B.
- **String Simulator:** the diagram of the simulated automaton, animated step by step (see *Interactive simulation & animation*).

**Layout and size.** Graphviz's `dot` layout arranges the states. The sidebar's *Diagram layout* setting defaults to **Automatic**: automata with up to 15 states are drawn left to right, and larger ones top to bottom. Wide left-to-right diagrams are shrunk to the page width until their labels become unreadable, while top-to-bottom ones keep their natural size and scroll. You can also choose *Left to right* or *Top to bottom* yourself. Diagrams are drawn for automata with up to 80 states and 250 transitions. Larger automata show a notice instead of a partial picture, and their full transition table and complete DOT source remain available.

**DOT download.** Every diagram has a **Download DOT** button with the complete Graphviz source (`finite-trace-dfa.dot` / `finite-trace-nfa.dot`). Open it in any Graphviz tool to render it as SVG, PNG or PDF. FiniteTrace itself does not export images.

**Accessibility.** Each diagram has a text description as alt text, for example *"DFA state diagram with 5 states, initial state D0, accepting states D4, and 10 transitions over a, b."* The transition table next to it is a complete textual alternative.

**Safety.** States are given internal node ids (`s0`, `s1`, … in sorted order) and names and symbols are escaped labels, so state names such as `state-final` or `x'y` and symbols such as `"`, `\` or `|` cannot change the diagram's structure. The DOT is generated deterministically: the same automaton always gives the same source.

```python
from core.converter import regex_to_dfa
from ui.visualizer import automaton_to_dot

dot = automaton_to_dot(regex_to_dfa("(a|b)*abb"))  # DOT source string, no Graphviz executable needed
```

## Interactive simulation & animation

After **Simulate String**, the String Simulator shows an *Interactive simulation* panel that replays the run on the automaton's diagram. The animation is a view of the trace the simulator already computed. It does not simulate anything itself, so it always agrees with the verdict.

**Frames.** Each `SimulationStep` is one frame. **Step 0** is the starting configuration: no input is consumed, and for an NFA it is the ε-closure of the initial state. Frame *i* has read *i* characters, so a string of length *n* has *n + 1* frames. The ε-transitions taken after a character belong to that character's frame; they are never counted as consumed input. The empty string has a single frame, which is also the last one.

**What is highlighted (in amber, with a thicker outline and filled states):**

- **Active states:** the one current state of a DFA, or *every* active state of an NFA. No branch is picked out.
- **Transitions just used:** the symbol transitions followed (`symbol_edges`) and the ε-transitions used for the closure (`epsilon_edges`, still dashed).
- Highlighting only restyles existing states and arrows. Layout, names, double circles and the initial arrow never change, so the diagram doesn't jump between frames. If an NFA's active set becomes empty, nothing is highlighted, and the remaining characters are still stepped through.

Next to the diagram the panel shows **Step i of n** with a status (*Ready*, *Playing*, *Paused*, *Completed*), a progress bar of characters consumed, and the input string with the character just read highlighted. It also shows the character being read, the active states before and after, the transitions used, and the step's explanation from the trace. On the last frame it repeats the final verdict (Accepted or Rejected) with its reason.

**Controls:**

| Control | Effect |
| --- | --- |
| ▶ Play | advance automatically from the current step; stops by itself on the last step |
| ⏸ Pause | stop on the current step; Play resumes from there |
| ⏮ Previous / ⏭ Next | move exactly one step (and pause) |
| ↺ Reset | back to step 0, stopped |
| ⟳ Replay | back to step 0 and play |
| Playback speed | Slow (2 s), Normal (1 s), Fast (0.5 s) or Very fast (0.25 s) per step |

Changing the speed keeps the current step and restarts the step timer. Each step waits at least the chosen interval, measured with a monotonic clock, and a late update never skips a step. Timing depends on the browser, so a step can take up to about a quarter-interval longer. In testing, Normal produced roughly 1.0–1.3 s per step.

**How it runs.** Playback uses Streamlit's `st.fragment(run_every=...)`: only the panel reruns on a timer, about four times per step, and only while playing. Pausing, finishing or changing speed recreates the panel with the right timer. Nothing reruns while idle, and there are no sleep loops or background threads. The automaton and trace are computed once by **Simulate String**; playback only redraws the current frame.

**Staleness.** Every simulation gets a new run id. Pressing **Simulate String** again, even with the same inputs, starts at step 0. Editing the test string, expression, machine type or chosen automaton stops playback and hides the old result. Each browser session has its own playback and speed.

**Large automata.** Above the diagram limit (80 states or 250 transitions), the panel still steps through the run, showing the step, the active states, the input progress and the explanation. It explains that the diagram cannot be drawn for highlighting. The verdict is unaffected.
