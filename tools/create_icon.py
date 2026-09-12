"""Generate the Windows application icon used by build.ps1."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def draw_icon(size: int) -> Image.Image:
    """Render the neon barrier-and-cursor mark used by CursorFence.

    It intentionally leans into a compact cyber-anime look: a violet tile,
    cyan/magenta energy ring, and a bright cursor cutting through the barrier.
    The silhouette is kept simple so it still reads in a 16px tray slot.
    """
    scale = size / 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    box = lambda values: tuple(round(value * scale) for value in values)
    stroke = lambda value: max(1, round(value * scale))

    # Dark violet tile with a soft magenta lower rim.
    draw.rounded_rectangle(box((3, 3, 60, 60)), radius=round(15 * scale), fill="#130d2d", outline="#5d2b83", width=stroke(2))
    draw.rounded_rectangle(box((7, 7, 56, 56)), radius=round(12 * scale), outline="#281c57", width=stroke(1))

    # Segmented energy ring: cyan on the left, pink on the right.  The gaps
    # make it feel like a game HUD / magical seal rather than a plain border.
    draw.arc(box((10, 10, 54, 54)), 198, 338, fill="#64f6ff", width=stroke(3))
    draw.arc(box((10, 10, 54, 54)), 18, 158, fill="#ff5ccf", width=stroke(3))
    draw.arc(box((13, 13, 51, 51)), 205, 315, fill="#30bff4", width=stroke(1))
    draw.arc(box((13, 13, 51, 51)), 25, 135, fill="#b45cff", width=stroke(1))

    # Four tiny sparkle nodes give the mark a more anime/cyber feel while
    # remaining bold enough to survive icon downsampling.
    for cx, cy, color in ((15, 17, "#a4fbff"), (49, 17, "#ffb2ed"), (14, 48, "#64f6ff"), (50, 47, "#ff5ccf")):
        draw.polygon((box((cx, cy - 3)), box((cx + 2, cy)), box((cx, cy + 3)), box((cx - 2, cy))), fill=color)

    # Central cursor pierces the energy seal.  A dark offset outline keeps it
    # legible against both neon colors at small sizes.
    cursor = [box((25, 14)), box((25, 45)), box((32, 37)), box((39, 50)), box((45, 47)), box((38, 34)), box((49, 34))]
    shadow = [(x + round(2 * scale), y + round(2 * scale)) for x, y in cursor]
    draw.polygon(shadow, fill="#090617")
    draw.polygon(cursor, fill="#fff8ff", outline="#ff72d2")
    draw.line((box((28, 20))[0], box((28, 20))[1], box((28, 36))[0], box((28, 36))[1]), fill="#d9b5ff", width=stroke(2))
    return image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--preview", type=Path, help="also write a 256px PNG preview")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sizes = (16, 20, 24, 32, 40, 48, 64, 128, 256)
    largest = draw_icon(256)
    largest.save(args.output, format="ICO", sizes=[(size, size) for size in sizes])
    if args.preview:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        largest.save(args.preview, format="PNG", optimize=True)


if __name__ == "__main__":
    main()
