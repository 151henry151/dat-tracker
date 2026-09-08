#!/usr/bin/env bash
# Download Jon King's already-uploaded Dave Ward / Brian H items for calibration.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${ROOT}/data/ground_truth"
LOG_FILE="${ROOT}/logs/ground-truth-download.log"
IA="${ROOT}/.venv/bin/ia"

if [[ ! -x "${IA}" ]]; then
  echo "Missing ${IA}; create .venv and pip install internetarchive" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}" "${ROOT}/logs"

IDENTIFIERS=(
  # Dave Ward Collection
  jcb2000-04-01
  docwatson2000-07-22.sbd
  jcb2002-08-02
  prtr2002-08-02
  hotrize1996-06-09
  # Brian H Collection
  ocms2005-05-29
  ymsb2003-04-18.Matrix
  rre2004-09-02
  rre2005-05-27
  crookedstill2005-05-26
  jmp2002-11-15
  del2005-05-29
  ymsb2003-04-18.SBD
  lf2005-05-28
  sci2002-04-06
)

{
  echo "==== $(date -Is) starting IA ground-truth download ===="
  echo "items=${#IDENTIFIERS[@]}"
} | tee -a "${LOG_FILE}"

for id in "${IDENTIFIERS[@]}"; do
  dest="${OUT_DIR}/${id}"
  mkdir -p "${dest}"
  echo "---- $(date -Is) ${id} ----" | tee -a "${LOG_FILE}"
  # Prefer FLACs + info text + fingerprints; skip derivatives.
  "${IA}" download "${id}" \
    --destdir "${OUT_DIR}" \
    --glob="*.flac" \
    --glob="*.txt" \
    --glob="*.ffp" \
    --glob="*fingerprint*" \
    --ignore-existing \
    2>&1 | tee -a "${LOG_FILE}"
done

echo "==== $(date -Is) finished IA ground-truth download ====" | tee -a "${LOG_FILE}"
