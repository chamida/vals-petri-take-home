#!/usr/bin/env bash
# Rebuild report.pdf (one page) from report/report.html with headless Chrome.
#   bash report/build.sh
set -euo pipefail
cd "$(dirname "$0")"
../.venv/bin/python make_figure.py
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="../report.pdf" "file://$PWD/report.html" 2>/dev/null
echo "wrote $(cd .. && pwd)/report.pdf"
