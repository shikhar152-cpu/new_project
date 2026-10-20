# Original soundtrack for the Xley Dussehra motion graphic, synthesised from scratch and
# locked to the animation's beat grid (BEAT = 0.52 s, 115 BPM, key of D).
# usage: python3 music.py out.wav
import sys
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR, DUR, BEAT = 48000, 12.0, 0.52
N = int(SR * DUR)
rng = np.random.default_rng(7)
mix = np.zeros((2, N))


def beat(b):
    return b * BEAT


def t_arr(d):
    return np.arange(int(d * SR)) / SR


def noise(d):
    return rng.standard_normal(int(d * SR))


def filt(x, kind, f, order=2):
    b, a = signal.butter(order, f, btype=kind, fs=SR)
    return signal.lfilter(b, a, x)


def sweep(f0, f1, d, curve=1.0):
    t = t_arr(d)
    f = f0 + (f1 - f0) * (t / d) ** curve
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def add(sig, at, gain=1.0, pan=0.0):
    i = int(round(at * SR))
    if i >= N:
        return
    if i < 0:
        sig, i = sig[-i:], 0
    n = min(len(sig), N - i)
    mix[0, i:i + n] += sig[:n] * gain * np.cos((pan + 1) * np.pi / 4)
    mix[1, i:i + n] += sig[:n] * gain * np.sin((pan + 1) * np.pi / 4)


# ---- instruments
def pluck(freq, d, decay=.996, bright=.6):
    """Karplus-Strong string, vectorised one period at a time."""
    p = max(2, int(SR / freq))
    n = int(d * SR)
    cur = filt(rng.uniform(-1, 1, p * 4), 'low', min(SR / 2.2, 1000 + 9000 * bright))[-p:]
    out = np.empty(((n // p) + 1) * p)
    for k in range(len(out) // p):
        out[k * p:(k + 1) * p] = cur
        cur = decay * .5 * (cur + np.concatenate(([out[k * p - 1] if k else cur[-1]], cur[:-1])))
    out = out[:n]
    return out / (np.abs(out).max() + 1e-9) * np.minimum(1, t_arr(d) / .002)


def tanpura(freq, d=2.6):
    # buzzy drone string: a bright pluck with soft saturation ("jawari") and a detuned octave
    s = pluck(freq, d, .9985, .9) + .4 * pluck(freq * 2.003, d, .998, .8)
    return filt(np.tanh(1.8 * s), 'low', 4200)


def bell(freq, d=1.6):
    t = t_arr(d)
    s = sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t / tau) for r, a, tau in ((1, 1, .9), (2.76, .45, .35), (5.4, .25, .18), (8.9, .12, .1)))
    return s * np.minimum(1, t / .003)


def dagga(d=.5, f0=150, f1=56):
    t = t_arr(d)
    f = f1 + (f0 - f1) * np.exp(-t / .03)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .17)
    click = filt(noise(d), 'low', 2500) * np.exp(-t / .006) * .5
    skin = filt(noise(d), 'band', [180, 600]) * np.exp(-t / .05) * .25
    return np.tanh(1.6 * (body + click + skin))


def tilli(d=.18, f=520):
    t = t_arr(d)
    tone = np.sin(2 * np.pi * f * t + 2 * np.sin(2 * np.pi * f * 1.5 * t)) * np.exp(-t / .035)
    snap = filt(noise(d), 'band', [1800, 6000]) * np.exp(-t / .02)
    return .6 * tone + .7 * snap


def impact(d=.7):
    t = t_arr(d)
    f = 42 + 70 * np.exp(-t / .04)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .22)
    crack = filt(noise(d), 'high', 1500) * np.exp(-t / .025)
    body = filt(noise(d), 'band', [80, 400]) * np.exp(-t / .1)
    return np.tanh(2 * (.9 * sub + .45 * crack + .5 * body))


def fire(d=.9):
    t = t_arr(d)
    n = noise(d)
    roar = filt(n, 'band', [200, 900]) * (1 - t / d) + .7 * filt(n, 'band', [900, 4000]) * (t / d)
    crackle = np.zeros(len(t))
    idx = rng.choice(len(t), 70)
    crackle[idx] = rng.uniform(-1, 1, 70)
    crackle = filt(crackle, 'high', 2000) * 4
    env = np.minimum(1, t / .05) * np.exp(-t / .3)
    return (roar + .6 * crackle) * env


def tick(f=2200, d=.03):
    t = t_arr(d)
    return np.sin(2 * np.pi * f * t) * np.exp(-t / .008)


def whoosh(d, lo=300, hi=3000, peak=.5):
    # noise through a band that sweeps up then down, loudest at `peak` of the way through
    n = noise(d)
    t = t_arr(d) / d
    bands = [filt(n, 'band', [f, f * 2]) for f in np.geomspace(lo, hi / 2, 5)]
    pos = np.sin(np.pi * np.clip(t / (2 * peak) if peak else t, 0, 1))
    out = np.zeros(len(n))
    for k, b in enumerate(bands):
        centre = k / (len(bands) - 1)
        out += b * np.clip(1 - 3 * np.abs(pos - centre), 0, 1)
    env = np.sin(np.pi * np.clip(t, 0, 1)) ** 1.5
    return out * env


def boom(d=1.6, f0=85, f1=34):
    t = t_arr(d)
    f = f1 + (f0 - f1) * np.exp(-t / .08)
    return np.tanh(1.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .5))


def crash(d=2.2):
    t = t_arr(d)
    return filt(noise(d), 'high', 3500) * np.exp(-t / .55) * (1 + .3 * np.sin(2 * np.pi * 9 * t))


def glitch(d=.14):
    out = np.zeros(int(d * SR))
    seg = int(.01 * SR)
    for k in range(0, len(out), seg):
        f = rng.uniform(300, 3000)
        out[k:k + seg] = np.sign(np.sin(2 * np.pi * f * np.arange(min(seg, len(out) - k)) / SR)) * rng.uniform(.3, 1)
    return out


def riser(d, f0=150, f1=900):
    t = t_arr(d)
    tone = sweep(f0, f1, d, 1.6) * (t / d) ** 2
    air = filt(noise(d), 'band', [1500, 7000]) * (t / d) ** 2.5
    return .6 * tone + .5 * air


# ---- arrangement
D2, A2, D3 = 73.42, 110.0, 146.83
SCALE = [293.66, 329.63, 369.99, 440.0, 493.88, 587.33, 659.26, 739.99, 880.0, 987.77]  # D major pentatonic, rising
T_REL, T_SPLIT, HIT0 = beat(3), beat(5), beat(6)
TX0 = beat(18)

# tanpura drone, Pa-Sa-Sa-Sa every two beats
for k in range(int(DUR / (2 * BEAT)) + 1):
    t0 = k * 2 * BEAT
    for off, f in ((0, A2), (.26, D3), (.52, D3), (.78, D2)):
        add(tanpura(f), t0 + off, .11 * min(1, t0 / 1.2 + .25), pan=-.3 if f == A2 else .25)

# intro: heartbeat, charge, release
add(dagga(), beat(1), .35); add(dagga(), beat(2), .5)
add(riser(T_REL - .5, 180, 760), .5, .32)
add(bell(587.33, 2.2), 0.02, .12, pan=.4)
add(pluck(98, .5, .985, .3), T_REL, .55)                                  # bow string twang
add(filt(noise(.07), 'band', [2000, 7000]) * np.exp(-t_arr(.07) / .015), T_REL, .6)  # thwip
add(boom(.9, 90, 40), T_REL, .7); add(dagga(), T_REL, .8)
add(whoosh(1.0, 250, 3500, .45), T_REL + .02, .5)
add(glitch(), 1.70, .12, pan=-.5)
for k in range(8):                                                          # dhol roll into the split
    add(tilli(), beat(4) + k * BEAT / 4, .12 + .05 * k, pan=.3)

# the arrow multiplies
t = t_arr(.7)
shing = sum(np.sin(2 * np.pi * f * t) * np.exp(-t / tau) for f, tau in ((3150, .5), (4720, .35), (6290, .25), (7930, .18)))
add(shing * .25 + filt(noise(.7), 'high', 5000) * np.exp(-t / .08) * .4, T_SPLIT, .4)
add(dagga(), T_SPLIT, .8)
for i in range(10):
    add(sweep(800, 2400, .07) * np.hanning(int(.07 * SR)), T_SPLIT + .035 * i, .1, pan=(-1) ** i * .6)

# ten hits, one per beat, over the full groove
for i in range(10):
    th = HIT0 + i * BEAT
    add(impact(), th, .5)
    add(fire(), th + .02, .22, pan=.2)
    add(pluck(SCALE[i], 1.4, .997, .7), th, .34, pan=-.15)
    add(bell(SCALE[i] * 2, 1.0), th, .06, pan=.3)
    add(tick(), th + .05, .12, pan=-.6)
for b in range(6, 16):
    add(dagga(), beat(b), .62)
    add(tilli(), beat(b + .5), .3, pan=.25)
    add(tilli(), beat(b + .25), .1, pan=.25)
    if b % 2:
        add(dagga(.35, 130, 62), beat(b + .75), .35)

# fill, embers gathering, ring, burst
for k in range(8):
    add(tilli(), beat(16) + k * BEAT / 4, .14 + .04 * k, pan=.3)
add(dagga(), beat(16), .6); add(dagga(), beat(16.75), .45); add(dagga(), beat(17), .6)
add(riser(TX0 - 8.06, 160, 1100), 8.06, .3)
for k, f in enumerate((1174.66, 1479.98, 1760.0, 2349.32)):
    add(bell(f, 1.2), 8.7 + .06 * k, .07, pan=-.5 + k * .33)
add(boom(), TX0, .95); add(crash(), TX0, .3); add(dagga(), TX0, .8)
for f in (293.66, 369.99, 440.0, 587.33):
    add(pluck(f, 2.4, .998, .8), TX0, .2)
    add(bell(f * 2, 2.0), TX0, .05)
add(glitch(), 9.7, .1, pan=.5)

# end card: logo pop, text, tape, mascot, lighter groove and a final cadence
add(sweep(600, 1300, .06) * np.exp(-t_arr(.06) / .03), 9.7, .25)
add(whoosh(.45, 600, 5000, .4), 9.82, .22, pan=-.3)
for k, at in enumerate((10.08, 10.18, 10.28, 10.38)):
    add(tick(1800 + 200 * k, .025), at, .1, pan=-.4 + .25 * k)
add(whoosh(.6, 300, 2500, .3), 10.22, .25, pan=.5)
add(sweep(300, 720, .25) * np.exp(-t_arr(.25) / .12), 9.9, .2, pan=.6)     # mascot pops in
for b in range(19, 23):
    add(dagga(), beat(b), .5)
    add(tilli(), beat(b + .5), .25, pan=.25)
add(dagga(.8), beat(22), .7)
for f in (587.33, 880.0, 1174.66):
    add(bell(f, 1.6), beat(22), .07)
add(pluck(293.66, 1.5, .997, .7), beat(22), .3)

# ---- master: short synthetic room, soft limiter, fade out
ir_t = t_arr(1.1)
ir = np.stack([filt(rng.standard_normal(len(ir_t)), 'low', 6000) * np.exp(-ir_t / .3) for _ in range(2)])
ir /= np.abs(ir).sum(axis=1, keepdims=True) / 6
wet = np.stack([signal.fftconvolve(mix[c], ir[c])[:N] for c in range(2)])
out = mix + .18 * wet
out = filt(out, 'high', 28)
out = np.tanh(1.2 * out / (np.abs(out).max() + 1e-9) * 1.4) / np.tanh(1.2 * 1.4)
fade = np.ones(N); nf = int(.4 * SR); fade[-nf:] = np.linspace(1, 0, nf) ** 2
out *= fade * .89
wavfile.write(sys.argv[1] if len(sys.argv) > 1 else 'music.wav', SR, (out.T * 32767).astype(np.int16))
print('peak %.3f  rms %.3f' % (np.abs(out).max(), np.sqrt((out ** 2).mean())))
