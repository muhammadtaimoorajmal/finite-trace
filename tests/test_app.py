"""Smoke tests for the Streamlit application using Streamlit's AppTest."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def run_app() -> AppTest:
    app = AppTest.from_file(APP_PATH, default_timeout=30)
    app.run()
    return app


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
    assert app.button, "expected placeholder buttons to be rendered"
    assert all(button.disabled for button in app.button)
    assert all(text_input.disabled for text_input in app.text_input)
