"""Builds the version of OpenSCAD Studio that runs inside Claude (as a Claude artifact).

studio/index.html works in two places:

* On GitHub Pages (or any web server) it calls the Claude/Gemini API with the user's own key
  and loads OpenSCAD, the fonts and the model library from the network.
* Inside Claude it uses the viewer's own Claude plan instead of a key. A page there has no
  network access, so OpenSCAD, the fonts and the library must be published next to it.

This script produces that second bundle:

  build/claude_studio/
    index.html                  studio/index.html without the page wrapper and CSP
    openscad.js                 openscad-wasm-prebuilt@1.2.0 (OpenSCAD 2025, Manifold backend)
    fonts/DejaVuSans.ttf        dejavu-fonts-ttf@2.37.3, for text()
    fonts/DejaVuSans-Bold.ttf
    library.json                list of the bundled models
    generated_models/openscad/<model>/<model>.scad

Downloads are pinned: each npm tarball must match its SHA-256 below, and openscad.js must match
the SHA-384 that studio/index.html itself checks before running OpenSCAD.

Usage:
  python tools/studio/build_claude_artifact.py                   # -> build/claude_studio
  python tools/studio/build_claude_artifact.py --out /tmp/studio
  python tools/studio/build_claude_artifact.py --cache ~/.cache/studio   # reuse downloads

To publish, ask Claude to publish build/claude_studio/index.html as an artifact with every
other file in the folder as a supporting file, and with these capabilities:
  {"sample": {"images": true}, "downloads": true}
(`sample` lets the page ask Claude on the viewer's plan and send the visual-check renders;
`downloads` lets it offer the .zip with the STL and .scad.)
"""

import argparse
import base64
import hashlib
import io
import json
import re
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STUDIO = REPO / "studio" / "index.html"
MODELS = REPO / "generated_models" / "openscad"
DEFAULT_OUT = REPO / "build" / "claude_studio"

PACKAGES = {
    "openscad": {
        "url": "https://registry.npmjs.org/openscad-wasm-prebuilt/-/openscad-wasm-prebuilt-1.2.0.tgz",
        "sha256": "99e5c314ded63dbadd4a9a958883591cf0f6a874c1f20e210f0e11f24f0ca725",
        "files": {"package/dist/openscad.js": "openscad.js"},
    },
    "fonts": {
        "url": "https://registry.npmjs.org/dejavu-fonts-ttf/-/dejavu-fonts-ttf-2.37.3.tgz",
        "sha256": "b7013ac58f9225250619db82cfb72e99c37ca8195f2b5a06a9e6a95bc5e1c84a",
        "files": {
            "package/ttf/DejaVuSans.ttf": "fonts/DejaVuSans.ttf",
            "package/ttf/DejaVuSans-Bold.ttf": "fonts/DejaVuSans-Bold.ttf",
        },
    },
}

# Parts of studio/index.html that the artifact viewer supplies itself, or that would block it:
# the viewer wraps the page in its own document, and the page's CSP has no 'self' in
# connect-src, which would stop it loading the files published next to it.
WRAPPER = [
    r"<!DOCTYPE html>\n",
    r'<html lang="en">\n',
    r"<head>\n",
    r'<meta charset="UTF-8">\n',
    r'<meta name="viewport"[^\n]*\n',
    r'<meta http-equiv="Content-Security-Policy"[^\n]*\n',
    r"</head>\n",
    r"<body>\n",
    r"</body>\n",
    r"</html>\n?",
]


def artifact_html(source: str) -> str:
    """Returns studio/index.html as an artifact page: no wrapper, no CSP, explicit dark scheme."""
    for pattern in WRAPPER:
        source, count = re.subn(pattern, "", source, count=1)
        if count != 1:
            raise ValueError(f"studio/index.html changed: expected to find {pattern!r} once")
    # The viewer's skeleton pins a light colour scheme; the studio is dark-only.
    marker = ":root {\n    --bg:"
    if marker not in source:
        raise ValueError("studio/index.html changed: could not find the :root colour tokens")
    return source.replace(marker, ":root {\n    color-scheme: dark;\n    --bg:", 1)


def expected_openscad_sha384(source: str) -> str:
    match = re.search(r"const OPENSCAD_SHA384 = '([A-Za-z0-9+/=]+)'", source)
    if not match:
        raise ValueError("Could not find OPENSCAD_SHA384 in studio/index.html")
    return match.group(1)


def fetch(name: str, cache: Path | None) -> bytes:
    pkg = PACKAGES[name]
    cached = cache / Path(pkg["url"]).name if cache else None
    if cached and cached.exists():
        data = cached.read_bytes()
    else:
        print(f"Downloading {pkg['url']}")
        with urllib.request.urlopen(pkg["url"], timeout=120) as resp:
            data = resp.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != pkg["sha256"]:
        raise RuntimeError(f"{name}: SHA-256 {digest} does not match the pinned {pkg['sha256']}")
    if cached and not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    return data


def extract(name: str, data: bytes, out: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member, dest in PACKAGES[name]["files"].items():
            target = out / dest
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src:  # only the listed files, never extractall
                target.write_bytes(src.read())


def library(out: Path) -> list[str]:
    paths = sorted(p.relative_to(REPO).as_posix() for p in MODELS.glob("*/*.scad"))
    for rel in paths:
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, target)
    (out / "library.json").write_text(json.dumps(paths, indent=1) + "\n")
    return paths


def build(out: Path, cache: Path | None = None) -> dict:
    source = STUDIO.read_text(encoding="utf-8")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "index.html").write_text(artifact_html(source), encoding="utf-8")
    for name in PACKAGES:
        extract(name, fetch(name, cache), out)
    got = base64.b64encode(hashlib.sha384((out / "openscad.js").read_bytes()).digest()).decode()
    if got != expected_openscad_sha384(source):
        raise RuntimeError("openscad.js does not match OPENSCAD_SHA384 in studio/index.html")
    models = library(out)
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    return {"out": out, "models": len(models), "files": files}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output folder (default: {DEFAULT_OUT.relative_to(REPO)})")
    parser.add_argument("--cache", type=Path, help="folder to keep downloaded tarballs in")
    args = parser.parse_args(argv)
    result = build(args.out.resolve(), args.cache)
    size = sum((result["out"] / f).stat().st_size for f in result["files"]) / 1e6
    print(f"Built {result['out']} ({len(result['files'])} files, {result['models']} library models, {size:.1f} MB)")
    print('Publish index.html as a Claude artifact with the other files alongside and capabilities {"sample": {"images": true}, "downloads": true}.')
    return 0


if __name__ == "__main__":
    sys.exit(main())
