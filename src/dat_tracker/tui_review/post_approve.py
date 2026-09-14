"""Post-approve screens: package → confirm upload → upload → done."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Static

from dat_tracker.ia_upload import (
    DEFAULT_IA_COLLECTION,
    build_ia_metadata,
    catalog_blocks_upload,
    ia_configured,
    identifier_exists,
    save_ia_login,
    upload_package,
)
from dat_tracker.package_pipeline import PackageResult, build_package


class IaLoginScreen(Screen[bool]):
    """Collect Archive.org email/password and run ``internetarchive.configure``."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    CSS = """
    #ia-login-body { height: 1fr; padding: 1 2; }
    #ia-login-status { color: $error; height: 3; }
    #ia-login-actions { height: 3; }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="ia-login-body"):
            yield Static(
                "Log in to Archive.org to upload.\n"
                "Uses the same login as archive.org (email + password).\n"
                "Keys are saved locally via the internetarchive library "
                "(equivalent to `ia configure`).\n"
                "Get an account at https://archive.org/account/signup\n"
            )
            yield Label("Email:")
            yield Input(placeholder="you@example.com", id="ia-email")
            yield Label("Password:")
            yield Input(password=True, id="ia-password")
            yield Static("", id="ia-login-status")
        with Vertical(id="ia-login-actions"):
            yield Button("Save login", id="ia-login-save", variant="success")
            yield Button("Cancel", id="ia-login-cancel")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#ia-email", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ia-login-cancel":
            self.dismiss(False)
        elif event.button.id == "ia-login-save":
            self._save()

    def _save(self) -> None:
        email = self.query_one("#ia-email", Input).value.strip()
        password = self.query_one("#ia-password", Input).value
        status = self.query_one("#ia-login-status", Static)
        if not email or not password:
            status.update("Email and password are required.")
            return
        status.update("Signing in…")
        self.query_one("#ia-login-save", Button).disabled = True
        self._do_login(email, password)

    @work(thread=True)
    def _do_login(self, email: str, password: str) -> None:
        try:
            path = save_ia_login(email, password)
            self.app.call_from_thread(self._on_login_ok, path)
        except Exception as exc:  # noqa: BLE001
            self.app.call_from_thread(self._on_login_fail, str(exc))

    def _on_login_ok(self, path: str) -> None:
        self.query_one("#ia-login-status", Static).update(f"Saved credentials to {path}")
        self.dismiss(True)

    def _on_login_fail(self, message: str) -> None:
        self.query_one("#ia-login-save", Button).disabled = False
        self.query_one("#ia-login-status", Static).update(f"Login failed: {message}")


class PackagingScreen(Screen[PackageResult | None]):
    """Run build_package with a progress log."""

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
    ]

    CSS = """
    #pack-log { height: 1fr; }
    #pack-actions { height: 3; }
    """

    def __init__(
        self,
        *,
        plan: dict[str, Any],
        plan_path: Path,
        source_audio: Path | None,
        project_root: Path,
    ) -> None:
        super().__init__()
        self.plan = plan
        self.plan_path = Path(plan_path)
        self.source_audio = Path(source_audio) if source_audio else None
        self.project_root = Path(project_root)
        self._result: PackageResult | None = None
        self._error: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            f"Packaging {self.plan.get('show_id')}…",
            id="pack-title",
        )
        yield RichLog(id="pack-log", markup=True)
        with Vertical(id="pack-actions"):
            yield Button("Retry", id="pack-retry", disabled=True)
            yield Button("Back to review", id="pack-back", disabled=True)
            yield Button("Quit", id="pack-quit", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self._run_package()

    def _log(self, line: str) -> None:
        self.query_one("#pack-log", RichLog).write(line)

    @work(thread=True)
    def _run_package(self) -> None:
        self.app.call_from_thread(self._set_busy, True)
        try:
            if self.source_audio is None or not self.source_audio.is_file():
                raise FileNotFoundError(
                    "No continuous source FLAC for export "
                    "(set plan source_path or open review with audio)."
                )

            def progress(msg: str) -> None:
                self.app.call_from_thread(self._log, msg)

            result = build_package(
                self.plan,
                source_audio=self.source_audio,
                project_root=self.project_root,
                progress=progress,
            )
            self._result = result
            self.app.call_from_thread(self._on_success, result)
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            self.app.call_from_thread(self._on_failure, str(exc))

    def _set_busy(self, busy: bool) -> None:
        self.query_one("#pack-retry", Button).disabled = busy
        self.query_one("#pack-back", Button).disabled = busy

    def _on_success(self, result: PackageResult) -> None:
        self._log(f"Done: {result.track_count} tracks → {result.out_dir}")
        self.dismiss(result)

    def _on_failure(self, message: str) -> None:
        self._log(f"[red]Failed:[/red] {message}")
        self._set_busy(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pack-retry":
            self.query_one("#pack-log", RichLog).clear()
            self._run_package()
        elif event.button.id == "pack-back":
            self.dismiss(None)
        elif event.button.id == "pack-quit":
            self.app.exit(1)

    def action_quit(self) -> None:
        self.app.exit(1)


class UploadConfirmScreen(Screen[str | None]):
    """Confirm Archive.org upload, or skip to done with local package only.

    Dismiss values: ``\"upload\"``, ``\"skip\"``, or ``None`` (quit/cancel).
    """

    BINDINGS = [
        Binding("u", "do_upload", "Upload", show=True),
        Binding("l", "do_login", "Log in", show=True),
        Binding("s", "do_skip", "Skip", show=True),
        Binding("q", "do_quit", "Quit", show=True),
    ]

    CSS = """
    #confirm-body { height: 1fr; padding: 1 2; }
    #confirm-actions { height: 3; }
    """

    def __init__(
        self,
        *,
        package: PackageResult,
        plan: dict[str, Any],
        project_root: Path,
    ) -> None:
        super().__init__()
        self.package = package
        self.plan = plan
        self.project_root = Path(project_root)
        self.collection = DEFAULT_IA_COLLECTION
        self._upload_after_login = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="confirm-body"):
            yield Static("", id="confirm-summary")
            yield Label("IA collection:")
            yield Input(value=self.collection, id="ia-collection")
        with Vertical(id="confirm-actions"):
            yield Button("Upload to Archive.org", id="confirm-upload", variant="success")
            yield Button("Log in to Archive.org", id="confirm-login")
            yield Button("Skip upload (keep local package)", id="confirm-skip")
            yield Button("Quit", id="confirm-quit", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        show_id = self.package.show_id
        meta = build_ia_metadata(
            self.plan, collection=self.collection, identifier=show_id
        )
        warnings: list[str] = []
        logged_in = ia_configured()
        if catalog_blocks_upload(show_id, project_root=self.project_root):
            warnings.append(
                "Catalog marks this show already_uploaded — upload will be refused."
            )
        if not logged_in:
            warnings.append(
                "Not logged in to Archive.org — press Log in (l) before uploading."
            )
        else:
            try:
                if identifier_exists(show_id):
                    warnings.append(
                        f"IA item {show_id!r} already exists — upload will be refused."
                    )
            except Exception:
                pass

        files = sorted(p.name for p in self.package.out_dir.iterdir() if p.is_file())
        warn_block = "\n".join(f"⚠ {w}" for w in warnings) if warnings else "(none)"
        auth = "logged in" if logged_in else "not logged in"
        body = (
            f"Local package: {self.package.out_dir}\n"
            f"Tracks: {self.package.track_count}\n"
            f"Files: {', '.join(files[:12])}"
            f"{'…' if len(files) > 12 else ''}\n\n"
            f"Archive.org: {auth}\n"
            f"Identifier: {show_id}\n"
            f"Title: {meta.get('title')}\n"
            f"Creator: {meta.get('creator')}\n"
            f"Date: {meta.get('date')}\n"
            f"Venue: {meta.get('venue')}\n"
            f"Subjects: {', '.join(meta.get('subject') or [])}\n\n"
            f"Warnings:\n{warn_block}\n"
        )
        self.query_one("#confirm-summary", Static).update(body)
        self.query_one("#confirm-login", Button).disabled = logged_in

    def _read_collection(self) -> str:
        raw = self.query_one("#ia-collection", Input).value.strip()
        return raw or DEFAULT_IA_COLLECTION

    def action_do_login(self) -> None:
        self._upload_after_login = False
        self.app.push_screen(IaLoginScreen(), self._after_login)

    def action_do_upload(self) -> None:
        self.collection = self._read_collection()
        if not ia_configured():
            self._upload_after_login = True
            self.app.push_screen(IaLoginScreen(), self._after_login)
            return
        self.dismiss("upload")

    def _after_login(self, ok: bool) -> None:
        self._refresh_summary()
        if ok and self._upload_after_login and ia_configured():
            self._upload_after_login = False
            self.collection = self._read_collection()
            self.dismiss("upload")
        else:
            self._upload_after_login = False

    def action_do_skip(self) -> None:
        self.dismiss("skip")

    def action_do_quit(self) -> None:
        self.app.exit(0)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-upload":
            self.action_do_upload()
        elif event.button.id == "confirm-login":
            self.action_do_login()
        elif event.button.id == "confirm-skip":
            self.action_do_skip()
        elif event.button.id == "confirm-quit":
            self.action_do_quit()


class UploadingScreen(Screen[bool]):
    """Run upload_package; dismiss True on success, False on failure."""

    BINDINGS = [Binding("q", "quit", "Quit", show=True)]

    CSS = """
    #up-log { height: 1fr; }
    """

    def __init__(
        self,
        *,
        package: PackageResult,
        plan: dict[str, Any],
        project_root: Path,
        collection: str,
    ) -> None:
        super().__init__()
        self.package = package
        self.plan = plan
        self.project_root = Path(project_root)
        self.collection = collection
        self.item_url: str | None = None
        self.error: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(f"Uploading {self.package.show_id}…", id="up-title")
        yield RichLog(id="up-log", markup=True)
        yield Button("Close", id="up-close", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self._run_upload()

    def _log(self, line: str) -> None:
        self.query_one("#up-log", RichLog).write(line)

    @work(thread=True)
    def _run_upload(self) -> None:
        def progress(msg: str) -> None:
            self.app.call_from_thread(self._log, msg)

        meta = build_ia_metadata(
            self.plan,
            collection=self.collection,
            identifier=self.package.show_id,
        )
        result = upload_package(
            self.package.out_dir,
            identifier=self.package.show_id,
            metadata=meta,
            progress=progress,
            project_root=self.project_root,
        )
        if result.ok:
            self.item_url = result.item_url
            self.app.call_from_thread(self._on_done, True, result.item_url or "")
        else:
            self.error = result.error
            self.app.call_from_thread(
                self._on_done, False, result.error or "upload failed"
            )

    def _on_done(self, ok: bool, detail: str) -> None:
        if ok:
            self._log(f"[green]Success:[/green] {detail}")
            self.dismiss(True)
        else:
            self._log(f"[red]Failed:[/red] {detail}")
            self.query_one("#up-close", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "up-close":
            self.dismiss(False)

    def action_quit(self) -> None:
        self.app.exit(1)


class DoneScreen(Screen[str | None]):
    """Show local path / IA URL; dismiss ``\"another\"`` or exit on quit."""

    BINDINGS = [
        Binding("a", "another", "Another", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(
        self,
        *,
        package: PackageResult,
        item_url: str | None = None,
        allow_another: bool = True,
    ) -> None:
        super().__init__()
        self.package = package
        self.item_url = item_url
        self.allow_another = allow_another

    def compose(self) -> ComposeResult:
        lines = [
            f"Packaged {self.package.show_id}",
            f"Local: {self.package.out_dir}",
        ]
        if self.item_url:
            lines.append(f"Archive.org: {self.item_url}")
        else:
            lines.append("Archive.org: (not uploaded)")
        yield Header(show_clock=True)
        yield Static("\n".join(lines), id="done-body")
        with Vertical():
            if self.allow_another:
                yield Button("Review another show", id="done-another", variant="primary")
            yield Button("Quit", id="done-quit")
        yield Footer()

    def action_another(self) -> None:
        if self.allow_another:
            self.dismiss("another")

    def action_quit(self) -> None:
        self.app.exit(0)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "done-another":
            self.action_another()
        elif event.button.id == "done-quit":
            self.action_quit()


def run_post_approve_flow(
    app: Any,
    *,
    plan: dict[str, Any],
    plan_path: Path,
    source_audio: Path | None,
    project_root: Path,
    allow_another: bool,
    on_another: Callable[[], None] | None = None,
    on_back_to_review: Callable[[], None] | None = None,
) -> None:
    """Push packaging → confirm → optional upload → done onto ``app``."""

    def after_done(choice: str | None) -> None:
        if choice == "another" and on_another is not None:
            on_another()
        else:
            app.exit(0)

    package_holder: dict[str, Any] = {
        "pkg": None,
        "url": None,
        "collection": DEFAULT_IA_COLLECTION,
    }

    def after_confirm(action: str | None) -> None:
        pkg: PackageResult | None = package_holder["pkg"]
        if pkg is None or action is None:
            app.exit(0)
            return
        if action == "skip":
            app.push_screen(
                DoneScreen(
                    package=pkg,
                    item_url=None,
                    allow_another=allow_another,
                ),
                after_done,
            )
            return

        collection = package_holder.get("collection") or DEFAULT_IA_COLLECTION

        def after_uploading(ok: bool) -> None:
            url = package_holder.get("url")
            app.push_screen(
                DoneScreen(
                    package=pkg,
                    item_url=url if ok else None,
                    allow_another=allow_another,
                ),
                after_done,
            )

        up_screen = UploadingScreen(
            package=pkg,
            plan=plan,
            project_root=project_root,
            collection=collection,
        )

        def wrap_upload(ok: bool) -> None:
            package_holder["url"] = up_screen.item_url
            after_uploading(ok)

        app.push_screen(up_screen, wrap_upload)

    def after_package(result: PackageResult | None) -> None:
        if result is None:
            if on_back_to_review is not None:
                on_back_to_review()
            return
        package_holder["pkg"] = result

        confirm = UploadConfirmScreen(
            package=result, plan=plan, project_root=project_root
        )

        def on_confirm(action: str | None) -> None:
            package_holder["collection"] = confirm.collection
            after_confirm(action)

        app.push_screen(confirm, on_confirm)

    app.push_screen(
        PackagingScreen(
            plan=plan,
            plan_path=plan_path,
            source_audio=source_audio,
            project_root=project_root,
        ),
        after_package,
    )
