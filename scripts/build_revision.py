from pathlib import Path
from PIL import Image
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
ART = ASSETS / 'artwork'
STICKERS = ASSETS / 'stickers'
SOURCE = ASSETS / 'source-stickers'


def trimmed(path: Path) -> Image.Image:
    image = Image.open(path).convert('RGBA')
    box = image.getchannel('A').getbbox()
    assert box, path
    return image.crop(box)


def fit(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    scale = min(max_width / image.width, max_height / image.height)
    return image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)


def stamp(number: str, text_crop_height: int) -> None:
    canvas = Image.new('RGBA', (370, 320), (0, 0, 0, 0))
    artwork = fit(trimmed(ART / f'{number}-v2.png'), 344, 213)
    canvas.alpha_composite(artwork, ((370 - artwork.width) // 2, 310 - artwork.height))
    original = Image.open(SOURCE / f'{number}.png').convert('RGBA')
    text = original.crop((0, 0, 370, text_crop_height))
    canvas.alpha_composite(text, (0, 0))
    canvas.save(STICKERS / f'{number}.png', optimize=True)


stamp('04', 82)
stamp('08', 94)
stamp('21', 82)

# Recompose the existing, approved character artwork below its exact Japanese
# lettering so ears and motion marks do not collide with the first line.
for number, text_height in [('14', 94), ('16', 94), ('17', 94),
                            ('19', 94), ('20', 94), ('22', 94), ('23', 94)]:
    canvas = Image.new('RGBA', (370, 320), (0, 0, 0, 0))
    artwork = fit(trimmed(ART / 'original' / f'{number}.png'), 344, 195)
    canvas.alpha_composite(artwork, ((370 - artwork.width) // 2, 310 - artwork.height))
    original = Image.open(SOURCE / f'{number}.png').convert('RGBA')
    canvas.alpha_composite(original.crop((0, 0, 370, text_height)), (0, 0))
    canvas.save(STICKERS / f'{number}.png', optimize=True)

main_art = trimmed(ART / 'main-v2.png')
main_fit = fit(main_art, 218, 218)
main = Image.new('RGBA', (240, 240), (0, 0, 0, 0))
main.alpha_composite(main_fit, ((240 - main_fit.width) // 2, (240 - main_fit.height) // 2))
main.save(STICKERS / 'main.png', optimize=True)

# The tab is a face close-up derived from the dedicated store illustration.
face = main_art.crop((round(main_art.width * .08), 0, round(main_art.width * .92), round(main_art.height * .70)))
face_box = face.getchannel('A').getbbox()
assert face_box
face = face.crop(face_box)
face_fit = fit(face, 88, 66)
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

print('Rebuilt 10 stickers, main, tab, both previews, and release ZIP')
