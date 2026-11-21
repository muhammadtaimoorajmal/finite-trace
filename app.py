"""FiniteTrace – Project 29: NFA, NFA -> DFA conversion and DFA for (b + bbb + bb)* cc + ad + bbd.

Run with:  python -m streamlit run app.py
All algorithms are in the automata/ folder; this file only shows the results.
"""
import time

import streamlit as st

from automata.convert import nfa_to_dfa, partial
from automata.diagram import to_dot
from automata.nfa import build_nfa
from automata.regex import LANGUAGE, PROJECT_RE, NotProjectRegex, RegexError, validate
from automata.simulate import accepts, check_word, run, trace

DELAY = 1.2  # seconds per animation step

st.set_page_config(page_title="FiniteTrace · Project 29", page_icon="🔁", layout="wide")
st.markdown("""
<style>
.hero {padding:1.3rem 1.6rem; border-radius:16px; margin-bottom:1rem;
       background:linear-gradient(135deg,#0e7490 0%,#1e293b 60%); border:1px solid #155e75;}
.hero h1 {margin:0; font-size:2rem;} .hero p {margin:.3rem 0 0; color:#cbd5e1;}
.re {font-family:monospace; font-size:1.2rem; color:#facc15;}
.tape span {display:inline-block; min-width:2.2rem; padding:.45rem .6rem; margin:2px; text-align:center;
            border-radius:8px; background:#1e293b; border:1px solid #334155; font-family:monospace; font-size:1.1rem;}
.tape .done {color:#64748b;} .tape .now {background:#facc15; color:#0f172a; font-weight:700;}
</style>""", unsafe_allow_html=True)

st.markdown(f"""<div class="hero"><h1>🔁 FiniteTrace</h1>
<p>Regular Expression → NFA → NFA to DFA conversion → DFA</p>
<p><b>Project 29</b> · Muhammad Taimoor Ajmal · RE: <span class="re">{PROJECT_RE}</span>
 · Language: <span class="re">{LANGUAGE}</span></p></div>""", unsafe_allow_html=True)


def table(rows, where=st):
    """Show a list of dicts as a table tall enough for every row."""
    where.dataframe(rows, hide_index=True, width="stretch", height=35 * (len(rows) + 1) + 3)


def player(key, last, frame):
    """Reset / Back / Play / Next buttons; frame(i) draws step i (0 .. last).

    While playing, Streamlit re-runs only this part of the page every DELAY seconds.
    """
    ss = st.session_state
    if key not in ss:
        ss[key] = {"pos": 0, "play": False, "t": 0.0}

    def go(pos=None, play=None):
        s = ss[key]
        if pos is not None:
            s["pos"] = max(0, min(last, pos))
        if play is not None:
            s["play"] = play
        s["t"] = time.monotonic()

    def panel(timed):
        s = ss[key]
        if s["play"] != timed:
            st.rerun()  # Play/Pause was pressed: rebuild this part with or without the timer
        if timed and time.monotonic() - s["t"] >= DELAY * 0.9:
            go(pos=s["pos"] + 1)  # the timer fired: next step
        if s["play"] and s["pos"] >= last:
            go(play=False)  # reached the end: stop
            st.rerun()
        pos = s["pos"]
        b = st.columns(4)
        b[0].button("⏮ Reset", key=key + "r", on_click=go, kwargs={"pos": 0, "play": False}, width="stretch")
        b[1].button("◀ Back", key=key + "b", on_click=go, kwargs={"pos": pos - 1, "play": False}, width="stretch")
        if s["play"]:
            b[2].button("⏸ Pause", key=key + "p", on_click=go, kwargs={"play": False}, width="stretch")
        else:
            b[2].button("▶ Play", key=key + "p", on_click=go, type="primary", width="stretch",
                        kwargs={"pos": 0 if pos >= last else pos, "play": True})
        b[3].button("Next ▶", key=key + "n", on_click=go, kwargs={"pos": pos + 1, "play": False}, width="stretch")
        frame(pos)

    st.fragment(panel, run_every=DELAY if ss[key]["play"] else None)(ss[key]["play"])


def animate_string(machine, name, default):
    """Text box for a string, then an animation of the machine reading it."""
    word = st.text_input(f"String to run on the {name} (empty = ε)", default, key=name + "word").strip()
    if error := check_word(machine, word):
        st.error(error)
        return
    history = run(machine, word)
    lines = trace(machine, word, history)

    def frame(i):
        tape = "".join(f'<span class="{"done" if j < i else "now" if j == i else ""}">{ch}</span>'
                       for j, ch in enumerate(word)) or "<span>ε</span>"
        st.markdown(f'<div class="tape">{tape}</div>', unsafe_allow_html=True)
        st.caption(f"Step {i} of {len(word)}" + (" · finished" if i == len(word) else " · yellow box = next symbol"))
        used = {(p, q) for p in history[i - 1] for q in machine.next(p, word[i - 1])} if i else set()
        st.graphviz_chart(to_dot(machine, active=history[i], used=used), width="stretch")
        log, verdict = st.columns([3, 2])
        log.code("\n".join(lines[: i + 1] + (lines[-1:] if i == len(word) else [])), language=None)
        if i == len(word):
            (verdict.success if accepts(machine, word) else verdict.error)(lines[-1])

    player(f"{name}:{word}", len(word), frame)


# ---------------------------------------------------------------- the regular expression
text = st.text_input("Regular expression ( + means OR, * means repeat ) — press Enter to check", PROJECT_RE)
try:
    validate(text)
except RegexError as error:
    st.error(f"Invalid Regular Expression: {error}".replace("*", r"\*"))
    st.stop()
except NotProjectRegex as error:
    st.warning(f"Not allowed: {error}".replace("*", r"\*"))
    st.stop()
st.success("Regular expression accepted. The NFA and the DFA are built below.")

nfa = build_nfa()
dfa, rows = nfa_to_dfa(nfa)
st.caption("🟢 start state · 🔵 final state (double circle) · ⚪ other state · "
           "🟡 current state during animation · φ = dead state (empty set)")
tab_nfa, tab_conv, tab_dfa, tab_test = st.tabs(
    ["① NFA", "② NFA → DFA conversion", "③ DFA", "④ Test many strings"])

# ---------------------------------------------------------------- ① NFA
with tab_nfa:
    st.subheader(f"NFA: {len(nfa.states)} states, start q0, final states q3, q5, q8")
    st.markdown("""From the start state **q0** there is one branch for each part of the RE:
* **(b + bbb + bb)\\* cc** → q1 loops on **b** (any mix of b, bb, bbb is just any number of b's),
  then **c** → q2, **c** → q3. The loop has its own state q1, because it belongs only to *cc*
  (a loop on q0 would wrongly accept *bad* and *bbbd*).
* **ad** → q4 → q5
* **bbd** → q6 → q7 → q8""")
    left, right = st.columns([3, 2])
    left.graphviz_chart(to_dot(nfa), width="stretch")
    right.markdown("**Transition table** (φ = no move)")
    table(nfa.table(), right)
    st.markdown("#### Animation")
    animate_string(nfa, "NFA", "bbd")

# ---------------------------------------------------------------- ② NFA -> DFA
with tab_conv:
    st.subheader("Subset construction, one row at a time")
    st.markdown("""**Step 1:** start with Q' = { {q0} }.  **Step 2:** for each new set, find where it goes on
a, b, c, d (the union of the NFA moves of its states).  **Step 3:** a set not seen before is added to Q'
(φ is the dead state).  **Step 4:** a DFA state is final if it contains q3, q5 or q8.""")

    def conv_frame(k):
        current = {rows[k - 1]["state"]} if k else set()
        st.graphviz_chart(to_dot(partial(dfa, rows, k), active=current), width="stretch")
        if k == 0:
            st.info("Step 1: the DFA starts with the start set {q0}. Press Next or Play.")
            return
        row = rows[k - 1]
        work, done = st.columns(2)
        work.markdown(f"**Row {k} of {len(rows)}: DFA state {row['state']}**")
        work.code("\n".join(row["work"]), language=None)
        work.markdown("New states: " + (", ".join(f"**{s}**" for s in row["new"]) or "none"))
        done.markdown("**DFA table so far**")
        table(dfa.table()[:k], done)
        if k == len(rows):
            st.success(f"Done: {len(dfa.states)} DFA states. Final states "
                          f"{', '.join(sorted(dfa.finals))} contain q3, q5 or q8.")

    player("conversion", len(rows), conv_frame)

# ---------------------------------------------------------------- ③ DFA
with tab_dfa:
    st.subheader(f"DFA: {len(dfa.states)} states (each one is a set of NFA states)")
    st.graphviz_chart(to_dot(dfa), width="stretch")
    st.markdown("**Transition table** (→ start, * final)")
    table(dfa.table())
    st.markdown("#### Animation")
    animate_string(dfa, "DFA", "bbd")

# ---------------------------------------------------------------- ④ test many strings
with tab_test:
    raw = st.text_area("One string per line (write ε for the empty string)",
                       "cc\nbcc\nbbbbcc\nad\nbbd\nbd\nbad\nbbbd\nacc\nε", height=230)
    for line in filter(str.strip, raw.splitlines()):
        word = "" if line.strip() == "ε" else line.strip()
        if error := check_word(nfa, word):
            st.error(error)
            continue
        verdict = "✅ Accepted" if accepts(dfa, word) else "❌ Rejected"
        with st.expander(f"{word or 'ε'}  →  {verdict}"):
            a, b = st.columns(2)
            a.markdown("**NFA**")
            a.code("\n".join(trace(nfa, word, run(nfa, word))), language=None)
            b.markdown("**DFA**")
            b.code("\n".join(trace(dfa, word, run(dfa, word))), language=None)
