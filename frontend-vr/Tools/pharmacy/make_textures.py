"""Generates the pharmacy's printed textures with PIL:

  medicine_atlas.png - 4x4 atlas of generic OTC packaging. Each 512x512 tile holds one product:
                       the top 320 px is the front face of the box, the bottom 192 px is the
                       side colour used for the other faces. build_pharmacy.py maps box UVs
                       into these regions.
  pharmacy_sign.png  - illuminated "PHARMACY" sign with a green cross.

Products are generic names only (no real brands). Paracetamol and the multivitamin match the
OTC study's own products.

    python3 make_textures.py <out_dir>
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"

TILE = 512
FRONT_H = 320  # front-face region height within a tile

# (name, strength, form, brand colour)
PRODUCTS = [
    ("Paracetamol", "500 mg", "16 Tablets", (0, 122, 94)),
    ("Multivitamin", "Daily", "30 Tablets", (230, 126, 34)),
    ("Ibuprofen", "200 mg", "24 Tablets", (192, 57, 43)),
    ("Vitamin C", "1000 mg", "20 Effervescent", (243, 156, 18)),
    ("Cetirizine", "10 mg", "30 Tablets", (41, 128, 185)),
    ("Loratadine", "10 mg", "14 Tablets", (52, 152, 219)),
    ("Aspirin", "300 mg", "32 Tablets", (127, 140, 141)),
    ("Antacid", "Fast Relief", "24 Chewables", (142, 68, 173)),
    ("Vitamin D3", "1000 IU", "60 Capsules", (241, 196, 15)),
    ("Zinc", "15 mg", "30 Tablets", (22, 160, 133)),
    ("Omega-3", "1000 mg", "60 Capsules", (211, 84, 0)),
    ("Throat Lozenges", "Honey & Lemon", "24 Lozenges", (230, 126, 34)),
    ("Saline Spray", "Nasal", "20 ml", (26, 188, 156)),
    ("Antiseptic", "Cream", "30 g", (39, 174, 96)),
    ("Hayfever Relief", "Non-drowsy", "7 Tablets", (155, 89, 182)),
    ("Cold & Flu", "Day & Night", "16 Capsules", (44, 62, 80)),
]


def font(path, size):
    return ImageFont.truetype(path, size)


def centered(draw, y, text, fnt, fill, width=TILE, x0=0):
    w = draw.textlength(text, font=fnt)
    draw.text((x0 + (width - w) / 2, y), text, font=fnt, fill=fill)


def fit_font(draw, text, path, size, max_w):
    while size > 18 and draw.textlength(text, font=font(path, size)) > max_w:
        size -= 2
    return font(path, size)


def draw_tile(img, col, row, product):
    name, strength, form, colour = product
    x0, y0 = col * TILE, row * TILE
    d = ImageDraw.Draw(img)

    # Front face: white card with a brand-colour band and a wave stripe.
    d.rectangle([x0, y0, x0 + TILE, y0 + FRONT_H], fill=(250, 250, 248))
    d.rectangle([x0, y0, x0 + TILE, y0 + 92], fill=colour)
    d.rectangle([x0, y0 + 92, x0 + TILE, y0 + 102], fill=tuple(min(255, c + 60) for c in colour))
    centered(d, y0 + 24, "PHARMACY CARE", font(FONT_BOLD, 34), (255, 255, 255), x0=x0)

    name_font = fit_font(d, name, FONT_BOLD, 64, TILE - 40)
    centered(d, y0 + 124, name, name_font, (30, 30, 30), x0=x0)
    centered(d, y0 + 204, strength, font(FONT_BOLD, 40), colour, x0=x0)
    centered(d, y0 + 258, form, font(FONT_REG, 30), (90, 90, 90), x0=x0)

    # Side/top region: solid brand colour with a light stripe.
    d.rectangle([x0, y0 + FRONT_H, x0 + TILE, y0 + TILE], fill=colour)
    d.rectangle([x0, y0 + FRONT_H + 120, x0 + TILE, y0 + FRONT_H + 136],
                fill=tuple(min(255, c + 70) for c in colour))


def make_atlas(out):
    img = Image.new("RGB", (TILE * 4, TILE * 4), (255, 255, 255))
    for i, product in enumerate(PRODUCTS):
        draw_tile(img, i % 4, i // 4, product)
    img.save(out / "medicine_atlas.png")


def make_sign(out):
    w, h = 2048, 384
    img = Image.new("RGB", (w, h), (0, 110, 84))
    d = ImageDraw.Draw(img)
    d.rectangle([12, 12, w - 12, h - 12], outline=(255, 255, 255), width=6)

    # Green cross on a white disc.
    cx, cy, r = 220, h // 2, 140
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255))
    arm, thick = 100, 64
    green = (0, 166, 81)
    d.rectangle([cx - thick // 2, cy - arm, cx + thick // 2, cy + arm], fill=green)
    d.rectangle([cx - arm, cy - thick // 2, cx + arm, cy + thick // 2], fill=green)

    title = font(FONT_BOLD, 200)
    text_left, text_right = cx + r + 40, w - 60
    tw = d.textlength("PHARMACY", font=title)
    d.text((text_left + (text_right - text_left - tw) / 2, 70), "PHARMACY", font=title, fill=(255, 255, 255))
    img.save(out / "pharmacy_sign.png")


# Shelf header boards, one per 128 px row of category_atlas.png (top row first).
CATEGORIES = [
    ("PAIN RELIEF", (0, 122, 94)),
    ("VITAMINS & SUPPLEMENTS", (230, 126, 34)),
    ("ALLERGY & HAYFEVER", (41, 128, 185)),
    ("COLD & FLU", (44, 62, 80)),
    ("FIRST AID", (39, 174, 96)),
    ("DIGESTIVE HEALTH", (142, 68, 173)),
    ("PRESCRIPTIONS", (0, 110, 84)),
    ("ASK OUR PHARMACIST", (0, 110, 84)),
]


def make_category_atlas(out):
    w, row_h = 1024, 128
    img = Image.new("RGB", (w, row_h * len(CATEGORIES)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for i, (label, colour) in enumerate(CATEGORIES):
        y = i * row_h
        d.rectangle([0, y, w, y + row_h], fill=colour)
        d.rectangle([0, y + row_h - 10, w, y + row_h], fill=tuple(min(255, c + 70) for c in colour))
        fnt = fit_font(d, label, FONT_BOLD, 72, w - 60)
        tw = d.textlength(label, font=fnt)
        d.text(((w - tw) / 2, y + 22), label, font=fnt, fill=(255, 255, 255))
    img.save(out / "category_atlas.png")


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    make_atlas(out)
    make_sign(out)
    make_category_atlas(out)
    print(f"textures written to {out}")
