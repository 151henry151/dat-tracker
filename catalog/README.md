# Catalog

Show inventory for the current DAT dump (first dump: Live Bluegrass).

| File | Role |
|------|------|
| `schema.json` | JSON Schema for `shows.json` (draft 2020-12) |
| `shows.json` | Canonical inventory (starts empty; filled in Phase 1) |
| `shows.csv` | Flat view of the same fields for spreadsheets |

Required fields per show: `id`, `raw_path`, `artist`, `date`, `collection`, `status`.

Status values: `todo`, `already_uploaded`, `in_progress`, `packaged`, `uploaded`.

Collection values: `Dave Ward Collection`, `Brian H Collection`.
