# Upload checklist (Archive.org)

Operator path after tracking: **review → package → confirm → upload**. Packaging and upload run inside `dat-review` after Accept-all or Save & approve. There is no silent upload.

## One-time setup

1. Install review extras (TUI + audio): `pip install -e ".[review]"` (or your usual install).
2. Archive.org login happens **inside `dat-review`** on the upload confirm screen (Log in / `l`, or Upload will prompt if you are not logged in). That uses your archive.org email + password and writes the same local config as `ia configure`. You can still run `ia configure` in a terminal if you prefer.
3. Gemini API key for tracking / companion hydrate — see README (“Configure your Gemini API key”). Not required for the upload step itself.

## Per show

1. Open `dat-review` (picker) or `dat-review <show-id>`.
2. Check cuts, titles, and package fields (artist, date, venue, source, transfer, transferer, tracker, subjects).
3. **Accept-all** (`a`) or **Save & approve** (`s`).
4. Wait for **Packaging** (export tagged FLACs, `show.txt`, `fingerprint.ffp.txt` under `data/out/<show_id>/`, mirrored to `data/work/<show_id>/package/`).
5. On **Upload confirm**:
   - Review identifier (`show_id`), collection (default `taperssection`), and metadata preview.
   - Fix warnings if shown (not logged in → use **Log in**; catalog `already_uploaded`; or IA item already exists).
   - **Upload**, **Skip upload** (keep local package only), or **Quit**.
6. On success, Done shows the local path and `https://archive.org/details/<show_id>`.

## Credits and collections

- Credits come from the approved plan package fields (transferer, tracker, source, transfer). Keep them honest.
- Default IA collection is **`taperssection`**; change on the confirm screen if the band’s etree collection should be used instead.
- Subjects include `plan.package.collection_subjects` (e.g. Dave Ward / Brian H Collection) when set.

## Do not re-upload calibration

If the catalog marks a show `already_uploaded`, or an IA item with that identifier already exists, upload is refused. Use Jon’s / Tier A–B packages for validation only—do not ship competing items for the same shows.

## Headless note

`dat-review --accept-all` still **approves only** (no package/upload). For local packaging without the TUI, use `scripts/package_tracking_plan.py`. Upload remains TUI-confirmed for now.
