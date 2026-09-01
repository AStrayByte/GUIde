"""Pins invariants shared between the Python and browser implementations against drift."""

from __future__ import annotations

import json
import re
from pathlib import Path

from guide import FORMAT_VERSION

WEB_DIR = Path(__file__).resolve().parents[1] / "src" / "guide" / "web"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "batch.schema.json"


def test_viewer_version_matches_the_package_format_version() -> None:
    render_js = (WEB_DIR / "render.js").read_text(encoding="utf-8")
    match = re.search(r'VIEWER_VERSION\s*=\s*"([^"]+)"', render_js)
    assert match is not None, "render.js must declare VIEWER_VERSION"
    assert match.group(1) == FORMAT_VERSION


def test_known_fields_matches_the_field_type_enum_in_the_schema() -> None:
    render_js = (WEB_DIR / "render.js").read_text(encoding="utf-8")
    match = re.search(r"const KNOWN_FIELDS = new Set\(\[(.*?)\]\);", render_js, re.DOTALL)
    assert match is not None, "render.js must declare KNOWN_FIELDS"
    js_fields = set(re.findall(r'"([^"]+)"', match.group(1)))

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_fields = set(schema["$defs"]["field"]["properties"]["type"]["enum"])

    assert js_fields == schema_fields


def _referenced_local_assets(html_path: Path) -> set[str]:
    """The ``src=``/``href=`` targets that point at a local file, not a served route."""
    html = html_path.read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="([^"]+)"', html)
    return {ref for ref in refs if not ref.startswith(("/", "http:", "https:", "#"))}


def test_index_html_references_only_files_that_exist() -> None:
    for asset in _referenced_local_assets(WEB_DIR / "index.html"):
        assert (WEB_DIR / asset).is_file(), f"index.html references missing asset {asset!r}"


def test_skill_html_references_only_files_that_exist() -> None:
    for asset in _referenced_local_assets(WEB_DIR / "skill.html"):
        assert (WEB_DIR / asset).is_file(), f"skill.html references missing asset {asset!r}"


def test_known_blocks_matches_the_block_type_examples_in_the_schema() -> None:
    """The schema deliberately lists block types under ``examples``, not ``enum``:
    an unknown block type must degrade to a labeled fallback rather than fail
    validation (a batch from a newer minor may use one this build has never heard
    of). ``KNOWN_BLOCKS`` in render.js is the *closed* set the viewer can actually
    draw, and it must not silently drift from the set the schema documents."""
    render_js = (WEB_DIR / "render.js").read_text(encoding="utf-8")
    match = re.search(r"const KNOWN_BLOCKS = new Set\(\[(.*?)\]\);", render_js, re.DOTALL)
    assert match is not None, "render.js must declare KNOWN_BLOCKS"
    js_blocks = set(re.findall(r'"([^"]+)"', match.group(1)))

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_blocks = set(schema["$defs"]["block"]["properties"]["type"]["examples"])

    assert js_blocks == schema_blocks


def test_ui_js_exists_and_is_loaded_after_render_js_in_both_pages() -> None:
    assert (WEB_DIR / "ui.js").is_file()
    for html_name in ("index.html", "skill.html"):
        html = (WEB_DIR / html_name).read_text(encoding="utf-8")
        render_pos = html.index('src="render.js"')
        ui_pos = html.index('src="ui.js"')
        assert render_pos < ui_pos, f"{html_name} must load render.js before ui.js"


def test_no_inline_style_attributes_or_style_blocks_in_web_assets() -> None:
    """The daemon serves ``style-src 'self'`` — an inline style would be silently dropped."""
    offenders = [
        path.name
        for path in WEB_DIR.iterdir()
        if path.is_file()
        and (
            re.search(r"\sstyle\s*=\s*[\"']", path.read_text(encoding="utf-8"))
            or "<style" in path.read_text(encoding="utf-8").lower()
        )
    ]
    assert offenders == []
