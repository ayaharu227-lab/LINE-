import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_has_24_unique_rows():
    with (ROOT / "docs" / "sticker-manifest.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 24
    assert [row["no"] for row in rows] == [f"{i:02}" for i in range(1, 25)]
    assert len({row["text"] for row in rows}) == 24


def test_utility_comedy_ratio():
    with (ROOT / "docs" / "sticker-manifest.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert sum(row["category"] == "utility" for row in rows) == 17
    assert sum(row["category"] == "comedy" for row in rows) == 7
