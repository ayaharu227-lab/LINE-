from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
ART = ASSETS / 'artwork'
STICKERS = ASSETS / 'stickers'
SOURCE = ASSETS / 'source-stickers'
FONT = ASSETS / 'fonts' / 'NotoSansJP-Subset.ttf'


def trimmed(path: Path) -> Image.Image:
    image = Image.open(path).convert('RGBA')
    box = image.getchannel('A').getbbox()
    assert box, path
    return image.crop(box)


def fit(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    scale = min(max_width / image.width, max_height / image.height)
    return image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)


def exact_text(phrase: str, size: int, top: int) -> Image.Image:
    layer = Image.new('RGBA', (370, 105), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = ImageFont.truetype(FONT, size)
    font.set_variation_by_axes([700])
    box = draw.textbbox((0, 0), phrase, font=font, stroke_width=3)
    x = round((370 - (box[2] - box[0])) / 2 - box[0])
    y = top - box[1]
    draw.text((x, y), phrase, font=font, fill=(51, 32, 25, 255),
              stroke_width=3, stroke_fill=(255, 255, 255, 255))
    return layer


def stamp(number: str, text_crop_height: int, phrase: str | None = None,
          text_size: int = 44, text_top: int = 45) -> None:
    canvas = Image.new('RGBA', (370, 320), (0, 0, 0, 0))
    art_name = '21-v3.png' if number == '21' else f'{number}-v2.png'
    artwork = fit(trimmed(ART / art_name), 344,
                  200 if number == '08' else 213)
    canvas.alpha_composite(artwork, ((370 - artwork.width) // 2, 310 - artwork.height))
    if phrase:
        text = exact_text(phrase, text_size, text_top)
    else:
        original = Image.open(SOURCE / f'{number}.png').convert('RGBA')
        text = original.crop((0, 0, 370, text_crop_height))
    canvas.alpha_composite(text, (0, 0))
    canvas.save(STICKERS / f'{number}.png', optimize=True)


stamp('04', 82)
stamp('08', 94, 'ごめんね', 46, 45)
stamp('09', 90)
stamp('21', 82)

# Recompose the existing, approved character artwork below its exact Japanese
# lettering so ears and motion marks do not collide with the first line.
for number, phrase in [('14', 'おやすみ'), ('16', 'いいね！'),
                       ('17', 'えらい！'), ('19', '任せて！'),
                       ('20', '今やる！'), ('22', '余裕だよ'),
                       ('23', '大丈夫！')]:
    canvas = Image.new('RGBA', (370, 320), (0, 0, 0, 0))
    artwork = fit(trimmed(ART / 'original' / f'{number}.png'), 344, 205)
    canvas.alpha_composite(artwork, ((370 - artwork.width) // 2, 310 - artwork.height))
    canvas.alpha_composite(exact_text(phrase, 43, 44), (0, 0))
    canvas.save(STICKERS / f'{number}.png', optimize=True)

main_art = trimmed(ART / 'main-v2.png')
main_fit = fit(main_art, 218, 218)
main = Image.new('RGBA', (240, 240), (0, 0, 0, 0))
main.alpha_composite(main_fit, ((240 - main_fit.width) // 2, (240 - main_fit.height) // 2))
main.save(STICKERS / 'main.png', optimize=True)

# A dedicated head portrait avoids amputating the hand, ears or question mark.
face_fit = fit(trimmed(ART / 'tab-v2.png'), 88, 66)
tab = Image.new('RGBA', (96, 74), (0, 0, 0, 0))
tab.alpha_composite(face_fit, ((96 - face_fit.width) // 2, (74 - face_fit.height) // 2))
tab.save(STICKERS / 'tab.png', optimize=True)

for bg, suffix in [((255, 255, 255), 'light'), ((87, 69, 63), 'dark')]:
    sheet = Image.new('RGB', (4 * 390, 6 * 340), bg)
    for index in range(24):
        sticker = Image.open(STICKERS / f'{index + 1:02}.png').convert('RGBA')
        tile = Image.new('RGBA', (390, 340), (*bg, 255))
        tile.alpha_composite(sticker, (10, 10))
        sheet.paste(tile.convert('RGB'), ((index % 4) * 390, (index // 4) * 340))
    sheet.save(ASSETS / 'preview' / f'preview-01-24-{suffix}.jpg', quality=94)

archive = ROOT / 'release' / 'clueless-cheerful-pig-line-stickers-final.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(STICKERS.glob('*.png')):
        bundle.write(path, path.name)

print('Rebuilt 11 stickers, main, tab, both previews, and release ZIP')
