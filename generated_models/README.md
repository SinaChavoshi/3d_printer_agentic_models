# Generated Models

This directory contains the source scripts for the various 3D models generated and managed by this project.

## Organization
- `python/`: 3D models generated programmatically via Python (`.py` files).
- `openscad/`: 3D models generated via OpenSCAD scripts (`.scad` files).

## ⚠️ Important Note on Binary Files
To keep the Git repository small and fast to clone, **binary 3D files (like `.stl`, `.obj`, etc.) are ignored by version control** via `.gitignore`. 

You should commit the lightweight *scripts* (`.py` and `.scad`) that generate the models here. When you or another user clones the repository, you can re-run the scripts to generate the final 3D meshes locally.
