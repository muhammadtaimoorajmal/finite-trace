"""Smoke and interaction tests for the Streamlit application using Streamlit's AppTest."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")

# Controls that are allowed to be enabled (parser, ε-NFA generation, DFA conversion,
# and the Module 05 language-rule, exact-string and manual-automaton forms).
PARSER_WIDGET_KEYS = {
    "regex_input", "parse_button", "generate_nfa_button", "generate_dfa_button",
    "converter_input", "convert_button",
    "lang_alphabet", "lang_pattern", "lang_symbol", "lang_generate",
    "exact_alphabet", "exact_text", "exact_generate",
    "manual_alphabet", "manual_states", "manual_initial", "manual_accepting", "manual_build", "manual_load",
    # Module 06 string simulator (the saved-automaton buttons stay disabled until something is built)
    "sim_regex", "sim_regex_text", "sim_regex_button", "sim_builder_text", "sim_converted_text",
}
MAIN_TABS = ["Automata Builder", "String Simulator", "NFA to DFA Converter"]
# All tabs in page order: the main tabs with the Builder's input modes and the Converter's sources nested.
ALL_TABS = [
    "Automata Builder", "Regular Expression", "Language Rule", "Exact String", "Manual Automaton",
    "String Simulator", "Regular Expression", "Builder Automaton", "Converted DFA",
    "NFA to DFA Converter", "From Regular Expression", "From Manual NFA",
]


def run_app() -> AppTest:
    app = AppTest.from_file(APP_PATH, default_timeout=30)
    app.run()
    return app


def parse_in_app(app: AppTest, expression: str) -> AppTest:
    app.text_input(key="regex_input").input(expression)
    app.button(key="parse_button").click()
    app.run()
    return app


def all_text(app: AppTest) -> str:
    return " ".join(block.value for block in app.markdown) + " " + " ".join(
        block.value for block in app.code
    )


def test_app_runs_without_exceptions():
    app = run_app()
    assert not app.exception


def test_app_shows_heading_and_navigation():
    app = run_app()
    page_markdown = " ".join(block.value for block in app.markdown)
    assert "FiniteTrace" in page_markdown
    assert "Interactive Finite Automata Visualizer &amp; Simulator" in page_markdown or \
        "Interactive Finite Automata Visualizer & Simulator" in page_markdown

    assert [tab.label for tab in app.tabs] == ALL_TABS
    assert [label for label in ALL_TABS if label in MAIN_TABS] == MAIN_TABS


def test_unfinished_controls_are_disabled():
    app = run_app()
    other_buttons = [b for b in app.button if b.key not in PARSER_WIDGET_KEYS]
    other_inputs = [t for t in app.text_input if t.key not in PARSER_WIDGET_KEYS]
    assert other_buttons, "expected placeholder buttons to be rendered"
    assert all(button.disabled for button in other_buttons)
    assert all(text_input.disabled for text_input in other_inputs)
    labels = {button.label for button in app.button}
    # Animation stays unavailable until Module 08 (string simulation itself works since Module 06).
    assert {"▶ Play", "⏸ Pause", "⏭ Step", "↺ Reset"} <= labels
    assert all(b.disabled for b in app.button if b.label in {"▶ Play", "⏸ Pause", "⏭ Step", "↺ Reset"})


def test_parser_controls_are_enabled():
    app = run_app()
    assert not app.text_input(key="regex_input").disabled
    assert not app.button(key="parse_button").disabled
    assert app.button(key="parse_button").label == "Validate & Parse"


def test_valid_expression_shows_parse_details():
    app = parse_in_app(run_app(), "(a|b)*abb")
    assert not app.exception
    assert [s.value for s in app.success] == ["Valid expression"]
    assert not app.error
    code_blocks = [block.value for block in app.code]
    assert "(a|b)*abb" in code_blocks
    assert "{a, b}" in code_blocks
    assert "(a|b)*.a.b.b" in code_blocks
    assert "ab|*a.b.b." in code_blocks
    table = app.dataframe[0].value
    assert list(table["Token"]) == list("ab|*a.b.b.")
    assert list(table["Type"])[:4] == ["Literal", "Literal", "Union", "Kleene star"]


def test_invalid_expression_shows_error_and_clears_previous_result():
    app = parse_in_app(run_app(), "(a|b)*abb")
    assert app.success

    app = parse_in_app(app, "a||b")
    assert not app.exception
    assert not app.success
    assert len(app.error) == 1
    assert "position 3" in app.error[0].value
    assert "ab|*a.b.b." not in all_text(app)
    assert len(app.dataframe) == 0


def test_editing_input_hides_stale_result():
    app = parse_in_app(run_app(), "ab")
    assert app.success
    app.text_input(key="regex_input").input("abc").run()
    assert not app.success
    assert not app.error


def test_other_tabs_still_render_after_parsing():
    app = parse_in_app(run_app(), "a(b|c)*")
    assert [tab.label for tab in app.tabs] == ALL_TABS
    subheaders = [block.value for block in app.subheader]
    assert subheaders == ["Automata Builder", "String Simulator", "NFA to DFA Converter"]
    assert app.success  # the parse result coexists with the other sections


# --- Module 03: ε-NFA generation -------------------------------------------

def generate_in_app(app: AppTest, expression: str) -> AppTest:
    app.text_input(key="regex_input").input(expression)
    app.button(key="generate_nfa_button").click()
    app.run()
    return app


def test_generate_buttons_are_enabled():
    app = run_app()
    assert not app.button(key="generate_nfa_button").disabled
    assert app.button(key="generate_nfa_button").label == "Generate ε-NFA"
    # Module 04 enabled DFA generation (it was a disabled placeholder before).
    assert not app.button(key="generate_dfa_button").disabled
    assert app.button(key="generate_dfa_button").label == "Generate DFA"


def test_generate_nfa_shows_summary_transitions_and_steps():
    app = generate_in_app(run_app(), "(a|b)*abb")
    assert not app.exception
    assert not app.error
    assert "14 states and 16 transitions" in app.success[0].value
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics == {"States": "14", "Transitions": "16", "ε-transitions": "11"}
    code_blocks = [block.value for block in app.code]
    assert "{a, b}" in code_blocks
    assert "q6" in code_blocks    # initial state
    assert "q13" in code_blocks   # accepting state
    assert "{" + ", ".join(f"q{i}" for i in range(14)) + "}" in code_blocks

    transitions, steps = app.dataframe[0].value, app.dataframe[1].value
    assert len(transitions) == 16
    assert {"Source": "q0", "Symbol": "a", "Destination": "q1"} in transitions.to_dict("records")
    assert (transitions["Symbol"] == "ε").sum() == 11
    assert list(steps["Token"]) == list("ab|*a.b.b.")
    assert list(steps["Operation"])[:4] == ["Literal", "Literal", "Union", "Kleene star"]


def test_generating_new_expression_replaces_previous_nfa():
    app = generate_in_app(run_app(), "a|b")
    assert "6 states" in app.success[0].value
    app = generate_in_app(app, "(ab)*")
    assert len(app.success) == 1
    assert "6 states and 7 transitions" in app.success[0].value
    assert "(ab)*" in [block.value for block in app.code]
    assert "a|b" not in [block.value for block in app.code]
    assert len(app.dataframe[0].value) == 7


def test_generate_with_invalid_expression_shows_error_only():
    app = generate_in_app(run_app(), "(a|b)*abb")
    app = generate_in_app(app, "a||b")
    assert not app.exception
    assert not app.success
    assert not app.metric
    assert len(app.dataframe) == 0
    assert "position 3" in app.error[0].value
    assert "Generate ε-NFA" in " ".join(c.value for c in app.caption)


def test_editing_input_hides_generated_nfa():
    app = generate_in_app(run_app(), "ab")
    app.text_input(key="regex_input").input("abc").run()
    assert not app.success
    assert not app.metric


def test_parser_still_works_after_generating():
    app = generate_in_app(run_app(), "ab")
    app = parse_in_app(app, "a(b|c)*")
    assert [s.value for s in app.success] == ["Valid expression"]
    assert "abc|*." in [block.value for block in app.code]
    assert not app.metric


# --- Module 04: DFA generation and the converter tab ---------------------

def builder_dfa(app: AppTest, expression: str) -> AppTest:
    app.text_input(key="regex_input").input(expression)
    app.button(key="generate_dfa_button").click()
    app.run()
    return app


def convert_in_app(app: AppTest, expression: str) -> AppTest:
    app.text_input(key="converter_input").input(expression)
    app.button(key="convert_button").click()
    app.run()
    return app


def frame_with_column(app: AppTest, column: str):
    matches = [frame.value for frame in app.dataframe if column in frame.value.columns]
    assert matches, f"no table with column {column!r}"
    return matches[0]


def test_builder_generate_dfa_shows_summary_mapping_and_table():
    app = builder_dfa(run_app(), "(a|b)*abb")
    assert not app.exception
    assert not app.error
    assert "DFA generated with 5 states" in app.success[0].value
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["DFA states"] == "5"
    assert metrics["Transitions"] == "10"
    assert metrics["Dead state"] == "None"
    mapping = frame_with_column(app, "NFA states")
    assert list(mapping["DFA state"]) == ["→ D0", "D1", "D2", "D3", "★ D4"]
    assert mapping["Type"].iloc[0] == "Initial"
    table = frame_with_column(app, "State")
    assert list(table.columns) == ["State", "a", "b"]
    assert table.iloc[0].to_dict() == {"State": "→ D0", "a": "D1", "b": "D2"}


def test_builder_dfa_shows_dead_state():
    app = builder_dfa(run_app(), "ab")
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Dead state"] == "D2"  # D0 --b--> ∅ is discovered before D1 is explored
    mapping = frame_with_column(app, "NFA states")
    dead = mapping[mapping["DFA state"] == "D2"].iloc[0]
    assert dead["NFA states"] == "∅" and "Dead" in dead["Type"]


def test_builder_dfa_with_empty_alphabet_explains_missing_table():
    app = builder_dfa(run_app(), "ε")
    assert not app.exception
    assert any("alphabet is empty" in info.value for info in app.info)


def test_converter_tab_shows_nfa_trace_and_dfa():
    app = convert_in_app(run_app(), "(0|1)*01")
    assert not app.exception
    assert not app.error
    assert "12-state ε-NFA into a 4-state DFA" in app.success[0].value
    headings = [block.value for block in app.markdown]
    for heading in ["### A. Original ε-NFA", "### B. Subset construction", "### C. Converted DFA"]:
        assert heading in headings
    nfa_rows = frame_with_column(app, "Source")
    assert len(nfa_rows) == 14
    trace = frame_with_column(app, "move(S, x)")
    assert len(trace) == 8
    assert list(trace["From"])[:2] == ["D0", "D0"]
    assert set(trace["Result"]) <= {"new", "existing", "new (dead state)"}
    assert any(c.value.startswith("D0 = ε-closure({q6}) = {") for c in app.code)
    table = frame_with_column(app, "State")
    assert list(table.columns) == ["State", "0", "1"]
    assert len(table) == 4


def test_converter_invalid_input_hides_previous_result():
    app = convert_in_app(run_app(), "(0|1)*01")
    app = convert_in_app(app, "a||b")
    assert not app.exception
    assert not app.success
    assert len(app.dataframe) == 0
    assert "position 3" in app.error[0].value


def test_converter_new_expression_replaces_result():
    app = convert_in_app(run_app(), "a|b")
    assert "4-state DFA" in app.success[0].value
    app = convert_in_app(app, "(ab)*")
    assert len(app.success) == 1
    assert "(ab)*" in [block.value for block in app.code]
    assert "a|b" not in [block.value for block in app.code]


def test_converter_edit_hides_stale_result():
    app = convert_in_app(run_app(), "a|b")
    app.text_input(key="converter_input").input("ab").run()
    assert not app.success
    assert len(app.dataframe) == 0


def test_builder_and_converter_results_are_independent():
    app = convert_in_app(run_app(), "(0|1)*01")
    app = generate_in_app(app, "ab")
    # Both results are shown: the Builder's ε-NFA and the Converter's DFA.
    assert len(app.success) == 2
    assert "ε-NFA generated" in app.success[0].value
    assert "4-state DFA" in app.success[1].value
    assert app.text_input(key="converter_input").value == "(0|1)*01"


def test_dfa_state_limit_shows_error_not_partial_dfa():
    # "10th symbol from the end is a" needs over 2**10 DFA states, above MAX_DFA_STATES.
    expression = "(a|b)*a" + "(a|b)" * 9
    app = convert_in_app(run_app(), expression)
    assert not app.exception
    assert not app.success
    assert len(app.dataframe) == 0
    assert "more than 512 states" in app.error[0].value
    app = builder_dfa(app, expression)
    assert not app.success
    assert "more than 512 states" in app.error[0].value
