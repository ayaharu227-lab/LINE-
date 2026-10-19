from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
STICKERS = ROOT / "assets" / "stickers"
TEXT = {
    "04": ("了解！", 44, 40),
    "06": ("はーい", 45, 40),
    "07": ("お願いします", 35, 40),
    "08": ("ごめんね", 46, 42),
    "09": ("だいじょうぶ？", 42, 40),
    "14": ("おやすみ", 43, 37),
    "15": ("よろしく！", 44, 40),
    "16": ("いいね！", 43, 37),
    "17": ("えらい！", 43, 37),
    "18": ("分かったよ", 44, 40),
    "19": ("任せて！", 43, 37),
    "20": ("今やる！", 43, 37),
    "21": ("ちゃんと聞いてる", 38, 40),
    "22": ("余裕だよ", 43, 37),
    "23": ("大丈夫！", 43, 37),
}
TEXT_BOTTOM = {"04": 90, "06": 85, "07": 79, "08": 93, "09": 83,
               "14": 83, "15": 87, "16": 81, "17": 82, "18": 88,
               "19": 84, "20": 84, "21": 82, "22": 85, "23": 85}


def test_rebuilt_lettering_has_no_old_dark_or_pink_fragments():
    """The independently lettered top band contains no art or old text strip."""
    for number in TEXT:
        art_top = (110 if number == "08" else
                   105 if number in {"04", "06", "07", "15", "18"} else
                   97 if number in {"09", "21"} else 95)
        with Image.open(STICKERS / f"{number}.png") as image:
            actual = image.convert("RGBA")
            # Allow different Pillow font rasterizers. The line has a clear
            # transparent gap before the art, and no pink can be in lettering.
            gap = actual.getchannel("A").crop((0, TEXT_BOTTOM[number], 370, art_top))
            assert gap.getbbox() is None, number
            pixels = actual.load()
            for y in range(art_top):
                for x in range(370):
                    red, green, blue, alpha = pixels[x, y]
                    assert not (alpha > 128 and red > 130 and
                                red > green * 1.13 and red > blue * 1.13), number


def test_tab_head_is_large_and_uncropped():
    with Image.open(STICKERS / "tab.png") as image:
        left, top, right, bottom = image.convert("RGBA").getchannel("A").getbbox()
        assert left >= 3 and top >= 3
        assert image.width - right >= 3 and image.height - bottom >= 3
        assert right - left >= 70
