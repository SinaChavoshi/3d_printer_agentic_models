"""Tests for tools/studio/build_claude_artifact.py (no network: downloads come from a local cache)."""

import base64
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "studio"))

import build_claude_artifact as build  # noqa: E402

SOURCE = build.STUDIO.read_text(encoding="utf-8")


def test_artifact_html_drops_wrapper_and_csp_but_keeps_page():
    html = build.artifact_html(SOURCE)
    for gone in ("<!DOCTYPE html>", "<html", "<head>", "<body>", "</html>", 'http-equiv="Content-Security-Policy"'):
        assert gone not in html
    assert "<title>OpenSCAD Agent Studio</title>" in html[:8192]  # viewer reads the title from the first 8 KB
    assert "color-scheme: dark;" in html
    assert 'type="importmap"' in html and "IN_CLAUDE" in html


def test_artifact_html_fails_loudly_if_the_page_changes_shape():
    with pytest.raises(ValueError):
        build.artifact_html(SOURCE.replace("<!DOCTYPE html>\n", "", 1))


def test_pinned_openscad_hash_is_read_from_the_page():
    sha = build.expected_openscad_sha384(SOURCE)
    assert len(base64.b64decode(sha)) == 48


def _tgz(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _fake_packages(monkeypatch, tmp_path, openscad_js: bytes):
    tarballs = {
        "openscad": _tgz({"package/dist/openscad.js": openscad_js}),
        "fonts": _tgz({"package/ttf/DejaVuSans.ttf": b"font", "package/ttf/DejaVuSans-Bold.ttf": b"bold"}),
    }
    cache = tmp_path / "cache"
    cache.mkdir()
    packages = {}
    for name, pkg in build.PACKAGES.items():
        (cache / Path(pkg["url"]).name).write_bytes(tarballs[name])
        packages[name] = {**pkg, "sha256": hashlib.sha256(tarballs[name]).hexdigest()}
    monkeypatch.setattr(build, "PACKAGES", packages)
    return cache


def test_build_bundles_page_engine_fonts_and_library(monkeypatch, tmp_path):
    js = b"export const createOpenSCAD = () => {};"
    page = SOURCE.replace(build.expected_openscad_sha384(SOURCE), base64.b64encode(hashlib.sha384(js).digest()).decode())
    monkeypatch.setattr(build, "STUDIO", tmp_path / "index.html")
    (tmp_path / "index.html").write_text(page, encoding="utf-8")
    cache = _fake_packages(monkeypatch, tmp_path, js)

    result = build.build(tmp_path / "out", cache)

    out = result["out"]
    assert (out / "openscad.js").read_bytes() == js
    assert (out / "fonts" / "DejaVuSans-Bold.ttf").exists()
    models = json.loads((out / "library.json").read_text())
    assert models and all((out / m).exists() for m in models)
    assert len(models) == len(list(build.MODELS.glob("*/*.scad")))


def test_build_rejects_an_openscad_that_does_not_match_the_page(monkeypatch, tmp_path):
    cache = _fake_packages(monkeypatch, tmp_path, b"not the real openscad")
    with pytest.raises(RuntimeError, match="OPENSCAD_SHA384"):
        build.build(tmp_path / "out", cache)


def test_build_rejects_a_tampered_download(monkeypatch, tmp_path):
    cache = _fake_packages(monkeypatch, tmp_path, b"x")
    name = Path(build.PACKAGES["fonts"]["url"]).name
    (cache / name).write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="SHA-256"):
        build.build(tmp_path / "out", cache)
