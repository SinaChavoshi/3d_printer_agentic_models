"""Extracts OpenSCAD source from an OpenSCAD Playground share link.

Playground links (https://ochafik.com/openscad2/#<payload>) store a gzip'd,
base64-encoded JSON project: one or more source files, the active file, and
customizer values ("vars") that override the defaults in the code.

Usage:
  python tools/decode_scad.py <url> <out_file.scad>             # active file
  python tools/decode_scad.py <url> <out_file.scad> --apply-vars # bake in customizer values
  python tools/decode_scad.py <url> --list                       # show files and overrides
"""

import argparse
import base64
import binascii
import gzip
import json
import os
import re
import sys


def decode_payload(url: str) -> dict:
    """Returns the playground project as a dict ({"params": {...}})."""
    fragment = url.split("#", 1)[1] if "#" in url else url
    fragment = fragment.strip().replace("-", "+").replace("_", "/")
    fragment += "=" * (-len(fragment) % 4)
    try:
        text = gzip.decompress(base64.b64decode(fragment)).decode("utf-8")
    except (binascii.Error, OSError, EOFError, UnicodeDecodeError) as err:
        raise ValueError(f"Not a valid OpenSCAD Playground link: {err}") from err
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Very old links contain the raw .scad text instead of JSON.
        return {
            "params": {
                "activePath": "/main.scad",
                "sources": [{"path": "/main.scad", "content": text}],
                "vars": {},
            }
        }
    if not isinstance(data, dict) or not data.get("params", {}).get("sources"):
        raise ValueError("Link does not contain any OpenSCAD sources.")
    return data


def select_source(payload: dict, path: str | None = None) -> tuple[str, str]:
    """Returns (path, content) of the requested file, defaulting to the active one."""
    params = payload["params"]
    sources = params["sources"]
    wanted = path or params.get("activePath")
    for src in sources:
        if src.get("path") == wanted or (
            path and src.get("path", "").endswith("/" + path)
        ):
            return src["path"], src.get("content", "")
    if path:
        raise ValueError(
            f"File '{path}' not found. Available: {[s['path'] for s in sources]}"
        )
    return sources[0]["path"], sources[0].get("content", "")


def _format_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return (
            repr(value)
            if isinstance(value, float) and not value.is_integer()
            else str(int(value))
        )
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format_value(v) for v in value) + "]"
    return str(value)


def _assignment_pattern(name: str) -> re.Pattern:
    return re.compile(rf"^(\s*{re.escape(name)}\s*=\s*)([^;]+)(;.*)$", re.M)


def find_overrides(source: str, variables: dict) -> list[tuple[str, str, str]]:
    """Lists (name, value_in_code, value_in_playground) where they differ."""
    overrides = []
    for name, value in variables.items():
        match = _assignment_pattern(name).search(source)
        if not match:
            continue
        in_code, in_link = match.group(2).strip(), _format_value(value)
        try:
            same = abs(float(in_code) - float(in_link)) < 1e-9
        except ValueError:
            same = in_code.lower() == in_link.lower()
        if not same:
            overrides.append((name, in_code, in_link))
    return overrides


def apply_vars(source: str, variables: dict) -> str:
    """Rewrites top-level `name = value;` defaults with the playground's customizer values."""
    for name, value in variables.items():
        source = _assignment_pattern(name).sub(
            lambda m, v=value: f"{m.group(1)}{_format_value(v)}{m.group(3)}",
            source,
            count=1,
        )
    return source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "url", help="OpenSCAD Playground share link (or just the #fragment)"
    )
    parser.add_argument("out_file", nargs="?", help="Where to write the .scad file")
    parser.add_argument("--file", help="Extract this file instead of the active one")
    parser.add_argument(
        "--apply-vars",
        action="store_true",
        help="Bake customizer values into the code defaults",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List files and customizer overrides, then exit",
    )
    args = parser.parse_args(argv)

    try:
        payload = decode_payload(args.url)
        path, content = select_source(payload, args.file)
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    params = payload["params"]
    variables = params.get("vars", {}) or {}
    overrides = find_overrides(content, variables)

    if args.list or not args.out_file:
        for src in params["sources"]:
            marker = "*" if src["path"] == params.get("activePath") else " "
            print(f"{marker} {src['path']} ({len(src.get('content', ''))} chars)")
        for name, in_code, in_link in overrides:
            print(f"  override: {name} = {in_link} (code default: {in_code})")
        return 0 if args.list else 1

    if len(params["sources"]) > 1:
        print(
            f"Note: link has {len(params['sources'])} files; extracting '{path}' (use --file to choose)."
        )
    if overrides and not args.apply_vars:
        print(
            "Warning: the playground customizer overrides these defaults (use --apply-vars to keep them):"
        )
        for name, in_code, in_link in overrides:
            print(f"  {name}: code={in_code} playground={in_link}")
    if args.apply_vars:
        content = apply_vars(content, variables)

    out_dir = os.path.dirname(args.out_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Extracted {path} -> {args.out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
