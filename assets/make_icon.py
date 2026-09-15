"""Draw the application icon, so it is reproducible rather than a binary blob.

    python assets\\make_icon.py

The PS2 Mod Studio's icon is a green reticle on a dark rounded plate. This tool
sits next to it in the same folder on the same taskbar, so it keeps the reticle
-- they are siblings and should look it -- and changes the two things that tell
icons apart at 16 pixels: the **hue**, and the **silhouette**.

  Hue        teal rather than green. It is the colour this tool actually wears
             -- GRAW's tactical display and Ghost Recon's HUD ring are both in
             this family -- and green against teal is unmistakable at any size,
             where green against green is not.

  Silhouette four corner brackets around the reticle. Those are the games' own:
             every briefing screenshot in Ghost Recon and Island Thunder is
             printed inside exactly that frame, and they change the outline
             enough that the two icons do not read as the same shape.

**The small sizes are drawn, not downsampled.** A 1024-pixel drawing resampled
to 16 turns the ring into a grey smudge and the brackets into four dirty
pixels, and a smudge reads as "some icon", not as this one -- which is the whole
job at taskbar size. So anything under 32 pixels is drawn again at 4x with a
heavier ring, a bigger centre and no brackets at all, then brought down. The
brackets are the first thing to go because they are the first thing that stops
resolving.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))

PLATE = (17, 22, 26, 255)     # near-black, a shade cooler than the PS2 one
EDGE = (44, 60, 66, 255)
INK = (62, 200, 216, 255)     # the teal
INK_DIM = (36, 122, 134, 255)

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

    if not simple:
        # the briefing-screenshot brackets, which is what makes the outline
        # this tool's rather than the PS2 one's
        inset = int(s * 0.115)
        leg = int(s * 0.115)
        thin = max(1, int(s * 0.028))
        for ox, oy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            x = inset if ox == 0 else s - inset
            y = inset if oy == 0 else s - inset
            sx = 1 if ox == 0 else -1
            sy = 1 if oy == 0 else -1
            d.line([x, y, x + sx * leg, y], fill=INK_DIM, width=thin)
            d.line([x, y, x, y + sy * leg], fill=INK_DIM, width=thin)

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
