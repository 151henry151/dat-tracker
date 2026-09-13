"""First-run / setup form for operator review defaults."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Button, Footer, Header, Input, Label, Static

from dat_tracker.review_defaults import (
    OPERATOR_DEFAULT_KEYS,
    load_operator_defaults,
    save_operator_defaults,
    user_defaults_path,
)


class DefaultsSetupApp(App[bool]):
    """Collect tracker name; Save writes XDG (or DAT_TRACKER_DEFAULTS)."""

    CSS = """
    #hint {
        height: auto;
        padding: 1;
        color: $text-muted;
    }
    .row {
        height: 3;
        padding: 0 1;
    }
    .row Label {
        width: 14;
    }
    .row Input {
        width: 1fr;
    }
    #actions {
        height: 3;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("s", "save", "Save", show=True),
        Binding("q", "skip", "Skip", show=True),
    ]

    def __init__(self, *, project_root: Path | None = None) -> None:
        super().__init__()
        self.project_root = project_root
        self._existing = load_operator_defaults(project_root=project_root)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "Set your tracker name (Tracked & Uploaded by). "
            f"Saved to {user_defaults_path()} (or $DAT_TRACKER_DEFAULTS). "
            "Transfer lineage, transferer, and set_label are edited per show in review; "
            "set_label still soft-defaults to “One Set”.",
            id="hint",
        )
        for key in OPERATOR_DEFAULT_KEYS:
            with Vertical(classes="row"):
                yield Label(f"{key}:")
                yield Input(
                    value=self._existing.get(key, ""),
                    id=f"def-{key}",
                    placeholder="Who tracks & uploads (your name / handle)",
                )
        with Vertical(id="actions"):
            yield Button("Save defaults", id="btn-save", variant="primary")
            yield Button("Skip for now", id="btn-skip")
        yield Footer()

    def action_save(self) -> None:
        fields = {
            key: self.query_one(f"#def-{key}", Input).value.strip()
            for key in OPERATOR_DEFAULT_KEYS
        }
        save_operator_defaults(fields, project_root=self.project_root)
        self.exit(True)

    def action_skip(self) -> None:
        self.exit(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-skip":
            self.action_skip()


def run_defaults_setup(*, project_root: Path | None = None) -> bool:
    """Return True if defaults were saved."""
    app = DefaultsSetupApp(project_root=project_root)
    result = app.run()
    return bool(result)
