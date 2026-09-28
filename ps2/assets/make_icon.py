"""Draw the application icon, so it is reproducible rather than a binary blob.

    python assets\\make_icon.py

The colours are this tool's own, sampled out of the icon it already had rather
than invented: the plate `#12151a`, the edge `#2c3542`, and the green `#6fae3f`.
Nothing about how it looks changes. What changes is that it is now drawn from
source at every size, which is worth doing for two reasons.

**The small sizes are drawn, not downsampled.** A 1024-pixel drawing resampled
to 16 turns the ring into a smudge, and a smudge reads as "some icon" rather
than as this one -- which is the entire job at taskbar size. So anything under
32 pixels is drawn again with a heavier ring and a bigger centre, then brought
down from 4x.

**It has a sibling now, and siblings have to be told apart.** The Xbox Mod
Studio wears the same reticle in blue, inside four corner brackets taken from
Ghost Recon's briefing screenshots. This one deliberately has no brackets: hue
and silhouette are the two things that separate icons at 16 pixels, and each
tool gets its own of both. The geometry is otherwise identical to the Xbox
one's on purpose -- same ring, same arms, same plate -- so the pair reads as one
family. If either icon is ever restyled, the things to preserve are that this
one stays green and bracket-free and that one stays blue and bracketed.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))

PLATE = (18, 21, 26, 255)     # #12151a
EDGE = (44, 53, 66, 255)      # #2c3542
INK = (111, 174, 63, 255)     # #6fae3f

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
