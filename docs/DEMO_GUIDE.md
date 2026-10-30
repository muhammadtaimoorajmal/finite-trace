# FiniteTrace Demonstration Guide

A step-by-step script for demonstrating FiniteTrace live. Each demonstration lists the exact input, what appears on screen, and the reasoning to explain. The state names below are what FiniteTrace generates for these inputs (construction is deterministic, so they are the same every time).

**Before you start:** run `python -m streamlit run app.py` and open http://localhost:8501. Leave the sidebar's *Diagram layout* on **Automatic**. For questions you may be asked, see the [questions and answers](CODE_WALKTHROUGH.md#questions-and-answers).

---

## 1. Regular expression → ε-NFA

**Where:** Automata Builder → Regular Expression. Enter `(a|b)*abb` and press **Generate ε-NFA**.

**On screen:** *ε-NFA generated with 14 states and 16 transitions.* The diagram starts at **q6** (arrow from the dot) and ends at **q13** (double circle); 11 of the transitions are dashed ε-arrows.

**Explain:**

- The expression is first turned into postfix `ab|*a.b.b.`. Press **Validate & Parse** to show this step.
- Thompson's construction reads it with a stack. `a` and `b` each become a two-state fragment, `|` joins them with a new start and end state, `*` adds a skip and a loop, and each `.` links fragments with an ε-arrow.
- The **Construction steps** table lists every operation.

## 2. NFA → DFA conversion

**Where:** NFA to DFA Converter → From Regular Expression. Enter `(a|b)*abb` and press **Convert NFA to DFA**.

**On screen:** *Converted a 14-state ε-NFA into a 5-state DFA.*

- **Section B** begins with `D0 = ε-closure({q6}) = {q0, q2, q4, q6, q7, q8}` and lists 10 conversion steps (5 states × 2 symbols).
- **Section C** shows DFA states D0–D4, with **D4** accepting.

**Explain:**

- **ε-closure** is every state reachable from a set using ε-moves only.
- **move(S, x)** is every state reachable by reading one `x`.
- Each DFA state is the set `ε-closure(move(S, x))`; a set seen for the first time gets the next name.
- D4 is accepting because its set contains q13, the NFA's accepting state.
- No dead state is needed, because every set has a move on both symbols.

## 3. The transition table

**Where:** Automata Builder → Regular Expression → **Generate DFA** for `(a|b)*abb`.

**On screen:** the *DFA transition table* has one row per state and one column per symbol:

| State | a | b |
| --- | --- | --- |
| → D0 | D1 | D2 |
| D1 | D1 | D3 |
| D2 | D1 | D2 |
| D3 | D1 | D4 |
| ★ D4 | D1 | D2 |

**Explain:** it is deterministic and complete, with exactly one entry in every cell. → marks the initial state and ★ accepting states. The diagram above it draws the same 10 transitions as arrows.

## 4. An accepted string

**Where:** String Simulator → Regular Expression. Enter `(a|b)*abb`, choose **DFA**, enter test string `aabb`, and press **Simulate String**.

**On screen:** **Accepted**: *the entire input was consumed and the final state D4 is accepting.* Press **▶ Play** (or **⏭ Next** repeatedly) to watch the amber active state move **D0 → D1 → D1 → D3 → D4**, with the transition just used highlighted and the input tape marking the current character.

**Explain:** a DFA is always in exactly one state. The verdict is decided only after the last character.

Switch the machine type to **NFA** and simulate again. Step 0 now highlights all of `{q0, q2, q4, q6, q7, q8}`: an NFA follows every possible path at once.

## 5. A rejected string

**Same place.** Change the test string to `abab` and press **Simulate String**.

**On screen:** **Rejected**: *the entire input was consumed, but the final state D3 is not accepting.* Stepping through shows D0 → D1 → D3 → D1 → D3.

**Explain:** the language is "strings ending in `abb`", and `abab` does not end in `abb`. Note that `abba` would also be rejected, even though it passes through the accepting state D4: only the state after the *whole* input matters.

## 6. A manual ε-NFA and its conversion

**Where:** Automata Builder → Manual Automaton.

**Enter:**

- **Machine type:** NFA
- **Alphabet:** `a,b`
- **States:** `q0,q1,q2,q3`
- **Initial state:** `q0`
- **Accepting states:** `q3`
- **Transitions:**

```text
q0,ε,q1
q0,ε,q2
q1,a,q3
q2,b,q3
```

Press **Validate & Build**. The diagram shows two dashed ε-arrows from q0, and in the table q0's ε cell is `{q1, q2}`.

Then open **NFA to DFA Converter → From Manual NFA** and press **Convert NFA to DFA**. The result is D0 = {q0, q1, q2}, D1 = {q3} (accepting), and D2 = ∅ (the dead state).

**Explain:**

- The starting set includes q1 and q2 because of the ε-moves.
- Reading `a` or `b` from D0 reaches {q3}.
- Reading anything after that reaches the empty set, which becomes the dead state.
- So the language is exactly {`a`, `b`}. Check it in the String Simulator under **Builder Automaton** (the manual NFA) and **Converted DFA**: `a` and `b` are accepted; the empty string and `ab` are rejected.

## 7. A structured language rule

**Where:** Automata Builder → Language Rule. Use alphabet `0,1`, rule **Ends with**, pattern `01`, and press **Generate Automaton**.

**On screen:** *DFA generated with 3 states.* The table's *Meaning* column reads "nothing matched yet", "matched '0'" and "input ends with '01'".

Then, in String Simulator → **Builder Automaton** (the new rule is selected automatically), `1101` is **Accepted** and `011` is **Rejected**.

**Explain:**

- Each state records how much of the pattern the input currently ends with.
- After reading a symbol, the new state is the longest prefix of the pattern that is a suffix of what was read.
- That rule handles overlapping patterns correctly.

## 8. A helpful error

**Where:** Automata Builder → Regular Expression. Enter `a||b` and press **Generate DFA**.

**On screen:** *Unexpected '|' at position 3: it directly follows '|' at position 2; an expression is required between them.*, with a `^` under the offending character. No automaton is shown.

**Explain:** expressions are validated before anything is built, and errors name the exact position. Correct the input to `a|b` and press the button again; there's no need to reload the page.

---

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| "The expression has changed. Press …" | The result belongs to earlier input; press the button again. |
| "Invalid test string: symbol 'c' at position 3 …" | The test string uses a character outside the automaton's alphabet. This is reported as invalid input, not as a rejection. |
| Typing `ε` as a test string gives an error | Leave the test string **empty** to test the empty string. |
| A large diagram is small or not drawn | Diagrams with more than 15 states are drawn top to bottom. Above 80 states or 250 transitions no diagram is drawn; the table, trace and DOT download remain. |
| "No Builder automaton is available" | Build one in the Automata Builder first; results whose inputs were edited afterwards are not offered. |
