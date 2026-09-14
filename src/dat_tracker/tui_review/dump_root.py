"""Prompt for the continuous-FLAC dump directory before listing shows."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, DirectoryTree, Footer, Header, Static
from textual.widgets.directory_tree import DirEntry
from textual.widgets.tree import TreeNode


class DirOnlyTree(DirectoryTree):
    """DirectoryTree that lists directories only (no files)."""

    def filter_paths(self, paths):  # type: ignore[no-untyped-def]
        return [path for path in paths if path.is_dir()]


class DumpRootScreen(Screen[Path | str | None]):
    """Browse for a directory of continuous FLACs; Enter confirms, q quits, w = work plans."""

    CSS = """
    #hint {
        height: auto;
        padding: 1 2;
        color: $text-muted;
    }
    #selected {
        height: auto;
        padding: 0 2;
        color: $text;
    }
    #dump-tree {
        height: 1fr;
        margin: 0 1;
    }
    #status {
        height: auto;
        padding: 0 2;
        color: $error;
    }
    #dump-actions {
        height: 3;
        padding: 0 2;
    }
    """

    BINDINGS = [
        Binding("enter", "confirm", "Use dir", show=True, priority=True),
        Binding("q", "quit_screen", "Quit", show=True),
        Binding("escape", "quit_screen", "Quit", show=False),
        Binding("w", "work_plans", "Work plans", show=True),
        Binding("u", "parent_dir", "Up", show=True),
        Binding("p", "project_root", "Project", show=True),
        Binding("h", "home_dir", "Home", show=True),
    ]

    def __init__(
        self,
        *,
        project_root: Path,
        initial_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.project_root = Path(project_root).resolve()
        start = Path(initial_path).resolve() if initial_path else self.project_root
        if not start.is_dir():
            start = self.project_root if self.project_root.is_dir() else Path.home()
        self._tree_root = start
        self._selected = start

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "Select the directory that contains continuous FLACs. "
            "↑/↓ move, Space expands folders, Enter (or Use directory) confirms. "
            "u parent · p project root · h home · w work plans · q quit.",
            id="hint",
        )
        yield Static(f"Selected: {self._selected}", id="selected")
        yield DirOnlyTree(self._tree_root, id="dump-tree")
        yield Static("", id="status")
        with Vertical(id="dump-actions"):
            yield Button("Use this directory", id="dump-confirm", variant="primary")
            yield Button("Work plans instead", id="dump-work")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#dump-tree", DirOnlyTree).focus()

    def _set_selected(self, path: Path) -> None:
        try:
            self._selected = path.resolve()
        except OSError:
            self._selected = path
        self.query_one("#selected", Static).update(f"Selected: {self._selected}")
        self.query_one("#status", Static).update("")

    def _node_path(self, node: TreeNode[DirEntry] | None) -> Path | None:
        if node is None or node.data is None:
            return None
        return Path(node.data.path)

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self._set_selected(Path(event.path))

    def on_directory_tree_node_highlighted(
        self, event: DirectoryTree.NodeHighlighted[DirEntry]
    ) -> None:
        path = self._node_path(event.node)
        if path is not None and path.is_dir():
            self._set_selected(path)

    def action_confirm(self) -> None:
        path = self._selected
        if not path.is_dir():
            self.query_one("#status", Static).update(f"Not a directory: {path}")
            return
        self.dismiss(path.resolve())

    def action_parent_dir(self) -> None:
        tree = self.query_one("#dump-tree", DirOnlyTree)
        parent = Path(tree.path).resolve().parent
        if parent == Path(tree.path).resolve():
            return
        tree.path = parent
        self._set_selected(parent)

    def action_project_root(self) -> None:
        tree = self.query_one("#dump-tree", DirOnlyTree)
        tree.path = self.project_root
        self._set_selected(self.project_root)

    def action_home_dir(self) -> None:
        home = Path.home()
        tree = self.query_one("#dump-tree", DirOnlyTree)
        tree.path = home
        self._set_selected(home)

    def action_quit_screen(self) -> None:
        self.dismiss(None)

    def action_work_plans(self) -> None:
        self.dismiss("work_plans")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dump-confirm":
            self.action_confirm()
        elif event.button.id == "dump-work":
            self.action_work_plans()
