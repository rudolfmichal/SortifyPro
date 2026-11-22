"""Generate a messy demo folder for testing Sortify Pro.

The folder contains documents, images, archives, installers, files with dates
in their names, ``(1)`` / ``- Copy`` copies and exact duplicates, so every
feature (sorting, duplicates, regex, space analysis) has something to do.

Usage::

    python scripts/generate_test_data.py [folder] [--seed 42]
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_FOLDER = ROOT / "test_data"

EXTENSIONS = (
    ".pdf", ".docx", ".txt", ".jpg", ".png", ".mp3", ".mp4",
    ".zip", ".exe", ".py", ".csv", ".xlsx",
)


def generate(folder: Path, seed: int = 42) -> list[Path]:
    """Create the demo files in ``folder`` and return their paths."""
    rng = random.Random(seed)
    folder.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    def write(name: str, size: int, payload: bytes | None = None) -> Path:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload if payload is not None else rng.randbytes(size))
        created.append(path)
        return path

    # Regular files of various types and sizes.
    for index in range(30):
        ext = EXTENSIONS[index % len(EXTENSIONS)]
        write(f"plik_{index:02d}{ext}", rng.randint(2_000, 400_000))

    # Files with a date in the name (regex with named groups).
    for year, month, day in ((2023, 5, 17), (2024, 1, 3), (2024, 11, 30)):
        write(f"raport_{year}-{month:02d}-{day:02d}.pdf", rng.randint(5_000, 50_000))
        write(f"IMG_{year}{month:02d}{day:02d}_123456.jpg", rng.randint(5_000, 50_000))

    # Exact duplicates and typical "copy" names.
    for base, ext in (("faktura", ".pdf"), ("zdjecie", ".jpg"), ("notatki", ".txt")):
        original = write(f"{base}{ext}", rng.randint(20_000, 120_000))
        content = original.read_bytes()
        write(f"{base} (1){ext}", 0, content)
        write(f"{base} - Kopia{ext}", 0, content)
        write(f"{base}_copy{ext}", 0, content)

    # Same size, different content: must NOT be reported as duplicates.
    write("podobny_a.bin", 0, b"A" * 50_000)
    write("podobny_b.bin", 0, b"B" * 50_000)

    # A large file and nested folders.
    write("duze_wideo.mp4", 3_000_000)
    write("projekt/dokumentacja.docx", 30_000)
    write("projekt/dane/wyniki.csv", 12_000)
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", nargs="?", type=Path, default=DEFAULT_FOLDER)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    files = generate(args.folder, args.seed)
    print(f"Utworzono {len(files)} plików w {args.folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
