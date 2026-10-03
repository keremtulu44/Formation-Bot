# --- FAZ 2.5: OUTCOME LINK (okuma tarafı bağlantı katmanı) ---
#
# AMAÇ
# ----
# Formation History ile MEVCUT Karne/outcome sistemi arasındaki eksik bağı kurmak.
# Bu modül yeni bir outcome algoritması DEĞİLDİR; mevcut `sinyal_sonucu()`'yu
# çağırır ve sonucu `stable_id` üzerinden history kaydına bağlar.
#
# NE YAPMAZ (bilinçli sınırlar)
# -----------------------------
#   * `sinyal_sonucu` / MFE / MAE / ATR hedef-stop / horizon / HEDEF-STOP-BEKLIYOR
#     karar mantığını DEĞİŞTİRMEZ — yalnızca çağırır.
#   * Karne kayıt biçimini, dedup anahtarlarını veya `formasyon_kaydet` TTL'sini
#     değiştirmez.
#   * Eski (stable_id'siz) kayıtları silmez, migrate etmez; onları görmezden gelir.
#   * Yeni bağımsız bir outcome datastore'u oluşturmaz — iki MEVCUT store'u okur.
#
# VERİ AKIŞI
# ----------
#   KarneDefteri.kayitlar()  ──┐
#                              ├─► stable_id ile birleştir ─► sinyal_sonucu() ─► history.sonuc_bagla()
#   formation_history kaydı  ─┘
#
# BİR FORMATION → BİRDEN FAZLA OLAY
# ---------------------------------
# Bir formation birden fazla kırılım denemesi yaşayabilir (başarısız → başarılı).
# Bu yüzden "birincil" outcome seçimi AÇIK ve deterministik bir kuralla yapılır:
#   1) Çözümlenmiş durumlar (hedef/stop/nötr) bekleyen'a üstün tutulur —
#      çözümlenmiş sonuç kesindir.
#   2) Aynı grupta EN YENİ bar_time kazanır (son kırılım denemesi).
#   3) Hiç kırılım yoksa outcome None'dır ve durum `KIRILIM_YOK` olur.
#      Bu, Karne'nin `bekliyor` semantiğini KULLANMAZ — ikisi farklı şeydir:
#      `bekliyor` = "kırılım var, ufuk dolmadı"; `KIRILIM_YOK` = "kırılım hiç yok".
#   4) `sinyal_sonucu` None döndürürse (ölçülemedi) Karne'nin kendi
#      `ölçülemedi` durumu korunur.
# TÜM kırılım denemeleri `kirilimlar` altında ayrıca döndürülür; hiçbir şey gizlenmez.
#
# RESTART / TERMINAL
# ------------------
# Her iki store da disk üzerindedir; bağlantı RAM'deki geçici referansa
# GÜVENMEZ, her çağrıda yeniden kurulur. Terminal formation'ın sonucu
# `sonuc_bagla` ile history kaydına yazıldığı için (ve retention onu koruduğu
# için) sonradan da okunabilir.

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from . import formation_history as fh

logger = logging.getLogger(__name__)

__all__ = [
    "DURUM_KIRILIM_YOK",
    "formasyon_kayitlari",
    "kirilim_kayitlari",
    "olay_kayitlari",
    "outcome_hesapla",
    "birincil_outcome",
    "formasyon_sonucu",
    "bagla",
    "stable_id_ozetleri",
]

# Karne'nin KENDİ durum sabitleri yeniden kullanılır (yeniden icat edilmez).
try:  # pragma: no cover - karne her zaman import edilebilir
    from karne import (DURUM_BEKLIYOR, DURUM_HEDEF, DURUM_NOTR, DURUM_OLCULEMEDI,
                       DURUM_STOP)
except Exception:  # pragma: no cover - savunma amaçlı
    DURUM_HEDEF, DURUM_STOP, DURUM_NOTR = "hedef", "stop", "nötr"
    DURUM_BEKLIYOR, DURUM_OLCULEMEDI = "bekliyor", "ölçülemedi"

# Karne'de KARŞILIĞI OLMAYAN tek durum: formation var ama kırılım hiç yok.
# Karne'nin `bekliyor`'sunu KULLANMAZ (aksi halde "kırılım bekliyor" ile
# "kırılım hiç olmadı" birbirine karışır).
DURUM_KIRILIM_YOK = "kirilim_yok"

_COZUMLENMIS = (DURUM_HEDEF, DURUM_STOP, DURUM_NOTR)

Saglayici = Callable[[str, str], Any]


# =====================================================================
# KARNE KAYITLARINI stable_id İLE FİLTRELE (salt okunur)
# =====================================================================

def _tumu(defter) -> List[dict]:
    if defter is None:
        return []
    try:
        return defter.kayitlar()
    except Exception:  # noqa: BLE001 - defter okunamazsa bağlantı kurulamaz
        logger.debug("Karne defteri okunamadı", exc_info=True)
        return []


def _sid_filtrele(tum_kayitlar: List[dict], stable_id: Optional[str],
                  tip: str) -> List[dict]:
    """Aynı stable_id'ye ve verilen tipe ait kayıtlar.

    stable_id None/boş ise BOŞ liste döner: eski (kimlik taşımayan) kayıtlar
    bu bağlantıya ASLA karışmaz — mevcut davranışlarıyla çalışmaya devam eder.

    `tum_kayitlar` çağıran tarafından BİR kez çekilir; `KarneDefteri.kayitlar()`
    her kaydı kopyaladığı için tip başına tekrar okumak gereksiz maliyettir.
    """
    if not stable_id:
        return []
    cikan = []
    for k in tum_kayitlar:
        if not isinstance(k, dict):
            continue
        if k.get("tip") != tip:
            continue
        if k.get("stable_id") != stable_id:
            continue
        cikan.append(dict(k))
    return cikan


def formasyon_kayitlari(defter, stable_id: Optional[str]) -> List[dict]:
    """Bu stable_id'ye ait Karne `formasyon` kayıtları."""
    return _sid_filtrele(_tumu(defter), stable_id, "formasyon")


def kirilim_kayitlari(defter, stable_id: Optional[str]) -> List[dict]:
    """Bu stable_id'ye ait Karne `kirilim` kayıtları (kırılım denemeleri)."""
    return _sid_filtrele(_tumu(defter), stable_id, "kirilim")


def olay_kayitlari(defter, stable_id: Optional[str]) -> List[dict]:
    """Bu stable_id'ye ait Karne `olay` kayıtları (retest/tamamlandı/başarısız)."""
    return _sid_filtrele(_tumu(defter), stable_id, "olay")


# =====================================================================
# OUTCOME HESABI — MEVCUT MOTORU ÇAĞIRIR, DEĞİŞTİRMEZ
# =====================================================================

def outcome_hesapla(kirilim_kaydi: dict, saglayici: Optional[Saglayici] = None,
                    now: datetime = None) -> Optional[dict]:
    """Tek bir kırılım kaydının outcome'ı.

    Bu, `karne_hesapla`'nın KENDİ çağrı şeklidir:
        seri = saglayici(kayit["stock"], kayit["tf"])
        sinyal_sonucu(kayit, seri, now=now)
    Matematik burada DEĞİŞMEZ; yalnızca aynı fonksiyon aynı argümanlarla çağrılır.
    Sağlayıcı yoksa/None dönerse `sinyal_sonucu` None döner (ölçülemedi).
    """
    if not isinstance(kirilim_kaydi, dict) or kirilim_kaydi.get("tip") != "kirilim":
        return None
    from karne import sinyal_sonucu  # yerel import: döngüsel bağımlılığı önler
    seri = None
    if saglayici is not None:
        try:
            seri = saglayici(kirilim_kaydi.get("stock"), kirilim_kaydi.get("tf"))
        except Exception:  # noqa: BLE001 - sağlayıcı hatası bağlantıyı düşürmesin
            logger.debug("Outcome seri sağlayıcı hatası (%s %s)",
                         kirilim_kaydi.get("stock"), kirilim_kaydi.get("tf"),
                         exc_info=True)
            seri = None
    try:
        return sinyal_sonucu(kirilim_kaydi, seri, now=now)
    except Exception:  # noqa: BLE001 - outcome motoru asla bağlantıyı kırmaz
        logger.debug("sinyal_sonucu hatası: %s", kirilim_kaydi.get("bar_time"),
                     exc_info=True)
        return None


def _bar_sirasi(kayit: dict) -> tuple:
    """Kırılım kayıtlarını deterministik sıralar: bar_time, sonra kayit_zaman."""
    return (str(kayit.get("bar_time") or ""), str(kayit.get("kayit_zaman") or ""))


def birincil_outcome(kirilimlar: List[dict], saglayici: Optional[Saglayici] = None,
                     now: datetime = None) -> Dict[str, Any]:
    """Birden fazla kırılım denemesinden BİRİNCİL outcome'ı seçer.

    Kural (deterministik):
      1) Çözümlenmiş (hedef/stop/nötr) > bekliyor — kesin sonuç üstün tutulur.
      2) Aynı grupta en yeni bar_time kazanır.
      3) Kırılım yoksa durum `KIRILIM_YOK`, outcome None.
      4) `sinyal_sonucu` None döndürdüyse Karne'nin `ölçülemedi` durumu korunur.

    Dönen sözlük HER ZAMAN `durum` içerir; `outcome` None olabilir.
    """
    if not kirilimlar:
        return {"durum": DURUM_KIRILIM_YOK, "outcome": None,
                "kaynak": None, "deneme": 0}

    hesaplanan = []
    for k in sorted(kirilimlar, key=_bar_sirasi):
        sonuc = outcome_hesapla(k, saglayici, now=now)
        if sonuc is None:
            # Ölçülemedi: Karne'nin kendi semantiği korunur.
            hesaplanan.append((k, {"durum": DURUM_OLCULEMEDI}))
        else:
            hesaplanan.append((k, dict(sonuc)))

    cozulmus = [(k, s) for k, s in hesaplanan if s.get("durum") in _COZUMLENMIS]
    grup = cozulmus or hesaplanan
    # En yeni bar_time (grup zaten sıralı; sonuncusu en yeni).
    kaynak, sonuc = grup[-1]
    return {"durum": sonuc.get("durum"), "outcome": sonuc,
            "kaynak": _bar_sirasi(kaynak)[0], "deneme": len(kirilimlar)}


# =====================================================================
# ANA OKUMA FONKSİYONU
# =====================================================================

def _stock_tf_turet(karne_kayitlar: List[dict], stock: Optional[str],
                    tf: Optional[str]) -> tuple:
    """(stock, tf) verilmemişse Karne kayıtlarından türetilir."""
    if stock and tf:
        return stock, tf
    for k in karne_kayitlar:
        s, t = k.get("stock"), k.get("tf")
        if s and t:
            return s, t
    return stock, tf


def formasyon_sonucu(stable_id: Optional[str], defter=None,
                     stock: Optional[str] = None, tf: Optional[str] = None,
                     saglayici: Optional[Saglayici] = None,
                     data_dir: Optional[str] = None,
                     now: datetime = None) -> Optional[Dict[str, Any]]:
    """Bir `stable_id` için formation + kirilim + olaylar + outcome birleşimi.

    Dönen sözlük:
        {
          "stable_id": str,
          "stock": str|None, "tf": str|None,
          "history": dict|None,        # formation history kaydı (doğum/olaylar/snapshot/terminal)
          "karne": {"formasyon": [...], "kirilim": [...], "olay": [...]},
          "outcome": dict|None,        # MEVCUT sinyal_sonucu çıktısı
          "durum": str,                # hedef|stop|nötr|bekliyor|ölçülemedi|kirilim_yok
          "deneme": int,               # kırılım denemesi sayısı
          "kaynak": str|None,          # birincil outcome'ın bar_time'ı
        }

    stable_id None/boş veya hiç kaydı yoksa None döner. Bu fonksiyon SAFTIR:
    dosya yazmaz, matematiği çalıştırmaz (yalnızca mevcut motoru çağırır).
    """
    if not stable_id:
        return None

    tum_kayitlar = _tumu(defter)
    formasyonlar = _sid_filtrele(tum_kayitlar, stable_id, "formasyon")
    kirilimlar = _sid_filtrele(tum_kayitlar, stable_id, "kirilim")
    olaylar = _sid_filtrele(tum_kayitlar, stable_id, "olay")
    tum_karne = formasyonlar + kirilimlar + olaylar

    stock, tf = _stock_tf_turet(tum_karne, stock, tf)

    # History kaydı (yoksa None — Karne kaydı olup history olmayabilir).
    history = None
    if stock and tf:
        try:
            defter_h = fh.yukle(stock, tf, data_dir)
            rec = fh.kayit_getir(defter_h, stable_id)
            if rec is not None:
                history = dict(rec)
        except Exception:  # noqa: BLE001 - history okunamazsa bağlantı yine döner
            logger.debug("History kaydı okunamadı (%s %s %s)", stock, tf, stable_id,
                         exc_info=True)

    birincil = birincil_outcome(kirilimlar, saglayici, now=now)

    durum = birincil.get("durum")
    outcome = birincil.get("outcome")

    # --- Geçmişten okuma (Faz 2.5 madde 10) ---
    # Taze hesap ÖLÇÜLEMEDİ ise (seri yok / bar bulunamadı) ve history'de daha
    # önce bağlanmış bir sonuç varsa, GERÇEK ÖLÇÜMÜ asla ezmeyiz — yalnızca
    # ölçemediğimizde boş bırakmak yerine bağlı sonucu kullanırız. Böylece
    # terminal formation'ın sonucu seri sağlanmasa da okunabilir.
    # Not: `bekliyor` bu kapsama DAHİL DEĞİLDİR — bekliyor geçerli bir
    # Karne durumudur ve geçmişteki sonuçla karıştırılmamalıdır.
    if durum == DURUM_OLCULEMEDI and history:
        sakli = history.get("sonuc") or {}
        sakli_durum = sakli.get("durum")
        if sakli_durum and sakli_durum != DURUM_OLCULEMEDI:
            durum = sakli_durum
            outcome = sakli.get("outcome")

    return {
        "stable_id": stable_id,
        "stock": stock,
        "tf": tf,
        "history": history,
        "karne": {"formasyon": formasyonlar, "kirilim": kirilimlar, "olay": olaylar},
        "outcome": outcome,
        "durum": durum,
        "deneme": birincil.get("deneme", 0),
        "kaynak": birincil.get("kaynak"),
    }


def bagla(defter, stock: str, tf: str, stable_id: Optional[str],
          saglayici: Optional[Saglayici] = None, data_dir: Optional[str] = None,
          now: datetime = None) -> Optional[Dict[str, Any]]:
    """Outcome'ı history kaydına YAZAR (mevcut `sonuc_bagla` üzerinden).

    Yazma, yalnızca outcome GERÇEKTEN değiştiğinde yapılır: her taramada
    gereksiz disk yazımı yapmaz (per-bar/per-scan yazma kasıtlı olarak sınırlı).

    Dönen: güncellenmiş özet veya değişiklik yoksa/bağlantı kurulamazsa None.
    """
    if not stable_id:
        return None
    ozet = formasyon_sonucu(stable_id, defter=defter, stock=stock, tf=tf,
                            saglayici=saglayici, data_dir=data_dir, now=now)
    if ozet is None:
        return None
    try:
        defter_h = fh.yukle(stock, tf, data_dir)
        rec = fh.kayit_getir(defter_h, stable_id)
        if rec is None:
            # History'de kayıt yok: bağlantı kuracak yer yok. Karne tarafı
            # zaten doğru çalışıyor; burada YENİ kayıt uydurmak yanlış birleşme
            # riskidir -> sessizce geç.
            return None
        mevcut = rec.get("sonuc")
        yeni = {
            "durum": ozet["durum"],
            "outcome": ozet["outcome"],
            "deneme": ozet["deneme"],
            "kaynak": ozet["kaynak"],
        }
        if mevcut == yeni:
            return None  # değişiklik yok -> yazma
        if fh.sonuc_bagla(defter_h, stable_id, yeni):
            fh.kaydet(defter_h, data_dir)
            return ozet
    except Exception:  # noqa: BLE001 - linkage botu asla durdurmaz
        logger.debug("Outcome bağlantısı yazılamadı (%s %s %s)", stock, tf, stable_id,
                     exc_info=True)
    return None


def stable_id_ozetleri(defter=None, saglayici: Optional[Saglayici] = None,
                       data_dir: Optional[str] = None,
                       now: datetime = None) -> Dict[str, Dict[str, Any]]:
    """Karne'de stable_id taşıyan TÜM kayıtların stable_id -> özet eşlemesi.

    Eski (stable_id'siz) kayıtlar BİLEREK hariç tutulur: onlar mevcut
    davranışlarıyla çalışmaya devam eder, burada bozulmaz.
    """
    ozetler: Dict[str, Dict[str, Any]] = {}
    for k in _tumu(defter):
        if not isinstance(k, dict):
            continue
        sid = k.get("stable_id")
        if not sid or sid in ozetler:
            continue
        try:
            ozet = formasyon_sonucu(sid, defter=defter, stock=k.get("stock"),
                                    tf=k.get("tf"), saglayici=saglayici,
                                    data_dir=data_dir, now=now)
            if ozet is not None:
                ozetler[sid] = ozet
        except Exception:  # noqa: BLE001
            logger.debug("Outcome özeti üretilemedi: %s", sid, exc_info=True)
    return ozetler
