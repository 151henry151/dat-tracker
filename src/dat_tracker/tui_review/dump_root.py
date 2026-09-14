"""Prompt for the continuous-FLAC dump directory before listing shows."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static


class DumpRootScreen(Screen[Path | str | None]):
    """Ask where the untrimmed FLACs live; Enter confirms, q quits, w = work plans."""

    CSS = """
    #hint {
        height: auto;
        padding: 1 2;
        color: $text-muted;
    }
    #dump-path {
        margin: 1 2;
        width: 1fr;
    }
    #status {
        height: auto;
        padding: 0 2;
        color: $error;
    }
    """

    BINDINGS = [
        Binding("q", "quit_screen", "Quit", show=True),
        Binding("escape", "quit_screen", "Quit", show=False),
        Binding("w", "work_plans", "Work plans", show=True),
    ]

    def __init__(
        self,
        *,
        project_root: Path,
        initial_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.project_root = Path(project_root)
        self.initial_path = initial_path

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "Enter the directory that contains continuous FLACs to track "
            "(e.g. data/raw/extracted). Enter confirms. "
            "w opens existing data/work tracking plans (calibration). q quits.",
            id="hint",
        )
        yield Input(
            value=str(self.initial_path) if self.initial_path else "",
            placeholder="/path/to/flac/dump",
            id="dump-path",
        )
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#dump-path", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "dump-path":
            return
        self._confirm_path(event.value)

    def _confirm_path(self, raw: str) -> None:
        text = (raw or "").strip()
        if not text:
            self.query_one("#status", Static).update(
                "Path required (or press w for existing work plans)."
            )
            return
        path = Path(text).expanduser()
        if not path.is_absolute():
            path = (self.project_root / path).resolve()
        else:
            path = path.resolve()
        if not path.is_dir():
            self.query_one("#status", Static).update(f"Not a directory: {path}")
            return
        self.dismiss(path)

    def action_quit_screen(self) -> None:
        self.dismiss(None)

    def action_work_plans(self) -> None:
        self.dismiss("work_plans")
