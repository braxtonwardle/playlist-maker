import json
from pathlib import Path

STATIC_DIR = Path(__file__).parent.parent / "src" / "soundtrack_engine" / "dashboard" / "static"


def test_manifest_is_valid_and_references_existing_icons() -> None:
    manifest = json.loads((STATIC_DIR / "manifest.json").read_text())

    assert manifest["display"] == "standalone"
    assert manifest["icons"]
    for icon in manifest["icons"]:
        icon_path = STATIC_DIR / Path(icon["src"]).name
        assert icon_path.exists(), f"missing icon file: {icon_path}"


def test_icon_files_are_valid_pngs() -> None:
    for name in ("icon-192.png", "icon-512.png"):
        data = (STATIC_DIR / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
