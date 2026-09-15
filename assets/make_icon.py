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

Written at 256 and saved into a multi-size `.ico`, so Windows has a real 16 and
32 rather than a downsample of a 256.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))

S = 1024                      # drawn big, resampled down
PLATE = (17, 22, 26, 255)     # near-black, a shade cooler than the PS2 one
EDGE = (44, 60, 66, 255)
INK = (62, 200, 216, 255)     # the teal
INK_DIM = (36, 122, 134, 255)

SIZES = (256, 128, 64, 48, 32, 24, 16)


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = int(S * 0.045)
    d.rounded_rectangle([pad, pad, S - pad, S - pad], radius=int(S * 0.17),
                        fill=PLATE, outline=EDGE, width=int(S * 0.012))

    cx = cy = S // 2
    ring = int(S * 0.225)
    weight = int(S * 0.055)
    d.ellipse([cx - ring, cy - ring, cx + ring, cy + ring],
              outline=INK, width=weight)

    arm = int(S * 0.345)
    gap = int(S * 0.115)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d.line([cx + dx * gap, cy + dy * gap, cx + dx * arm, cy + dy * arm],
               fill=INK, width=weight)
    d.ellipse([cx - weight, cy - weight, cx + weight, cy + weight], fill=INK)

    # the briefing-screenshot brackets, which is what makes the outline this
    # tool's rather than the PS2 one's
    inset = int(S * 0.115)
    leg = int(S * 0.115)
    thin = int(S * 0.028)
    for ox, oy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        x = inset if ox == 0 else S - inset
        y = inset if oy == 0 else S - inset
        sx = 1 if ox == 0 else -1
        sy = 1 if oy == 0 else -1
        d.line([x, y, x + sx * leg, y], fill=INK_DIM, width=thin)
        d.line([x, y, x, y + sy * leg], fill=INK_DIM, width=thin)
    return img


def main():
    big = draw()
    png = os.path.join(HERE, "icon.png")
    big.resize((256, 256), Image.LANCZOS).save(png)
    frames = [big.resize((n, n), Image.LANCZOS) for n in SIZES]
    frames[0].save(os.path.join(HERE, "icon.ico"), format="ICO",
                   sizes=[(n, n) for n in SIZES], append_images=frames[1:])
    print("wrote icon.png and icon.ico (%s)"
          % ", ".join("%dx%d" % (n, n) for n in SIZES))


if __name__ == "__main__":
    main()
