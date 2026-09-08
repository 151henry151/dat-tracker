# Agent instructions

1. Read **[PLAN.md](PLAN.md)** fully before making changes.
2. Execute the plan in phase order. Locked decisions in PLAN.md override older chat context.
3. Do not commit unless Henry explicitly asks. Suggest commits; use imperative commit messages; no AI attribution trailers.
4. Use semver + Keep a Changelog; changelog entries in the imperative describing code changes only.
5. Large media belongs under `data/` (gitignored). Do not commit FLACs or the Dropbox dump.
6. Calibrate against Jon King’s existing Archive.org uploads before uploading new competing items for the same shows.
7. Prefer automatic LLM tracking; do not add a required human waveform review UI. Treat weak calibration metrics as a pipeline bug to fix.
8. When drafting Reddit/email text for the community, leave posting to Henry unless he explicitly asks you to send it.
