#!/usr/bin/env bash
# Print Dropbox zip + ground-truth download progress.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ZIP="${ROOT}/data/raw/Live Bluegrass.zip"
EXPECTED=107045111705

if [[ -f "${ZIP}" ]]; then
  size="$(stat -c '%s' "${ZIP}")"
  python3 - <<PY
size=${size}
exp=${EXPECTED}
print(f"dropbox_zip: {size}/{exp} bytes ({100*size/exp:.2f}%)")
PY
else
  echo "dropbox_zip: missing"
fi

if pgrep -f '[d]ownload_dropbox_zip|[c]url.*Live Bluegrass' >/dev/null; then
  echo "dropbox_download: running"
else
  echo "dropbox_download: not running"
fi

gt="${ROOT}/data/ground_truth"
echo "ground_truth: $(du -sh "${gt}" | awk '{print $1}') across $(find "${gt}" -mindepth 1 -maxdepth 1 -type d | wc -l) item dirs"
if pgrep -f '[d]ownload_ground_truth|[.]venv/bin/ia download' >/dev/null; then
  echo "ground_truth_download: running"
else
  echo "ground_truth_download: not running"
fi
