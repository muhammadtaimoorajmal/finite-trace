"""FiniteTrace – Project 29: RE -> ε-NFA -> DFA -> minimized DFA, with animation.

Run with:  python -m streamlit run app.py
All algorithms are in the automata/ package; this file only shows the results.
"""
import time

import streamlit as st

from automata import build_all
from automata.diagram import to_dot
from automata.regex import LANGUAGE, PROJECT_RE, NotProjectRegex, RegexError, validate
from automata.simulate import accepts, check_word, run, trace

st.set_page_config(page_title="FiniteTrace · Project 29", page_icon="🔁", layout="wide")
st.markdown("""
<style>
.hero {padding:1.4rem 1.6rem; border-radius:16px; margin-bottom:1rem;
       background:linear-gradient(135deg,#0e7490 0%,#1e293b 60%); border:1px solid #155e75;}
.hero h1 {margin:0; font-size:2.1rem;} .hero p {margin:.25rem 0 0; color:#cbd5e1;}
.re {font-family:monospace; font-size:1.25rem; color:#facc15;}
.tape span {display:inline-block; min-width:2.2rem; padding:.45rem .6rem; margin:2px; text-align:center;
            border-radius:8px; background:#1e293b; border:1px solid #334155; font-family:monospace; font-size:1.1rem;}
.tape .done {color:#64748b;} .tape .now {background:#facc15; color:#0f172a; font-weight:700;}
</style>""", unsafe_allow_html=True)

st.markdown(f"""<div class="hero">
<h1>🔁 FiniteTrace</h1>
<p>Regular Expression → ε-NFA (Thompson) → DFA (Subset Construction) → Minimized DFA (Table-Filling)</p>
<p><b>Project 29</b> · Muhammad Taimoor Ajmal · RE: <span class="re">{PROJECT_RE}</span>
 · Language: <span class="re">{LANGUAGE}</span></p></div>""", unsafe_allow_html=True)


@st.cache_resource
def pipeline(regex):
    return build_all(regex)


def table(rows, where=st):
    """Show a list of dicts as a table tall enough to show every row."""
    where.dataframe(rows, hide_index=True, width="stretch", height=35 * (len(rows) + 1) + 3)


# ---------------------------------------------------------------- input and validation
with st.form("re_form"):
    left, right = st.columns([5, 1], vertical_alignment="bottom")
    text = left.text_input("Enter the regular expression  ( + means OR, * means star )", PROJECT_RE)
    if right.form_submit_button("Build machines", type="primary", width="stretch"):
        try:
            validate(text)
            st.session_state.status = ("ok", "Regular expression accepted. All three machines were built.")
            st.session_state.regex = text
        except RegexError as error:
            st.session_state.status = ("error", f"Invalid Regular Expression: {error}")
        except NotProjectRegex as error:
            st.session_state.status = ("warning", f"Not allowed: {error}")

kind, message = st.session_state.get("status", ("info", "Press 'Build machines' to start."))
show = {"ok": st.success, "error": st.error, "warning": st.warning, "info": st.info}[kind]
show(message.replace("*", r"\*"))  # escape * so Markdown does not turn it into italics
if kind != "ok":
    st.stop()  # nothing else is shown until the Project 29 RE is entered

r = pipeline(st.session_state.regex)
nfa, dfa, mdfa = r["nfa"], r["dfa"], r["min_dfa"]
merged = [g for g in r["groups"] if len(g) > 1]
MACHINES = {"ε-NFA": nfa, "DFA": dfa, "Minimized DFA": mdfa}

cols = st.columns(4)
cols[0].metric("Alphabet", "{" + ", ".join(nfa.alphabet) + "}")
cols[1].metric("ε-NFA states", len(nfa.states))
cols[2].metric("DFA states", len(dfa.states))
cols[3].metric("Minimized DFA states", len(mdfa.states), delta=f"-{len(dfa.states) - len(mdfa.states)}",
                delta_color="inverse")
st.caption("Diagram colours: 🟢 start state · 🔵 final state (double circle) · ⚪ normal state · "
           "dashed arrow = ε-move · 🟠 border = merged states · 🟡 = active during animation")

tab_nfa, tab_dfa, tab_min, tab_sim = st.tabs(
    ["① Thompson ε-NFA", "② Subset Construction → DFA", "③ Minimization", "④ Simulate & Animate"])

# ---------------------------------------------------------------- ① ε-NFA
with tab_nfa:
    st.subheader("Thompson's construction")
    st.markdown(f"**Postfix form** (`.` = concatenation): `{' '.join(r['postfix'])}`")
    st.markdown("**Intermediate steps:** each row builds one fragment with one start and one final state.")
    table(r["nfa_steps"])
    st.markdown(f"**ε-NFA diagram:** {len(nfa.states)} states, start `{nfa.start}`, "
                f"final `{nfa.show(nfa.finals)}`")
    st.graphviz_chart(to_dot(nfa), width="stretch")
    st.markdown("**Transition table** (with ε-moves)")
    table(nfa.table())

# ---------------------------------------------------------------- ② DFA
with tab_dfa:
    st.subheader("Subset construction")
    st.markdown(f"Start state **D0 = ε-closure({{{nfa.start}}})**. For every DFA state and symbol: "
                "**ε-closure(move(state, symbol))**. Each DFA state is a *set* of NFA states; "
                "a DFA state is final if its set contains the NFA final state "
                f"`{nfa.show(nfa.finals)}`. The empty set `∅` is the dead state.")
    subsets = {name: nfa.show(s) for name, s in r["subsets"].items()}
    table(dfa.table({"NFA subset": subsets}))
    with st.expander("Show every move / ε-closure step"):
        table(r["subset_steps"])
    st.graphviz_chart(to_dot(dfa), width="stretch")

# ---------------------------------------------------------------- ③ minimization
with tab_min:
    st.subheader("Table-Filling method")
    st.markdown("Round 0 marks every *(final, non-final)* pair. Each later round marks a pair if some "
                "symbol sends it to an already-marked pair. **✗n** = marked in round n, "
                "**≡** = never marked, so the two states are equivalent and merge.")
    states = dfa.states
    grid = []
    for i, p in enumerate(states[1:], start=1):
        row = {"": p}
        for q in states[:-1]:
            j = states.index(q)
            row[q] = "" if j >= i else (f"✗{r['marked'][(p, q)][0]}" if (p, q) in r["marked"] else "≡")
        grid.append(row)
    table(grid)
    with st.expander("Why each pair was marked"):
        table([{"Pair": f"({p}, {q})", "Round": rnd, "Reason": why}
               for (p, q), (rnd, why) in r["marked"].items()])

    group_of = {s: f"M{i}" for i, g in enumerate(r["groups"]) for s in g}
    for g in merged:
        st.success(f"Merged: **{' ≡ '.join(g)}** → one state **{group_of[g[0]]}**")
    before, after = st.columns(2)
    before.markdown(f"**Before:** DFA with {len(dfa.states)} states (merged states have an orange border)")
    table(dfa.table(), before)
    before.graphviz_chart(to_dot(dfa, merged={s for g in merged for s in g}), width="stretch")
    after.markdown(f"**After:** minimized DFA with {len(mdfa.states)} states")
    members = {group_of[g[0]]: "{" + ", ".join(g) + "}" for g in r["groups"]}
    table(mdfa.table({"DFA states": members}), after)
    merged_labels = {group_of[g[0]]: members[group_of[g[0]]] for g in merged}
    after.graphviz_chart(to_dot(mdfa, merged=set(merged_labels), labels=merged_labels), width="stretch")

# ---------------------------------------------------------------- ④ simulation and animation
with tab_sim:
    st.subheader("Test strings")
    raw = st.text_area("One string per line (write ε for the empty string)",
                       "cc\nbcc\nbbbbcc\nad\nbbd\nbd\nbbbd\nacc\nε", height=200)
    words, results = [], []
    for line in raw.splitlines():
        word = "" if line.strip() == "ε" else line.strip()
        if not line.strip():
            continue
        if error := check_word(nfa, word):
            st.error(error)
            continue
        words.append(word)
        row = {"String": word or "ε"}
        row.update({name: "✅ Accepted" if accepts(m, word) else "❌ Rejected" for name, m in MACHINES.items()})
        results.append(row)
    table(results)

    if words:
        st.subheader("Animation")
        c1, c2, c3 = st.columns([2, 3, 2])
        word = c1.selectbox("String to animate", words, format_func=lambda w: w or "ε")
        choice = c2.radio("Machine", [*MACHINES, "All three"], horizontal=True)
        delay = c3.select_slider("Speed (seconds per step)", [2.0, 1.5, 1.0, 0.6, 0.3], value=1.0)
        shown = MACHINES if choice == "All three" else {choice: MACHINES[choice]}
        key = f"anim:{choice}:{word}"
        st.session_state.setdefault(key + ":pos", 0)
        st.session_state.setdefault(key + ":play", False)

        def set_state(pos=None, play=None):
            """Button callbacks: change the step position and/or the playing flag."""
            if pos is not None:
                st.session_state[key + ":pos"] = max(0, min(len(word), pos))
            if play is not None:
                st.session_state[key + ":play"] = play
            st.session_state[key + ":time"] = time.monotonic()

        def panel(timed):
            """One animation frame. While playing, Streamlit reruns only this panel every `delay` seconds."""
            ss = st.session_state
            if ss[key + ":play"] != timed:
                st.rerun()  # Play/Pause changed: rebuild the panel with or without a timer
            if timed and time.monotonic() - ss.get(key + ":time", 0) >= delay * 0.9:
                set_state(pos=ss[key + ":pos"] + 1)
            pos = ss[key + ":pos"]
            if pos >= len(word) and ss[key + ":play"]:
                set_state(play=False)
                st.rerun()

            b = st.columns(5)
            b[0].button("⏮ Reset", on_click=set_state, kwargs={"pos": 0, "play": False}, width="stretch")
            b[1].button("◀ Back", on_click=set_state, kwargs={"pos": pos - 1, "play": False}, width="stretch")
            if ss[key + ":play"]:
                b[2].button("⏸ Pause", on_click=set_state, kwargs={"play": False}, width="stretch")
            else:
                start = 0 if pos >= len(word) else pos  # pressing Play at the end replays
                b[2].button("▶ Play", on_click=set_state, kwargs={"pos": start, "play": True},
                            type="primary", width="stretch")
            b[3].button("Next ▶", on_click=set_state, kwargs={"pos": pos + 1, "play": False}, width="stretch")
            b[4].button("End ⏭", on_click=set_state, kwargs={"pos": len(word), "play": False}, width="stretch")

            tape = "".join(f'<span class="{"done" if i < pos else "now" if i == pos else ""}">{ch}</span>'
                           for i, ch in enumerate(word)) or "<span>ε</span>"
            st.markdown(f'<div class="tape">{tape}</div>', unsafe_allow_html=True)
            st.caption(f"Step {pos} of {len(word)}" + (" · finished" if pos == len(word) else
                                                       " · yellow box = next symbol to read"))

            for name, m in shown.items():
                history = run(m, word)
                lines = trace(m, word, history)
                used = set()
                if pos > 0:  # highlight the arrows used by the last symbol
                    used = {(p, q) for p in history[pos - 1] for q in m.next(p, word[pos - 1])}
                st.markdown(f"**{name}**")
                # The 36-state ε-NFA needs the full width; the DFAs leave room for the trace beside them.
                graph, log = (st.container(), st.container()) if m is nfa else st.columns([3, 1])
                graph.graphviz_chart(to_dot(m, active=history[pos], used=used), width="stretch")
                shown_lines = lines[: pos + 1] + (lines[-1:] if pos == len(word) else [])
                log.code("\n".join(shown_lines), language=None, wrap_lines=True)
                if pos == len(word):
                    (log.success if accepts(m, word) else log.error)(lines[-1].split("→ ")[-1])

        playing = st.session_state[key + ":play"]
        st.fragment(panel, run_every=delay if playing else None)(playing)
