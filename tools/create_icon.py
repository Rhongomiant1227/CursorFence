"""Generate the Windows application icon used by build.ps1."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def draw_icon(size: int) -> Image.Image:
    """Render a clear utility mark: cursor inside a visible boundary.

    The icon deliberately prioritizes state recognition over decoration.  A
    muted blue frame means unlocked; the same frame turns bright green when
    active, with a small status dot that remains visible in a 16px tray slot.
    """
    scale = size / 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    box = lambda values: tuple(round(value * scale) for value in values)
    stroke = lambda value: max(1, round(value * scale))

    # Neutral dark tile and a simple frame.  The frame is the status signal;
    # keep its geometry unchanged so color is the only thing users need to
    # learn.
    draw.rounded_rectangle(box((3, 3, 60, 60)), radius=round(15 * scale), fill="#182236", outline="#2f405b", width=stroke(2))
    draw.rounded_rectangle(box((7, 7, 56, 56)), radius=round(12 * scale), outline="#22314b", width=stroke(1))

    # Four open corner brackets read as a boundary without looking like a
    # decorative frame.  The gaps leave the cursor visibly inside it.
    boundary = "#93a4bd"
    width = stroke(4)
    draw.line((box((15, 24))[0], box((15, 24))[1], box((15, 15))[0], box((15, 15))[1], box((15, 15))[0], box((24, 15))[1]), fill=boundary, width=width, joint="curve")
    draw.line((box((40, 15))[0], box((40, 15))[1], box((49, 15))[0], box((49, 15))[1], box((49, 15))[0], box((49, 24))[1]), fill=boundary, width=width, joint="curve")
    draw.line((box((15, 40))[0], box((15, 40))[1], box((15, 49))[0], box((15, 49))[1], box((15, 49))[0], box((24, 49))[1]), fill=boundary, width=width, joint="curve")
    draw.line((box((40, 49))[0], box((40, 49))[1], box((49, 49))[0], box((49, 49))[1], box((49, 49))[0], box((49, 40))[1]), fill=boundary, width=width, joint="curve")

    # Central cursor has a dark keyline and a single cool accent, making the
    # symbol readable on either the muted or active boundary color.
    cursor = [box((25, 16)), box((25, 43)), box((31, 36)), box((37, 48)), box((43, 45)), box((37, 33)), box((47, 33))]
    shadow = [(x + round(2 * scale), y + round(2 * scale)) for x, y in cursor]
    draw.polygon(shadow, fill="#0a101d")
    draw.polygon(cursor, fill="#f5f8fc", outline="#ffffff")
    draw.line((box((28, 21))[0], box((28, 21))[1], box((28, 35))[0], box((28, 35))[1]), fill="#b8d3f2", width=stroke(2))

    # Small neutral status mark in the top-right corner; the active generator
    # below changes this to a bright green dot.
    draw.ellipse(box((48, 8, 56, 16)), fill="#71839e", outline="#182236", width=stroke(1))
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
