#!/usr/bin/env bash
# Download Tier B external calibration packages from Archive.org.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${ROOT}/data/calibration"
MANIFEST="${ROOT}/catalog/calibration_tier_b.json"
LOG_FILE="${ROOT}/logs/calibration-tier-b-download.log"
IA="${ROOT}/.venv/bin/ia"
PYTHON="${ROOT}/.venv/bin/python"

if [[ ! -x "${IA}" ]]; then
  echo "Missing ${IA}; create .venv and pip install internetarchive" >&2
  exit 1
fi
if [[ ! -f "${MANIFEST}" ]]; then
  echo "Missing manifest ${MANIFEST}" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}" "${ROOT}/logs"

mapfile -t IDENTIFIERS < <(
  "${PYTHON}" - <<PY
import json
from pathlib import Path
doc = json.loads(Path("${MANIFEST}").read_text())
for show in doc["shows"]:
    print(show["id"])
PY
)

{
  echo "==== $(date -Is) starting Tier B calibration download ===="
  echo "items=${#IDENTIFIERS[@]}"
} | tee -a "${LOG_FILE}"

for id in "${IDENTIFIERS[@]}"; do
  dest="${OUT_DIR}/${id}"
  mkdir -p "${dest}"
  echo "---- $(date -Is) ${id} ----" | tee -a "${LOG_FILE}"
  "${IA}" download "${id}" \
    --destdir "${OUT_DIR}" \
    --glob="*.flac" \
    --glob="*.txt" \
    --glob="*.ffp" \
    --glob="*fingerprint*" \
    --ignore-existing \
    2>&1 | tee -a "${LOG_FILE}"
done

echo "==== $(date -Is) finished Tier B calibration download ====" | tee -a "${LOG_FILE}"
