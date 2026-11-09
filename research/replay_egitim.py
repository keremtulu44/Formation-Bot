"""Kişisel DM için arşiv tabanlı, hafızada kalan tek soruluk Replay.

Bu modül canlı domain/formation state'ine ve hiçbir veri sağlayıcısına yazmaz.
"""
from __future__ import annotations

import logging
import math
import os
import random
import re
import secrets
import tempfile
import threading
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from config import sembol_turu
from data import mum_kapanis_anlari
from patterns.indicators import calculate_atr
from research.arsiv import arsiv_sembolleri, tf_frame

TFS = ("1h", "2h", "4h", "1d")
HORIZONS = (8, 10, 20)
MIN_HISTORY = 80
log = logging.getLogger(__name__)


@dataclass
class Soru:
    sembol: str
    frames: dict
    closes: dict
    positions: dict
    code: str
    tf: str | None = None
    horizon: int | None = None
    snapshots: dict = field(default_factory=dict, repr=False)


def _bad(frame):
    o, h, l, c = (pd.to_numeric(frame[k], errors="coerce") for k in ("open", "high", "low", "close"))
    bad = (~np.isfinite(o) | ~np.isfinite(h) | ~np.isfinite(l) | ~np.isfinite(c) |
           (o <= 0) | (l <= 0) | (h < o) | (h < c) | (h < l) | (l > o) | (l > c))
    # Bölünme/ham fiyat sıçraması: karşılaştırılamayan pencereyi oyun yapma.
    volume = pd.to_numeric(frame["volume"], errors="coerce") if "volume" in frame else None
    if volume is not None:
        bad |= ~np.isfinite(volume) | (volume < 0)
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
                # Günlük ufuk seçilince saatlikte 20 değil, o güne kadarki
                # tüm mumlar açılır. Arşiv ve veri kontrolleri tamamını kapsar.
                finish = max(closes[tf][p + max(HORIZONS)] for tf, p in pos.items())
                if any(closes[tf][-1] < finish for tf in TFS):
                    continue
                ends = {tf: int(closes[tf].searchsorted(finish, side="right") - 1)
                        for tf in TFS}
                if any(bad[tf][ends[tf] + 1] - bad[tf][p - MIN_HISTORY + 1]
                       for tf, p in pos.items()):
                    continue
                valid.append(pos)
            if valid:
                return Soru(
                    name,
                    frames,
                    closes,
                    rng.choice(valid),
                    secrets.token_hex(3).upper(),
                    horizon=rng.choice(HORIZONS),
                )
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


def _soru_goruntusu(soru: Soru, tf: str) -> dict:
    """Normal grafik hattını yalnız kesitte kapanmış mumlarla çalıştır.

    Sonuç karesi bu görüntünün kopyasına sadece açılan mumları ekler; hiçbir
    analiz motoru geleceği görmez ve canlı domain kayıtları değiştirilmez.
    """
    if tf in soru.snapshots:
        return deepcopy(soru.snapshots[tf])
    import chart_experience
    import grafik
    import grafik_uret
    from domain_engines.runner import run_domain_engines, run_stabil_domain
    from grafik.core import _ortam_sayi

    p = soru.positions[tf]
    cutoff = soru.closes[tf][p]
    history = soru.frames[tf].iloc[max(0, p + 1 - 900):p + 1].copy(deep=True)
    candidate, state, warning = grafik_uret._formasyon_tara_ayrintili(history, tf)
    domains = run_domain_engines(soru.sembol, tf, history, isolated=True)
    try:
        # `kare_uret(stabil_frames=...)` ile aynı nedensel kesim yardımcı
        # fonksiyonu kullanılır; replay ve normal grafik yolu ayrışmasın.
        daily_history, h4_history, stabil_kesim = grafik_uret.stabil_baglami_arsivden(
            soru.frames, cutoff
        )
        domains["stabil"] = run_stabil_domain(
            soru.sembol,
            tf,
            history,
            daily_frame=daily_history,
            h4_frame=h4_history,
            as_of_close=cutoff,
            isolated=True,
        )
        # Canlı `/grafik` yolu (grafik_uret) İKİ katmanı da hesaplıyor; replay
        # yolu yalnız desteği hesapladığı için eğitim/soru karelerinde direnç
        # katmanı hiç görünmüyordu (2026-11-08, §8.1'in kalan izi). Aynı
        # `resistance_for_chart` köprüsü ve aynı nedensel kesim kullanılır.
        # Direnç hatası destek katmanını ve kareyi düşürmez.
        try:
            from domain_engines.stabil.chart_bridge import resistance_for_chart

            domains["stabil_direnc"] = resistance_for_chart(
                soru.sembol,
                tf,
                history,
                daily_frame=daily_history,
                hourly_frame=h4_history,
                as_of_close=stabil_kesim,
            )
        except Exception:  # noqa: BLE001 - direnç hatası eğitim karesini düşürmez
            log.warning(
                "Eğitim direnç katmanı hesaplanamadı (%s %s)",
                soru.sembol, tf, exc_info=True,
            )
    except Exception:  # noqa: BLE001 - Stabil hatası eğitim karesini düşürmez
        # Sessizce yutulan bir motor hatası replay/normal karşılaştırmasını
        # yanıltıcı biçimde "eşit" gösterebilir; en azından traceback görünsün.
        log.warning(
            "Eğitim Stabil katmanı hesaplanamadı (%s %s)",
            soru.sembol, tf, exc_info=True,
        )
    snapshot = grafik.anlik_goruntu(
        candidate, tf, history, sonuclar=domains, sembol=soru.sembol,
        simdi=soru.closes[tf][p].to_pydatetime(), veri_kaynagi="arşiv", tarihsel=True,
        etiket_detay=False,
    )
    if state and snapshot.get("formasyon"):
        snapshot["formasyon"]["state"] = state
    if warning:
        snapshot["uyarilar"] = list(snapshot.get("uyarilar") or []) + list(warning)
    # Aynı mod ve eşik normal ciz() ile birebir. Sonuç karesinde aynı
    # bölgelerin/olayların kalması için görünüm geçmiş fiyata göre seçilir.
    mode = str(os.environ.get("GRAFIK_GORUNUM", "odak")).strip().lower()
    snapshot = chart_experience.prepare_view(
        snapshot, mode, max_distance_atr=max(.1, _ortam_sayi("GRAFIK_ODAK_MESAFE_ATR", 3.0)),
    )
    # Bağlam modundaki bölge künyelerinden de gerçek tarih sızmasın.
    for key in ("tum", "cizilen"):
        for zone in (snapshot.get("zone") or {}).get(key) or []:
            zone.pop("zaman", None)
    snapshot["guven"]["kaynak"] = "yerel arşiv"
    snapshot["replay"] = {"asama": "soru", "hazir_gorunum": True,
                          "kesit": len(snapshot["zamanlar"]) - 1,
                          "formasyon_etiketi": ("formasyon hesaplanamadı"
                              if any(str(w).startswith("tarama hatası") for w in warning)
                              else "kullanılabilir formasyon yok")}
    soru.snapshots[tf] = deepcopy(snapshot)
    return deepcopy(snapshot)


def _sonuc_goruntusu(soru: Soru, tf: str, end: int) -> dict:
    """Soru kadrajını ve katmanları koru; yalnız kapanmış sonuç mumlarını ekle."""
    snapshot = _soru_goruntusu(soru, tf)
    p = soru.positions[tf]
    if end < p or end >= len(soru.frames[tf]):
        raise ValueError("Sonuç mumlarının sınırı geçersiz.")
    future = soru.frames[tf].iloc[p + 1:end + 1]
    for target, column in (("acilis", "open"), ("yuksek", "high"),
                           ("dusuk", "low"), ("kapanis", "close"), ("hacim", "volume")):
        values = future[column].tolist() if column in future else [None] * len(future)
        snapshot[target] = list(snapshot.get(target) or []) + values
    snapshot["zamanlar"] = list(snapshot["zamanlar"]) + list(future.index.to_pydatetime())
    # Dipnot görünür pencereyi tarif eder; yeni mumların hacimsizlikleri de
    # sayılmalı. RVOL/diğer analizler ise soru anında sabit kalır.
    volumes = pd.to_numeric(pd.Series(snapshot["hacim"]), errors="coerce")
    snapshot["hacimsiz_bar"] = int((volumes.isna() | ~np.isfinite(volumes) | (volumes <= 0)).sum())
    # RVOL ve yapı yalnız soru anında hesaplandı; geleceğe ait ölçüm uydurma.
    snapshot["son_kapanis"] = snapshot["kapanis"][-1]
    snapshot["son_bar_ts"] = snapshot["zamanlar"][-1]
    snapshot["bar_sayisi"] = int(snapshot.get("bar_sayisi") or 0) + len(future)
    snapshot["replay"]["asama"] = "sonuc"
    return snapshot


def _draw(soru: Soru, tf: str, end: int, path: str, *, result: bool = False):
    import grafik

    snapshot = _sonuc_goruntusu(soru, tf, end) if result else _soru_goruntusu(soru, tf)
    yol, meta = grafik.ciz(snapshot, tf, secenekler={"cikti": path, "etiket_detay": False, "serit": None})
    if not yol:
        raise RuntimeError("Eğitim grafiği üretilemedi.")
    return meta


def album_hazirla(soru: Soru, tmp, *, answer=None):
    paths, captions = [], []
    for tf in TFS:
        p = soru.positions[tf]
        end = p if answer is None else int(soru.closes[tf].searchsorted(answer["finish"], side="right") - 1)
        path = str(Path(tmp) / (tf + ".png"))
        _draw(soru, tf, end, path, result=answer is not None)
        paths.append(path)
        label = {"1h": "1s", "2h": "2s", "4h": "4s", "1d": "1g"}[tf]
        if answer is None:
            captions.append(f"{soru.sembol} · {label} · Soru")
        else:
            ek = " · bu sürede yeni mum kapanmadı" if end == p else f" · {end - p} yeni mum"
            captions.append(f"{soru.sembol} · {label} · Sonuç{ek}")
    return paths, captions


def _album_gonder(paths, captions, notifier, halen_gecerli) -> int | None:
    """Kesin ret dışında tekil tekrar yapma; belirsiz teslimde None döndür."""
    from transport.telegram import foto_gonder, medya_grubu_gonder, medya_kesin_reddedildi

    if not halen_gecerli():
        return 0
    if len(paths) >= 2:
        try:
            ok, reason = medya_grubu_gonder(paths, captions=captions, notifier=notifier)
        except Exception:  # noqa: BLE001 - API kabul edip yanıtı kaybetmiş olabilir
            log.warning("Eğitim albümünün teslimi belirsiz; tekil tekrar yapılmadı.")
            return None
        if ok:
            return len(paths)
        if not medya_kesin_reddedildi(reason):
            log.warning("Eğitim albümünün teslimi belirsiz; tekil tekrar yapılmadı.")
            return None
    sent = 0
    for path, caption in zip(paths, captions):
        if not halen_gecerli():
            break
        try:
            ok, _ = foto_gonder(path, notifier=notifier, caption=caption)
            sent += int(bool(ok))
        except Exception:  # noqa: BLE001 - kalan karelerin teslimini engelleme
            log.warning("Eğitim karesi gönderilemedi.")
    return sent


def _sonuc_metni(result: dict, delivered: int | None) -> str:
    from reporting.format import sayi, tf_kisa

    def signed(value, decimals):
        return ("+" if value >= 0 else "−") + sayi(abs(value), decimals)

    correct = result["tahmin"] == result["direction"]
    percent = result["diff"] / result["start"] * 100
    lines = [f"{'✅' if correct else '❌'} Tahmin: {result['tahmin']} · Sonuç: {result['direction']}",
             f"{tf_kisa(result['tf'])} · {result['horizon']} kapanmış mum",
             f"Kapanış: {sayi(result['start'], 4)} → {sayi(result['end'], 4)}",
             f"Değişim: {signed(result['diff'], 4)} ({signed(percent, 2)}%)",
             f"ATR: {sayi(result['atr'], 4)} · yatay sınır: ±{sayi(1.5 * result['atr'], 4)}"]
    if delivered is None:
        lines.append("⚠️ Sonuç albümünün teslimi belirsiz; çift gönderimi önlemek için tekrar denenmedi.")
    elif delivered < len(TFS):
        lines.append(f"⚠️ Sonuç görsellerinden {delivered}/{len(TFS)} tanesinin teslimi doğrulandı.")
    lines.append("Yeni soru: /test")
    return "\n".join(lines)


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
        def gecerli():
            with self.lock:
                return generation == self.generation

        def job():
            try:
                try:
                    question = soru_sec(symbol)
                except ValueError as error:
                    if gecerli():
                        notifier.send_to_chat(f"❌ {error}", notifier.chat_id)
                    return
                with tempfile.TemporaryDirectory(prefix="replay_egitim_") as tmp:
                    paths, captions = album_hazirla(question, tmp)
                    sent_count = _album_gonder(paths, captions, notifier, gecerli)
                    if not gecerli():
                        return
                    if sent_count is None:
                        notifier.send_to_chat(
                            "⚠️ Soru albümünün teslimi belirsiz; çift gönderimi önlemek için "
                            "tekrar denenmedi ve soru iptal edildi. Yeniden denemek için /test yazın.",
                            notifier.chat_id)
                        return
                    if sent_count != len(TFS):
                        notifier.send_to_chat(
                            f"⚠️ Soru görsellerinden {sent_count}/{len(TFS)} tanesinin teslimi doğrulandı; "
                            "soru iptal edildi. Yeniden denemek için /test yazın.", notifier.chat_id)
                        return
                    with self.lock:
                        if generation != self.generation:
                            return
                        if getattr(question, "horizon", None) not in HORIZONS:
                            question.horizon = random.SystemRandom().choice(HORIZONS)
                        self.current = question
                    sent = notifier.send_to_chat(
                        f"{question.sembol} · 4 kare aynı ana kadar kapanan mumları gösterir; "
                        "son kapanışlar zaman dilimine göre farklı olabilir.\n"
                        f"Tahmin ufku: seçtiğiniz zaman diliminde {question.horizon} kapanmış mum "
                        "(yatay: ±1,5 ATR).\n"
                        "Zaman dilimi ve yönü birlikte yazabilirsiniz: ör. 1s aşağı "
                        f"(veya yalnız TF: 4s {question.code})", notifier.chat_id)
                    if not sent:
                        with self.lock:
                            if generation == self.generation and self.current is question:
                                self.current = None
            except Exception:  # noqa: BLE001 - eğitim hatası komut işleyicisini durdurmasın
                log.exception("Eğitim sorusu hazırlanamadı")
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
        raw_parts = str(text or "").strip().split()
        if not raw_parts:
            return None
        tf_aliases = {"1h": "1h", "1s": "1h", "2h": "2h", "2s": "2h",
                      "4h": "4h", "4s": "4h", "1d": "1d", "1g": "1d"}
        yon_aliases = {"yukarı": "yukarı", "yukari": "yukarı",
                       "aşağı": "aşağı", "asagi": "aşağı", "yatay": "yatay"}
        with self.lock:
            q = self.current
            if q is None:
                return None
            tokens = [tok.lower() for tok in raw_parts]
            # Soru kodu zorunlu değildir; ancak kullanıcı açıkça kod yazdıysa
            # eski/yanlış soru kodu gecikmiş yanıt olarak reddedilir.
            if len(tokens) >= 2:
                last_upper = raw_parts[-1].upper()
                if last_upper == str(q.code).upper():
                    tokens = tokens[:-1]
                elif (
                    last_upper.lower() not in tf_aliases
                    and last_upper.lower() not in yon_aliases
                    and re.fullmatch(r"[A-Z0-9]{4,10}", last_upper)
                ):
                    return (
                        "Eski veya hatalı soru kodu; kod yazmadan doğrudan "
                        "ör. 1s aşağı şeklinde yanıtlayabilirsiniz."
                    )

            secilen_tf = None
            secilen_yon = None
            taninmayan = []
            for tok in tokens:
                if secilen_tf is None and tok in tf_aliases:
                    secilen_tf = tf_aliases[tok]
                elif secilen_yon is None and tok in yon_aliases:
                    secilen_yon = yon_aliases[tok]
                else:
                    taninmayan.append(tok)

            if taninmayan or (secilen_tf is None and secilen_yon is None):
                if q.tf is None:
                    return (
                        f"Zaman dilimi ve yön yazın (ör. 1s aşağı) veya "
                        f"önce zaman dilimi seçin: 1s, 2s, 4s, 1g."
                    )
                return "Yukarı, yatay veya aşağı yazın (ör. aşağı veya 1s aşağı)."

            if secilen_tf is not None:
                q.tf = secilen_tf
            if getattr(q, "horizon", None) not in HORIZONS:
                q.horizon = random.SystemRandom().choice(HORIZONS)

            if secilen_yon is None:
                from reporting.format import tf_kisa
                return (
                    f"{tf_kisa(q.tf)} · {q.horizon} kapanmış mum sonra yön?\n"
                    "Yukarı, yatay veya aşağı yazın. Yatay: başlangıç kapanışına "
                    "göre ±1,5 ATR aralığı (sınırlar dahil)."
                )

            if q.tf is None:
                return "Zaman dilimini de belirtin: ör. 1s aşağı (1s, 2s, 4s veya 1g)."

            yon = secilen_yon
            try:
                result = sonuc(q, yon)
            except ValueError as error:
                self.current = None
                return f"❌ {error}"
            self.current = None
            generation = self.generation
        def gecerli():
            with self.lock:
                return generation == self.generation

        def job():
            sent_count = 0
            try:
                with tempfile.TemporaryDirectory(prefix="replay_egitim_") as tmp:
                    paths, captions = album_hazirla(q, tmp, answer=result)
                    sent_count = _album_gonder(paths, captions, notifier, gecerli)
            except Exception:  # noqa: BLE001 - sayısal sonucu grafik hatası gizlemesin
                log.exception("Eğitim sonuç grafikleri hazırlanamadı")
            finally:
                try:
                    if gecerli():
                        notifier.send_to_chat(_sonuc_metni(result, sent_count), notifier.chat_id)
                except Exception:  # noqa: BLE001 - ağ hatası sonraki işi kilitlemesin
                    log.warning("Eğitim sonuç metni gönderilemedi.")
                finally:
                    self._finished()
        return ArkaPlanYaniti("⏳ Sonuç hazırlanıyor.", lambda: self._schedule(job, generation))


session = Session()
