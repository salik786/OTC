"""Builds juliette_face_glow.png: an emission mask of LED rings around Pepper's eyes.

Real Pepper's eyes are lenses ringed by RGB LEDs that change colour with its state. The SDK face
texture only has the black lenses, so this finds them (dark blobs in the upper part of the face)
and draws a ring just outside each one. Unity uses the mask as the face material's emission map
and tints it at runtime (PepperBehaviour).

    python3 make_eye_glow.py <juliette_face.png> <out.png>
"""
import sys

from PIL import Image, ImageChops, ImageFilter

src, out = sys.argv[1], sys.argv[2]
face = Image.open(src).convert("RGBA")
w, h = face.size

# Dark pixels in the top 70% are the eye lenses (the mouth sits lower).
gray = face.convert("L")
mask = Image.new("L", (w, h), 0)
px, mpx = gray.load(), mask.load()
alpha = face.getchannel("A").load()
for y in range(int(h * 0.7)):
    for x in range(w):
        if alpha[x, y] > 128 and px[x, y] < 60:
            mpx[x, y] = 255
mask = mask.filter(ImageFilter.MaxFilter(5))  # close the white pupil highlight

ring_w = max(3, w // 40)
outer = mask.filter(ImageFilter.MaxFilter(ring_w * 2 + 1))
ring = ImageChops.subtract(outer, mask).filter(ImageFilter.GaussianBlur(1.2))

Image.merge("RGB", (ring, ring, ring)).save(out)
print(f"eye glow mask written to {out}")
