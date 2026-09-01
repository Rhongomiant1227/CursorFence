"""Generate the Windows application icon used by build.ps1."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def draw_icon(size: int) -> Image.Image:
    scale = size / 64
    image = Image.new("RGBA", (size, size), "#50617d")
    draw = ImageDraw.Draw(image)
    box = lambda values: tuple(round(value * scale) for value in values)
    draw.rounded_rectangle(box((3, 3, 60, 60)), radius=round(14 * scale), fill="#50617d", outline="#303c52", width=max(1, round(3 * scale)))
    draw.polygon([box((22, 13)), box((22, 46)), box((30, 37)), box((37, 51)), box((44, 47)), box((36, 33)), box((50, 33))], fill="#f4f7fb")
    return image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sizes = (16, 20, 24, 32, 40, 48, 64, 128, 256)
    largest = draw_icon(256)
    largest.save(args.output, format="ICO", sizes=[(size, size) for size in sizes])


if __name__ == "__main__":
    main()
