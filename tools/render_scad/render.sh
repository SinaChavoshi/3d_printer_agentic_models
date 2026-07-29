#!/bin/bash
if [ -z "$1" ]; then
  echo "Usage: $0 <path_to_scad_file>"
  exit 1
fi
SCAD_FILE="$1"
DIR_NAME=$(dirname "$SCAD_FILE")
echo "Rendering $SCAD_FILE..."
xvfb-run openscad -o "$DIR_NAME/render.png" "$SCAD_FILE" --autocenter --viewall --colorscheme="Tomorrow"
echo "Done rendering $DIR_NAME/render.png"
