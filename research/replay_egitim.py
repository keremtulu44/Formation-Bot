"""Kişisel DM için arşiv tabanlı, hafızada kalan tek soruluk Replay.

Bu modül canlı domain/formation state'ine ve hiçbir veri sağlayıcısına yazmaz.
"""
from __future__ import annotations

import math
import random
import re
import secrets
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from config import sembol_turu
from data import mum_kapanis_anlari
from grafik.core import _seri_cizim
from patterns.indicators import calculate_atr
from research.arsiv import arsiv_sembolleri, tf_frame

TFS = ("1h", "2h", "4h", "1d")
HORIZONS = (8, 10, 20)
MIN_HISTORY = 80


@dataclass
class Soru:
    sembol: str
    frames: dict
    closes: dict
    positions: dict
    code: str
    tf: str | None = None
    horizon: int | None = None


def _bad(frame):
    o, h, l, c = (pd.to_numeric(frame[k], errors="coerce") for k in ("open", "high", "low", "close"))
    bad = (~np.isfinite(o) | ~np.isfinite(h) | ~np.isfinite(l) | ~np.isfinite(c) |
           (o <= 0) | (l <= 0) | (h < o) | (h < c) | (h < l) | (l > o) | (l > c))
    # Bölünme/ham fiyat sıçraması: karşılaştırılamayan pencereyi oyun yapma.
    bad |= (c / c.shift(1) - 1).abs() > 0.30
    return np.asarray(bad, dtype=int)


def soru_sec(sembol: str = "", *, rng=None, kok=None) -> Soru:
    rng = rng or random.SystemRandom()
    semboller = [s for s in arsiv_sembolleri(kok) if sembol_turu(s) == "hisse"]
    if sembol:
        sembol = sembol.strip().upper()
        if sembol not in semboller:
            raise ValueError("Bu hisse arşivde yok; /test ASTOR gibi deneyin.")
        candidates = [sembol]
    else:
        # Önce hisse, sonra o hissenin geçerli anlarından eşit seçim.
        candidates = rng.sample(semboller, len(semboller))
    for name in candidates:
        try:
            frames = {tf: tf_frame(name, tf, kok).copy() for tf in TFS}
            closes = {tf: mum_kapanis_anlari(frames[tf].index, tf).tz_convert("UTC") for tf in TFS}
            if any(not closes[tf].is_monotonic_increasing or closes[tf].has_duplicates for tf in TFS):
                continue
            bad = {tf: np.r_[0, np.cumsum(_bad(frames[tf]))] for tf in TFS}
            valid = []
            for i in range(MIN_HISTORY - 1, len(frames["1h"]) - max(HORIZONS)):
                anchor = closes["1h"][i]
                pos = {tf: int(closes[tf].searchsorted(anchor, side="right") - 1) for tf in TFS}
                if any(p < MIN_HISTORY - 1 or p + max(HORIZONS) >= len(frames[tf]) for tf, p in pos.items()):
                    continue
                if any(bad[tf][p + max(HORIZONS) + 1] - bad[tf][p - MIN_HISTORY + 1] for tf, p in pos.items()):
                    continue
                valid.append(pos)
            if valid:
                return Soru(name, frames, closes, rng.choice(valid), secrets.token_hex(3).upper())
        except (ValueError, OSError, KeyError, TypeError):
            continue
    raise ValueError("Yeterli ortak geçmiş ve gelecek içeren geçerli arşiv penceresi bulunamadı.")


def sonuc(soru: Soru, tahmin: str):
    if soru.tf not in TFS or soru.horizon not in HORIZONS:
        raise ValueError("Önce zaman dilimi seçilmeli.")
    p, tf, n = soru.positions[soru.tf], soru.tf, soru.horizon
    frame = soru.frames[tf]
    history = frame.iloc[:p + 1]
    bad_positions = np.flatnonzero(_bad(history))
    if len(bad_positions):
        history = history.iloc[int(bad_positions[-1]) + 1:]
    if len(history) < 14:
        raise ValueError("Temiz ATR geçmişi yetersiz; yeni soru açın.")
    atr = float(calculate_atr(history, 14).iloc[-1])
    start, end = float(frame.close.iloc[p]), float(frame.close.iloc[p + n])
    if not math.isfinite(atr) or atr <= 0:
        raise ValueError("ATR hesaplanamadı; yeni soru açın.")
    diff = end - start
    direction = "yukarı" if diff > 1.5 * atr else "aşağı" if diff < -1.5 * atr else "yatay"
    finish = soru.closes[tf][p + n]
    return {"tf": tf, "horizon": n, "tahmin": tahmin, "direction": direction,
            "start": start, "end": end, "diff": diff, "atr": atr, "finish": finish}


@_seri_cizim
def _draw(frame, tf, symbol, path, cut=None, pattern_frame=None):
    """Tarih/ATR içermeyen görüntü; aynı bot formasyon motoru izole örneği."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from grafik.core import _kadrajla
    from patterns.lifecycle import ArgentEngine

    history = pattern_frame if pattern_frame is not None else frame
    history = history.iloc[-900:].copy()
    snapshot = ArgentEngine(timeframe=tf).process(history, tam_yeniden=True)
    # Offline replay, yalnız kesit verisiyle ve canlı motor kayıtlarına dokunmadan.
    from directional_zone_replay import replay_fvg_zones, replay_ob_zones
    try:
        zones = replay_ob_zones(symbol, tf, history)
        if tf in {"4h", "1d"}:  # Canlı varsayılanında 1h/2h FVG kullanılmaz.
            zones += replay_fvg_zones(symbol, tf, history)[0]
        zones = [z for z in zones if z["active_at_asof"]]
        last_price = float(history.close.iloc[-1])
        zones = sorted(zones, key=lambda z: abs((z["zone_lower"] + z["zone_upper"]) / 2 - last_price))[:6]
        zone_note = "OB/FVG"
    except Exception:  # noqa: BLE001 - görünür eksik analizi grafiği tamamen engellemesin
        zones, zone_note = [], "OB/FVG hesaplanamadı"
    cand = snapshot.active
    bas = cand.start_bar if cand is not None else None
    sol, _, _ = _kadrajla(len(history), bas, tf=tf)
    # Sonuç görüntüsünde başlangıç kadrajını koru ve sonraki mumları ekle.
    count = len(history) - sol
    visible = frame.iloc[-(count + (cut or 0)):].copy()
    first_in_history = len(history) - count
    fig, ax = plt.subplots(figsize=(12, 6), dpi=110)
    fig.patch.set_facecolor("#0f151c")
    ax.set_facecolor("#0f151c")
    for x, row in enumerate(visible.itertuples()):
        color = "#2ec4a0" if row.close >= row.open else "#ef6262"
        ax.vlines(x, row.low, row.high, color=color, linewidth=0.7)
        height = max(abs(row.close - row.open), abs(row.close) * .0001)
        ax.add_patch(plt.Rectangle((x - .30, min(row.open, row.close)), .60, height,
                                   facecolor=color, edgecolor=color, linewidth=.6))
    for zone in zones:
        left = max(0, int(zone["available_index"]) - first_in_history)
        right = count - 1
        if left <= right:
            color = "#2ec4a0" if zone["direction"] == "bullish" else "#ef6262"
            low, high = zone["current_remaining_lower"], zone["current_remaining_upper"]
            ax.add_patch(plt.Rectangle((left, low), max(.1, right - left), high - low,
                                      facecolor=color, edgecolor=color, alpha=.15, linewidth=.5))
    if cand is not None:
        # Çizgiler yalnız soru anına kadarki, motorun bilinen geometrisi.
        for b1, p1, slope in ((cand.hb1, cand.hp1, cand.upper_slope), (cand.lb1, cand.lp1, cand.lower_slope)):
            if b1 is not None and p1 is not None and slope is not None:
                a, b = max(0, int(b1) - first_in_history), count - 1
                if a <= b:
                    ax.plot([a, b], [p1 + slope * (a + first_in_history - b1),
                                     p1 + slope * (b + first_in_history - b1)], color="#f4bd5c", lw=1.1)
    if cut is not None:
        ax.axvline(count - .5, color="#eee6a0", linestyle="--", lw=1.3)
    state = str(snapshot.state or "YOK").replace("_", " ")
    ax.set_title(f"{symbol} · {tf} · Formasyon: {state} · {zone_note}", color="#e9eef5", loc="left")
    ax.tick_params(colors="#e9eef5")
    ax.set_xticks([])  # gerçek ve sentetik tarih gösterilmez
    ax.grid(axis="y", color="#33414e", linestyle=":", alpha=.6)
    for spine in ax.spines.values(): spine.set_color("#33414e")
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def album_hazirla(soru: Soru, tmp, *, answer=None):
    paths, captions = [], []
    for tf in TFS:
        p = soru.positions[tf]
        end = p if answer is None else int(soru.closes[tf].searchsorted(answer["finish"], side="right") - 1)
        path = str(Path(tmp) / (tf + ".png"))
        _draw(soru.frames[tf].iloc[:end + 1], tf, soru.sembol, path,
              cut=(end - p) if answer is not None else None,
              pattern_frame=soru.frames[tf].iloc[:p + 1])
        paths.append(path)
        captions.append(tf + (" · yeni kapanmış mum yok" if answer is not None and end == p else ""))
    return paths, captions


class Session:
    """Tek DM ve en fazla bir açık soru; kod eski gecikmiş yanıtları reddeder."""
    def __init__(self):
        self.lock = threading.RLock()
        self.current = None
        self.generation = 0
        self.busy = False
        self.pending = None

    def _schedule(self, job, generation):
        with self.lock:
            if generation != self.generation:
                return
            if self.busy:
                self.pending = (job, generation)
                return
            self.busy = True
            threading.Thread(target=job, daemon=True, name="replay-egitim").start()

    def _finished(self):
        with self.lock:
            self.busy = False
            pending, self.pending = self.pending, None
            if pending:
                self._schedule(*pending)

    def yeni(self, arg, notifier):
        from telegram_commands import ArkaPlanYaniti
        symbol = str(arg or "").strip().upper()
        if symbol and not re.fullmatch(r"[A-Z0-9]{1,12}", symbol):
            return "Kullanım: /test veya /test ASTOR"
        with self.lock:
            self.generation += 1
            generation = self.generation
            self.current = None
            self.pending = None
        def job():
            try:
                from transport.telegram import medya_grubu_gonder
                question = soru_sec(symbol)
                with tempfile.TemporaryDirectory(prefix="replay_egitim_") as tmp:
                    paths, captions = album_hazirla(question, tmp)
                    with self.lock:
                        if generation != self.generation: return
                    ok, error = medya_grubu_gonder(paths, captions=captions, notifier=notifier)
                    if not ok: raise RuntimeError(error)
                    with self.lock:
                        if generation != self.generation: return
                        self.current = question
                    sent = notifier.send_to_chat(f"{question.sembol}: TF seçin: 1h, 2h, 4h veya 1d. "
                                                 f"Yanıtınıza kodu ekleyin: ör. 4h {question.code}", notifier.chat_id)
                    if not sent:
                        with self.lock:
                            if generation == self.generation and self.current is question:
                                self.current = None
            except Exception:
                with self.lock:
                    current = generation == self.generation
                    if current:
                        self.current = None
                if current:
                    notifier.send_to_chat("Eğitim sorusu hazırlanamadı; arşiv ve grafik bağımlılıklarını kontrol edin.", notifier.chat_id)
            finally:
                self._finished()
        return ArkaPlanYaniti("⏳ Geçmiş soru hazırlanıyor; önceki açık soru iptal edildi.",
                              lambda: self._schedule(job, generation))

    def cevap(self, text, notifier):
        from telegram_commands import ArkaPlanYaniti
        parts = str(text or "").strip().lower().split()
        with self.lock:
            q = self.current
            if q is None: return None
            if len(parts) != 2 or parts[1].upper() != q.code:
                return f"Açık sorunun koduyla yanıtlayın: ör. 1h {q.code}."
            if q.tf is None:
                aliases = {"1h":"1h", "1s":"1h", "2h":"2h", "2s":"2h", "4h":"4h", "4s":"4h", "1d":"1d", "1g":"1d"}
                if parts[0] not in aliases: return f"TF seçin: 1h, 2h, 4h veya 1d · kod {q.code}"
                q.tf = aliases[parts[0]]
                q.horizon = random.SystemRandom().choice(HORIZONS)
                return f"{q.tf}: {q.horizon} mum sonra yön? Yukarı, yatay veya aşağı yazın; ör. yukarı {q.code}"
            yon = {"yukarı":"yukarı", "yukari":"yukarı", "aşağı":"aşağı", "asagi":"aşağı", "yatay":"yatay"}.get(parts[0])
            if yon is None: return f"Yukarı, yatay veya aşağı yazın; ör. yatay {q.code}"
            result = sonuc(q, yon)
            self.current = None
            generation = self.generation
        def job():
            try:
                from transport.telegram import medya_grubu_gonder
                with tempfile.TemporaryDirectory(prefix="replay_egitim_") as tmp:
                    paths, captions = album_hazirla(q, tmp, answer=result)
                    with self.lock:
                        if generation != self.generation: return
                    ok, _ = medya_grubu_gonder(paths, captions=captions, notifier=notifier)
                    if not ok: raise RuntimeError("albüm")
                    with self.lock:
                        if generation != self.generation: return
                    notifier.send_to_chat(f"Tahmin: {yon} · Sonuç: {result['direction']}\n"
                        f"{result['start']:.4f} → {result['end']:.4f} · değişim {result['diff']:+.4f} "
                        f"(%{result['diff'] / result['start'] * 100:+.2f})\n"
                        f"ATR: {result['atr']:.4f} · yatay sınır ±{1.5 * result['atr']:.4f}\n"
                        "Yeni soru: /test", notifier.chat_id)
            except Exception:
                with self.lock:
                    current = generation == self.generation
                if current:
                    notifier.send_to_chat("Sonuç grafikleri gönderilemedi; yeni soru için /test yazın.", notifier.chat_id)
            finally:
                self._finished()
        return ArkaPlanYaniti("⏳ Sonuç hazırlanıyor.", lambda: self._schedule(job, generation))


session = Session()
