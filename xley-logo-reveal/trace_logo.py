# Traces xley_logo.png into vector pieces (X, L, E, Y, ring, dot) for the reveal.
# Writes logo_paths.js: each piece's outline(s) as point lists in logo pixel space.
import cv2, json, numpy as np
im = cv2.imread('xley_logo.png', cv2.IMREAD_UNCHANGED).astype(np.float32)
a = im[..., 3] / 255.0
b = im[..., 0]                      # OpenCV is BGR: blue channel is low on the orange dot
orange = a * np.clip((235 - b) / (235 - 70), 0, 1)
up = 2                              # trace at 2x with smoothing for clean curves
def mask(m):
    m = cv2.resize(m, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    m = cv2.GaussianBlur(m, (0, 0), 2.0)
    return (m > 0.5).astype(np.uint8)
full, dot = mask(a), mask(orange)
def contours(m, eps=0.6):
    cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cs:
        if cv2.contourArea(c) < 200: continue
        c = cv2.approxPolyDP(c, eps * up, True)[:, 0, :] / up
        out.append([[round(float(x), 2), round(float(y), 2)] for x, y in c])
    return out
n, lab, stats, cent = cv2.connectedComponentsWithStats(full)
pieces = []
for i in range(1, n):
    if stats[i, cv2.CC_STAT_AREA] < 500: continue
    m = (lab == i).astype(np.uint8)
    x, y, w, h = [int(v) / up for v in stats[i, :4]]
    pieces.append({'x': x, 'y': y, 'w': w, 'h': h, 'paths': contours(m)})
pieces.sort(key=lambda p: p['x'])
# the leftmost-bottom round piece is the ring around the dot; name the rest by position
names = ['ring', 'X', 'L', 'E', 'Y'] if len(pieces) == 5 else [f'p{i}' for i in range(len(pieces))]
ring_first = min(pieces, key=lambda p: p['w'] * p['h'])
order = sorted(pieces, key=lambda p: p['x'])
for p in pieces: p['name'] = None
ring_first['name'] = 'ring'
for nm, p in zip(['X', 'L', 'E', 'Y'], [p for p in order if p is not ring_first]): p['name'] = nm
dp = contours(dot)
data = {'w': im.shape[1], 'h': im.shape[0], 'pieces': pieces, 'dot': dp}
open('logo_paths.js', 'w').write('window.LOGO_PATHS = ' + json.dumps(data) + ';\n')
for p in pieces: print(p['name'], p['x'], p['y'], p['w'], p['h'], 'paths', len(p['paths']), [len(q) for q in p['paths']])
print('dot paths', len(dp), [len(q) for q in dp])
