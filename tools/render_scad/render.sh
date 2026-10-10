#!/usr/bin/env bash
# Renders a thumbnail PNG for an OpenSCAD model.
# Usage: render.sh <model.scad> [output.png]   (default output: render.png next to the model)
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <path_to_scad_file> [output_png]" >&2
  exit 1
fi

SCAD_FILE="$1"
OUT_FILE="${2:-$(dirname "$SCAD_FILE")/render.png}"

[[ -f "$SCAD_FILE" ]] || { echo "Error: '$SCAD_FILE' not found." >&2; exit 1; }
command -v openscad >/dev/null || { echo "Error: openscad is not installed or not on PATH." >&2; exit 1; }
command -v xvfb-run >/dev/null || { echo "Error: xvfb-run is required for headless rendering." >&2; exit 1; }

echo "Rendering $SCAD_FILE -> $OUT_FILE ..."
# --render does a full geometry render; preview mode leaves z-fighting artifacts.
# -a picks a free X display so several renders can run at once.
xvfb-run -a openscad --render -o "$OUT_FILE" "$SCAD_FILE" --autocenter --viewall --colorscheme="Tomorrow"

[[ -s "$OUT_FILE" ]] || { echo "Error: OpenSCAD did not produce $OUT_FILE." >&2; exit 1; }
echo "Done: $OUT_FILE"
