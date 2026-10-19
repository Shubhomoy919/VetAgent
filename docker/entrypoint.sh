#!/bin/sh
# Prepare the persistent data volume, then start the server (exec, so signals reach gunicorn directly).
set -eu

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR" "$DATA_DIR/backups"

# First start: copy the frozen v1.0 case set, drug table and guardrail seed onto the volume.
# Later starts keep the volume's copies, so edits made in the app persist.
for f in cases.json drug_table.csv knowledge_seed.json; do
  if [ ! -f "$DATA_DIR/$f" ]; then
    cp "/app/seed-data/$f" "$DATA_DIR/$f"
    echo "entrypoint: seeded $f"
  fi
done

# The SVTG PDF stays on the server. Upload it to the volume, or set SVTG_PDF_URL to fetch DAHD's copy once.
PDF="${SVTG_PDF_PATH:-$DATA_DIR/StandardVeterinaryTreatment.pdf}"
case "$PDF" in
  /*) ;;
  data/*) PDF="$DATA_DIR/${PDF#data/}" ;;
esac
if [ ! -f "$PDF" ] && [ -n "${SVTG_PDF_URL:-}" ]; then
  echo "entrypoint: downloading the SVTG PDF from SVTG_PDF_URL"
  python - "$PDF" <<'PY'
import os, sys, urllib.request
dest = sys.argv[1]
tmp = dest + ".part"
with urllib.request.urlopen(os.environ["SVTG_PDF_URL"], timeout=120) as r, open(tmp, "wb") as f:
    while chunk := r.read(1 << 16):
        f.write(chunk)
with open(tmp, "rb") as f:
    if f.read(5) != b"%PDF-":
        os.remove(tmp)
        sys.exit("entrypoint: SVTG_PDF_URL did not return a PDF")
os.replace(tmp, dest)
PY
fi
if [ ! -f "$PDF" ]; then
  echo "entrypoint: WARNING no SVTG PDF at $PDF. Stored results still display; runs and passages need it."
fi

exec "$@"
