from pathlib import Path
import zipfile

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
STICKERS = ROOT / "assets" / "stickers"
ARCHIVE = ROOT / "release" / "clueless-cheerful-pig-line-stickers-final.zip"
NAMES = {f"{i:02}.png" for i in range(1, 25)} | {"main.png", "tab.png"}


def test_release_archive_matches_reviewed_images():
    assert ARCHIVE.stat().st_size < 60_000_000
    with zipfile.ZipFile(ARCHIVE) as bundle:
        assert set(bundle.namelist()) == NAMES
        assert bundle.testzip() is None
        for name in NAMES:
            assert bundle.read(name) == (STICKERS / name).read_bytes()


def test_stamp_safe_margins():
    for name in NAMES - {"main.png", "tab.png"}:
        with Image.open(STICKERS / name) as image:
            bounds = image.convert("RGBA").getchannel("A").getbbox()
            assert bounds is not None
            left, top, right, bottom = bounds
            assert min(left, top, image.width - right, image.height - bottom) >= 10, name
