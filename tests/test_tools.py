"""Tests for tools/decode_scad.py and tools/encode_scad.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import decode_scad
import encode_scad

SOURCE = 'width = 10; // mm\nshow_lid = false;\nlabel = "A";\ncube(width);\n'


def make_url(sources, active, variables=None):
    payload = encode_scad.build_payload("unused")
    payload["params"]["sources"] = [{"path": p, "content": c} for p, c in sources]
    payload["params"]["activePath"] = active
    payload["params"]["vars"] = variables or {}
    return encode_scad.encode_url(payload)


def test_roundtrip_encode_decode():
    url = encode_scad.encode_url(encode_scad.build_payload(SOURCE))
    path, content = decode_scad.select_source(decode_scad.decode_payload(url))
    assert content == SOURCE
    assert path == encode_scad.DEFAULT_PATH


def test_active_file_is_selected_not_first():
    url = make_url([("/a.scad", "old();"), ("/b.scad", "new();")], active="/b.scad")
    assert decode_scad.select_source(decode_scad.decode_payload(url)) == (
        "/b.scad",
        "new();",
    )


def test_overrides_detected_and_applied():
    variables = {"width": 12.5, "show_lid": True, "label": "A"}
    assert decode_scad.find_overrides(SOURCE, variables) == [
        ("width", "10", "12.5"),
        ("show_lid", "false", "true"),
    ]
    applied = decode_scad.apply_vars(SOURCE, variables)
    assert "width = 12.5; // mm" in applied
    assert "show_lid = true;" in applied
    assert decode_scad.find_overrides(applied, variables) == []


def test_invalid_link_raises():
    with pytest.raises(ValueError):
        decode_scad.decode_payload("https://ochafik.com/openscad2/#not-a-real-payload")


def test_cli_writes_file_without_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    url = make_url([("/m.scad", SOURCE)], active="/m.scad", variables={"width": 20})
    assert decode_scad.main([url, "model.scad", "--apply-vars"]) == 0
    assert "width = 20;" in (tmp_path / "model.scad").read_text()


def test_template_reuse_clears_overrides():
    template = decode_scad.decode_payload(
        make_url([("/x.scad", "a = 1;")], active="/x.scad", variables={"a": 5})
    )
    payload = encode_scad.build_payload("a = 2;", template)
    assert payload["params"]["vars"] == {}
    assert decode_scad.select_source(payload) == ("/x.scad", "a = 2;")
