"""AppTest workflows for the Module 05 input modes and manual-NFA conversion."""

from test_app import (
    ALL_TABS,
    builder_dfa,
    convert_in_app,
    frame_with_column,
    generate_in_app,
    parse_in_app,
    run_app,
)

EVEN_ZEROS = {
    "manual_type": "DFA", "manual_alphabet": "0,1", "manual_states": "q0,q1", "manual_initial": "q0",
    "manual_accepting": "q0", "manual_transitions": "q0,0,q1\nq0,1,q0\nq1,0,q0\nq1,1,q1",
}
EPSILON_NFA = {
    "manual_type": "NFA", "manual_alphabet": "a,b", "manual_states": "q0,q1,q2,q3", "manual_initial": "q0",
    "manual_accepting": "q3", "manual_transitions": "q0,ε,q1\nq0,ε,q2\nq1,a,q3\nq2,b,q3",
}


def set_manual(app, fields):
    for key, value in fields.items():
        if key == "manual_type":
            app.radio(key=key).set_value(value)
        elif key == "manual_transitions":
            app.text_area(key=key).input(value)
        else:
            app.text_input(key=key).input(value)
    app.button(key="manual_build").click()
    return app.run()


def generate_rule(app, alphabet, rule, output="DFA", pattern=None, symbol=None, count=None):
    app.text_input(key="lang_alphabet").input(alphabet)
    app.selectbox(key="lang_rule").select(rule)
    app.run()  # show the fields this rule needs
    if pattern is not None:
        app.text_input(key="lang_pattern").input(pattern)
    if symbol is not None:
        app.text_input(key="lang_symbol").input(symbol)
    if count is not None:
        app.number_input(key="lang_count").set_value(count)
    app.radio(key="lang_output").set_value(output)
    app.button(key="lang_generate").click()
    return app.run()


def successes(app):
    return [s.value for s in app.success]


def test_all_input_modes_render_with_unique_controls():
    app = run_app()
    assert not app.exception
    assert [t.label for t in app.tabs] == ALL_TABS
    for key in ["regex_input", "lang_alphabet", "exact_alphabet", "exact_text", "manual_alphabet", "manual_states"]:
        assert app.text_input(key=key) is not None
    for key in ["parse_button", "lang_generate", "exact_generate", "manual_build", "convert_manual_button"]:
        assert app.button(key=key) is not None


def test_regex_mode_still_works():
    app = parse_in_app(run_app(), "(a|b)*abb")
    assert successes(app) == ["Valid expression"]
    app = generate_in_app(app, "(a|b)*abb")
    assert "14 states and 16 transitions" in successes(app)[0]
    app = builder_dfa(app, "(a|b)*abb")
    assert "DFA generated with 5 states" in successes(app)[0]


def test_language_rule_ends_with():
    app = generate_rule(run_app(), "0,1", "Ends with", pattern="01")
    assert not app.exception and not app.error
    assert successes(app) == ["DFA generated with 3 states."]
    code = [c.value for c in app.code]
    assert "{0, 1}" in code and "q0" in code and "q2" in code
    assert "All strings over {0, 1} that end with '01'." in code
    table = frame_with_column(app, "Meaning")
    assert table.to_dict("records") == [
        {"State": "→ q0", "0": "q1", "1": "q0", "Meaning": "nothing matched yet"},
        {"State": "q1", "0": "q1", "1": "q2", "Meaning": "matched '0'"},
        {"State": "★ q2", "0": "q1", "1": "q0", "Meaning": "input ends with '01'"},
    ]


def test_language_rule_shows_only_relevant_fields():
    app = run_app()
    keys = {t.key for t in app.text_input}
    assert "lang_pattern" in keys and "lang_symbol" not in keys
    app.selectbox(key="lang_rule").select("Exactly k occurrences of a symbol").run()
    keys = {t.key for t in app.text_input}
    assert "lang_symbol" in keys and "lang_pattern" not in keys
    assert app.number_input(key="lang_count") is not None


def test_parity_rule_two_states_and_nfa_output():
    app = generate_rule(run_app(), "0,1", "Even number of a symbol", symbol="0")
    assert successes(app) == ["DFA generated with 2 states."]
    app = generate_rule(app, "0,1", "Even number of a symbol", symbol="0", output="NFA")
    assert successes(app) == ["NFA generated with 2 states."]
    assert any("every DFA is also an NFA" in c.value for c in app.caption)
    table = frame_with_column(app, "Meaning")
    assert table.iloc[0]["0"] == "{q1}"  # NFA cells show destination sets


def test_exact_count_rule():
    app = generate_rule(run_app(), "0,1", "Exactly k occurrences of a symbol", symbol="0", count=3)
    assert successes(app) == ["DFA generated with 5 states."]


def test_language_rule_error_and_stale_result():
    app = generate_rule(run_app(), "0,1", "Contains substring", pattern="00")
    assert successes(app)
    app = generate_rule(app, "0,1", "Contains substring", pattern="02")
    assert not successes(app)
    assert "'2' at position 2" in app.error[0].value
    app = generate_rule(app, "0,1", "Contains substring", pattern="00")
    app.text_input(key="lang_pattern").input("000").run()
    assert not successes(app)
    assert any("inputs have changed" in c.value for c in app.caption)


def test_exact_string():
    app = run_app()
    app.text_input(key="exact_alphabet").input("a,b")
    app.text_input(key="exact_text").input("aabb")
    app.button(key="exact_generate").click()
    app.run()
    assert successes(app) == ["DFA generated with 6 states."]
    table = frame_with_column(app, "Meaning")
    assert list(table["State"]) == ["→ q0", "q1", "q2", "q3", "★ q4", "q5"]
    assert table.iloc[3].to_dict() == {"State": "q3", "a": "q5", "b": "q4", "Meaning": "matched 'aab'"}


def test_empty_exact_string():
    app = run_app()
    app.button(key="exact_generate").click()
    app.run()
    assert successes(app) == ["DFA generated with 2 states."]
    assert "ε (empty string)" in [c.value for c in app.code]


def test_manual_dfa():
    app = set_manual(run_app(), EVEN_ZEROS)
    assert not app.exception and not app.error
    assert successes(app) == ["Valid DFA (complete and deterministic) with 2 states."]
    table = frame_with_column(app, "State")
    assert table.to_dict("records") == [
        {"State": "→★ q0", "0": "q1", "1": "q0"},
        {"State": "q1", "0": "q0", "1": "q1"},
    ]


def test_manual_nfa_shows_epsilon_column():
    app = set_manual(run_app(), EPSILON_NFA)
    assert successes(app) == ["Valid NFA with 4 states."]
    table = frame_with_column(app, "ε")
    assert table.iloc[0].to_dict() == {"State": "→ q0", "a": "∅", "b": "∅", "ε": "{q1, q2}"}


def test_invalid_manual_dfa_shows_error_only():
    bad = dict(EVEN_ZEROS, manual_transitions="q0,0,q1\nq0,0,q0\nq0,1,q0\nq1,0,q0\nq1,1,q1")
    app = set_manual(run_app(), bad)
    assert not app.exception
    assert not successes(app)
    assert "line 2" in app.error[0].value and "one destination" in app.error[0].value


def test_load_example_fills_the_form():
    app = run_app()
    app.selectbox(key="manual_example").select("ε-NFA: exactly a or b")
    app.button(key="manual_load").click()
    app.run()
    assert app.text_area(key="manual_transitions").value == EPSILON_NFA["manual_transitions"]
    assert app.radio(key="manual_type").value == "NFA"


def test_manual_nfa_conversion():
    app = run_app()
    assert app.button(key="convert_manual_button").disabled  # nothing built yet
    assert any("No manual automaton yet" in i.value for i in app.info)
    app = set_manual(app, EPSILON_NFA)
    assert not app.button(key="convert_manual_button").disabled
    app.button(key="convert_manual_button").click()
    app.run()
    assert not app.exception
    assert "4-state manual NFA into a 3-state DFA" in successes(app)[-1]
    mapping = frame_with_column(app, "NFA states")
    assert mapping.to_dict("records") == [
        {"DFA state": "→ D0", "NFA states": "{q0, q1, q2}", "Type": "Initial"},
        {"DFA state": "★ D1", "NFA states": "{q3}", "Type": "Accepting"},
        {"DFA state": "D2", "NFA states": "∅", "Type": "Dead (empty subset)"},
    ]
    dfa_table = [f.value for f in app.dataframe if list(f.value.columns) == ["State", "a", "b"]][-1]
    assert dfa_table.to_dict("records") == [
        {"State": "→ D0", "a": "D1", "b": "D1"},
        {"State": "★ D1", "a": "D2", "b": "D2"},
        {"State": "D2", "a": "D2", "b": "D2"},
    ]


def test_manual_conversion_becomes_stale_after_edit():
    app = set_manual(run_app(), EPSILON_NFA)
    app.button(key="convert_manual_button").click()
    app.run()
    app.text_input(key="manual_accepting").input("q1").run()
    assert app.button(key="convert_manual_button").disabled
    assert any("changed after it was built" in i.value for i in app.info)
    assert not any("manual NFA into" in s for s in successes(app))


def test_manual_dfa_is_not_offered_for_conversion():
    app = set_manual(run_app(), EVEN_ZEROS)
    assert app.button(key="convert_manual_button").disabled
    assert any("already deterministic" in i.value for i in app.info)


def test_results_stay_with_their_mode():
    app = generate_in_app(run_app(), "ab")
    app = generate_rule(app, "a,b", "Starts with", pattern="ab")
    app = set_manual(app, EVEN_ZEROS)
    # Each mode shows its own result; none replaces another.
    found = successes(app)
    assert any("ε-NFA generated" in s for s in found)
    assert "DFA generated with 4 states." in found
    assert "Valid DFA (complete and deterministic) with 2 states." in found


def test_regex_converter_regression_and_future_controls():
    app = convert_in_app(run_app(), "(0|1)*01")
    assert "12-state ε-NFA into a 4-state DFA" in successes(app)[0]
    for label in ["▶ Play", "⏸ Pause", "⏭ Step", "↺ Reset"]:
        assert all(b.disabled for b in app.button if b.label == label)
