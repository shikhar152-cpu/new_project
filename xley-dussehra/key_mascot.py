# Magenta-screen keyer for the mascot clip.
# usage: python3 key_mascot.py <frames_dir> <out_dir> [count] [height] [x0,y0,x1,y1]
#   frames_dir: raw RGB frames raw_001.png ... (decoded with full chroma interpolation)
#   out_dir:    RGBA frames m_000.png ... cropped to one shared box (the given one, or the
#               union of all frames) and scaled to <height> px
#
# The clip is compressed 4:2:0 video, so magenta bleeds a few pixels into every edge and
# fast moves are motion-blurred. Per frame: build a colour-difference matte from
# "magenta-ness" (min(R,B) - G), drop specks and faint smears, choke away the outermost
# contaminated ring, then repaint the remaining rim with colour pulled from cleaner pixels
# further inside (edge colour extension), despill whatever magenta is left near the edge and
# ease the pink bounce light on skin and the bow back to warm tones.
import sys, glob, os
import numpy as np
import cv2
from PIL import Image


def blur_fill(values, mask, sigmas=(2.5, 6, 16, 40)):
    """Fill every pixel with the mask-weighted local average of `values`."""
    out = np.zeros_like(values)
    done = np.zeros(mask.shape, bool)
    m = mask.astype(np.float32)
    for s in sigmas:
        num = cv2.GaussianBlur(values * m[..., None], (0, 0), s)
        den = cv2.GaussianBlur(m, (0, 0), s)
        ok = (den > 1e-3) & ~done
        out[ok] = num[ok] / den[ok][:, None]
        done |= ok
    return out


def key(rgb):
    C = rgb.astype(np.float32) / 255.0
    mag = np.minimum(C[..., 0], C[..., 2]) - C[..., 1]

    edge = np.concatenate([C[:10].reshape(-1, 3), C[-10:].reshape(-1, 3), C[:, :10].reshape(-1, 3), C[:, -10:].reshape(-1, 3)])
    em = np.minimum(edge[:, 0], edge[:, 2]) - edge[:, 1]
    b0 = np.median(edge[em > .5], axis=0)
    mb = min(b0[0], b0[2]) - b0[1]

    # colour-difference matte: opaque below 12% of the backdrop's magenta-ness, clear above 78%
    lo, hi = .12 * mb, .78 * mb
    a = np.clip((hi - mag) / (hi - lo), 0, 1)

    # drop specks and faint motion smears that are not attached to the character
    solid = (a > .5).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(solid, connectivity=8)
    if n > 1:
        keep = np.zeros(n, bool)
        keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 30
        zone = cv2.dilate(keep[lab].astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        a[~zone] = 0

    # choke: the outermost ring is mostly bled-in magenta, so fade it out
    inside = cv2.distanceTransform((a > .5).astype(np.uint8), cv2.DIST_L2, 5)
    a = a * np.clip((inside - 1) / 2, 0, 1)
    a = cv2.GaussianBlur(a, (0, 0), .6)

    # edge colour extension: repaint the rim from pixels at least 7px in, or from clearly
    # non-magenta pixels so thin parts like the bow keep their own gold
    clean = (inside >= 7) | ((mag < -.28) & (inside >= 2))
    F = blur_fill(C, clean)
    k = np.clip((inside - 4) / 3, 0, 1)[..., None]
    col = k * C + (1 - k) * F

    # despill what is left near the edge: pull R and B back down to G
    spill = np.clip(np.minimum(col[..., 0], col[..., 2]) - col[..., 1], 0, None) * (inside < 8)
    col[..., 0] -= spill; col[..., 2] -= spill

    # the render picked up pink bounce light from the backdrop (fist, bow): ease light,
    # low-saturation pinks near the silhouette back to a warm skin/gold hue. Saturated or
    # dark reds (tongue, mouth) and anything deep inside the body are left alone.
    hsv = cv2.cvtColor((np.clip(col, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    h, s, v = hsv[..., 0] * 2, hsv[..., 1] / 255, hsv[..., 2] / 255
    w = (np.clip((h - 285) / 10, 0, 1) * np.clip((355 - h) / 10, 0, 1)
         * np.clip((.6 - s) / .15, 0, 1) * np.clip((v - .45) / .15, 0, 1)
         * np.clip((28 - inside) / 10, 0, 1))[..., None]
    luma = (col * np.array([.299, .587, .114], np.float32)).sum(-1, keepdims=True)
    warm = np.clip(luma * np.array([1.14, .93, .74], np.float32), 0, 1)
    col = col * (1 - w) + warm * w

    # thin parts (bow, bow string, hair tips) are all edge, so any pink left there is backdrop
    # mixed in by motion blur: tint it to the bow's gold
    body = cv2.morphologyEx((a > .5).astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    thin = (a > .02) & ~(cv2.dilate(body, np.ones((3, 3), np.uint8)) > 0)
    pink = np.clip((np.minimum(col[..., 0], col[..., 2]) - col[..., 1] + .18) / .14, 0, 1) * thin
    luma = (col * np.array([.299, .587, .114], np.float32)).sum(-1, keepdims=True)
    gold = np.clip(luma * np.array([1.2, .97, .52], np.float32), 0, 1)
    col = col * (1 - pink[..., None]) + gold * pink[..., None]

    out = np.dstack([col, a]) * 255.0
    return np.clip(out + .5, 0, 255).astype(np.uint8)


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 90
    height = int(sys.argv[4]) if len(sys.argv) > 4 else 700
    os.makedirs(dst, exist_ok=True)
    frames = sorted(glob.glob(os.path.join(src, 'raw_*.png')))[:count]
    keyed = [key(np.asarray(Image.open(f).convert('RGB'))) for f in frames]
    if len(sys.argv) > 5:
        box = tuple(int(v) for v in sys.argv[5].split(','))
    else:
        box = None
        for k in keyed:
            ys, xs = np.nonzero(k[..., 3] > 8)
            b = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        pad = 6
        box = (max(0, box[0] - pad), max(0, box[1] - pad), box[2] + pad, box[3] + pad)
    for i, k in enumerate(keyed):
        im = Image.fromarray(k, 'RGBA').crop(box)
        im = im.resize((round(im.width * height / im.height), height), Image.LANCZOS)
        im.save(os.path.join(dst, f'm_{i:03d}.png'))
    print('keyed', len(keyed), 'box', box)
