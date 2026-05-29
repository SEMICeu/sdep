#!/usr/bin/env bash
# Generate a ZIP archive containing the EICAR anti-malware test file.
#
# Usage:
#   scripts/generate-eicar-zip.sh [output-zip]
#
# The generated archive is for testing malware detection only. It is harmless,
# but anti-malware tools should detect it as the EICAR test signature.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_FILE="${1:-${REPO_DIR}/tmp/eicar-test.zip}"

mkdir -p "$(dirname "${OUTPUT_FILE}")"

export EICAR_PART_1='X5O!P%@AP[4\PZX54(P^)7CC)7}$'
export EICAR_PART_2='EICAR-STANDARD-ANTIVIRUS-TEST-FILE'
export EICAR_PART_3='!$H+H*'
export OUTPUT_FILE

GENERATED_FILE="$(python3 <<'PY'
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED
import os

payload = (
    os.environ["EICAR_PART_1"]
    + os.environ["EICAR_PART_2"]
    + os.environ["EICAR_PART_3"]
).encode("ascii")

output_file = Path(os.environ["OUTPUT_FILE"]).expanduser().resolve()
output_file.parent.mkdir(parents=True, exist_ok=True)

with ZipFile(output_file, "w", compression=ZIP_STORED) as archive:
    archive.writestr("eicar.com", payload)

print(output_file)
PY
)"

echo ""
echo "Generated EICAR test archive:"
echo "  ${GENERATED_FILE}"
echo ""
echo "Use this file only to verify malware detection. Uploading it should be rejected."
