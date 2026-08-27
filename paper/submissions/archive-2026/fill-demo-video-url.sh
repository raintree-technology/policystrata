#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 https://www.youtube.com/watch?v=..." >&2
  exit 2
fi

url="$1"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
papers_root="$(cd "$root/.." && pwd)"
tex="$root/issta-splash-tool-demo-paper.tex"
pdf="$root/issta-splash-tool-demo-paper.pdf"
build_dir="$papers_root/build/issta-splash-tool-demo-final"
tectonic="${TECTONIC:-/Users/mb1/.codex/plugins/cache/openai-bundled/latex/0.2.3/bin/tectonic}"

case "$url" in
  https://www.youtube.com/watch\?v=*|https://youtu.be/*)
    ;;
  *)
    echo "error: expected a YouTube watch URL, got: $url" >&2
    exit 2
    ;;
esac

python3 - "$tex" "$url" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
url = sys.argv[2]
text = path.read_text()
text = re.sub(
    r"\\newcommand\{\\DemoVideoUrl\}\{[^}]*\}",
    r"\\newcommand{\\DemoVideoUrl}{" + url.replace("\\", "\\\\") + "}",
    text,
)
path.write_text(text)
PY

mkdir -p "$build_dir"

(
  cd "$root"
  "$tectonic" -X compile \
    --outdir "$build_dir" \
    --outfmt pdf \
    issta-splash-tool-demo-paper.tex
)

cp "$build_dir/issta-splash-tool-demo-paper.pdf" "$pdf"

if pdftotext "$pdf" - | grep -E "TODO|TODO-YOUTUBE" >/tmp/policystrata-tool-demo-todo.txt; then
  echo "error: rebuilt PDF still contains TODO text:" >&2
  cat /tmp/policystrata-tool-demo-todo.txt >&2
  exit 1
fi

pages="$(pdfinfo "$pdf" | awk '/^Pages:/ {print $2}')"
if [[ "$pages" != "3" ]]; then
  echo "error: expected 3 PDF pages, got $pages" >&2
  exit 1
fi

echo "Updated source: $tex"
echo "Rebuilt PDF: $pdf"
echo "Pages: $pages"
echo "SHA256:"
shasum -a 256 "$pdf"
