"""
Interactive playback of a SimulationResult: play, pause, step and reset.

The animation is a presentation layer over the trace that core/simulator.py
already computed. Frame i shows SimulationStep i: its active states and the
symbol and ε-transitions it used are highlighted on the existing diagram. No
simulation happens here, so the animation can never disagree with the verdict.

PlaybackState and the functions below are plain Python (no Streamlit), with
the clock passed in as `now` so the timing rules can be unit-tested:

    - one frame per SimulationStep: step 0 is the start, step i has read i characters
    - while playing, a frame advances only after `seconds_per_step` have passed,
      and never more than one frame per update, so a late update cannot skip frames
    - playback stops by itself on the last frame
    - Next / Previous pause playback and move exactly one frame
    - changing speed keeps the current frame and restarts the step timer

Automatic playback uses st.fragment(run_every=...): only the animation panel
reruns on a timer (four checks per step), and only while playing. A fragment's timer is fixed when it
is created, so when play/pause/speed changes what the timer should be, the
panel requests one full rerun to recreate the fragment with the new timer.
"""

import html
import time
from dataclasses import dataclass
from typing import Optional

import streamlit as st

from core.automata import DFA, FiniteAutomaton
from core.converter import format_subset
from core.simulator import SimulationResult
from ui.visualizer import is_too_large, render_automaton_diagram

# Seconds per step. There is no zero option, so playback can never busy-loop.
SPEEDS = {"Slow (2 s)": 2.0, "Normal (1 s)": 1.0, "Fast (0.5 s)": 0.5, "Very fast (0.25 s)": 0.25}
DEFAULT_SPEED = "Normal (1 s)"
MIN_SECONDS_PER_STEP = 0.1

READY, PLAYING, PAUSED, COMPLETED = "Ready", "Playing", "Paused", "Completed"


@dataclass
class PlaybackState:
    run_id: int                 # identifies the simulation run this playback belongs to
    total_steps: int            # len(SimulationResult.steps), at least 1
    current_step: int = 0
    playing: bool = False
    seconds_per_step: float = 1.0
    last_advance: float = 0.0   # monotonic time of the last frame change while playing

    @property
    def last_index(self) -> int:
        return self.total_steps - 1

    @property
    def at_end(self) -> bool:
        return self.current_step >= self.last_index

    @property
    def status(self) -> str:
        if self.playing:
            return PLAYING
        if self.at_end:
            return COMPLETED
        return READY if self.current_step == 0 else PAUSED


def new_playback(run_id: int, total_steps: int, seconds_per_step: float = SPEEDS[DEFAULT_SPEED]) -> PlaybackState:
    if total_steps < 1:
        raise ValueError("A simulation always has at least step 0.")
    return PlaybackState(run_id=run_id, total_steps=total_steps, seconds_per_step=_valid_speed(seconds_per_step))


def _valid_speed(seconds: float) -> float:
    if not seconds >= MIN_SECONDS_PER_STEP:
        raise ValueError(f"Seconds per step must be at least {MIN_SECONDS_PER_STEP}.")
    return float(seconds)


def start_playback(state: PlaybackState, now: float) -> None:
    """Play from the current frame. Does nothing on the last frame (use replay)."""
    if state.at_end:
        state.playing = False
        return
    state.playing = True
    state.last_advance = now


def pause_playback(state: PlaybackState) -> None:
    state.playing = False


def next_step(state: PlaybackState) -> None:
    state.playing = False
    state.current_step = min(state.current_step + 1, state.last_index)


def previous_step(state: PlaybackState) -> None:
    state.playing = False
    state.current_step = max(state.current_step - 1, 0)


def reset_playback(state: PlaybackState) -> None:
    state.playing = False
    state.current_step = 0


def replay_playback(state: PlaybackState, now: float) -> None:
    reset_playback(state)
    start_playback(state, now)


def set_speed(state: PlaybackState, seconds: float, now: float) -> None:
    """Change the interval; the frame is kept and the step timer restarts from now."""
    state.seconds_per_step = _valid_speed(seconds)
    state.last_advance = now


def advance_playback(state: PlaybackState, now: float) -> bool:
    """Move one frame forward if playing and a full interval has passed. Returns True if it moved."""
    if not state.playing:
        return False
    if state.at_end:
        state.playing = False
        return False
    if now - state.last_advance < state.seconds_per_step:
        return False
    state.current_step += 1
    state.last_advance = now  # measure the next interval from this frame; no catch-up bursts
    if state.at_end:
        state.playing = False
    return True


def frame_highlights(simulation: SimulationResult, index: int):
    """States and edges to highlight for frame `index`: exactly what that step recorded."""
    step = simulation.steps[index]
    return step.active_after, step.symbol_edges + step.epsilon_edges


# ---------------------------------------------------------------------------
# Streamlit panel
# ---------------------------------------------------------------------------

def _tick_interval(state: PlaybackState) -> Optional[float]:
    """
    How often the panel reruns: four times per step while playing, never otherwise. A frame
    still advances only once a full interval has passed, so each step takes between the
    chosen interval and a quarter-interval more (browser timers are not exact).
    """
    if not state.playing:
        return None
    return max(state.seconds_per_step / 4, MIN_SECONDS_PER_STEP)


def playback_for(key: str, run_id: int, total_steps: int) -> PlaybackState:
    """The session's playback for this run, starting a fresh one (at step 0) for a new run."""
    state = st.session_state.get(key)
    if state is None or state.run_id != run_id or state.total_steps != total_steps:
        speed = SPEEDS.get(st.session_state.get(f"{key}_speed", DEFAULT_SPEED), SPEEDS[DEFAULT_SPEED])
        state = new_playback(run_id, total_steps, speed)
        st.session_state[key] = state
    return state


def stop_playback(key: str) -> None:
    """Stop a playback whose simulation is no longer current (e.g. its input was edited)."""
    state = st.session_state.get(key)
    if state is not None:
        state.playing = False


def input_tape_html(text: str, consumed: int) -> str:
    """The test string with consumed characters dimmed and the one just read outlined (HTML-escaped)."""
    if not text:
        return '<span style="color:#94a3b8">ε (empty string): nothing to read</span>'
    cells = []
    for index, character in enumerate(text):
        if index < consumed - 1:
            style = "color:#64748b;background:#1e293b;border:1px solid #334155"
        elif index == consumed - 1:
            style = "color:#0f172a;background:#fbbf24;border:1px solid #fbbf24;font-weight:700"
        else:
            style = "color:#e2e8f0;background:#0f172a;border:1px solid #475569"
        cells.append(
            f'<span style="display:inline-block;min-width:1.6em;padding:2px 6px;margin:1px;'
            f'border-radius:4px;text-align:center;font-family:monospace;{style}">{html.escape(character)}</span>'
        )
    return "".join(cells)


def _render_controls(key: str, state: PlaybackState) -> None:
    def act(action):
        def callback():
            now = time.monotonic()
            {
                "play": lambda: start_playback(state, now),
                "pause": lambda: pause_playback(state),
                "previous": lambda: previous_step(state),
                "next": lambda: next_step(state),
                "reset": lambda: reset_playback(state),
                "replay": lambda: replay_playback(state, now),
            }[action]()
        return callback

    single = state.total_steps == 1
    columns = st.columns(6)
    columns[0].button("↺ Reset", key=f"{key}_reset", on_click=act("reset"), width="stretch",
                      disabled=state.current_step == 0 and not state.playing, help="Back to step 0 and stop")
    columns[1].button("⏮ Previous", key=f"{key}_previous", on_click=act("previous"), width="stretch",
                      disabled=state.current_step == 0, help="One step back")
    columns[2].button("▶ Play", key=f"{key}_play", on_click=act("play"), width="stretch", type="primary",
                      disabled=state.playing or state.at_end, help="Play from the current step")
    columns[3].button("⏸ Pause", key=f"{key}_pause", on_click=act("pause"), width="stretch",
                      disabled=not state.playing, help="Stop at the current step")
    columns[4].button("⏭ Next", key=f"{key}_next", on_click=act("next"), width="stretch",
                      disabled=state.at_end, help="One step forward")
    columns[5].button("⟳ Replay", key=f"{key}_replay", on_click=act("replay"), width="stretch",
                      disabled=single, help="Restart from step 0 and play")

    def change_speed():
        set_speed(state, SPEEDS[st.session_state[f"{key}_speed"]], time.monotonic())

    st.session_state.setdefault(f"{key}_speed", DEFAULT_SPEED)
    st.select_slider("Playback speed", options=list(SPEEDS), key=f"{key}_speed",
                     on_change=change_speed, help="Time between steps while playing.")


def _render_frame(key: str, automaton: FiniteAutomaton, simulation: SimulationResult, state: PlaybackState) -> None:
    index = state.current_step
    step = simulation.steps[index]
    length = len(simulation.input_string)

    st.markdown(f"**Step {index} of {length}** · {state.status}")
    st.progress(index / length if length else 1.0, text=f"Input consumed: {index} of {length} characters")
    st.markdown(input_tape_html(simulation.input_string, index), unsafe_allow_html=True)

    _render_controls(key, state)

    active, edges = frame_highlights(simulation, index)
    if is_too_large(automaton):
        st.info("This automaton is too large to draw, so states cannot be highlighted on a diagram. "
                "The current step is described below, and the full trace and transition table remain available.",
                icon="ℹ️")
    else:
        render_automaton_diagram(automaton, key=f"{key}_diagram", highlight_states=active, highlight_edges=edges)

    with st.container(border=True):
        left, right = st.columns(2)
        with left:
            st.markdown("**Reading**")
            st.code("— (start, no input consumed)" if step.symbol is None else f"'{step.symbol}' at position {step.position}",
                    language=None)
            st.markdown("**Active before**")
            st.code(format_subset(step.active_before) if index else "—", language=None, wrap_lines=True)
        with right:
            label = "Current state" if simulation.machine_type == DFA else "Active states (after ε-closure)"
            st.markdown(f"**{label}**")
            st.code(format_subset(active), language=None, wrap_lines=True)
            st.markdown("**Transitions highlighted**")
            followed = [f"{s} --{'ε' if x is None else x}--> {t}" for s, x, t in edges]
            st.code(", ".join(followed) if followed else "none", language=None, wrap_lines=True)
        st.caption(step.explanation)

    if state.at_end:
        if simulation.accepted:
            st.success(f"**Final configuration: Accepted.** {simulation.explanation.removeprefix('Accepted: ')}", icon="✅")
        else:
            st.warning(f"**Final configuration: Rejected.** {simulation.explanation.removeprefix('Rejected: ')}", icon="❌")


def render_animation(key: str, automaton: FiniteAutomaton, simulation: SimulationResult, run_id: int) -> None:
    """Interactive playback panel for one simulation run. `key` must be unique per source."""
    st.markdown("#### Interactive simulation")
    state = playback_for(key, run_id, len(simulation.steps))
    scheduled = _tick_interval(state)

    def panel() -> None:
        live = st.session_state.get(key)
        if live is None or live.run_id != run_id:
            return  # a newer simulation replaced this one; the next full run shows it
        advance_playback(live, time.monotonic())
        _render_frame(key, automaton, simulation, live)
        if _tick_interval(live) != scheduled:
            # Play/pause/speed/finish changed the timer this fragment needs: recreate it.
            st.rerun(scope="app")

    st.fragment(panel, run_every=scheduled)()
