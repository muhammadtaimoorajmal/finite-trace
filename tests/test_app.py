"""Smoke and interaction tests for the Streamlit application using Streamlit's AppTest."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")

# Controls that are allowed to be enabled (the regular expression parser).
PARSER_WIDGET_KEYS = {"regex_input", "parse_button"}


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

    tab_labels = [tab.label for tab in app.tabs]
    assert tab_labels == ["Automata Builder", "String Simulator", "NFA to DFA Converter"]


def test_unfinished_controls_are_disabled():
    app = run_app()
    other_buttons = [b for b in app.button if b.key not in PARSER_WIDGET_KEYS]
    other_inputs = [t for t in app.text_input if t.key not in PARSER_WIDGET_KEYS]
    assert other_buttons, "expected placeholder buttons to be rendered"
    assert all(button.disabled for button in other_buttons)
    assert all(text_input.disabled for text_input in other_inputs)
    labels = {button.label for button in app.button}
    assert "Generate automaton" in labels


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
    assert [tab.label for tab in app.tabs] == ["Automata Builder", "String Simulator", "NFA to DFA Converter"]
    subheaders = [block.value for block in app.subheader]
    assert subheaders == ["Automata Builder", "String Simulator", "NFA to DFA Converter"]
    assert app.success  # the parse result coexists with the other sections
