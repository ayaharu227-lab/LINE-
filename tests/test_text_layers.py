from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


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


def test_rebuilt_lettering_has_no_old_dark_or_pink_fragments():
    """Above the art there must be precisely the independently drawn text."""
    for number, (phrase, size, top) in TEXT.items():
        expected = Image.new("RGBA", (370, 95), (0, 0, 0, 0))
        draw = ImageDraw.Draw(expected)
        font = ImageFont.truetype(ROOT / "assets/fonts/NotoSansJP-Subset.ttf", size)
        font.set_variation_by_axes([700])
        box = draw.textbbox((0, 0), phrase, font=font, stroke_width=3)
        x = round((370 - (box[2] - box[0])) / 2 - box[0])
        draw.text((x, top - box[1]), phrase, font=font,
                  fill=(51, 32, 25, 255), stroke_width=3,
                  stroke_fill=(255, 255, 255, 255))
        with Image.open(STICKERS / f"{number}.png") as image:
            actual = image.convert("RGBA").crop((0, 0, 370, 95))
            assert ImageChops.difference(actual, expected).getbbox() is None, number


def test_tab_head_is_large_and_uncropped():
    with Image.open(STICKERS / "tab.png") as image:
        left, top, right, bottom = image.convert("RGBA").getchannel("A").getbbox()
        assert left >= 3 and top >= 3
        assert image.width - right >= 3 and image.height - bottom >= 3
        assert right - left >= 70
