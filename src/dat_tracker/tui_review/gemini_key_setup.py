"""In-TUI prompt to paste a Gemini API key on first run."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static

from dat_tracker.gemini_tracker import save_gemini_api_key

AI_STUDIO_URL = "https://aistudio.google.com/apikey"


class GeminiApiKeyScreen(Screen[bool]):
    """Collect GEMINI_API_KEY; dismiss True if saved, False if skipped."""

    CSS = """
    #gemini-hint {
        height: auto;
        padding: 1 2;
        color: $text-muted;
    }
    #gemini-warn {
        height: auto;
        padding: 0 2 1 2;
        color: $warning;
    }
    #gemini-key {
        margin: 0 2;
        width: 1fr;
    }
    #gemini-status {
        height: auto;
        padding: 0 2;
        color: $error;
    }
    #gemini-actions {
        height: 3;
        padding: 0 2;
    }
    """

    BINDINGS = [
        Binding("s", "save", "Save", show=True),
        Binding("q", "skip", "Skip", show=True),
    ]

    def __init__(self, *, project_root: Path | None = None) -> None:
        super().__init__()
        self.project_root = Path(project_root) if project_root else Path.cwd()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll():
            yield Static(
                "Paste your Google Gemini API key.\n"
                "Tracking and review hydration need Gemini to listen and decide cuts.\n"
                f"Get a free key (Google account): {AI_STUDIO_URL}\n"
                "The key is saved to this project's gitignored .env as GEMINI_API_KEY.",
                id="gemini-hint",
            )
            yield Static(
                "You can skip for now, but tracking will fail without a key. "
                "Set GEMINI_API_KEY in .env or your shell later (see README).",
                id="gemini-warn",
            )
            yield Input(
                password=True,
                placeholder="Paste API key here",
                id="gemini-key",
            )
            yield Static("", id="gemini-status")
        with Vertical(id="gemini-actions"):
            yield Button("Save key", id="gemini-save", variant="primary")
            yield Button("Skip for now", id="gemini-skip")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#gemini-key", Input).focus()

    def action_save(self) -> None:
        raw = self.query_one("#gemini-key", Input).value.strip()
        status = self.query_one("#gemini-status", Static)
        if not raw:
            status.update("Paste an API key, or press Skip for now.")
            return
        try:
            save_gemini_api_key(raw, project_root=self.project_root)
        except OSError as exc:
            status.update(f"Could not write .env: {exc}")
            return
        self.dismiss(True)

    def action_skip(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "gemini-save":
            self.action_save()
        elif event.button.id == "gemini-skip":
            self.action_skip()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "gemini-key":
            self.action_save()
