#!/bin/bash
# Render report_draft.md -> report_draft.pdf.
#
# Requires (one-time, via Homebrew + pipx):
#   brew install pandoc pango poppler
#   pipx install weasyprint
#
# report_draft.pdf is gitignored (regenerate locally, don't commit the
# binary) -- run this after each edit pass.
set -euo pipefail
cd "$(dirname "$0")"

pandoc report_draft.md -o report_draft.html --standalone --embed-resources -V geometry:margin=1in
weasyprint report_draft.html report_draft.pdf
rm report_draft.html

echo "Wrote writeup/report_draft.pdf ($(pdfinfo report_draft.pdf | grep Pages))"
