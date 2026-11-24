import os
# Replaces the wrong ".XLEY" decal on the car door (frames 254-344) with the real Xley logo.
import cv2, numpy as np
SP = os.environ.get('WORK', '.')  # folder with oldf/ (source frames) and fixf/ (output)
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'xley_logo.png')
N0, N1 = 254, 344
Hs = np.load('Hs.npy')
wm = (cv2.imread('refwhite.png', 0) > 127).astype(np.uint8)
om = (cv2.imread('reforange.png', 0) > 127).astype(np.uint8)
ref = cv2.imread(f'{SP}/oldf/f{N0:03d}.png')

# --- decal geometry in the reference frame: baseline and cap line (robust fits)
ys, xs = np.nonzero(wm)
bot = np.array([(x, ys[xs == x].max()) for x in np.unique(xs)], float)
topp = np.array([(x, ys[xs == x].min()) for x in np.unique(xs)], float)
rng = np.random.default_rng(0)
def ransac(P, thr=1.2, it=4000):
    best, bi = None, -1
    for _ in range(it):
        i, j = rng.choice(len(P), 2, replace=False)
        if P[i, 0] == P[j, 0]: continue
        sl = (P[j, 1] - P[i, 1]) / (P[j, 0] - P[i, 0]); ic = P[i, 1] - sl * P[i, 0]
        inl = np.abs(P[:, 1] - (sl * P[:, 0] + ic)) < thr
        if inl.sum() > bi: bi, best = inl.sum(), inl
    return np.polyfit(P[best, 0], P[best, 1], 1)
a, b = ransac(bot); at, bt = ransac(topp)
ys, xs = np.nonzero(wm | om)
xc = (xs.min() + xs.max()) / 2
base = lambda x: a * x + b
hold = lambda x: base(x) - (at * x + bt)          # old letter height at x (shrinks with perspective)
print(f'baseline {np.degrees(np.arctan(a)):.1f} deg, cap line {np.degrees(np.arctan(at)):.1f} deg, cap {hold(xc):.1f}px')

# --- the real logo, split into white parts and the orange dot
lg = cv2.imread(LOGO, cv2.IMREAD_UNCHANGED).astype(np.float32)
D = 512 / lg.shape[1]
lg = cv2.resize(lg, None, fx=D, fy=D, interpolation=cv2.INTER_AREA)
alpha = lg[..., 3] / 255
whiteness = np.clip((lg[..., 0] - 70) / (235 - 70), 0, 1)   # blue is low on the orange dot
layers = np.dstack([alpha * whiteness, alpha * (1 - whiteness)]).astype(np.float32)
# letters span x 23.5..1952, y 25..652 in full-size logo pixels; map that box onto
# the door between the baseline and a cap line just under the old one (true perspective)
K_H = 0.88
hc = K_H * hold(xc); Wd = (1952 - 23.5) / (652 - 25) * hc
xL, xR = xc - Wd / 2, xc + Wd / 2
quad = np.float32([[xL, base(xL) - K_H * hold(xL)], [xR, base(xR) - K_H * hold(xR)], [xR, base(xR)], [xL, base(xL)]])
box = np.float32([[23.5, 25], [1952, 25], [1952, 652], [23.5, 652]])
A = cv2.getPerspectiveTransform(box, quad).astype(np.float64) @ np.diag([1 / D, 1 / D, 1])
print('new logo width (ref frame):', round(Wd, 1), 'px, letter height', round(hc, 1), 'px')

ORANGE = np.array([58, 133, 232], float)                 # brand orange, BGR
er = lambda m: cv2.erode(m, np.ones((3, 3), np.uint8))
tm = (cv2.imread('refspeck.png', 0) > 127).astype(np.uint8)          # the small trademark mark beside the Y
remove_ref = cv2.dilate(wm | om | tm, np.ones((5, 5), np.uint8))
F = 4
for k, nfr in enumerate(range(N0, N1 + 1)):
    im = cv2.imread(f'{SP}/oldf/f{nfr:03d}.png'); H = Hs[k]
    # how the old white paint is lit in this frame
    wmask = cv2.warpPerspective(er(wm) * 255, H, (480, 854)) > 200
    lit = np.median(im[wmask].astype(float), axis=0)
    # 1. erase the old decal
    rm = cv2.warpPerspective(remove_ref * 255, H, (480, 854))
    rm = cv2.dilate((rm > 20).astype(np.uint8), np.ones((3, 3), np.uint8))
    clean = cv2.inpaint(im, rm, 4, cv2.INPAINT_TELEA)
    # 2. render the real logo with this frame's perspective, 4x supersampled
    M = H @ A
    h0, w0 = layers.shape[:2]
    cr = cv2.perspectiveTransform(np.array([[[0, 0], [w0, 0], [w0, h0], [0, h0]]], np.float64), M)[0]
    x0, y0 = int(np.floor(cr[:, 0].min())) - 4, int(np.floor(cr[:, 1].min())) - 4
    x1, y1 = int(np.ceil(cr[:, 0].max())) + 4, int(np.ceil(cr[:, 1].max())) + 4
    Mc = np.diag([F, F, 1.0]) @ np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]]) @ M
    big = cv2.warpPerspective(layers, Mc, ((x1 - x0) * F, (y1 - y0) * F), flags=cv2.INTER_LINEAR)
    small = cv2.resize(big, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), 0.55)
    aw, ao = small[..., 0:1], small[..., 1:2]
    col = aw * lit + ao * np.clip(ORANGE * lit / 235.0, 0, 255)
    A_tot = np.clip(aw + ao, 0, 1)
    roi = clean[y0:y1, x0:x1].astype(float)
    clean[y0:y1, x0:x1] = np.clip(roi * (1 - A_tot) + col, 0, 255).astype(np.uint8)
    cv2.imwrite(f'{SP}/fixf/f{nfr:03d}.png', clean)
print('done')
