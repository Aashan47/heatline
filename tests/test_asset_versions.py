"""The page must not be served against a stale copy of its own assets.

An edge cache held a four hour old app.js after a deploy, so the live page
ran the previous script against the current server. Stamping each reference
with the referenced file's content hash makes every deploy a new cache key.
"""

import re

from heatline import service


def test_every_static_reference_carries_its_file_hash():
    html = service._versioned_index()
    refs = re.findall(r"/static/([A-Za-z0-9_.\-]+)(\?v=[0-9a-f]{8})?", html)
    assert refs, "index.html referenced no static assets, so nothing was checked"
    for name, version in refs:
        assert (service.STATIC / name).exists(), name
        assert version, f"{name} was served without a version stamp"
        assert version == "?v=" + service._asset_version(name)


def test_a_changed_file_changes_its_version(tmp_path, monkeypatch):
    asset = service.STATIC / "app.js"
    original = asset.read_bytes()
    before = service._asset_version("app.js")
    try:
        asset.write_bytes(original + b"\n// touched by a test\n")
        after = service._asset_version("app.js")
    finally:
        asset.write_bytes(original)
    assert after != before
    # And it returns once the file does, so the cache is keyed on content.
    assert service._asset_version("app.js") == before


def test_a_missing_file_is_left_unstamped_rather_than_crashing():
    assert service._asset_version("not-a-real-file.css") == ""
