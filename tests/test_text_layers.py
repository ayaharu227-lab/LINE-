from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
STICKERS = ROOT / "assets" / "stickers"
REBUILT_TEXT = ("08", "14", "16", "17", "19", "20", "22", "23")


def test_rebuilt_lettering_has_no_pink_ear_fragments():
    for number in REBUILT_TEXT:
        with Image.open(STICKERS / f"{number}.png") as image:
            pixels = image.convert("RGBA").load()
            for y in range(100):
                for x in range(370):
                    red, green, blue, alpha = pixels[x, y]
                    assert not (
                        alpha > 128 and red > 130
                        and red > green * 1.13 and red > blue * 1.13
                    ), number


def test_tab_head_is_large_and_uncropped():
    with Image.open(STICKERS / "tab.png") as image:
        left, top, right, bottom = image.convert("RGBA").getchannel("A").getbbox()
        assert left >= 3 and top >= 3
        assert image.width - right >= 3 and image.height - bottom >= 3
        assert right - left >= 70
