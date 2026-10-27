#!/usr/bin/env bash
# Validate solution/src and zip it into an importable unmanaged solution.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
version="$(sed -n 's:.*<Version>\(.*\)</Version>.*:\1:p' "$root/solution/src/solution.xml" | head -1)"
out="$root/dist/DigitalAssetSurvey_${version//./_}.zip"

python3 "$root/scripts/validate.py"
mkdir -p "$root/dist"
rm -f "$out"
(cd "$root/solution/src" && zip -qrXD "$out" '[Content_Types].xml' solution.xml customizations.xml Workflows environmentvariabledefinitions)
echo "wrote $out"
