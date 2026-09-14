"""Textual review application: cuts, labels, package metadata, waveform, playback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)

from dat_tracker.audio_playback import AudioPlayer, loop_window_around_cut
from dat_tracker.review_edits import (
    delete_mid_cut,
    insert_mid_cut,
    nudge_cut,
    set_package_field,
    set_track_field,
)
from dat_tracker.review_baseline import (
    ensure_as_delivered_snapshot,
    require_as_delivered,
    reset_plan_to_as_delivered,
)
from dat_tracker.review_plan import approve_plan, migrate_tracking_plan
from dat_tracker.review_hydrate import (
    hydrate_plan_from_notes,
    hydrate_titles_from_published_setlist,
    reconcile_track_count_to_published_setlist,
    seed_package_metadata,
)
from dat_tracker.review_package_polish import polish_package_metadata
from dat_tracker.tui_review.widgets.package_form import (
    PACKAGE_FIELD_ORDER,
    package_field_tooltip,
    package_form_values,
)
from dat_tracker.tui_review.widgets.track_table import format_track_rows
from dat_tracker.tui_review.widgets.waveform import DetailWaveformView, WaveformView
from dat_tracker.waveform import load_or_build_envelope

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _format_hear_clock(sec: float) -> str:
    """Show minutes:seconds.tenths for the live hearing cursor."""
    sec = max(0.0, float(sec))
    m = int(sec // 60)
    s = sec % 60.0
    return f"{m}:{s:04.1f}"


class ReviewApp(App[int]):
    """Required review gate UI with Accept-all fast path."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #toolbar {
        height: 3;
        dock: top;
    }
    #package-row {
        height: 14;
        padding: 0 1;
        border: solid $panel;
    }
    #package-row .pkg-label {
        width: 11;
        height: 1;
        content-align: left middle;
        color: $text-muted;
    }
    #package-row .pkg-input {
        width: 1fr;
        height: 1;
    }
    #package-row .pkg-pair {
        height: 1;
        margin: 0 0 1 0;
    }
    #tracks {
        height: 10;
    }
    #overview {
        height: 8;
    }
    #detail {
        height: 10;
    }
    #status {
        dock: bottom;
        height: 1;
        background: $surface;
    }
    #track-edit {
        height: 3;
    }
    #track-edit .pkg-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("a", "accept_all", "Accept-all", show=True),
        Binding("s", "save_approve", "Save&approve", show=True),
        Binding("r", "reset_llm", "Reset LLM", show=True),
        Binding("q", "quit_pending", "Quit", show=True),
        Binding("left", "nudge_left", "Nudge ←", show=True),
        Binding("right", "nudge_right", "Nudge →", show=True),
        Binding("shift+left", "nudge_left_large", "Nudge -1s", show=False),
        Binding("shift+right", "nudge_right_large", "Nudge +1s", show=False),
        Binding("ctrl+left", "nudge_left_fine", "Nudge -0.01s", show=False),
        Binding("ctrl+right", "nudge_right_fine", "Nudge +0.01s", show=False),
        Binding("[", "prev_cut", "Prev cut", show=True),
        Binding("]", "next_cut", "Next cut", show=True),
        Binding("i", "insert_cut", "Insert cut", show=False),
        Binding("d", "delete_cut", "Delete cut", show=False),
        Binding("space", "toggle_play", "Play/Pause", show=True),
        Binding("l", "loop_cut", "Loop cut", show=True),
        Binding("j", "seek_back", "Seek -2s", show=False),
        Binding("k", "seek_forward", "Seek +2s", show=False),
    ]

    def __init__(
        self,
        *,
        plan_path: Path,
        plan: dict[str, Any],
        source_audio: Path | None = None,
        approved_by: str | None = None,
    ) -> None:
        super().__init__()
        self.plan_path = Path(plan_path)
        self.plan = migrate_tracking_plan(plan)
        # Snapshot before hydrate so a first-open legacy dir keeps the
        # on-disk LLM lattice (not titles we fill in-memory).
        ensure_as_delivered_snapshot(self.plan_path, self.plan)
        self.plan = hydrate_plan_from_notes(self.plan)
        self.plan = reconcile_track_count_to_published_setlist(
            self.plan, project_root=_REPO_ROOT
        )
        self.plan = hydrate_titles_from_published_setlist(
            self.plan, project_root=_REPO_ROOT
        )
        self.plan = seed_package_metadata(self.plan, project_root=_REPO_ROOT)
        # Known spelling fixes always; Gemini text polish when API key present.
        self.plan = polish_package_metadata(
            self.plan, project_root=_REPO_ROOT, use_llm=True
        )
        self.source_audio = Path(source_audio) if source_audio else None
        self.approved_by = approved_by
        self.dirty = False
        self.selected_cut_index = 1 if len(self.plan.get("cuts_sec") or []) > 2 else 0
        self.selected_track_index = 1
        self.exit_code = 1
        self._envelope: dict[str, Any] | None = None
        self._player = AudioPlayer()
        self._playhead: float | None = None
        self._play_timer = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="toolbar"):
            yield Button("Accept-all", id="btn-accept", variant="success")
            yield Button("Save & approve", id="btn-save", variant="primary")
            yield Button("Reset to LLM", id="btn-reset")
            yield Button("Quit", id="btn-quit")
            yield Label(self.plan.get("show_id") or "", id="show-id")
        with VerticalScroll(id="package-row"):
            # Compact Inputs (height 1). Default Input height is 3 and was
            # clipped by pkg-pair height:1 — values invisible / not editable.
            keys = list(PACKAGE_FIELD_ORDER)
            vals = package_form_values(self.plan)
            for i in range(0, len(keys), 2):
                with Horizontal(classes="pkg-pair"):
                    left = keys[i]
                    tip_l = package_field_tooltip(left)
                    lbl = Label(f"{left}:", classes="pkg-label")
                    lbl.tooltip = tip_l
                    yield lbl
                    inp = Input(
                        value=vals.get(left, ""),
                        id=f"pkg-{left}",
                        classes="pkg-input",
                        compact=True,
                    )
                    inp.tooltip = tip_l
                    yield inp
                    if i + 1 < len(keys):
                        right = keys[i + 1]
                        tip_r = package_field_tooltip(right)
                        lbl_r = Label(f"{right}:", classes="pkg-label")
                        lbl_r.tooltip = tip_r
                        yield lbl_r
                        inp_r = Input(
                            value=vals.get(right, ""),
                            id=f"pkg-{right}",
                            classes="pkg-input",
                            compact=True,
                        )
                        inp_r.tooltip = tip_r
                        yield inp_r
        yield DataTable(id="tracks")
        yield WaveformView(id="overview")
        yield DetailWaveformView(id="detail")
        with Horizontal(id="track-edit"):
            yield Label("Title:")
            yield Input(id="track-title", classes="pkg-input")
            yield Label("Type:")
            yield Select(
                options=[
                    ("song", "song"),
                    ("banter", "banter"),
                    ("tuning", "tuning"),
                    ("intro", "intro"),
                    ("encore_break", "encore_break"),
                    ("unknown", "unknown"),
                ],
                id="track-type",
                value="song",
                allow_blank=False,
            )
            yield Button("Toggle segue", id="btn-segue")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tracks", DataTable)
        table.add_columns("Idx", "Type", "Title", "Segue", "Dur")
        table.cursor_type = "row"
        self._sync_package_editors()
        self._reload_tracks()
        self._sync_track_editors()
        self._set_status("Loading waveform…")
        self._load_envelope()
        self._refresh_waveforms()
        pkg_filled = sum(1 for v in package_form_values(self.plan).values() if v)
        self._set_status(
            f"Ready — Accept-all (a) or edit then Save & approve (s)"
            + (f" | {pkg_filled} package fields seeded" if pkg_filled else "")
        )

    def _sync_package_editors(self) -> None:
        """Push plan.package into Inputs after mount."""
        vals = package_form_values(self.plan)
        for key in PACKAGE_FIELD_ORDER:
            self.query_one(f"#pkg-{key}", Input).value = vals.get(key, "")

    def _load_envelope(self) -> None:
        if self.source_audio is None or not self.source_audio.is_file():
            self._envelope = None
            return
        cache = self.plan_path.parent / "waveform_envelope.npz"
        try:
            self._envelope = load_or_build_envelope(
                self.source_audio, cache_path=cache, bucket_count=2000
            )
        except Exception as exc:  # noqa: BLE001 — show in status, keep UI up
            self._envelope = None
            self._set_status(f"Waveform unavailable: {exc}")

    def _reload_tracks(self) -> None:
        table = self.query_one("#tracks", DataTable)
        table.clear()
        for row in format_track_rows(self.plan):
            table.add_row(*row)

    def _refresh_waveforms(self) -> None:
        cuts = [float(c) for c in self.plan.get("cuts_sec") or []]
        overview = self.query_one("#overview", WaveformView)
        detail = self.query_one("#detail", DetailWaveformView)
        if not self._envelope:
            overview.label = "waveform (no source audio)"
            overview.peaks = []
            overview.refresh()
            return
        hearing = self._player.hearing_window
        playing = self._player.is_playing and hearing is not None
        if playing and hearing is not None and self._playhead is not None:
            overview.label = (
                f"overview — HEARING {_format_hear_clock(self._playhead)}  "
                f"(loop {_format_hear_clock(hearing[0])}–"
                f"{_format_hear_clock(hearing[1])}; cyan ▶)"
            )
        else:
            overview.label = (
                "overview — click a yellow cut, then ←/→ (±0.1s) "
                "([ / ] select; shift←/→ ±1s)"
            )
        overview.set_envelope(self._envelope)
        overview.absolute_markers = cuts
        overview.markers_sec = cuts
        overview.playhead_sec = self._playhead
        selected = (
            cuts[self.selected_cut_index]
            if cuts and 0 <= self.selected_cut_index < len(cuts)
            else None
        )
        overview.selected_marker_sec = selected
        if playing and hearing is not None:
            # Lock detail to the audible loop so only the cyan cursor moves.
            hear_start, hear_end = hearing
            center = (hear_start + hear_end) / 2.0
            half = max(0.5, (hear_end - hear_start) / 2.0)
            window = detail.set_detail(
                self._envelope,
                center_sec=center,
                half_window_sec=half,
                markers_sec=cuts,
                playhead_sec=self._playhead,
                selected_marker_sec=selected,
            )
            overview.viewport_sec = hearing
        else:
            center = selected if selected is not None else 0.0
            window = detail.set_detail(
                self._envelope,
                center_sec=center,
                half_window_sec=20.0,
                markers_sec=cuts,
                playhead_sec=self._playhead,
                selected_marker_sec=selected,
            )
            overview.viewport_sec = window
        overview.refresh()

    def _refresh_playhead_only(self) -> None:
        """Move the cyan cursor without rebuilding waveform envelopes."""
        overview = self.query_one("#overview", WaveformView)
        detail = self.query_one("#detail", DetailWaveformView)
        overview.playhead_sec = self._playhead
        if self._playhead is not None:
            detail.playhead_sec = float(self._playhead) - float(
                detail.window_start_sec
            )
            detail.absolute_playhead = self._playhead
        else:
            detail.playhead_sec = None
            detail.absolute_playhead = None
        if self._playhead is not None:
            hearing = self._player.hearing_window
            if hearing is not None:
                overview.label = (
                    f"overview — HEARING {_format_hear_clock(self._playhead)}  "
                    f"(loop {_format_hear_clock(hearing[0])}–"
                    f"{_format_hear_clock(hearing[1])}; cyan ▶)"
                )
        overview.refresh()
        detail.refresh()

    def _start_play_ui(self) -> None:
        self._stop_play_ui()
        # Full layout once, then light cursor ticks (~40 Hz).
        self._refresh_waveforms()
        self._play_timer = self.set_interval(0.025, self._on_play_tick)

    def _stop_play_ui(self) -> None:
        if self._play_timer is not None:
            self._play_timer.stop()
            self._play_timer = None

    def _on_play_tick(self) -> None:
        err = self._player.last_error
        if err:
            self._stop_play_ui()
            self._set_status(f"Playback error: {err}")
            self._refresh_waveforms()
            return
        if not self._player.is_playing:
            self._stop_play_ui()
            self._set_status("Playback finished")
            self._refresh_waveforms()
            return
        pos = self._player.current_position_sec()
        if pos is not None:
            self._playhead = pos
        hearing = self._player.hearing_window
        self._refresh_playhead_only()
        if hearing is not None and pos is not None:
            self._set_status(
                f"Hearing {_format_hear_clock(pos)}  "
                f"loop {_format_hear_clock(hearing[0])}–"
                f"{_format_hear_clock(hearing[1])}  (space stop)"
            )

    def _sync_track_editors(self) -> None:
        tracks = self.plan.get("tracks") or []
        track = next(
            (t for t in tracks if int(t["index"]) == self.selected_track_index),
            tracks[0] if tracks else None,
        )
        if not track:
            return
        self.query_one("#track-title", Input).value = str(track.get("title") or "")
        try:
            self.query_one("#track-type", Select).value = str(
                track.get("track_type") or "song"
            )
        except Exception:
            pass

    def _set_status(self, msg: str) -> None:
        dirty = " [dirty]" if self.dirty else ""
        cuts = self.plan.get("cuts_sec") or []
        cut_t = (
            f"cut[{self.selected_cut_index}]={cuts[self.selected_cut_index]:.3f}s"
            if cuts and 0 <= self.selected_cut_index < len(cuts)
            else ""
        )
        play = " playing" if self._player.is_playing else ""
        self.query_one("#status", Static).update(
            f"{msg}{dirty} | {cut_t}{play}"
        )

    def _write_plan(self, plan: dict[str, Any]) -> None:
        self.plan_path.write_text(json.dumps(plan, indent=2) + "\n")

    def _collect_package_from_inputs(self) -> None:
        fields: dict[str, Any] = {}
        for key in PACKAGE_FIELD_ORDER:
            widget = self.query_one(f"#pkg-{key}", Input)
            text = widget.value.strip()
            fields[key] = text if text else None
        self.plan = set_package_field(self.plan, **fields)

    def _apply_track_editors(self) -> None:
        title = self.query_one("#track-title", Input).value.strip()
        track_type = self.query_one("#track-type", Select).value
        self.plan = set_track_field(
            self.plan,
            track_index=self.selected_track_index,
            title=title if title else None,
            track_type=str(track_type) if track_type else None,
        )

    @on(Button.Pressed, "#btn-accept")
    def _btn_accept(self) -> None:
        self.action_accept_all()

    @on(Button.Pressed, "#btn-save")
    def _btn_save(self) -> None:
        self.action_save_approve()

    @on(Button.Pressed, "#btn-reset")
    def _btn_reset(self) -> None:
        self.action_reset_llm()

    @on(Button.Pressed, "#btn-quit")
    def _btn_quit(self) -> None:
        self.action_quit_pending()

    @on(Button.Pressed, "#btn-segue")
    def _btn_segue(self) -> None:
        tracks = self.plan.get("tracks") or []
        track = next(
            (t for t in tracks if int(t["index"]) == self.selected_track_index),
            None,
        )
        if not track:
            return
        self.plan = set_track_field(
            self.plan,
            track_index=self.selected_track_index,
            segue_into_next=not bool(track.get("segue_into_next")),
        )
        self.dirty = True
        self._reload_tracks()
        self._set_status("Toggled segue")

    @on(DataTable.RowSelected, "#tracks")
    def _row_selected(self, event: DataTable.RowSelected) -> None:
        if event.cursor_row is None:
            return
        self.selected_track_index = int(event.cursor_row) + 1
        # Select the cut at the start of this track when possible.
        tracks = self.plan.get("tracks") or []
        if 0 <= event.cursor_row < len(tracks):
            start = float(tracks[event.cursor_row]["start_sec"])
            cuts = [float(c) for c in self.plan.get("cuts_sec") or []]
            if cuts:
                self.selected_cut_index = min(
                    range(len(cuts)), key=lambda i: abs(cuts[i] - start)
                )
        self._sync_track_editors()
        self._refresh_waveforms()
        self._set_status("Selected track")

    @on(WaveformView.CutMarkerClicked)
    def _cut_marker_clicked(self, event: WaveformView.CutMarkerClicked) -> None:
        self._select_cut(event.cut_index, status_prefix="Selected cut")

    def _select_cut(self, cut_index: int, *, status_prefix: str = "Selected cut") -> None:
        cuts = [float(c) for c in self.plan.get("cuts_sec") or []]
        if not cuts:
            return
        self.selected_cut_index = max(0, min(len(cuts) - 1, int(cut_index)))
        # Sync track table to the track that begins at this cut (or previous).
        tracks = self.plan.get("tracks") or []
        t = cuts[self.selected_cut_index]
        if tracks:
            self.selected_track_index = min(
                tracks,
                key=lambda tr: abs(float(tr["start_sec"]) - t),
            )["index"]
            self.selected_track_index = int(self.selected_track_index)
            self._sync_track_editors()
        self._refresh_waveforms()
        endpoint = self.selected_cut_index in (0, len(cuts) - 1)
        note = " (start/end fixed — pick a mid cut to nudge)" if endpoint else " — ←/→ nudge"
        self._set_status(f"{status_prefix}{note}")

    def action_prev_cut(self) -> None:
        cuts = self.plan.get("cuts_sec") or []
        if len(cuts) < 2:
            return
        # Prefer mid-cuts when stepping.
        self._select_cut(max(0, self.selected_cut_index - 1), status_prefix="Prev cut")

    def action_next_cut(self) -> None:
        cuts = self.plan.get("cuts_sec") or []
        if len(cuts) < 2:
            return
        self._select_cut(
            min(len(cuts) - 1, self.selected_cut_index + 1), status_prefix="Next cut"
        )

    def action_accept_all(self) -> None:
        self._stop_play_ui()
        self._player.stop()
        self._collect_package_from_inputs()
        approved = approve_plan(
            self.plan, method="accept_all", approved_by=self.approved_by
        )
        self._write_plan(approved)
        self.plan = approved
        self.dirty = False
        self.exit_code = 0
        self._set_status("Approved (accept_all)")
        self.exit(self.exit_code)

    def action_save_approve(self) -> None:
        self._stop_play_ui()
        self._player.stop()
        self._collect_package_from_inputs()
        self._apply_track_editors()
        approved = approve_plan(
            self.plan, method="edited", approved_by=self.approved_by
        )
        self._write_plan(approved)
        self.plan = approved
        self.dirty = False
        self.exit_code = 0
        self._set_status("Approved (edited)")
        self.exit(self.exit_code)

    def action_reset_llm(self) -> None:
        """Restore cuts/tracks from the as-delivered LLM snapshot; keep package."""
        self._stop_play_ui()
        self._player.stop()
        try:
            delivered = require_as_delivered(self.plan_path)
        except FileNotFoundError as exc:
            self._set_status(str(exc))
            return
        self._collect_package_from_inputs()
        self.plan = reset_plan_to_as_delivered(
            self.plan, delivered, keep_package=True
        )
        self.plan = hydrate_plan_from_notes(self.plan)
        self.plan = reconcile_track_count_to_published_setlist(
            self.plan, project_root=_REPO_ROOT
        )
        self.plan = hydrate_titles_from_published_setlist(
            self.plan, project_root=_REPO_ROOT
        )
        self.plan = seed_package_metadata(self.plan, project_root=_REPO_ROOT)
        self.plan = polish_package_metadata(
            self.plan, project_root=_REPO_ROOT, use_llm=True
        )
        self.dirty = True
        self.selected_cut_index = 1 if len(self.plan.get("cuts_sec") or []) > 2 else 0
        self.selected_track_index = 1
        self._sync_package_editors()
        self._reload_tracks()
        self._refresh_waveforms()
        self._sync_track_editors()
        n_cuts = len(self.plan.get("cuts_sec") or [])
        self._set_status(
            f"Reset to LLM baseline ({n_cuts} cuts); package fields kept"
        )

    def action_quit_pending(self) -> None:
        self._stop_play_ui()
        self._player.stop()
        if self.dirty:
            self._collect_package_from_inputs()
            self._apply_track_editors()
            pending = migrate_tracking_plan(self.plan)
            pending["review"] = {
                "status": "pending",
                "approved_at": None,
                "approved_by": None,
                "method": None,
            }
            self._write_plan(pending)
        self.exit_code = 1
        self.exit(self.exit_code)

    def action_nudge_cut(self, delta: float) -> None:
        cuts = self.plan.get("cuts_sec") or []
        if not cuts:
            return
        if self.selected_cut_index in (0, len(cuts) - 1):
            self._set_status("Start/end cuts are fixed — click a mid (yellow) cut first")
            return
        # Keep focus on overview so further arrow keys keep nudging.
        try:
            self.query_one("#overview", WaveformView).focus()
        except Exception:
            pass
        self.plan = nudge_cut(
            self.plan, cut_index=self.selected_cut_index, delta_sec=float(delta)
        )
        self.dirty = True
        self._reload_tracks()
        self._refresh_waveforms()
        self._set_status(f"Moved cut {delta:+.2f}s")

    def action_nudge_left(self) -> None:
        self.action_nudge_cut(-0.1)

    def action_nudge_right(self) -> None:
        self.action_nudge_cut(0.1)

    def action_nudge_left_large(self) -> None:
        self.action_nudge_cut(-1.0)

    def action_nudge_right_large(self) -> None:
        self.action_nudge_cut(1.0)

    def action_nudge_left_fine(self) -> None:
        self.action_nudge_cut(-0.01)

    def action_nudge_right_fine(self) -> None:
        self.action_nudge_cut(0.01)
    def action_insert_cut(self) -> None:
        cuts = [float(c) for c in self.plan.get("cuts_sec") or []]
        if len(cuts) < 2:
            return
        # Insert midway in the segment after selected cut.
        i = min(self.selected_cut_index, len(cuts) - 2)
        at = (cuts[i] + cuts[i + 1]) / 2.0
        self.plan = insert_mid_cut(self.plan, at_sec=at)
        self.dirty = True
        self._reload_tracks()
        self._refresh_waveforms()
        self._set_status(f"Inserted cut at {at:.3f}s")

    def action_delete_cut(self) -> None:
        self.plan = delete_mid_cut(self.plan, cut_index=self.selected_cut_index)
        cuts = self.plan.get("cuts_sec") or []
        self.selected_cut_index = min(self.selected_cut_index, max(0, len(cuts) - 1))
        self.dirty = True
        self._reload_tracks()
        self._refresh_waveforms()
        self._set_status("Deleted cut")

    def action_toggle_play(self) -> None:
        if self._player.is_playing:
            self._player.stop()
            self._stop_play_ui()
            self._set_status("Stopped")
            self._refresh_waveforms()
            return
        self.action_loop_cut()

    def action_loop_cut(self) -> None:
        if self.source_audio is None or not self.source_audio.is_file():
            self._set_status("No source audio for playback")
            return
        cuts = [float(c) for c in self.plan.get("cuts_sec") or []]
        if not cuts:
            return
        cut = cuts[self.selected_cut_index]
        duration = float(self.plan.get("duration_sec") or cuts[-1])
        start, end = loop_window_around_cut(
            cut, duration_sec=duration, half_window_sec=8.0
        )
        self._playhead = start
        self._player.play_segment(
            self.source_audio, start_sec=start, end_sec=end, loop=True
        )
        self._start_play_ui()
        self._set_status(
            f"Hearing {_format_hear_clock(start)}  "
            f"loop {_format_hear_clock(start)}–{_format_hear_clock(end)}  "
            "(space stop)"
        )

    def _report_playback_status(self) -> None:
        err = self._player.last_error
        if err:
            self._stop_play_ui()
            self._set_status(f"Playback error: {err}")
            return
        if self._player.is_playing:
            pos = self._player.current_position_sec() or self._playhead or 0.0
            hearing = self._player.hearing_window
            if hearing is not None:
                self._set_status(
                    f"Hearing {_format_hear_clock(pos)}  "
                    f"loop {_format_hear_clock(hearing[0])}–"
                    f"{_format_hear_clock(hearing[1])}  (space stop)"
                )
            else:
                self._set_status("Playing — space to stop")
        else:
            self._stop_play_ui()
            self._set_status("Playback finished")

    def action_seek(self, delta: float) -> None:
        cuts = [float(c) for c in self.plan.get("cuts_sec") or []]
        if not cuts:
            return
        # Seek by moving playhead and restarting a short one-shot.
        if self._playhead is None:
            self._playhead = cuts[self.selected_cut_index]
        self._playhead = max(
            0.0,
            min(float(self.plan["duration_sec"]), self._playhead + float(delta)),
        )
        if self.source_audio and self.source_audio.is_file():
            self._player.play_segment(
                self.source_audio,
                start_sec=self._playhead,
                end_sec=min(float(self.plan["duration_sec"]), self._playhead + 3.0),
                loop=False,
            )
            self._start_play_ui()
        self._refresh_waveforms()
        self._set_status(f"Hearing {_format_hear_clock(self._playhead)}")

    def action_seek_back(self) -> None:
        self.action_seek(-2.0)

    def action_seek_forward(self) -> None:
        self.action_seek(2.0)

    def on_unmount(self) -> None:
        self._stop_play_ui()
        self._player.stop()


def run_review_app(
    *,
    plan_path: Path,
    plan: dict[str, Any],
    source_audio: Path | None = None,
    approved_by: str | None = None,
) -> int:
    app = ReviewApp(
        plan_path=plan_path,
        plan=plan,
        source_audio=source_audio,
        approved_by=approved_by,
    )
    result = app.run()
    if isinstance(result, int):
        return result
    return int(getattr(app, "exit_code", 1))
