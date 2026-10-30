"""AppTest workflows for the String Simulator tab (Module 06)."""

from test_app import builder_dfa, convert_in_app, frame_with_column, generate_in_app, parse_in_app, run_app
from test_app_modes import EPSILON_NFA, EVEN_ZEROS, generate_rule, set_manual


def simulate_regex(app, expression, machine, text):
    app.text_input(key="sim_regex").input(expression)
    app.radio(key="sim_regex_machine").set_value(machine)
    app.text_input(key="sim_regex_text").input(text)
    app.button(key="sim_regex_button").click()
    return app.run()


def simulate_saved(app, prefix, label_part, text):
    box = app.selectbox(key=f"{prefix}_choice")
    matches = [option for option in box.options if label_part in option]
    assert matches, f"{label_part!r} not offered; options were {box.options}"
    box.select(matches[0])
    app.text_input(key=f"{prefix}_text").input(text)
    app.button(key=f"{prefix}_button").click()
    return app.run()


def verdicts(app):
    accepted = [s.value for s in app.success if s.value.startswith("**Accepted**")]
    rejected = [w.value for w in app.warning if w.value.startswith("**Rejected**")]
    return accepted, rejected


def test_a_direct_regex_dfa_accepts():
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    assert not app.exception and not app.error
    accepted, rejected = verdicts(app)
    assert len(accepted) == 1 and not rejected
    assert "final state D4 is accepting" in accepted[0]
    trace = frame_with_column(app, "From")
    assert list(trace["To"]) == ["D0", "D1", "D1", "D3", "D4"]
    assert list(trace["Read"]) == ["Start", "a", "a", "b", "b"]


def test_b_direct_regex_nfa_shows_active_sets_and_epsilon():
    app = simulate_regex(run_app(), "(a|b)*abb", "NFA", "aabb")
    accepted, _ = verdicts(app)
    assert accepted and "accepting state q13" in accepted[0]
    trace = frame_with_column(app, "Active after ε-closure")
    assert trace.iloc[0]["Active after ε-closure"] == "{q0, q2, q4, q6, q7, q8}"
    assert trace.iloc[0]["ε-transitions"] != "—"
    assert trace.iloc[1]["move"] == "{q1, q9}"
    assert len(trace) == 5


def test_c_rejected_string():
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "abab")
    accepted, rejected = verdicts(app)
    assert not accepted and len(rejected) == 1
    assert "is not accepting" in rejected[0]


def test_d_empty_string():
    app = simulate_regex(run_app(), "a*", "NFA", "")
    accepted, _ = verdicts(app)
    assert accepted
    assert "ε (empty string)" in [c.value for c in app.code]
    app = simulate_regex(app, "a+", "NFA", "")
    assert verdicts(app)[1]


def test_e_invalid_alphabet_hides_previous_result():
    app = simulate_regex(run_app(), "a*", "DFA", "aa")
    assert verdicts(app)[0]
    app = simulate_regex(app, "a*", "DFA", "ab")
    assert verdicts(app) == ([], [])
    assert "symbol 'b' at position 2 is not in the alphabet {a}" in app.error[0].value


def test_invalid_regex_in_simulator():
    app = simulate_regex(run_app(), "a||b", "NFA", "a")
    assert "position 3" in app.error[0].value
    assert verdicts(app) == ([], [])


def test_f_language_rule_automaton():
    app = generate_rule(run_app(), "0,1", "Ends with", pattern="01")
    app = simulate_saved(app, "sim_builder", "Language Rule → DFA", "1101")
    assert verdicts(app)[0]


def test_g_exact_string_automaton():
    app = run_app()
    app.text_input(key="exact_alphabet").input("a,b")
    app.text_input(key="exact_text").input("aabb")
    app.button(key="exact_generate").click()
    app.run()
    app = simulate_saved(app, "sim_builder", "Exact String", "aabb")
    assert verdicts(app)[0]
    app = simulate_saved(app, "sim_builder", "Exact String", "aabba")
    assert verdicts(app)[1]


def test_h_manual_dfa():
    app = set_manual(run_app(), EVEN_ZEROS)
    app = simulate_saved(app, "sim_builder", "Manual Automaton → DFA", "1010")
    accepted, _ = verdicts(app)
    assert accepted and "final state q0 is accepting" in accepted[0]
    trace = frame_with_column(app, "From")
    assert list(trace["To"]) == ["q0", "q0", "q1", "q1", "q0"]


def test_i_manual_nfa():
    app = set_manual(run_app(), EPSILON_NFA)
    app = simulate_saved(app, "sim_builder", "Manual Automaton → NFA", "a")
    assert verdicts(app)[0]


def test_regex_builder_results_are_offered():
    app = generate_in_app(run_app(), "(a|b)*abb")
    app = simulate_saved(app, "sim_builder", "Regular Expression → ε-NFA", "babb")
    assert verdicts(app)[0]
    app = builder_dfa(app, "(0|1)*01")
    app = simulate_saved(app, "sim_builder", "Regular Expression → DFA", "011")
    assert verdicts(app)[1]


def test_j_converted_dfa():
    app = convert_in_app(run_app(), "(0|1)*01")
    app = simulate_saved(app, "sim_converted", "Converted from regular expression", "1101")
    assert verdicts(app)[0]
    app = set_manual(app, EPSILON_NFA)
    app.button(key="convert_manual_button").click()
    app.run()
    app = simulate_saved(app, "sim_converted", "Converted from manual NFA", "b")
    assert verdicts(app)[0]


def test_k_changed_test_string_hides_old_result():
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    app.text_input(key="sim_regex_text").input("aab").run()
    assert verdicts(app) == ([], [])
    assert any("has changed" in c.value for c in app.caption)
    app.button(key="sim_regex_button").click()
    app.run()
    assert verdicts(app)[1]


def test_changed_machine_type_hides_old_result():
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    app.radio(key="sim_regex_machine").set_value("NFA").run()
    assert verdicts(app) == ([], [])


def test_l_changed_source_hides_old_result():
    app = set_manual(run_app(), EVEN_ZEROS)
    app = generate_rule(app, "0,1", "Contains substring", pattern="00")
    app = simulate_saved(app, "sim_builder", "Manual Automaton", "1010")
    assert verdicts(app)[0]
    other = [o for o in app.selectbox(key="sim_builder_choice").options if "Language Rule" in o][0]
    app.selectbox(key="sim_builder_choice").select(other).run()
    assert verdicts(app) == ([], [])


def test_edited_builder_input_removes_stale_automaton():
    app = set_manual(run_app(), EVEN_ZEROS)
    assert any("Manual Automaton" in o for o in app.selectbox(key="sim_builder_choice").options)
    app.text_input(key="manual_accepting").input("q1").run()
    assert not app.selectbox(key="sim_builder_choice").options
    assert app.button(key="sim_builder_button").disabled
    assert any("No Builder automaton is available" in i.value for i in app.info)


def test_m_existing_features_still_work():
    app = parse_in_app(run_app(), "(a|b)*abb")
    assert [s.value for s in app.success] == ["Valid expression"]
    app = generate_in_app(app, "(a|b)*abb")
    assert any("ε-NFA generated" in s.value for s in app.success)
    app = builder_dfa(app, "(a|b)*abb")
    assert any("DFA generated with 5 states" in s.value for s in app.success)
    app = convert_in_app(app, "(0|1)*01")
    assert any("4-state DFA" in s.value for s in app.success)


def test_n_playback_controls_are_live_after_simulating():
    # Module 08 replaced the disabled animation placeholders with working controls.
    app = simulate_regex(run_app(), "a*", "NFA", "aa")
    controls = {b.label: b for b in app.button if b.key and b.key.startswith("sim_regex_outcome_playback_")}
    assert set(controls) == {"↺ Reset", "⏮ Previous", "▶ Play", "⏸ Pause", "⏭ Next", "⟳ Replay"}
    assert not controls["▶ Play"].disabled and not controls["⏭ Next"].disabled
    assert controls["⏮ Previous"].disabled and controls["⏸ Pause"].disabled


def test_saved_source_selects_automaton_that_appears_later():
    # Regression: the dropdown is first drawn with no options (value None). When an automaton
    # becomes available later it must be selected automatically, so Simulate String works
    # without the user having to open the dropdown first.
    app = set_manual(run_app(), EPSILON_NFA)
    assert app.selectbox(key="sim_builder_choice").value is not None
    app.text_input(key="sim_builder_text").input("a")
    app.button(key="sim_builder_button").click()
    app.run()
    assert verdicts(app)[0]


def test_newly_built_automaton_is_selected_automatically():
    # A Builder result that appears after others is selected, so "build, then simulate"
    # works without opening the dropdown.
    app = set_manual(run_app(), EVEN_ZEROS)
    assert app.selectbox(key="sim_builder_choice").value.startswith("Manual Automaton")
    app = generate_rule(app, "0,1", "Ends with", pattern="01")
    assert app.selectbox(key="sim_builder_choice").value.startswith("Language Rule")
    app.text_input(key="sim_builder_text").input("101")
    app.button(key="sim_builder_button").click()
    app.run()
    assert verdicts(app)[0]
    # An explicit choice is kept while the available automata do not change.
    manual = [o for o in app.selectbox(key="sim_builder_choice").options if o.startswith("Manual")][0]
    app.selectbox(key="sim_builder_choice").select(manual).run()
    app.text_input(key="sim_builder_text").input("00").run()
    assert app.selectbox(key="sim_builder_choice").value == manual
