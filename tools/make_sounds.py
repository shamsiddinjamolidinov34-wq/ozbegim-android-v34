#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
O'zbegim: tovush signallari uchun tabiat tovushlari va iPhone uslubidagi tovushlarni sintez qiladi (v33).

Barcha tovushlar shu skriptda matematik usulda yaratiladi (tarmoq, tashqi yozuv va mualliflik huquqi shartlari yo'q).
iPhone uslubidagi tovushlar Apple yozuvlari emas: ularning xarakteri (yumshoq yog'och va shisha "tik", "tok", "pop") bo'yicha
yangidan sintez qilingan asl tovushlar.

Natija: app/src/main/res/raw/snd_<id>.wav, 16 bit, 44100 Hz (uzun tabiat tovushlari 22050 Hz: ularda 11 kHz dan yuqori qism yo'q,
fayl hajmi esa ikki baravar kichik). Qisqa tovushlar bir kanalli: ilova ularni chapga-o'ngga siljitmaydi, chunki ba'zi ekran
o'quvchilarda tovushning joyi elementning ekrandagi joyini bildiradi. Tabiat matnlari (suv, yomg'ir, shamol, olov) ikki kanalli:
kanallardagi shovqinlar bir-biriga bog'liq emas, shuning uchun quloqchinda keng eshitiladi, bir karnayli telefonda esa qo'shilib
ketib so'nmaydi (shu shart tekshiriladi: --report dagi "mono" ustuni).
Ba'zi tovushlarning bir nechta varianti bor (snd_<id>_2.wav, snd_<id>_3.wav ...): ilova ularni navbat bilan chaladi,
shunda tabiat tovushi takrorlanib "mashinadek" bo'lib qolmaydi.

Aks sado (reverb) FAQAT ataylab tanlangan 3 tovushda: chuqur tomchi, g'orda tomchi, shamol qo'ng'irog'i. Qolgan hammasi quruq:
ularning uzunligi va "jonliligi" aks sadodan emas, narsaning o'z tabiiy so'nishidan (pufakcha, ikkilamchi tomchilar,
yog'och va shishaning jaranglashi, don-donli shovqin) keladi.

Ishga tushirish (loyiha ildizidan):
    python3 tools/make_sounds.py                 # tovushlarni yozadi
    python3 tools/make_sounds.py --report        # o'lchovlar jadvalini ham chiqaradi
    python3 tools/make_sounds.py --plots /tmp/p  # spektrogramma rasmlarini ham saqlaydi (matplotlib kerak)

Talab: python3, numpy, scipy. Natija har safar bir xil (tasodifiy sonlar tovush nomi va variant raqamiga bog'langan).

Balandlik: oldingi (v32) tovushlar "tik" ohangiga nisbatan tenglashtirilgan va juda past edi; v33 da har sinf uchun mutlaq nishon
(TARGET_DB, A-vaznli, 250 ms oynada) berilgan: v32 dan o'zgargan 22 ta tovush o'rtacha 3,7 dB baland (eng kichigi +0,9, eng kattasi +5,5 dB).
Cho'qqi chegarasi (PEAK_MAX) tufayli ba'zi qisqa zarbali tovushlar (tomchi, yomg'ir tomchisi, yog'och qadam) nishondan 2-6 dB past qoladi.
Klassik oltita ohang v31/v32 dagidek qoladi.
"""
import argparse
import os
import sys
import wave
import zlib

import numpy as np
from scipy import signal

SR = 44100
SQ2 = float(np.sqrt(2.0))


# ---------------------------------------------------------------------------------------------------------------- yordamchilar
# (n_of ... tone_seq: v32 dagidek o'zgarmagan, klassik ohanglar shularga tayanadi)

def n_of(sec):
    return int(round(sec * SR))


def axis(n):
    return np.arange(n) / SR


def seeded(name):
    return np.random.default_rng(zlib.crc32(name.encode("utf-8")))


def _filt(x, kind, freqs, order):
    sos = signal.butter(order, freqs, btype=kind, fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=-1)


def bp(x, lo, hi, order=2):
    return _filt(x, "bandpass", [lo, hi], order)


def lp(x, fc, order=2):
    return _filt(x, "lowpass", fc, order)


def hp(x, fc, order=2):
    return _filt(x, "highpass", fc, order)


class Buf:
    """Vaqt bo'yicha tovushlarni joylashtiradigan bir kanalli bufer."""

    def __init__(self, dur):
        self.x = np.zeros(n_of(dur))

    def add(self, y, at=0.0, gain=1.0):
        i = n_of(at)
        j = i + len(y)
        if j > len(self.x):
            self.x = np.concatenate([self.x, np.zeros(j - len(self.x))])
        self.x[i:j] += gain * y
        return self


def decay_env(n, tau, attack=0.0006):
    t = axis(n)
    e = np.exp(-t / tau)
    if attack > 0:
        e = e * np.minimum(1.0, t / attack)
    return e


def fade_env(n, fin, fout):
    """Kirish va chiqishda kosinusli yumshoq o'zgarish (soniyada)."""
    e = np.ones(n)
    a = min(n, n_of(fin))
    r = min(n, n_of(fout))
    if a > 1:
        e[:a] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    if r > 1:
        e[n - r:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(r) / r)
    return e


def swell(n, lo=0.0, hi=1.0, power=2.0):
    """lo..hi oralig'ida (0..1) ko'tarilib tushuvchi sin^power to'lqin; tashqarisi nol."""
    t = np.linspace(0.0, 1.0, n)
    u = np.clip((t - lo) / max(hi - lo, 1e-9), 0.0, 1.0)
    return np.sin(np.pi * u) ** power


def slow_noise(rng, n, fc):
    """Birlik dispersiyali past chastotali shovqin (sekin tebranish uchun)."""
    x = lp(rng.standard_normal(n), fc, 2)
    s = np.std(x)
    return x / s if s > 0 else x


def pink(rng, n):
    """Pushti shovqin (1/f): oq shovqindan yumshoqroq, tabiiyroq eshitiladi. Birlik dispersiya."""
    w = rng.standard_normal(n)
    y = np.zeros(n)
    for a, g in [(0.99886, 0.0555179), (0.99332, 0.0750759), (0.96900, 0.1538520),
                 (0.86650, 0.3104856), (0.55000, 0.5329522), (-0.7616, -0.0168980)]:
        y += signal.lfilter([g], [1.0, -a], w)
    y += 0.5362 * w
    y[1:] += 0.115926 * w[:-1]
    y = hp(y, 45, 2)  # 1/f yaqinlashuvining past chastotali "siljishi" (dinamikda eshitilmaydi, faqat joy oladi) olib tashlanadi
    return y / (np.std(y) + 1e-12)


def impact(rng, dur=0.008, lo=1500, hi=9000, tau=None):
    n = n_of(dur)
    x = bp(rng.standard_normal(n), lo, hi, 2)
    return x * decay_env(n, tau or dur / 3.0, 0.0002)


def tone_seq(parts, fade=0.004, harm=(1.0,)):
    """Oddiy ohanlar ketma-ketligi: [(chastota, davomiylik, keyingi tovushgacha pauza), ...]."""
    b = Buf(0.0)
    at = 0.0
    for f, d, gap in parts:
        n = n_of(d)
        t = axis(n)
        x = np.zeros(n)
        for k, h in enumerate(harm):
            x += h * np.sin(2 * np.pi * f * (k + 1) * t)
        x *= fade_env(n, fade, fade)
        b.add(x, at)
        at += d + gap
    return b.x


# ------------------------------------------------------------------------------------------------------- v33: yangi yordamchilar

def U(rng, a, b):
    return float(rng.uniform(a, b))


def LU(rng, a, b):
    """Logarifmik tekis tasodifiy son (chastota va hajm uchun)."""
    return float(np.exp(rng.uniform(np.log(a), np.log(b))))


def pan_gains(p):
    """Doimiy quvvatli siljitish, markazda har kanalda 1,0 (bir kanalli tovush ikki kanalga balandligini o'zgartirmay o'tadi)."""
    th = (min(1.0, max(-1.0, float(p))) + 1.0) * np.pi / 4.0
    return SQ2 * float(np.cos(th)), SQ2 * float(np.sin(th))


class Mix:
    """Ikki kanalli bufer: add(bir yoki ikki kanalli tovush, vaqt, kuch, siljish -1..+1)."""

    def __init__(self, dur=0.0):
        self.x = np.zeros((2, n_of(dur)))

    def add(self, y, at=0.0, gain=1.0, pan=0.0):
        y = np.asarray(y, dtype=float)
        if y.ndim == 1:
            l, r = pan_gains(pan)
            y = np.stack([y * l, y * r])
        i = n_of(at)
        j = i + y.shape[1]
        if j > self.x.shape[1]:
            self.x = np.concatenate([self.x, np.zeros((2, j - self.x.shape[1]))], axis=1)
        self.x[:, i:j] += gain * y
        return self


def noise2(rng, n):
    """Ikki mustaqil oq shovqin (kanallar bir-biriga bog'liq emas: keng, lekin bir kanalli karnayda so'nmaydigan tasvir)."""
    return rng.standard_normal((2, n))


def pink2(rng, n):
    return np.stack([pink(rng, n), pink(rng, n)])


def smooth(y, w):
    """Hann oynasi bilan silliqlash (egri chiziqlarni yumshatish uchun); chekkalar takrorlanadi."""
    w = int(max(1, w))
    if w <= 1:
        return y
    k = np.hanning(w + 2)[1:-1]
    k = k / k.sum()
    pad = w // 2
    yp = np.concatenate([np.full(pad, y[0]), y, np.full(pad, y[-1])])
    return np.convolve(yp, k, mode="same")[pad:pad + len(y)]


def curve(points, n, sm=0.004):
    """(vaqt soniyada, qiymat) juftliklaridan n namunali silliq egri chiziq."""
    ts = [p[0] for p in points]
    vs = [p[1] for p in points]
    return smooth(np.interp(axis(n), ts, vs), n_of(sm))


def sample_times(rng, k, env):
    """k ta namuna indeksi, env (>=0) ga mutanosib zichlikda."""
    c = np.cumsum(np.maximum(env, 0.0))
    if len(c) == 0 or c[-1] <= 0 or k <= 0:
        return np.zeros(0, dtype=int)
    u = rng.uniform(0.0, c[-1], int(k))
    return np.minimum(np.searchsorted(c, u), len(c) - 1)


def grains(rng, n, k, env, flo, fhi, tau_lo, tau_hi, sigma=0.6):
    """
    Don-donli tovush (shag'al, qor, barg, olov, yomg'ir): k ta qisqa so'nuvchi rezonans, zichligi env ga mutanosib.
    Har dona tasodifiy chastotada (flo..fhi), so'nish vaqti (tau_lo..tau_hi) va logarifmik-normal kuchda.
    """
    y = np.zeros(n)
    for i in sample_times(rng, k, env):
        i = int(i)
        f = LU(rng, flo, fhi)
        tau = LU(rng, tau_lo, tau_hi)
        a = float(rng.lognormal(0.0, sigma))
        m = min(n - i, n_of(min(tau * 7.0, 0.04)))
        if m < 4:
            continue
        tt = np.arange(m) / SR
        y[i:i + m] += a * np.sin(2 * np.pi * f * tt + U(rng, 0.0, 6.2832)) * np.exp(-tt / tau)
    return y


def svf_bp(x, fc, q=2.0):
    """Vaqt bo'yicha o'zgaruvchan markaziy chastotali polosali filtr (Chamberlin holat-o'zgaruvchan filtri). Cho'qqi kuchaytirish 1."""
    n = len(x)
    fc = np.broadcast_to(np.asarray(fc, dtype=float), (n,))
    f = (2.0 * np.sin(np.pi * np.minimum(fc, 9000.0) / SR)).tolist()
    xs = np.asarray(x, dtype=float).tolist()
    qi = 1.0 / q
    lo = 0.0
    bd = 0.0
    out = [0.0] * n
    for i in range(n):
        lo += f[i] * bd
        hi = xs[i] - lo - qi * bd
        bd += f[i] * hi
        out[i] = bd
    return np.asarray(out) * qi


def bubble2(rng, f0, rise=0.30, h2=0.10, jitter=0.003, tau_scale=1.6, dur=None):
    """
    Havo pufakchasining Minnaert tebranishi (Van den Doel): boshlang'ich chastota f0, so'nish f0 ga bog'liq (katta pufakcha sekin
    so'nadi), chastota so'nish paytida `rise` nisbatda ko'tariladi, ikkinchi garmonika va kichik tebranish (jitter) tabiiylik beradi.
    tau_scale: qayd etilgan tovushlarda pufakcha erkin suvdagiga qaraganda biroz uzoqroq jaranglaydi.
    """
    d = 0.043 * f0 + 0.0014 * f0 ** 1.5
    tau = tau_scale / d
    n = n_of(dur if dur else min(7.0 * tau, 0.6))
    t = axis(n)
    f = f0 * (1.0 + rise * (1.0 - np.exp(-t / (2.2 * tau))))
    if jitter and n > 400:
        f = f * (1.0 + jitter * slow_noise(rng, n, 35))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + h2 * np.sin(2 * ph + 0.7)
    return x * np.exp(-t / tau) * np.minimum(1.0, t / 0.0008)


def strike(freqs, taus, amps, dur, hard=0.0008, rng=None, detune=0.0):
    """
    Qattiq jism zarbasi (modal sintez): so'nuvchi sinuslar yig'indisi, so'ng zarba vaqti `hard` (soniya) ga teng sin^1,5 impuls bilan
    "yumshatiladi": qattiq zarba (kichik hard) yorqin, yumshoq zarba (katta hard) xira. detune: har chalinganda chastotalar siljishi.
    """
    n = n_of(dur)
    t = axis(n)
    y = np.zeros(n)
    for f, tau, a in zip(freqs, taus, amps):
        if rng is not None and detune:
            f = f * (1.0 + U(rng, -detune, detune))
        if f >= SR * 0.45:
            continue
        y += a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau)
    m = max(2, n_of(hard))
    p = np.sin(np.pi * np.linspace(0.0, 1.0, m)) ** 1.5
    p = p / np.sum(p)
    y = np.convolve(y, p)[:n]
    return y * fade_env(n, 0.0, min(0.10, dur / 5.0))


def pitched(f0, ratios, taus, amps, dur, hard=0.0008, rng=None, detune=0.0005, pair=0.0):
    """Ohangli zarba (marimba, shisha, qo'ng'iroq): chastotalari f0 ga nisbatan; pair>0 bo'lsa har qism biroz farqli ikkinchi nusxa bilan ("titrash")."""
    fr = [f0 * r for r in ratios]
    y = strike(fr, taus, amps, dur, hard, rng, detune)
    if pair:
        y = y + 0.6 * strike([f * (1.0 + pair) for f in fr], taus, amps, dur, hard, rng, detune)
    return y


# --------------------------------------------------------------------------------------------------------------- aks sado (faqat 3 tovushda)

def make_ir(rng, rt60, pre=0.010, damp=1.0, early=6, size=1.0):
    """
    Ikki kanalli xona impuls javobi: erta aks sadolar (alohida urilishlar) va chastotaga qarab so'nuvchi tarqoq quyruq.
    Yuqori chastotalar tezroq so'nadi (havo va devorlar yutadi); damp=0: hamma polosa bir xil so'nadi.
    """
    ln = n_of(min(1.3 * rt60 + pre, 3.2))
    t = axis(ln)
    edges = [(70, 300), (300, 900), (900, 2600), (2600, 6500), (6500, 15000)]
    mult = [1.2, 1.0, 0.75, 0.5, 0.28]
    ir = np.zeros((2, ln))
    for c in range(2):
        for (lo, hi), m in zip(edges, mult):
            tb = max(0.05, rt60 * (1.0 - damp * (1.0 - m)))
            ir[c] += bp(rng.standard_normal(ln), lo, hi, 2) * np.exp(-6.9078 * t / tb)
    ir *= 1.0 - np.exp(-t / 0.015)
    ir[:, : n_of(pre)] = 0.0
    ir /= np.sqrt(np.sum(ir ** 2, axis=1, keepdims=True)) + 1e-12
    for c in range(2):
        for k in range(early):
            at = pre + (0.004 + 0.013 * k) * size * U(rng, 0.7, 1.4)
            i = n_of(at)
            if i < ln:
                ir[c, i] += (1.0 if coin(rng) else -1.0) * 0.16 * (0.86 ** k)
    ir /= np.sqrt(np.sum(ir ** 2, axis=1, keepdims=True)) + 1e-12
    return ir


def coin(rng, p=0.5):
    return bool(rng.uniform() < p)


def space(x, rng, rt60=1.0, pre=0.012, wet_db=-9.0, damp=1.0, early=6, size=1.0):
    """Tovushga aks sado qo'shadi (bir kanalli kirish ikki kanalli chiqishga aylanadi). wet_db: aks sado quvvati quruq tovushga nisbatan."""
    ir = make_ir(rng, rt60, pre, damp, early, size)
    x2 = x if np.ndim(x) == 2 else np.stack([x, x])
    wl = signal.fftconvolve(x2[0], ir[0])
    wr = signal.fftconvolve(x2[1], ir[1])
    out = np.zeros((2, len(wl)))
    out[:, : x2.shape[1]] += x2
    ex = np.sum(x2 ** 2)
    ew = np.sum(wl ** 2) + np.sum(wr ** 2)
    g = 10 ** (wet_db / 20.0) * np.sqrt(ex / (ew + 1e-12))
    out[0] += g * wl
    out[1] += g * wr
    return out


# ----------------------------------------------------------------------------------------------------------------- tovushlar
# Har tovush: s_<id>(rng) -> bir kanalli (N,) yoki ikki kanalli (2, N) massiv. Bir nechta varianti bo'lsa, har variant o'z rng (urug') bilan
# chaqiriladi: tomchi hajmi, vaqti, pufakchalar soni har safar boshqacha. _VARIANT["k"] variant raqami (ohangli tovushda nota tanlash uchun).

_VARIANT = {"k": 1}


def unit(x):
    """Cho'qqisi 1 ga keltiradi (qismlarni bir-biriga nisbatan aniq kuchda aralashtirish uchun)."""
    return x / (np.max(np.abs(x)) + 1e-12)


# ---- klassik ohanglar (v31/v32 dagidek, baytma-bayt o'zgarmaydi)

def s_tone_tik(rng):
    return tone_seq([(1200, 0.018, 0.0)])


def s_tone_tuk(rng):
    return tone_seq([(900, 0.016, 0.0), (1500, 0.022, 0.0)])


def s_tone_edge(rng):
    return tone_seq([(330, 0.07, 0.0), (260, 0.09, 0.0)])


def s_tone_window(rng):
    return tone_seq([(660, 0.05, 0.0), (880, 0.07, 0.0)])


def s_tone_scroll(rng):
    return tone_seq([(820, 0.010, 0.026), (820, 0.010, 0.026), (820, 0.010, 0.0)], fade=0.002)


def s_tone_error(rng):
    return tone_seq([(250, 0.07, 0.015), (200, 0.12, 0.0)], fade=0.006, harm=(1.0, 0.5, 0.33))


# ---- suv

def water_drop(rng, f0, dur=0.6, sec=2, thump=0.35, splash=0.22, ripple=0.05, basin=0.0, rise=None, tick=0.10):
    """
    Bitta suv tomchisi (quruq, yaqindan yozilgandek). Haqiqiy tomchi bir "blyum" emas, bir necha qismdan iborat:
    1) sathga tegish "tik"i va chayqalish shovqini (tomchi qanchalik katta bo'lsa, shuncha uzun va past);
    2) asosiy havo pufakchasi (chastotasi ko'tarilib so'nadi);
    3) kavitatsiyaning past "gup"i;
    4) 1-3 ta kichik ikkilamchi pufakcha (tomchidan keyin sekin-asta);
    5) sath tinchlanayotgandagi mayda to'lqinchalar shitirlashi (tez-tez tebranuvchi yuqori chastotali shovqin);
    6) ixtiyoriy: idish (havza) rezonansi.
    """
    rise = U(rng, 0.25, 0.5) if rise is None else rise
    b = Buf(dur)
    sd = 0.006 + 3.5 / f0
    n = n_of(sd * 6.0)
    crown = bp(rng.standard_normal(n), max(500.0, 0.7 * f0), min(9000.0, 6.0 * f0), 2) * decay_env(n, sd, 0.0006)
    b.add(crown, 0.0, splash)
    b.add(impact(rng, 0.0012, 2500, 9000, 0.0004), 0.0, tick)
    t0 = U(rng, 0.0035, 0.007)
    b.add(bubble2(rng, f0, rise=rise), t0, 1.0)
    nt = n_of(0.09)
    tt = axis(nt)
    fr = f0 * 0.45 * (1.25 - 0.5 * tt / 0.09)
    b.add(np.sin(2 * np.pi * np.cumsum(fr) / SR) * decay_env(nt, 0.028, 0.002), 0.001, thump)
    at = t0
    for i in range(sec):
        at += U(rng, 0.030, 0.075) * (1.0 + 0.7 * i) * (1.0 + 300.0 / f0)
        fi = f0 * LU(rng, 1.5, 3.6)
        b.add(bubble2(rng, fi, rise=U(rng, 0.1, 0.5)), at, 0.5 * (0.6 ** i) * U(rng, 0.7, 1.1))
    tau_r = 0.07 + 20.0 / f0
    nr = n_of(min(dur, 6.0 * tau_r))
    tr = axis(nr)
    rp = bp(pink(rng, nr), 2600, 8500, 2) * np.exp(-tr / tau_r) * np.minimum(1.0, tr / 0.01)
    rp = rp * (1.0 + 0.5 * np.sin(2 * np.pi * U(rng, 18.0, 45.0) * tr + U(rng, 0.0, 6.28)))
    b.add(rp, 0.004, ripple)
    if basin > 0:
        fb = U(rng, 260.0, 470.0)
        b.add(strike([fb, fb * 2.31, fb * 3.9], [0.075, 0.04, 0.02], [1.0, 0.35, 0.15], 0.35, 0.0015), 0.002, basin)
    return b.x


def s_drop_tiny(rng):
    return water_drop(rng, LU(rng, 1250, 1750), dur=0.42, sec=2, thump=0.16, splash=0.20, ripple=0.07)


def s_drop_water(rng):
    return water_drop(rng, LU(rng, 680, 900), dur=0.75, sec=3, thump=0.34, splash=0.22, ripple=0.06, basin=0.10)


def s_drop_big(rng):
    return water_drop(rng, LU(rng, 400, 520), dur=1.0, sec=4, thump=0.50, splash=0.28, ripple=0.06)


def s_drop_stone(rng):
    """Suvga tosh tushishi: kuchli chayqalish va past "gup"."""
    b = Buf(0.85)
    b.add(water_drop(rng, LU(rng, 300, 400), dur=0.9, sec=3, thump=0.60, splash=0.35, ripple=0.07), 0.0, 1.0)
    n = n_of(0.22)
    b.add(bp(rng.standard_normal(n), 400, 5500, 2) * decay_env(n, 0.05, 0.001), 0.0, 0.35)
    return b.x


def s_drop_pair(rng):
    b = Buf(1.0)
    b.add(water_drop(rng, LU(rng, 900, 1100), dur=0.55, sec=1, thump=0.25, splash=0.20, ripple=0.05), 0.0, 1.0)
    b.add(water_drop(rng, LU(rng, 1250, 1500), dur=0.50, sec=1, thump=0.20, splash=0.18, ripple=0.05), 0.27, 0.75)
    return b.x


def s_drop_deep(rng):
    """Chuqur tomchi (quduq, g'or): ATAYLAB aks sadoli. Pastki chastotali katta pufakcha va uzun so'nuvchi aks sado."""
    x = water_drop(rng, LU(rng, 230, 300), dur=0.9, sec=2, thump=0.60, splash=0.22, ripple=0.04, rise=0.7)
    return space(x, rng, rt60=1.6, pre=0.014, wet_db=-6.0, damp=1.0, early=7, size=1.6)


def s_drop_cave(rng):
    """G'orda tomchi: ATAYLAB aks sadoli. Yuqoriroq tomchi, juda uzun aks sado, erta aks sadolar ko'p."""
    x = water_drop(rng, LU(rng, 520, 680), dur=0.7, sec=2, thump=0.30, splash=0.20, ripple=0.05)
    return space(x, rng, rt60=2.1, pre=0.022, wet_db=-4.0, damp=0.8, early=9, size=2.3)


def s_water_splash(rng):
    """Suv sathiga urilish: chayqalish shovqini, past "gumb", ko'plab pufakchalar (boshida zich) va keyin sekin tomchilar."""
    dur = 1.0
    m = Mix(dur)
    n = n_of(0.5)
    crown = np.stack([bp(rng.standard_normal(n), 600, 7500, 2), bp(rng.standard_normal(n), 600, 7500, 2)]) * decay_env(n, 0.055, 0.002)
    m.add(crown, 0.0, 0.50)
    hiss = np.stack([bp(rng.standard_normal(n), 3000, 9500, 2), bp(rng.standard_normal(n), 3000, 9500, 2)]) * decay_env(n, 0.14, 0.004)
    m.add(hiss, 0.0, 0.12)
    nl = n_of(0.16)
    tl = axis(nl)
    low = np.sin(2 * np.pi * np.cumsum(300.0 - 160.0 * np.minimum(1.0, tl / 0.12)) / SR) * decay_env(nl, 0.05, 0.002)
    m.add(low, 0.0, 0.55)
    for _ in range(30):
        at = float(-0.10 * np.log(1.0 - rng.uniform(0.0, 0.93)))
        a = U(rng, 0.15, 0.55) * float(np.exp(-at / 0.22))
        m.add(bubble2(rng, LU(rng, 380, 3300), rise=U(rng, 0.2, 0.8), tau_scale=1.2), 0.004 + at, a, pan=U(rng, -0.8, 0.8))
    for _ in range(7):
        m.add(bubble2(rng, LU(rng, 1100, 3500), rise=U(rng, 0.2, 0.7), tau_scale=1.2), U(rng, 0.30, 0.85), U(rng, 0.08, 0.20), pan=U(rng, -0.8, 0.8))
    return m.x


def s_water_ripple(rng):
    """To'lqinchalar: yumshoq tomchi, so'ng sohilga ketma-ket sekin urilayotgan kichik to'lqinlar (chap-o'ng almashinadi)."""
    dur = 1.1
    m = Mix(dur)
    m.add(water_drop(rng, LU(rng, 800, 1000), dur=0.4, sec=1, thump=0.25, splash=0.18, ripple=0.05), 0.0, 0.9)
    for k, at in enumerate([0.22, 0.38, 0.58, 0.82]):
        ln = n_of(U(rng, 0.10, 0.15))
        f = LU(rng, 900, 1500)
        nz = noise2(rng, ln)
        lap = np.stack([bp(nz[0], f * 0.7, f * 1.5, 2), bp(nz[1], f * 0.7, f * 1.5, 2)]) * swell(ln, 0.0, 1.0, 2.0)
        m.add(lap, at + U(rng, -0.01, 0.01), 0.55 * (0.7 ** k))
        m.add(bubble2(rng, f * U(rng, 1.2, 1.9), rise=0.4), at + 0.03, 0.22 * (0.7 ** k), pan=(-0.5 if k % 2 == 0 else 0.5))
    return m.x


def s_water_brook(rng):
    """Soy: zich pufakchalar oqimi (soniyasiga ~150) va keng polosali shovqin, ikki kanalda mustaqil."""
    dur = 1.5
    n = n_of(dur)
    m = Mix(dur)
    w = pink2(rng, n)
    bed = np.stack([bp(w[0], 350, 2600, 2), bp(w[1], 350, 2600, 2)])
    slow = np.clip(1.0 + 0.25 * slow_noise(rng, n, 6), 0.3, None)
    m.add(bed * slow * fade_env(n, 0.15, 0.35), 0.0, 0.09)
    for _ in range(int(150 * dur)):
        at = U(rng, 0.0, dur - 0.05)
        e = max(0.0, min(1.0, at / 0.15, (dur - at) / 0.35))
        m.add(bubble2(rng, LU(rng, 450, 4200), rise=U(rng, 0.3, 1.0), tau_scale=1.0, jitter=0.0), at, U(rng, 0.10, 0.50) * e, pan=U(rng, -0.85, 0.85))
    return m.x


def s_water_wave(rng):
    """Dengiz to'lqini: past gumburlash, o'rta chastotalar, ko'pik shitirlashi va qaytayotganda mayda toshlar; chapdan o'ngga siljiydi."""
    dur = 1.9
    n = n_of(dur)
    w = pink2(rng, n)
    low = bp(w, 90, 420, 2) * swell(n, 0.0, 0.62, 2.0)
    mid = bp(w, 420, 1800, 2) * swell(n, 0.10, 0.75, 2.0)
    high = bp(w, 1800, 6500, 2) * swell(n, 0.30, 0.90, 3.0)
    back = bp(w[:, ::-1].copy(), 1500, 6000, 2) * swell(n, 0.50, 1.0, 2.0)
    y = 1.0 * low + 0.85 * mid + 0.5 * high + 0.25 * back
    u = np.linspace(0.0, 1.0, n)
    y = y * np.stack([1.0 - 0.3 * u, 0.7 + 0.3 * u]) * fade_env(n, 0.03, 0.25)
    m = Mix(dur)
    m.add(y, 0.0, 1.0)
    env_b = swell(n, 0.45, 1.0, 2.0)
    peb = np.stack([grains(rng, n, 50, env_b, 1500, 5200, 0.001, 0.004), grains(rng, n, 50, env_b, 1500, 5200, 0.001, 0.004)])
    m.add(peb, 0.0, 0.05)
    return m.x


def s_water_fountain(rng):
    """Favvora: ko'plab mayda tomchilar kichik havzaga tushadi (har biri alohida pufakcha va "tink"), ustida yupqa shitirlash."""
    dur = 1.3
    n = n_of(dur)
    m = Mix(dur)
    hiss = np.stack([bp(pink(rng, n), 2500, 9000, 2), bp(pink(rng, n), 2500, 9000, 2)]) * fade_env(n, 0.12, 0.3)
    m.add(hiss, 0.0, 0.06)
    for _ in range(int(46 * dur)):
        at = U(rng, 0.0, dur - 0.08)
        e = max(0.0, min(1.0, at / 0.12, (dur - at) / 0.30))
        p = U(rng, -0.8, 0.8)
        m.add(bubble2(rng, LU(rng, 950, 3000), rise=U(rng, 0.2, 0.7), tau_scale=1.3), at, U(rng, 0.12, 0.60) * e, pan=p)
        if coin(rng, 0.5):
            m.add(impact(rng, 0.002, 2500, 8000, 0.0006), at, 0.08 * e, pan=p)
    return m.x


# ---- yomg'ir

def rain_hit(rng, kind="hard", f=None):
    """Bitta yomg'ir tomchisi: qattiq sirt (yog'och, tom), barg yoki ko'lmak."""
    if kind == "puddle":
        return water_drop(rng, LU(rng, 1000, 1700), dur=0.3, sec=1, thump=0.15, splash=0.2, ripple=0.04)
    if kind == "leaf":
        n = n_of(0.09)
        y = bp(rng.standard_normal(n), 600, 3500, 2) * decay_env(n, 0.012, 0.002)
        fl = LU(rng, 850, 1600)
        return y + 0.6 * strike([fl, fl * 1.7], [0.022, 0.012], [1.0, 0.4], 0.09, 0.0015)
    f = f or LU(rng, 1600, 3400)
    y = np.zeros(n_of(0.14))
    y += strike([f, f * 1.55, f * 2.4], [0.012, 0.007, 0.004], [1.0, 0.45, 0.2], 0.14, 0.0004, rng, 0.01)
    body = U(rng, 500, 900)
    y += 0.4 * strike([body, body * 2.2], [0.020, 0.010], [1.0, 0.3], 0.14, 0.001)
    ik = impact(rng, 0.0012, 2500, 9000, 0.0004)
    y[: len(ik)] += 0.15 * ik
    return y


def s_rain_tap(rng):
    b = Buf(0.3)
    f = LU(rng, 2000, 3200)
    b.add(rain_hit(rng, "hard", f), 0.0, 1.0)
    at = 0.0
    for i in range(int(rng.integers(2, 4))):
        at += U(rng, 0.025, 0.07)
        b.add(rain_hit(rng, "hard", f * U(rng, 1.1, 1.5)), at, 0.35 * (0.6 ** i))
    return b.x


def s_rain_leaves(rng):
    dur = 0.75
    m = Mix(dur)
    k = int(rng.integers(7, 11))
    for at in sorted([0.0] + [U(rng, 0.03, 0.62) for _ in range(k - 1)]):
        m.add(rain_hit(rng, "leaf"), at, U(rng, 0.4, 1.0), pan=U(rng, -0.7, 0.7))
    n = n_of(dur)
    w = pink2(rng, n)
    m.add(np.stack([bp(w[0], 1200, 6000, 1), bp(w[1], 1200, 6000, 1)]) * fade_env(n, 0.08, 0.25), 0.0, 0.05)
    return m.x


def s_rain_shower(rng):
    dur = 1.6
    n = n_of(dur)
    m = Mix(dur)
    w = pink2(rng, n)
    am = np.clip(1.0 + 0.3 * slow_noise(rng, n, 20), 0.3, None)
    m.add(np.stack([bp(w[0], 600, 7000, 2), bp(w[1], 600, 7000, 2)]) * am * fade_env(n, 0.20, 0.45), 0.0, 0.28)
    for _ in range(int(95 * dur)):
        at = U(rng, 0.02, dur - 0.12)
        e = max(0.0, min(1.0, at / 0.2, (dur - at) / 0.45))
        m.add(rain_hit(rng, "hard" if rng.uniform() < 0.55 else "leaf"), at, U(rng, 0.15, 0.65) * e, pan=U(rng, -0.9, 0.9))
    return m.x


def s_rain_roof(rng):
    """Tomga yomg'ir: metall tom, har tomchi uzoqroq jaranglaydi; vaqti-vaqti bilan yirik tomchi va tom rezonansi."""
    dur = 1.3
    n = n_of(dur)
    m = Mix(dur)
    w = pink2(rng, n)
    m.add(np.stack([bp(w[0], 900, 3500, 2), bp(w[1], 900, 3500, 2)]) * fade_env(n, 0.15, 0.4), 0.0, 0.08)
    for _ in range(int(42 * dur)):
        at = U(rng, 0.0, dur - 0.2)
        e = max(0.0, min(1.0, at / 0.15, (dur - at) / 0.4))
        f = LU(rng, 1800, 4200)
        y = strike([f, f * 1.6, f * 2.7], [0.030, 0.018, 0.010], [1.0, 0.5, 0.25], 0.2, 0.0004, rng, 0.01)
        m.add(y, at, U(rng, 0.12, 0.55) * e, pan=U(rng, -0.9, 0.9))
    for at in (0.25, 0.7, 1.0):
        fb = U(rng, 700, 1100)
        m.add(strike([fb, fb * 2.1], [0.06, 0.03], [1.0, 0.4], 0.25, 0.001), at, 0.45, pan=U(rng, -0.6, 0.6))
    return m.x


def s_rain_puddle(rng):
    return rain_hit(rng, "puddle")


# ---- qushlar va hasharotlar

def voice(f, a, rng, harm=(1.0, 0.18, 0.05), breath=0.0):
    """Qush ovozi: chastotasi f(t) bo'lgan garmonikalar yig'indisi, amplitudasi a(t) va nafas shovqini."""
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.zeros(len(f))
    for k, h in enumerate(harm):
        x += h * np.sin((k + 1) * ph)
    if breath > 0:
        fm = float(np.mean(f))
        x += breath * bp(rng.standard_normal(len(f)), max(300.0, fm * 0.7), min(10000.0, fm * 1.8), 1)
    return x * a


def syllable(rng, pts, dur, vib=None, harm=(1.0, 0.15, 0.05), breath=0.02, attack=0.12, release=0.35, wob=0.01):
    """Qush bo'g'ini: pts = [(0..1 nisbiy vaqt, chastota Hz), ...], ixtiyoriy tebranish vib=(Hz, chuqurlik) va tasodifiy mayda tebranish wob."""
    n = n_of(dur)
    f = curve([(p[0] * dur, p[1]) for p in pts], n, sm=0.003)
    if vib:
        f = f + vib[1] * np.sin(2 * np.pi * vib[0] * axis(n))
    f = f * (1.0 + wob * slow_noise(rng, n, 60))
    u = np.linspace(0.0, 1.0, n)
    a = np.minimum(1.0, u / attack) * np.minimum(1.0, (1.0 - u) / release) ** 1.2
    return voice(f, a, rng, harm, breath)


def s_bird_tweet(rng):
    b = Buf(0.8)
    k = LU(rng, 0.93, 1.07)
    h = (1.0, 0.12, 0.04)
    b.add(syllable(rng, [(0, 2500 * k), (1, 3600 * k)], 0.085, harm=h), 0.0, 0.8)
    b.add(syllable(rng, [(0, 3000 * k), (0.55, 4000 * k), (1, 3500 * k)], 0.11, vib=(52, 90), harm=h), 0.14, 1.0)
    b.add(syllable(rng, [(0, 2800 * k), (1, 3300 * k)], 0.07, harm=h), 0.32, 0.6)
    b.add(syllable(rng, [(0, 3300 * k), (0.5, 3900 * k), (1, 2900 * k)], 0.12, vib=(40, 70), harm=h), 0.46, 0.75)
    return b.x


def s_bird_trill(rng):
    b = Buf(0.9)
    t = 0.0
    pulses = 13
    for i in range(pulses):
        amp = np.sin(np.pi * (i + 0.5) / pulses) ** 1.1
        f0 = 2300 + 55 * i + U(rng, -35, 35)
        b.add(syllable(rng, [(0, f0), (1, f0 + 750)], 0.032, harm=(1.0, 0.1, 0.03), breath=0.01), t, float(amp))
        t += 0.052 - 0.0015 * i
    b.add(syllable(rng, [(0, 3600), (1, 2700)], 0.16, vib=(30, 60), harm=(1.0, 0.1)), t + 0.03, 0.7)
    return b.x


def s_bird_dove(rng):
    """Kaptar g'u-g'usi: to'rt past nota, garmonikalarga boy, biroz titroq; yumshoq (1,9 kHz dan yuqorisi olib tashlanadi)."""
    b = Buf(1.1)
    for f0, f1, dur, at, amp in [(440, 470, 0.09, 0.00, 0.5), (480, 530, 0.20, 0.12, 1.0), (500, 430, 0.26, 0.38, 0.85), (470, 400, 0.28, 0.70, 0.7)]:
        n = n_of(dur)
        t = axis(n)
        f = np.linspace(f0, f1, n) * (1.0 + 0.012 * np.sin(2 * np.pi * 6.0 * t))
        u = np.linspace(0.0, 1.0, n)
        a = np.minimum(1.0, u / 0.25) * np.minimum(1.0, (1.0 - u) / 0.35)
        b.add(voice(f, a, rng, harm=(1.0, 0.5, 0.25, 0.1), breath=0.03), at, amp)
    return lp(b.x, 1900, 2)


def s_bird_sparrow(rng):
    b = Buf(0.7)
    t = 0.0
    for _ in range(int(rng.integers(4, 7))):
        f0 = U(rng, 3800, 4800)
        d = U(rng, 0.035, 0.06)
        b.add(syllable(rng, [(0, f0), (1, f0 * U(rng, 0.62, 0.8))], d, harm=(1.0, 0.45, 0.2, 0.08), breath=0.05, attack=0.1, release=0.45), t, U(rng, 0.6, 1.0))
        t += d + U(rng, 0.045, 0.11)
    return b.x


def s_bird_bulbul(rng):
    """Bulbul: hushtak, tez ko'tariluvchi chirqillashlar, tremolo va yakuniy tushuvchi hushtak."""
    b = Buf(1.5)
    b.add(syllable(rng, [(0, 2100), (0.6, 3300), (1, 3100)], 0.20, harm=(1.0, 0.1), breath=0.01, attack=0.2, release=0.3), 0.0, 0.85)
    t = 0.26
    for i in range(3):
        b.add(syllable(rng, [(0, 2600 + 150 * i), (1, 3900 + 150 * i)], 0.05, harm=(1.0, 0.12)), t, 0.8)
        t += 0.075
    t = 0.55
    for i in range(14):
        b.add(syllable(rng, [(0, 3600), (1, 3300 - 25 * i)], 0.026, harm=(1.0, 0.08)), t, 0.75 * float(np.sin(np.pi * (i + 0.5) / 14) ** 0.8))
        t += 0.032
    b.add(syllable(rng, [(0, 1800), (1, 2400)], 0.12, harm=(1.0, 0.1)), 1.05, 0.9)
    b.add(syllable(rng, [(0, 3400), (1, 2200)], 0.18, vib=(24, 120), harm=(1.0, 0.1)), 1.20, 1.0)
    return b.x


def s_bird_hoopoe(rng):
    """Hudhud: past, bo'g'iq "up-up-up" uch nota."""
    b = Buf(1.1)
    for i, at in enumerate([0.0, 0.30, 0.60]):
        n = n_of(0.20)
        t = axis(n)
        f = (470.0 - 40.0 * np.minimum(1.0, t / 0.12)) * (1.0 + 0.01 * np.sin(2 * np.pi * 40.0 * t))
        a = np.minimum(1.0, t / 0.02) * np.exp(-t / 0.055) * fade_env(n, 0.0, 0.06)
        b.add(lp(voice(f, a, rng, harm=(1.0, 0.6, 0.3, 0.15, 0.07), breath=0.04), 1800, 2), at, 0.9 if i == 1 else 1.0)
    return b.x


def s_cricket(rng):
    """Chirildoq: har "chirillash" 4 ta tez impuls (4,5 kHz ga yaqin), takrorlanish oralig'i biroz tasodifiy."""
    dur = 1.4
    b = Buf(dur)
    f = LU(rng, 4300, 4900)
    t = 0.0
    while t < dur - 0.25:
        for p in range(4):
            n = n_of(0.018)
            tt = axis(n)
            pulse = (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 1.012 * tt)) * np.minimum(1.0, tt / 0.003) * np.exp(-tt / 0.005) * fade_env(n, 0.0, 0.007)
            b.add(pulse, t + p * 0.021, 0.65 + 0.12 * p)
        t += U(rng, 0.27, 0.33)
    return b.x


def s_leaf_rustle(rng):
    dur = 0.8
    n = n_of(dur)
    env = 0.25 + swell(n, 0.0, 0.45, 2.0) + 0.7 * swell(n, 0.35, 0.85, 2.0)
    g = unit(lp(grains(rng, n, 160, env, 1800, 6500, 0.0015, 0.006, sigma=0.7), 9500, 1))
    bed = unit(bp(pink(rng, n), 1500, 7500, 2)) * env / np.max(env)
    return (g + 0.25 * bed) * fade_env(n, 0.01, 0.15)


def s_wind_breeze(rng):
    """Shabada: sekin siljiydigan polosali shovqin (hushtaksimon) va pushti shovqin; kanallar mustaqil, kuch to'lqinsimon."""
    dur = 1.8
    n = n_of(dur)
    m = Mix(dur)
    sw = swell(n, 0.0, 1.0, 1.6)
    ch = []
    for _ in range(2):
        fc = np.clip(curve([(0, 350), (0.5 * dur, 800), (dur, 450)], n) * (1.0 + 0.15 * slow_noise(rng, n, 1.5)), 200.0, 1500.0)
        y1 = svf_bp(rng.standard_normal(n), fc, 1.8)
        y2 = bp(pink(rng, n), 200, 1200, 2)
        ch.append(0.8 * y1 / (np.std(y1) + 1e-9) + 0.6 * y2)
    m.add(np.stack(ch) * sw, 0.0, 1.0)
    return m.x


def s_fire_crackle(rng):
    """Gulxan: yupqa shitirlash, don-donli chirsillash (tasodifiy zichlik) va vaqti-vaqti bilan yirikroq "chars"."""
    dur = 1.3
    n = n_of(dur)
    m = Mix(dur)
    hiss = np.stack([bp(pink(rng, n), 900, 8000, 1), bp(pink(rng, n), 900, 8000, 1)])
    am = np.clip(1.0 + 0.5 * slow_noise(rng, n, 9), 0.2, None)
    m.add(hiss * am * fade_env(n, 0.1, 0.3), 0.0, 0.05)
    env = fade_env(n, 0.05, 0.25) + 0.02
    cr = np.stack([unit(grains(rng, n, 70, env, 1200, 6000, 0.0008, 0.004, sigma=0.55)), unit(grains(rng, n, 70, env, 1200, 6000, 0.0008, 0.004, sigma=0.55))])
    m.add(cr, 0.0, 0.5)
    for _ in range(int(rng.integers(3, 6))):
        nb = n_of(0.03)
        pop = strike([U(rng, 250, 500)], [0.02], [1.0], 0.1, 0.0015)
        pop[:nb] += 0.8 * bp(rng.standard_normal(nb), 500, 4000, 2) * decay_env(nb, 0.008, 0.0005)
        m.add(unit(pop), U(rng, 0.05, dur - 0.2), U(rng, 0.35, 0.6), pan=U(rng, -0.7, 0.7))
    return m.x


# ---- qadam tovushlari (harakat)

def step_env(n, toe_at, h_tau, t_tau, toe_gain):
    """Qadam: tovon (0 da) va panja (toe_at da) ikki zarba."""
    t = axis(n)
    return np.exp(-t / h_tau) + toe_gain * np.where(t >= toe_at, np.exp(-np.maximum(t - toe_at, 0.0) / t_tau), 0.0)


def s_step_gravel(rng):
    dur = 0.38
    n = n_of(dur)
    toe = U(rng, 0.10, 0.14)
    env = step_env(n, toe, 0.035, 0.030, 0.7)
    g = unit(lp(grains(rng, n, 190, env, 1800, 7000, 0.0015, 0.005, sigma=0.7), 9500, 1))
    thud = unit(lp(rng.standard_normal(n), 420, 2)) * step_env(n, toe, 0.030, 0.025, 0.6)
    return (0.8 * g + 0.45 * thud) * fade_env(n, 0.002, 0.05)


def s_step_grass(rng):
    dur = 0.4
    n = n_of(dur)
    toe = U(rng, 0.11, 0.15)
    env = step_env(n, toe, 0.05, 0.045, 0.7)
    swish = unit(bp(rng.standard_normal(n), 1400, 6500, 2)) * env
    soft = unit(lp(grains(rng, n, 80, env, 1200, 4500, 0.002, 0.007, sigma=0.6), 8000, 1))
    thud = unit(lp(rng.standard_normal(n), 320, 2)) * step_env(n, toe, 0.035, 0.03, 0.6)
    return (0.55 * swish + 0.35 * soft + 0.5 * thud) * fade_env(n, 0.003, 0.06)


def s_step_wood(rng):
    """Yog'och pol: tovon "tok" va panja "tak" (ichi bo'sh yog'och). Telefon karnayi past chastotani chiqarmaydi, shuning uchun 400-1500 Hz qismlari kuchli."""
    b = Buf(0.42)
    f = U(rng, 150, 200)
    heel = strike([f, f * 2.3, f * 4.1, f * 6.2, f * 8.5], [0.05, 0.034, 0.022, 0.014, 0.008], [0.3, 1.0, 0.95, 0.65, 0.35], 0.4, 0.0010, rng, 0.01)
    b.add(heel, 0.0, 1.0)
    nb = n_of(0.02)
    b.add(bp(rng.standard_normal(nb), 600, 4000, 2) * decay_env(nb, 0.004, 0.0005), 0.0, 0.4)
    toe = strike([f * 1.4, f * 3.3, f * 5.9, f * 8.2], [0.035, 0.024, 0.014, 0.008], [0.5, 1.0, 0.8, 0.4], 0.3, 0.0009, rng, 0.01)
    b.add(toe, U(rng, 0.09, 0.13), 0.6)
    return b.x


def s_step_snow(rng):
    """Qorda qadam: baland Q li don-donlar (g'ijirlash) va pastroq "g'archillash"."""
    dur = 0.46
    n = n_of(dur)
    toe = U(rng, 0.13, 0.18)
    env = step_env(n, toe, 0.05, 0.045, 0.7)
    sq = unit(lp(grains(rng, n, 260, env, 2200, 5200, 0.004, 0.012, sigma=0.7), 9000, 1))
    cr = unit(bp(rng.standard_normal(n), 600, 1500, 2)) * step_env(n, toe, 0.025, 0.02, 0.6)
    return (0.75 * sq + 0.45 * cr) * fade_env(n, 0.003, 0.07)


# ---- sokinlik: yog'och, tosh, qo'ng'iroq, kosa, kalimba

def s_bamboo_tap(rng):
    f0 = LU(rng, 640, 780)
    b = Buf(0.55)
    b.add(strike([f0, f0 * 2.54, f0 * 4.6, f0 * 6.9], [0.11, 0.045, 0.02, 0.01], [1.0, 0.55, 0.28, 0.12], 0.55, 0.0007, rng, 0.004), 0.0, 1.0)
    b.add(strike([f0 * 0.5], [0.07], [0.5], 0.2, 0.002), 0.0, 0.5)
    b.add(impact(rng, 0.004, 700, 4500, 0.0012), 0.0, 0.35)
    return b.x


def s_wood_block(rng):
    f0 = LU(rng, 980, 1120)
    b = Buf(0.35)
    b.add(strike([f0, f0 * 2.1, f0 * 3.7], [0.045, 0.022, 0.012], [1.0, 0.45, 0.2], 0.35, 0.0006, rng, 0.004), 0.0, 1.0)
    b.add(strike([420.0, 880.0], [0.03, 0.015], [1.0, 0.3], 0.15, 0.002), 0.0, 0.5)
    b.add(impact(rng, 0.002, 800, 5000, 0.0007), 0.0, 0.25)
    return b.x


def s_pebble(rng):
    """Ikki-uch mayda tosh bir-biriga uriladi: oraliqlari notekis, har biri keyingisidan sal sekinroq."""
    b = Buf(0.4)
    at = 0.0
    for i in range(int(rng.integers(2, 4))):
        f = LU(rng, 1500, 3200)
        y = strike([f, f * 1.7, f * 0.26], [0.014, 0.009, 0.03], [0.6, 0.3, 0.5], 0.14, 0.0004, rng, 0.02)
        y[: n_of(0.002)] += 0.4 * impact(rng, 0.002, 1500, 8000, 0.0007)
        b.add(y, at, 1.0 * (0.7 ** i))
        at += U(rng, 0.04, 0.10) * (1.0 + 0.4 * i)
    return b.x


def chime_note(f0, dur):
    """Shamol qo'ng'irog'i naychasi: metall naycha qismlari (1 : 2,756 : 5,404 : 8,933); biroz farqli ikkinchi nusxa "titrash" beradi."""
    ratios = [1.0, 2.756, 5.404, 8.933]
    taus = [0.40, 0.17, 0.08, 0.035]
    amps = [1.0, 0.33, 0.14, 0.05]
    return strike([f0 * r for r in ratios], taus, amps, dur, 0.0006) + 0.5 * strike([f0 * r * 1.0035 for r in ratios], taus, amps, dur, 0.0006)


def s_chime_wind(rng):
    """Shamol qo'ng'irog'i: to'rt naycha tabiiy notekis vaqtda; yengil aks sado (ATAYLAB)."""
    b = Buf(2.0)
    for f, at in [(1318.5, 0.0), (987.8, 0.16), (1174.7, 0.37), (1568.0, 0.55)]:
        b.add(chime_note(f, 1.5), at + U(rng, -0.02, 0.02), U(rng, 0.45, 0.9))
    return space(b.x, rng, rt60=0.9, pre=0.012, wet_db=-12.0, damp=1.0, early=5, size=1.2)


def s_bowl_soft(rng):
    """Kuylovchi kosa: yumshoq zarba va "uchlanish" beruvchi juft chastotalar; quruq, lekin uzoq jaranglaydi."""
    f0 = 523.0
    freqs = []
    taus = []
    amps = []
    for r, tau, a in zip([1.0, 2.71, 5.12], [0.5, 0.25, 0.12], [1.0, 0.4, 0.12]):
        freqs += [f0 * r, f0 * r + 0.7]
        taus += [tau, tau]
        amps += [a, a * 0.9]
    return strike(freqs, taus, amps, 2.0, 0.0012)


def s_kalimba(rng):
    """Kalimba (bosh barmoq pianinosi): ohangli, variantlar turli notada (do, mi, sol)."""
    f0 = [523.25, 659.25, 783.99][(_VARIANT["k"] - 1) % 3]
    b = Buf(1.2)
    b.add(strike([f0, f0 * 6.27, f0 * 17.5], [0.28, 0.04, 0.01], [1.0, 0.35, 0.12], 1.2, 0.0008, rng, 0.0005), 0.0, 1.0)
    b.add(strike([870.0, 1260.0], [0.05, 0.03], [1.0, 0.4], 0.3, 0.001), 0.0, 0.35)
    b.add(impact(rng, 0.0015, 1500, 6000, 0.0005), 0.0, 0.15)
    return b.x


# ---- iPhone uslubidagi tovushlar (asl sintez; Apple yozuvlari emas)

def knock(f, dur=0.3, tau=0.05, hard=0.002, ratios=(1.0, 2.0, 3.0, 5.0), amps=(1.0, 0.8, 0.5, 0.2)):
    """Yumshoq "tuk": chastotalari butun nisbatda (past ohang karnay chiqara olmasa ham, garmonikalardan quloq asosiy ohangni sezadi)."""
    return strike([f * r for r in ratios], [tau / (1.0 + 0.6 * i) for i in range(len(ratios))], list(amps), dur, hard)


def ios_tick_wave(rng, f=1900.0, body=640.0):
    b = Buf(0.18)
    b.add(strike([f, f * 1.78, f * 2.9, f * 4.1], [0.018, 0.010, 0.006, 0.003], [1.0, 0.5, 0.3, 0.12], 0.18, 0.0005), 0.0, 0.9)
    b.add(strike([body, body * 2.0], [0.024, 0.012], [1.0, 0.3], 0.12, 0.0012), 0.0, 0.5)
    b.add(impact(rng, 0.0015, 2500, 8000, 0.0005), 0.0, 0.10)
    return b.x


def s_ios_tick(rng):
    return ios_tick_wave(rng)


def s_ios_tock(rng):
    f = 780.0
    b = Buf(0.25)
    b.add(strike([f, f * 2.05, f * 3.3, f * 4.6], [0.045, 0.024, 0.013, 0.007], [1.0, 0.55, 0.3, 0.12], 0.25, 0.0009), 0.0, 1.0)
    b.add(strike([300.0, 600.0], [0.035, 0.02], [1.0, 0.4], 0.15, 0.002), 0.0, 0.5)
    b.add(impact(rng, 0.0015, 1500, 6000, 0.0006), 0.0, 0.08)
    return b.x


def s_ios_pop(rng):
    """Bosish: chastotasi tez tushuvchi yumshoq "pop" (940 dan 560 Hz gacha)."""
    n = n_of(0.24)
    t = axis(n)
    f = 560.0 + 400.0 * np.exp(-t / 0.02)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sin(ph) + 0.20 * np.sin(2 * ph)) * (1.0 - np.exp(-t / 0.0025)) * np.exp(-t / 0.055)
    b = Buf(0.24)
    b.add(x, 0.0, 1.0)
    b.add(impact(rng, 0.002, 1500, 6000, 0.0007), 0.0, 0.10)
    return b.x


def s_ios_thud(rng):
    """Chegara: yumshoq past "tuk"."""
    b = Buf(0.4)
    b.add(knock(200.0, 0.4, 0.075, 0.0012, (1.0, 2.0, 3.0, 4.5), (0.7, 1.0, 0.8, 0.4)), 0.0, 1.0)
    nth = n_of(0.15)
    b.add(unit(bp(rng.standard_normal(nth), 150, 900, 2) * decay_env(nth, 0.035, 0.002)), 0.0, 0.5)
    return b.x


def s_ios_swoosh(rng):
    """Oyna: ko'tariluvchi havo shitirlashi va oxirida yumshoq shisha "ding"."""
    n = n_of(0.45)
    fc = curve([(0, 500), (0.30, 3300), (0.45, 3300)], n, 0.01)
    sw = unit(svf_bp(rng.standard_normal(n), fc, 2.2) * swell(n, 0.0, 1.0, 2.0))
    b = Buf(0.95)
    b.add(sw, 0.0, 0.55)
    b.add(pitched(1568.0, [1.0, 2.32, 4.25, 6.63], [0.45, 0.22, 0.10, 0.05], [1.0, 0.4, 0.2, 0.08], 0.7, 0.0005, rng, 0.0003, pair=0.002), 0.27, 0.5)
    return b.x


def s_ios_scroll(rng):
    """Surish: tezlashib-sekinlashuvchi to'rt yumshoq tiqirlash."""
    b = Buf(0.4)
    for at, f, a in zip([0.0, 0.055, 0.107, 0.168], [1700.0, 1800.0, 1920.0, 2050.0], [0.8, 0.95, 1.0, 0.7]):
        b.add(ios_tick_wave(rng, f), at, a)
    return b.x


def s_ios_error(rng):
    """Xato: ikki past yog'ochsimon "dum-dum", ikkinchisi pastroq."""
    b = Buf(0.55)
    b.add(knock(330.0, 0.3, 0.06, 0.001, (1.0, 2.0, 3.0), (0.8, 1.0, 0.6)), 0.0, 1.0)
    b.add(knock(262.0, 0.34, 0.07, 0.001, (1.0, 2.0, 3.0), (0.8, 1.0, 0.6)), 0.17, 0.9)
    return b.x


def s_ios_glass(rng):
    b = Buf(1.4)
    b.add(pitched(1568.0, [1.0, 2.32, 4.25, 6.63], [0.28, 0.16, 0.09, 0.05], [1.0, 0.45, 0.22, 0.10], 1.4, 0.0004, rng, 0.0003, pair=0.002), 0.0, 1.0)
    b.add(impact(rng, 0.001, 3000, 9000, 0.0004), 0.0, 0.08)
    return b.x


def s_ios_marimba(rng):
    return pitched(880.0, [1.0, 3.97, 9.9], [0.25, 0.06, 0.02], [1.0, 0.5, 0.15], 1.0, 0.0009, rng, 0.0003)


def s_ios_chime_up(rng):
    """Uch ko'tariluvchi nota (do-mi-sol), vibrafon tembri."""
    b = Buf(1.4)
    for f, at, a in [(1046.5, 0.0, 0.8), (1318.5, 0.11, 0.85), (1568.0, 0.22, 1.0)]:
        b.add(pitched(f, [1.0, 3.97, 9.9], [0.22, 0.05, 0.015], [1.0, 0.45, 0.12], 0.9, 0.0007, rng, 0.0003), at, a)
    return b.x


# id, yaratuvchi, sinf, variantlar soni.
# Sinflar: "kls" (klassik ohang: v31 amplitudasi, qayta o'lchanmaydi), "leg" (v32 dagi surish/xato ohangi: v32 usulida tenglashtiriladi,
# baytma-bayt o'zgarmaydi), "tick" (qisqa, <=0,3 s), "cue" (0,3-1 s), "long" (uzoq: matn, ohang, aks sadoli)
CATALOG = [
    ("tone_tik", s_tone_tik, "kls", 1),
    ("tone_tuk", s_tone_tuk, "kls", 1),
    ("tone_edge", s_tone_edge, "kls", 1),
    ("tone_window", s_tone_window, "kls", 1),
    ("tone_scroll", s_tone_scroll, "leg", 1),
    ("tone_error", s_tone_error, "leg", 1),

    ("ios_tick", s_ios_tick, "tick", 1),
    ("ios_tock", s_ios_tock, "tick", 1),
    ("ios_pop", s_ios_pop, "tick", 1),
    ("ios_thud", s_ios_thud, "cue", 1),
    ("ios_swoosh", s_ios_swoosh, "cue", 1),
    ("ios_scroll", s_ios_scroll, "tick", 1),
    ("ios_error", s_ios_error, "cue", 1),
    ("ios_glass", s_ios_glass, "long", 1),
    ("ios_marimba", s_ios_marimba, "cue", 1),
    ("ios_chime_up", s_ios_chime_up, "long", 1),

    ("drop_tiny", s_drop_tiny, "tick", 4),
    ("drop_water", s_drop_water, "cue", 3),
    ("drop_big", s_drop_big, "cue", 3),
    ("drop_stone", s_drop_stone, "cue", 3),
    ("drop_pair", s_drop_pair, "cue", 2),
    ("drop_deep", s_drop_deep, "long", 1),
    ("drop_cave", s_drop_cave, "long", 1),
    ("water_splash", s_water_splash, "cue", 2),
    ("water_ripple", s_water_ripple, "cue", 2),
    ("water_brook", s_water_brook, "long", 1),
    ("water_wave", s_water_wave, "long", 1),
    ("water_fountain", s_water_fountain, "long", 1),

    ("rain_tap", s_rain_tap, "tick", 4),
    ("rain_leaves", s_rain_leaves, "cue", 3),
    ("rain_puddle", s_rain_puddle, "tick", 3),
    ("rain_shower", s_rain_shower, "long", 1),
    ("rain_roof", s_rain_roof, "long", 1),

    ("bird_tweet", s_bird_tweet, "cue", 3),
    ("bird_trill", s_bird_trill, "cue", 2),
    ("bird_dove", s_bird_dove, "long", 1),
    ("bird_sparrow", s_bird_sparrow, "cue", 3),
    ("bird_bulbul", s_bird_bulbul, "long", 1),
    ("bird_hoopoe", s_bird_hoopoe, "long", 1),
    ("cricket", s_cricket, "cue", 2),
    ("leaf_rustle", s_leaf_rustle, "cue", 3),
    ("wind_breeze", s_wind_breeze, "long", 1),
    ("fire_crackle", s_fire_crackle, "long", 1),

    ("step_grass", s_step_grass, "tick", 4),
    ("step_gravel", s_step_gravel, "tick", 3),
    ("step_wood", s_step_wood, "tick", 3),
    ("step_snow", s_step_snow, "tick", 3),

    ("bamboo_tap", s_bamboo_tap, "cue", 3),
    ("wood_block", s_wood_block, "tick", 4),
    ("pebble", s_pebble, "tick", 4),
    ("kalimba", s_kalimba, "cue", 3),
    ("chime_wind", s_chime_wind, "long", 1),
    ("bowl_soft", s_bowl_soft, "long", 1),
]

# Mutlaq nishon balandligi (dB, A-vaznli, 250 ms oynadagi eng katta o'rtacha kvadrat; to'liq shkalaga nisbatan).
# v32 da: tick -22,6, cue -20,6, long -19,6 edi: sezilarli past ("nozik") va tovush uzunligiga qarab ham har xil.
TARGET_DB = {"tick": -17.5, "cue": -16.0, "long": -15.5}
CLASSIC_PEAK = 0.46  # v31 tik amplitudasi 0,275 edi; standart balandlik 60% da 0,46*0,6 = 0,276
PEAK_MAX = 0.88      # undan yuqori cho'qqilar yumshoq cheklanadi (tanh), qirqilmaydi


def var_name(name, k):
    return name if k == 1 else "%s_%d" % (name, k)


# ------------------------------------------------------------------------------------------------------------------ o'lchov

def a_weight_db(f):
    f = np.maximum(f, 1.0)
    f2 = f * f
    ra = (12194.0 ** 2 * f2 * f2) / (
        (f2 + 20.6 ** 2) * np.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) * (f2 + 12194.0 ** 2)
    )
    return 20 * np.log10(ra) + 2.0


def a_weighted(x):
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    return np.fft.irfft(spec * (10 ** (a_weight_db(f) / 20.0)), len(x))


def loudness_db(x):
    """Qisqa muddatli balandlik (bir kanalli): A-vaznli signalning 250 ms oynadagi eng katta o'rtacha kvadrati (dB, to'liq shkalaga nisbatan)."""
    xa = a_weighted(np.concatenate([x, np.zeros(n_of(0.01))]))
    w = n_of(0.25)
    p = xa ** 2
    c = np.concatenate([[0.0], np.cumsum(p)])
    if len(p) <= w:
        ms = c[-1] / w
    else:
        ms = np.max((c[w:] - c[:-w]) / w)
    return 10 * np.log10(ms + 1e-12)


def loudness_db2(x):
    """Ikki kanalli tovush uchun: kanallar quvvatining o'rtachasi (bir kanalli uchun loudness_db bilan bir xil)."""
    if x.ndim == 1:
        return loudness_db(x)
    p = None
    for ch in x:
        xa = a_weighted(np.concatenate([ch, np.zeros(n_of(0.01))]))
        p = xa ** 2 if p is None else p + xa ** 2
    p = p / x.shape[0]
    w = n_of(0.25)
    c = np.concatenate([[0.0], np.cumsum(p)])
    ms = c[-1] / w if len(p) <= w else np.max((c[w:] - c[:-w]) / w)
    return 10 * np.log10(ms + 1e-12)


def centroid_hz(x):
    m = np.abs(np.fft.rfft(x if x.ndim == 1 else x.mean(axis=0))) ** 2
    f = np.fft.rfftfreq(x.shape[-1], 1.0 / SR)
    return float(np.sum(f * m) / (np.sum(m) + 1e-12))


def low_ratio(x, below=80.0):
    """Energiyaning 80 Hz dan pastdagi ulushi (telefon dinamigi bu chastotalarni chiqarmaydi, faqat balandlikdan joy oladi)."""
    m = np.abs(np.fft.rfft(x if x.ndim == 1 else x.mean(axis=0))) ** 2
    f = np.fft.rfftfreq(x.shape[-1], 1.0 / SR)
    return float(np.sum(m[f < below]) / (np.sum(m) + 1e-12))


def decay_time_20(x):
    """So'nish vaqti T20 x 3 (Shreder integrali: -5 dan -25 dB gacha vaqtni 60 dB ga ekstrapolyatsiya): aks sadoli tovushlarni tekshirish uchun."""
    m = x if x.ndim == 1 else x.mean(axis=0)
    e = np.cumsum((m ** 2)[::-1])[::-1]
    e = 10 * np.log10(e / (e[0] + 1e-18) + 1e-12)
    i5 = int(np.argmax(e <= -5.0))
    i25 = int(np.argmax(e <= -25.0))
    return 3.0 * (i25 - i5) / SR if i25 > i5 else float("nan")


def stereo_stats(x):
    """(kanallar korrelyatsiyasi, bir kanalli karnayda (L+R)/2 quvvati / kanal o'rtacha quvvati)."""
    if x.ndim == 1:
        return 1.0, 1.0
    l, r = x[0], x[1]
    pl, pr = np.sum(l ** 2), np.sum(r ** 2)
    corr = float(np.sum(l * r) / (np.sqrt(pl * pr) + 1e-18))
    ms = float(np.sum(((l + r) / 2.0) ** 2) / ((pl + pr) / 2.0 + 1e-18))
    return corr, ms


# ----------------------------------------------------------------------------------------------------- tayyorlash va yozish

def finish(x, fade_in=0.0003, fade_out=0.006, trim_db=-55.0):
    """(v32 dagidek, klassik ohanglar uchun) Oxiridagi jimlikni kesadi va boshi-oxiriga yumshoq o'tish beradi (bosilish ovozi bo'lmasligi uchun)."""
    x = x - np.mean(x[: max(1, min(len(x), 8))]) * 0.0
    pk = np.max(np.abs(x)) + 1e-12
    thr = pk * 10 ** (trim_db / 20.0)
    idx = np.nonzero(np.abs(x) > thr)[0]
    end = (idx[-1] + 1) if len(idx) else len(x)
    x = x[:end].copy()
    n = len(x)
    fo = min(n // 2, n_of(fade_out))
    fi = min(n // 4, n_of(fade_in))
    if fi > 1:
        x[:fi] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(fi) / fi)
    if fo > 1:
        x[n - fo:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(fo) / fo)
    return x


def finish2(x, fade_in=0.0004, fade_out=0.03, trim_db=-62.0):
    """Yangi tovushlar uchun: bir yoki ikki kanalli; doimiy siljish olib tashlanadi, sokin quyruq -62 dB da kesiladi, 30 ms yumshoq so'nadi."""
    x = np.asarray(x, dtype=float)
    x = x - np.mean(x, axis=-1, keepdims=True)
    a = np.max(np.abs(x), axis=0) if x.ndim == 2 else np.abs(x)
    pk = np.max(a) + 1e-12
    idx = np.nonzero(a > pk * 10 ** (trim_db / 20.0))[0]
    end = (idx[-1] + 1) if len(idx) else x.shape[-1]
    x = x[..., :end].copy()
    n = x.shape[-1]
    fo = min(n // 2, n_of(fade_out))
    fi = min(n // 4, n_of(fade_in))
    if fi > 1:
        x[..., :fi] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(fi) / fi)
    if fo > 1:
        x[..., n - fo:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(fo) / fo)
    return x


def level2(x, cls):
    """Mutlaq nishonga (TARGET_DB) keltiradi. Cho'qqi PEAK_MAX dan 3 dB gacha oshsa yumshoq cheklanadi (tanh): zarbali tovush nishondan sal past qolishi mumkin."""
    g = 10 ** ((TARGET_DB[cls] - loudness_db2(x)) / 20.0)
    g = min(g, PEAK_MAX * 1.4 / (np.max(np.abs(x)) + 1e-12))
    y = x * g
    if np.max(np.abs(y)) > PEAK_MAX:
        y = PEAK_MAX * np.tanh(y / PEAK_MAX)
    return y


# 22,05 kHz da yoziladigan tovushlar: ularning energiyasi 9 kHz dan past (suv, yomg'ir, shamol, olov, kosa, aks sado), shuning uchun
# yuqori chastotalar yo'qolmaydi, fayl esa ikki barobar kichik. SoundPool har qanday chastotadagi faylni o'zi to'g'rilaydi.
HALF_RATE = {"drop_deep", "drop_cave", "water_splash", "water_ripple", "water_brook", "water_wave", "water_fountain",
             "rain_leaves", "rain_shower", "rain_roof", "wind_breeze", "fire_crackle", "bowl_soft"}


def write_wav(path, x, rate=SR):
    if rate != SR:
        x = signal.resample_poly(x, rate, SR, axis=-1)
    pcm = np.clip(np.round(x * 32767.0), -32768, 32767).astype("<i2")
    ch = 1 if x.ndim == 1 else x.shape[0]
    with wave.open(path, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((pcm if ch == 1 else pcm.T.reshape(-1)).tobytes())


def classic_ref_db():
    """v32 dagi nishon: "tik" ohangining (amplitudasi CLASSIC_PEAK) balandligi; "leg" sinfidagi tovushlar shunga nisbatan tenglashtiriladi."""
    x = finish(s_tone_tik(None))
    return loudness_db(x * (CLASSIC_PEAK / np.max(np.abs(x))))


def render_all(only=None):
    """Hamma fayllar: {fayl nomi (snd_ dan keyin): massiv}. only berilsa, faqat shu tovush id lari."""
    out = {}
    for name, fn, cls, nv in CATALOG:
        if only and name not in only:
            continue
        for k in range(1, nv + 1):
            _VARIANT["k"] = k
            rng = seeded(name if k == 1 else "%s#%d" % (name, k))
            x = fn(rng)
            if cls == "kls":
                x = finish(x)
                y = x * (CLASSIC_PEAK / np.max(np.abs(x)))
            elif cls == "leg":
                x = finish(x)
                g = 10 ** ((classic_ref_db() + 2.0 - loudness_db(x)) / 20.0)
                g = min(g, PEAK_MAX * 1.4 / np.max(np.abs(x)))
                y = x * g
                if np.max(np.abs(y)) > PEAK_MAX:
                    y = PEAK_MAX * np.tanh(y / PEAK_MAX)
            else:
                y = level2(finish2(x), cls)
            out[var_name(name, k)] = y
    return out


def report_rows(sounds):
    rows = []
    cls_of = {var_name(n, k): c for n, f, c, nv in CATALOG for k in range(1, nv + 1)}
    for name, x in sounds.items():
        ch = 1 if x.ndim == 1 else x.shape[0]
        corr, ms = stereo_stats(x)
        first = float(np.max(np.abs(x[..., 0])))
        last = float(np.max(np.abs(x[..., -1])))
        rows.append((name, cls_of[name], ch, 1000.0 * x.shape[-1] / SR, float(np.max(np.abs(x))), loudness_db2(x), centroid_hz(x),
                     100.0 * low_ratio(x), first, last, float(np.mean(x)), decay_time_20(x), corr, ms, ch * x.shape[-1] * 2 / 1024.0))
    return rows


def plot_sheets(sounds, outdir, names=None):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(outdir, exist_ok=True)
    names = names or [c[0] for c in CATALOG]
    per = 16
    for s in range(0, len(names), per):
        chunk = names[s:s + per]
        fig, axes = plt.subplots(4, 4, figsize=(16, 11))
        for ax in axes.ravel():
            ax.axis("off")
        for ax, name in zip(axes.ravel(), chunk):
            x = sounds[name]
            m = x if x.ndim == 1 else x.mean(axis=0)
            ax.axis("on")
            dither = 1e-6 * np.random.default_rng(1).standard_normal(len(m) + n_of(0.02))  # log10(0) ogohlantirishi bo'lmasligi uchun
            ax.specgram(np.concatenate([m, np.zeros(n_of(0.02))]) + dither, NFFT=512, Fs=SR, noverlap=448, cmap="magma", vmin=-120, vmax=-30)
            ax.set_ylim(0, 12000)
            ax.set_title("%s  %d ms  pk %.2f" % (name, round(1000 * len(m) / SR), np.max(np.abs(x))), fontsize=10)
            ax.tick_params(labelsize=7)
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, "sheet_%d.png" % (s // per + 1)), dpi=70)
        plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--out", default=os.path.join(here, "..", "app", "src", "main", "res", "raw"))
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--plots", default=None)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--only", default=None, help="vergul bilan ajratilgan tovush id lari (sinash uchun)")
    args = ap.parse_args(argv)

    only = set(args.only.split(",")) if args.only else None
    sounds = render_all(only)
    if not args.no_write:
        os.makedirs(args.out, exist_ok=True)
        for name, x in sounds.items():
            base = name.rsplit("_", 1)[0] if name.rsplit("_", 1)[-1].isdigit() else name
            write_wav(os.path.join(args.out, "snd_%s.wav" % name), x, SR // 2 if base in HALF_RATE else SR)
        print("yozildi: %d ta fayl -> %s" % (len(sounds), os.path.normpath(args.out)))
    if args.report:
        print("%-17s %-5s %2s %6s %6s %7s %6s %6s %6s %8s %7s %9s %5s %5s %5s %6s" % (
            "fayl", "sinf", "ch", "ms", "pik", "dB(A)", "markaz", "<80Hz%", "birinchi", "oxirgi", "o'rtacha", "T60~", "corr", "mono", "KB", ""))
        total = 0.0
        for r in report_rows(sounds):
            total += r[14]
            print("%-17s %-5s %2d %6.0f %6.2f %7.1f %6.0f %6.2f %8.4f %7.4f %9.5f %5.2f %5.2f %5.2f %5.0f" % r)
        print("jami hajm: %.0f KB (%.1f MB), fayllar: %d" % (total, total / 1024.0, len(sounds)))
    if args.plots:
        plot_sheets(sounds, args.plots, [c[0] for c in CATALOG if c[0] in sounds])
        print("rasmlar:", args.plots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
