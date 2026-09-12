"""Generate the Windows application icon used by build.ps1."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def draw_icon(size: int) -> Image.Image:
    """Render the CursorFence mark at high resolution for crisp ICO layers.

    The cyan fence communicates the boundary while the warm cursor provides a
    distinctive focal point that remains readable in a 16px notification icon.
    """
    scale = size / 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    box = lambda values: tuple(round(value * scale) for value in values)
    stroke = lambda value: max(1, round(value * scale))

    # Deep navy tile with a subtle double rim; transparent corners work well
    # against both the taskbar and the desktop.
    draw.rounded_rectangle(box((3, 3, 60, 60)), radius=round(15 * scale), fill="#101a2e", outline="#263a5c", width=stroke(2))
    draw.rounded_rectangle(box((7, 7, 56, 56)), radius=round(12 * scale), outline="#172944", width=stroke(1))

    # Stylised fence: two posts and a bright central rail.
    cyan = "#41e6d2"
    cyan_dark = "#1aa7b4"
    draw.line((box((17, 16))[0], box((17, 16))[1], box((17, 49))[0], box((17, 49))[1]), fill=cyan_dark, width=stroke(4))
    draw.line((box((47, 16))[0], box((47, 16))[1], box((47, 49))[0], box((47, 49))[1]), fill=cyan_dark, width=stroke(4))
    draw.line((box((16, 25))[0], box((16, 25))[1], box((48, 25))[0], box((48, 25))[1]), fill=cyan, width=stroke(3))
    draw.line((box((16, 39))[0], box((16, 39))[1], box((48, 39))[0], box((48, 39))[1]), fill=cyan, width=stroke(3))
    draw.ellipse(box((14, 13, 20, 19)), fill="#77fff0")
    draw.ellipse(box((44, 13, 50, 19)), fill="#77fff0")

    # Cursor crossing the fence, with a warm accent that doubles as the
    # active-state cue.
    orange = "#ffb454"
    orange_hot = "#ffd37a"
    draw.polygon([box((26, 14)), box((26, 45)), box((33, 37)), box((39, 50)), box((45, 47)), box((38, 34)), box((49, 34))], fill=orange, outline="#ffe2a6")
    draw.line((box((29, 21))[0], box((29, 21))[1], box((29, 36))[0], box((29, 36))[1]), fill=orange_hot, width=stroke(2))
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
