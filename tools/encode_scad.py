"""Builds an OpenSCAD Playground share link from a .scad file.

Use it after editing a model so the README's "Try it out" link matches the code.

Usage:
  python tools/encode_scad.py model.scad                      # new link
  python tools/encode_scad.py model.scad --template-url <url> # reuse an existing link's settings
"""

import argparse
import base64
import gzip
import json
import sys

from decode_scad import decode_payload, select_source

PLAYGROUND_URL = "https://ochafik.com/openscad2/"
DEFAULT_PATH = "/libraries/openscad/examples/Basics/CSG-modules.scad"


def build_payload(source: str, template: dict | None = None) -> dict:
    """Returns a playground project with `source` as the active file and no customizer overrides."""
    if template is None:
        return {
            "params": {
                "activePath": DEFAULT_PATH,
                "features": ["lazy-union"],
                "vars": {},
                "sources": [{"path": DEFAULT_PATH, "content": source}],
                "exportFormat2D": "svg",
                "exportFormat3D": "stl",
            },
            "view": {
                "layout": {
                    "mode": "multi",
                    "editor": True,
                    "viewer": True,
                    "customizer": True,
                }
            },
        }
    payload = json.loads(json.dumps(template))  # deep copy
    path, _ = select_source(payload)
    payload["params"]["sources"] = [{"path": path, "content": source}]
    payload["params"]["activePath"] = path
    payload["params"]["vars"] = {}
    payload.pop("preview", None)  # stale thumbnail hash
    return payload


def encode_url(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return (
        PLAYGROUND_URL
        + "#"
        + base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("scad_file")
    parser.add_argument(
        "--template-url",
        help="Existing playground link whose settings should be reused",
    )
    args = parser.parse_args(argv)

    with open(args.scad_file, encoding="utf-8") as f:
        source = f.read()
    template = decode_payload(args.template_url) if args.template_url else None
    print(encode_url(build_payload(source, template)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
