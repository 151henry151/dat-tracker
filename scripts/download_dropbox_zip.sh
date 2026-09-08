#!/usr/bin/env bash
# Resume-capable download of the Live Bluegrass Dropbox shared zip into data/raw/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${ROOT}/data/raw"
OUT_FILE="${OUT_DIR}/Live Bluegrass.zip"
LOG_FILE="${ROOT}/logs/dropbox-download.log"
EXPECTED_BYTES=107045111705
DROPBOX_URL='https://www.dropbox.com/scl/fo/lwcwu3y8qwktcdmcwt5b0/AFV4nzvqJ66AZ1vSMjs85vE?rlkey=62qci0un4hk40q9s0zu7r5gdg&dl=1'

mkdir -p "${OUT_DIR}" "${ROOT}/logs"

{
  echo "==== $(date -Is) starting Dropbox zip download ===="
  echo "url=${DROPBOX_URL}"
  echo "out=${OUT_FILE}"
  echo "expected_bytes=${EXPECTED_BYTES}"
} | tee -a "${LOG_FILE}"

# Always resolve from the shared link so resume works after signed URLs expire.
# --retry handles transient network failures; -C - resumes partial files.
curl \
  --location \
  --fail \
  --retry 50 \
  --retry-delay 30 \
  --retry-all-errors \
  --continue-at - \
  --output "${OUT_FILE}" \
  --silent \
  --show-error \
  --write-out "\ncurl_exit=%{http_code} size_download=%{size_download} speed=%{speed_download}\n" \
  "${DROPBOX_URL}" \
  >>"${LOG_FILE}" 2>&1

actual="$(stat -c '%s' "${OUT_FILE}")"
echo "==== $(date -Is) finished: bytes=${actual} ====" | tee -a "${LOG_FILE}"

if [[ "${actual}" -ne "${EXPECTED_BYTES}" ]]; then
  echo "ERROR: size mismatch (got ${actual}, expected ${EXPECTED_BYTES})" | tee -a "${LOG_FILE}" >&2
  exit 1
fi

echo "OK: size matches expected ${EXPECTED_BYTES} bytes" | tee -a "${LOG_FILE}"
