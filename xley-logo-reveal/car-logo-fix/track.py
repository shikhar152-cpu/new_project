import os
import cv2, numpy as np, json
SP = os.environ.get('WORK', '.')  # folder with oldf/ (source frames) and fixf/ (output)
N0, N1 = 254, 344
frames = {n: cv2.imread(f'{SP}/oldf/f{n:03d}.png') for n in range(N0, N1 + 1)}
def text_masks(im, box):
    x0, y0, x1, y1 = box
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    r = hsv[y0:y1, x0:x1]
    white = ((r[..., 2] > 150) & (r[..., 1] < 80)).astype(np.uint8)
    orange = ((r[..., 0] >= 3) & (r[..., 0] <= 24) & (r[..., 1] > 110) & (r[..., 2] > 120)).astype(np.uint8)
    full = lambda m: np.pad(m, ((y0, im.shape[0] - y1), (x0, im.shape[1] - x1)))
    return full(white), full(orange)
# reference masks (frame 254), restricted to the decal area
ref = frames[N0]
wm, om = text_masks(ref, (340, 470, 450, 535))
ys, xs = np.nonzero(wm | om)
bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max(), ys.max()
print('decal bbox', bx0, by0, bx1, by1)
m = 8
tx0, ty0, tx1, ty1 = bx0 - m, by0 - m, bx1 + m, by1 + m
gray = lambda im: cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
tmpl = gray(ref)[ty0:ty1, tx0:tx1]
T = np.array([[1, 0, tx0], [0, 1, ty0], [0, 0, 1]], np.float64)   # template crop -> ref frame
Hs = {N0: np.eye(3)}
Wc = T.copy()                                                      # template crop -> current frame
crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-7)
ccs = {}
for n in range(N0 + 1, N1 + 1):
    W0 = Wc.astype(np.float32)
    try:
        cc, Wn = cv2.findTransformECC(tmpl, gray(frames[n]), W0.copy(), cv2.MOTION_HOMOGRAPHY, crit, None, 3)
    except cv2.error as e:
        cc, Wn = -1, W0
    ccs[n] = cc
    Wc = Wn.astype(np.float64)
    Hs[n] = Wc @ np.linalg.inv(T)                                  # ref frame -> frame n
# check: warp the reference decal mask into each frame and compare with what is detected there
ious = []
refmask = (wm | om).astype(np.uint8) * 255
for n in range(N0, N1 + 1):
    warped = cv2.warpPerspective(refmask, Hs[n], (480, 854)) > 127
    ys, xs = np.nonzero(warped)
    box = (max(xs.min() - 6, 0), max(ys.min() - 6, 0), min(xs.max() + 7, 480), min(ys.max() + 7, 854))
    w2, o2 = text_masks(frames[n], box)
    det = (w2 | o2) > 0
    ious.append((n, (warped & det).sum() / max((warped | det).sum(), 1)))
iou = np.array([v for _, v in ious])
print('ECC cc min/median', round(min(ccs.values()), 3), round(float(np.median(list(ccs.values()))), 3))
print('IoU min/median/max', iou.min().round(3), np.median(iou).round(3), iou.max().round(3))
print('worst frames', sorted(ious, key=lambda x: x[1])[:6])
np.save('Hs.npy', np.array([Hs[n] for n in range(N0, N1 + 1)]))
json.dump({'bbox': [int(bx0), int(by0), int(bx1), int(by1)]}, open('ref.json', 'w'))
cv2.imwrite('refmask.png', refmask); cv2.imwrite('refwhite.png', wm * 255); cv2.imwrite('reforange.png', om * 255)
