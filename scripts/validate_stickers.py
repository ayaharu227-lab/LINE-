from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "stickers"


def validate_png(path: Path, expected: tuple[int, int], exact: bool = True) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing: {path.relative_to(ROOT)}"]
    if path.stat().st_size >= 1_000_000:
        errors.append(f"1MB以上: {path.name}")
    with Image.open(path) as image:
        if image.format != "PNG":
            errors.append(f"PNGではない: {path.name}")
        if "A" not in image.getbands():
            errors.append(f"alphaなし: {path.name}")
        if exact and image.size != expected:
            errors.append(f"寸法不一致: {path.name} {image.size} != {expected}")
        if not exact and (image.width > expected[0] or image.height > expected[1]):
            errors.append(f"寸法超過: {path.name} {image.size} > {expected}")
        if image.width % 2 or image.height % 2:
            errors.append(f"奇数寸法: {path.name} {image.size}")
        alpha = image.convert("RGBA").getchannel("A")
        if alpha.getbbox() is None:
            errors.append(f"完全透明: {path.name}")
        if alpha.getextrema() == (255, 255):
            errors.append(f"透過ピクセルなし: {path.name}")
    return errors


def main() -> int:
    errors: list[str] = []
    expected_names = {f"{i:02}.png" for i in range(1, 25)} | {"main.png", "tab.png"}
    actual_names = {p.name for p in ASSETS.glob("*.png")}
    if actual_names != expected_names:
        errors.append(f"ファイル集合不一致: missing={sorted(expected_names-actual_names)}, extra={sorted(actual_names-expected_names)}")
    for i in range(1, 25):
        errors += validate_png(ASSETS / f"{i:02}.png", (370, 320))
    errors += validate_png(ASSETS / "main.png", (240, 240))
    errors += validate_png(ASSETS / "tab.png", (96, 74))
    if errors:
        print("FAIL")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("PASS: 24 stickers + main + tab meet file-level requirements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
