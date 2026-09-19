r"""Draw the application icon, so it is reproducible rather than a binary blob.

    python assets\make_icon.py

A red reticle on a dark plate: Raven Shield's own colour, because Raven
Shield is what most people open this tool for.

**The red is the game's, not a guess.** Sampling the strongly-red pixels of
Raven Shield's sixteen menu backdrops, the dominant tone is `#a80018` -- a
crimson shifted slightly towards blue, not an orange-red. That is too dark to
survive a 16-pixel icon, so it is brightened along its own hue rather than
replaced: `#d81e34` keeps the ratio and reads at taskbar size. For reference
the game's in-game reticule config defaults to pure `(255,0,0)`, which is
brighter still and flatter; the menu art is the better source for a plate
this dark.

**This also fixes a collision.** The icon this replaces was `#6fae3f` green on
`#12151a` -- byte-identical in colour and geometry to the PS2 Mod Studio's, so
two of the three tools wore the same icon while this file's own notes claimed
each got its own hue. They no longer do.

**The small sizes are drawn, not downsampled.** A 1024-pixel drawing resampled
to 16 turns the ring into a smudge, and a smudge reads as "some icon" rather
than as this one -- which is the entire job at taskbar size. So anything under
32 pixels is drawn again with a heavier ring and a bigger centre, then brought
down from 4x.

**The family.** All three tools wear the same reticle geometry on purpose, so
the set reads as one thing; hue and silhouette are what separate them at 16
pixels. PS2 is green and bracket-free, Xbox is blue inside four corner
brackets, and this one is red and bracket-free. If any of them is ever
restyled, those are the three pairs to keep distinct.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))

PLATE = (20, 17, 19, 255)     # #141113 -- the grey given the faintest red cast
EDGE = (58, 42, 46, 255)      # #3a2a2e
INK = (216, 30, 52, 255)      # #d81e34, the menu art's crimson brought up

SIZES = (256, 128, 64, 48, 32, 24, 16)

#: below this, the icon is drawn in its simplified form
SMALL = 32


def draw(side: int, simple: bool) -> Image.Image:
    """The icon at `side` pixels, drawn at 4x and brought down."""
    s = side * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = int(s * (0.02 if simple else 0.045))
    d.rounded_rectangle([pad, pad, s - pad, s - pad],
                        radius=int(s * (0.20 if simple else 0.17)),
                        fill=PLATE, outline=EDGE,
                        width=max(1, int(s * 0.012)))

    cx = cy = s // 2
    ring = int(s * (0.275 if simple else 0.225))
    weight = max(1, int(s * (0.075 if simple else 0.055)))
    d.ellipse([cx - ring, cy - ring, cx + ring, cy + ring],
              outline=INK, width=weight)

    arm = int(s * (0.40 if simple else 0.345))
    gap = int(s * (0.145 if simple else 0.115))
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d.line([cx + dx * gap, cy + dy * gap, cx + dx * arm, cy + dy * arm],
               fill=INK, width=weight)
    dot = int(weight * (1.35 if simple else 1.0))
    d.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill=INK)

    return img.resize((side, side), Image.LANCZOS)


def main():
    frames = [draw(n, simple=n < SMALL) for n in SIZES]
    frames[0].save(os.path.join(HERE, "icon.png"))
    frames[0].save(os.path.join(HERE, "icon.ico"), format="ICO",
                   sizes=[(n, n) for n in SIZES], append_images=frames[1:])
    print("wrote icon.png and icon.ico (%s; under %d drawn simplified)"
          % (", ".join("%d" % n for n in SIZES), SMALL))


if __name__ == "__main__":
    main()
