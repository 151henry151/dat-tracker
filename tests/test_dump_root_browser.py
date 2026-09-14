"""Tests for dump-root directory browser."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


def test_dir_only_tree_filters_files(tmp_path: Path):
    (tmp_path / "keep").mkdir()
    (tmp_path / "skip.flac").write_bytes(b"x")
    (tmp_path / "also").mkdir()
    from dat_tracker.tui_review.dump_root import DirOnlyTree

    tree = DirOnlyTree(tmp_path)
    filtered = list(tree.filter_paths(tmp_path.iterdir()))
    names = {p.name for p in filtered}
    assert names == {"keep", "also"}


def test_dump_root_screen_is_directory_browser(tmp_path: Path):
    pytest.importorskip("textual")
    from dat_tracker.tui_review.dump_root import DirOnlyTree, DumpRootScreen
    from textual.app import App

    dump = tmp_path / "extracted"
    dump.mkdir()
    (dump / "show.flac").write_bytes(b"f")

    class Host(App[None]):
        def on_mount(self) -> None:
            self.push_screen(
                DumpRootScreen(project_root=tmp_path, initial_path=dump),
                self._done,
            )

        def _done(self, result) -> None:  # noqa: ANN001
            self.exit(result)

    app = Host()

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DumpRootScreen)
            tree = app.screen.query_one(DirOnlyTree)
            assert tree.path.resolve() == dump.resolve()
            # Confirm current directory without typing a path.
            app.screen.action_confirm()
            await pilot.pause()
        assert app.return_value == dump.resolve()

    asyncio.run(run())
