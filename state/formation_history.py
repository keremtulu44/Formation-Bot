# --- FAZ 2.1: FORMATION HISTORY REGISTRY (çoklu formasyon kayıt defteri) ---
#
# NEDEN GEREKLİ
# -------------
# Faz 1, `(stock, timeframe)` başına TEK bir identity anchor'ü saklar
# (`state/formation_identity.py`). Tek slot, tek formasyon demektir. Aynı
# pencere içinde iki canlı formasyon varsa tek slot yetmez: ölçümlerde tek
# canlı formasyonda bile pencere kaydığında gereksiz yeni stable_id üretimi
# görüldü (bkz. PHASE2_TASARIM_NOTLARI.md §2). Faz 2.1 bunu çözer: tek slot
# yerine, (stock,tf) başına birden fazla formation kaydı tutan bir defter.
#
# KİMLİK BAĞI (identity link)
# ---------------------------
# Kimlik köprüsü `stable_id`'dir ve değişmez. `PatternCandidate.identity`
# motor-içi sayaçtır; ikisi asla karıştırılmaz.
#
# BAR-TIME ALIGNMENT (en kritik tasarım kararı)
# ---------------------------------------------
# Tüm bar indeksleri PENCERE-RELATİF'dir: pencere her taramada ~1 bar ötelendiği
# için aynı fiziksel barın indeksi 1 birim kayar. Ham indeksleri karşılaştırmak
# (mevcut `continuity_score`'un yaptığı) kaymaya açıktır. Bu yüzden defter:
#   1. Doğum anının MUTLAK zamanını (`bar_time`) saklar,
#   2. Eşleştirmede o zamanın bugünkü pencere içindeki konumunu bulur,
#   3. `delta = simdiki_konum - kayitli_konum` hesaplar,
#   4. Kaydın bar indekslerini `delta` ile taşır, FİYATLARA DOKUNMAZ.
# Böylece `continuity_score` / `identity_compatible` DEĞİŞTİRİLMEDEN,
# aynı pencere koordinat sisteminde çalışır.
#
# GÜVENLİK KURALLARI (öncelik sırası)
# -----------------------------------
#   1) YANLIŞ BİRLEŞTİRME asla olmamalı. Eşleşme için doğum barı hâlâ
#      pencerede olmalı; değilse kayıt atlanır (hiç eşleşme olmaması
#      tercih edilir). Eşik 60 ve `identity_compatible` aynen korunur.
#   2) Gereksiz yeni ID'yi en aza indir.
#   3) Bir scan'de aynı stable_id iki farklı candidate'a atanamaz
#      (`kullanilan` kümesi ile deterministik "ilk gelen alır").
#
# YAZMA İŞ AKIŞI
# --------------
# Yazma yalnızca ANLAMLI olaylarda tetiklenir (per-bar dump YOK):
# doğum, olay (state geçişi), kırılım snapshot'ı, terminal snapshot'ı.
# Yazma, tek taramada tek save ile sınırlanır.
#
# GÜVENİLİRLİK
# ------------
# Bozuk/okunamaz dosya -> boş defter döner, bot ÇALIŞMAYA DEVAM EDER.
# Hiçbir exception çağırana sızmaz (history botu asla durdurmaz).

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import formation_schema as schema

__all__ = [
    "HISTORY_SURUMU",
    "MAX_KAYIT",
    "MAX_OLAY",
    "MAX_SNAPSHOT",
    "BAR_ALANLARI",
    "DURUM_ACIK",
    "DURUM_KIRILIM",
    "DURUM_RETEST",
    "DURUM_TERMINAL",
    "yol",
    "yukle",
    "kaydet",
    "saglik_raporu",
    "bos_defter",
    "dogum_ekle",
    "olay_ekle",
    "snapshot_ekle",
    "terminal_ekle",
    "sonuc_bagla",
    "kayit_getir",
    "kayitlar",
    "eslestir",
    "kirilim_turu",
    "terminal_durumu",
]

HISTORY_SURUMU = 1

# --- retention (sonsuz büyüme yasak) ---
MAX_KAYIT = 30       # (stock,tf) başına tutulacak formation kaydı
MAX_OLAY = 200       # kayıt başına tutulacak olay
MAX_SNAPSHOT = 40    # kayıt başına tutulacak snapshot

# Kaydın yaşam döngüsü durumu (motorun ST_* state'lerinden bağımsız,
# history'nin kendi basit durumu).
DURUM_ACIK = "acik"
DURUM_KIRILIM = "kirilim"
DURUM_RETEST = "retest"
DURUM_TERMINAL = "terminal"

# Bar indeksi olarak taşınması gereken alanlar (fiyat/skor alanları DEĞİL).
# Bu liste, bar-time alignment sırasında `delta` ile ötelenir.
BAR_ALANLARI = frozenset({
    "start_bar", "end_bar", "known_bar", "apex_bar",
    "hb1", "hb2", "lb1", "lb2",
    "pole_start_bar", "pole_end_bar",
    "break_snapshot_bar",
})

_kilitle = threading.RLock()


# =====================================================================
# YARDIMCILAR
# =====================================================================

def _data_dir() -> str:
    try:
        from config import DATA_DIR
        return str(DATA_DIR)
    except Exception:
        return "bot_data"


def yol(stock: str, tf: str, data_dir: Optional[str] = None) -> str:
    """(stock,tf) defterinin yolu.

    `bot_data/{STOCK}.json` yazım kuralı taklit edilir:
    `bot_data/formation_history/{STOCK}_{TF}.json`
    Yol tek yerden (state/paths.py) üretilir; testlerde `data_dir` verilebilir.
    """
    from .paths import formation_history_yolu
    return formation_history_yolu(stock, tf, data_dir)


def _simdi() -> str:
    return datetime.now().isoformat()


def bos_defter(stock: str, tf: str) -> Dict[str, Any]:
    return {
        "surum": HISTORY_SURUMU,
        "stock": stock,
        "timeframe": tf,
        "guncellendi": None,
        "kayitlar": {},
    }


def yukle(stock: str, tf: str, data_dir: Optional[str] = None) -> Dict[str, Any]:
    """Defteri yükler. Bozuk/eksik dosyada boş defter döner (exception yok)."""
    dosya = yol(stock, tf, data_dir)
    if not os.path.exists(dosya):
        return bos_defter(stock, tf)
    try:
        with open(dosya, "r", encoding="utf-8") as fh:
            veri = json.load(fh)
    except Exception:
        # Bozuk JSON: history botu durdurmaz, sıfırdan başlanır.
        return bos_defter(stock, tf)
    if not isinstance(veri, dict):
        return bos_defter(stock, tf)
    kayitlar = veri.get("kayitlar")
    if not isinstance(kayitlar, dict):
        kayitlar = {}
    temiz: Dict[str, Any] = {}
    for sid, rec in kayitlar.items():
        if isinstance(sid, str) and isinstance(rec, dict):
            rec.setdefault("stable_id", sid)
            temiz[sid] = rec
    veri["kayitlar"] = temiz
    veri.setdefault("surum", HISTORY_SURUMU)
    veri["stock"] = stock
    veri["timeframe"] = tf
    return veri


def kaydet(defter: Dict[str, Any], data_dir: Optional[str] = None) -> bool:
    """Defteri ATOMİK yazar (tmp + os.replace) ve thread-lock korur.

    Yarım yazılmış dosya asla görülmez: ya eski içerik ya yeni içerik.
    """
    try:
        stock = str(defter.get("stock"))
        tf = str(defter.get("timeframe"))
        dosya = yol(stock, tf, data_dir)
        klasor = os.path.dirname(dosya)
        with _kilitle:
            if klasor and not os.path.isdir(klasor):
                os.makedirs(klasor, exist_ok=True)
            defter["surum"] = HISTORY_SURUMU
            defter["guncellendi"] = _simdi()
            tmp = dosya + ".tmp.{}.{}".format(os.getpid(), threading.get_ident())
            with open(tmp, "w", encoding="utf-8") as fh:
                # `default` SON GÜVENLİK AĞI: sözleşme dışı bir tip (ör. ham
                # Timestamp) hiçbir koşulda history yazımını kıramaz. Böyle
                # bir değer None yazılır, defter bozulmaz.
                json.dump(defter, fh, ensure_ascii=False,
                          default=lambda o: schema.json_guvenli(o))
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, dosya)
        return True
    except Exception:
        # Disk dolu, izin yok, vb. -> history yazılamaz ama bot çalışır.
        return False


def _kayitlar(defter: Dict[str, Any]) -> Dict[str, Any]:
    kayitlar = defter.get("kayitlar")
    if not isinstance(kayitlar, dict):
        kayitlar = {}
        defter["kayitlar"] = kayitlar
    return kayitlar


def kayitlar(defter: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(_kayitlar(defter).values())


def kayit_getir(defter: Dict[str, Any], stable_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not stable_id:
        return None
    rec = _kayitlar(defter).get(stable_id)
    return rec if isinstance(rec, dict) else None


def _bar_time(engine: Any, bar_index: Optional[int]) -> Optional[str]:
    """Verilen pencere-relative bar indeksinin MUTLAK zamanı."""
    if bar_index is None:
        return None
    idx = getattr(engine, "index_values", None)
    if idx is None:
        return None
    try:
        if 0 <= int(bar_index) < len(idx):
            return str(idx[int(bar_index)])
    except Exception:
        return None
    return None


def _konum_bul(index_values: Any, bar_time: Optional[str]) -> Optional[int]:
    """`bar_time`'ın bugünkü penceredeki konumu. Bulunamazsa None.

    Bozuk/boş veride veya zaman damgası bulunamazsa None döner; çağıran bu
    durumda eşleşmeyi reddeder (güvenlik kuralı 1).
    """
    if index_values is None or not bar_time:
        return None
    hedef = str(bar_time)
    try:
        n = len(index_values)
    except Exception:
        return None
    for i in range(n):
        try:
            if str(index_values[i]) == hedef:
                return i
        except Exception:
            continue
    return None


def _bos_alanlar() -> Dict[str, Any]:
    return {}


# =====================================================================
# YAZMA: DOĞUM
# =====================================================================

def dogum_ekle(defter: Dict[str, Any], candidate: Any, engine: Any) -> Optional[Dict[str, Any]]:
    """Doğum kaydı oluşturur/günceller. Yazma değişiklik yaptıysa kayıt döner.

    Idempotent: aynı stable_id tekrar gelirse doğum snapshot'ı üzerine
    yazılmaz, yalnızca `son_gorulme` tazelenir.
    """
    sid = getattr(candidate, "stable_id", None)
    if not sid:
        return None
    rec = kayit_getir(defter, sid)
    bar_time = _bar_time(engine, getattr(candidate, "start_bar", None))
    snap = schema.dogum_snapshot(candidate, bar_time=bar_time)
    if rec is None:
        rec = {
            "stable_id": sid,
            "durum": DURUM_ACIK,
            "ilk_gorulme": _simdi(),
            "son_gorulme": _simdi(),
            "dogum": {
                "bar_time": bar_time,
                "bar_index": getattr(candidate, "start_bar", None),
                "alanlar": snap["alanlar"],
            },
            "olaylar": [],
            "snapshotlar": [],
        }
        _kayitlar(defter)[sid] = rec
        return rec
    # Var olan kayıt: doğum bilgisini koru, yalnızca tazele.
    rec["son_gorulme"] = _simdi()
    if not rec.get("dogum", {}).get("bar_time") and bar_time:
        rec["dogum"] = {
            "bar_time": bar_time,
            "bar_index": getattr(candidate, "start_bar", None),
            "alanlar": snap["alanlar"],
        }
    return None


# =====================================================================
# YAZMA: OLAYLAR
# =====================================================================

def _olay_guvenli(olay: Dict[str, Any]) -> Dict[str, Any]:
    """Olay sözlüğünü JSON-safe kopyasını üretir.

    Motorun olay sözlüğündeki `time` alanı ham `pandas.Timestamp` taşır
    (index_values doğrudan kopyalanır). Bu, `json.dump`'ı kırar. Sözleşmedeki
    `json_guvenli` ile indirgenir. Anahtar adları DEĞİŞTİRİLMEZ.
    """
    return {str(k): schema.json_guvenli(v) for k, v in olay.items()}


def _olay_anahtar(olay: Dict[str, Any]) -> str:
    """Olay dedup anahtarı: stable_id + type + name + bar + time.

    Motorun olay sözlüğü anahtarları birebir kullanılır (`type`, `name`,
    `bar`, `time`); Faz 2.2 sadece `stable_id` ekler, anahtar adlarını
    DEĞİŞTİRMEZ.
    """
    return "{}|{}|{}|{}|{}".format(
        olay.get("stable_id"),
        olay.get("type"),
        olay.get("name"),
        olay.get("bar"),
        olay.get("time"),
    )


def olay_ekle(defter: Dict[str, Any], olaylar: Iterable[Dict[str, Any]]) -> int:
    """Snapshot olaylarını kayıtlara dağıtır. Eklenen olay sayısını döner.

    Dedup: aynı tarama tekrarlandığında (tam_yeniden replay) olay iki kez
    yazılmaz. `stable_id`'si olmayan olay (doğumdan önceki POLE olayı vb.)
    hiçbir kayda bağlanamaz -> atlanır.
    """
    eklendi = 0
    kayitlar_map = _kayitlar(defter)
    for olay in olaylar or []:
        if not isinstance(olay, dict):
            continue
        sid = olay.get("stable_id")
        if not sid:
            continue
        rec = kayitlar_map.get(sid)
        if rec is None:
            # Olay bilinen bir formasyona ait değil (doğum bu turda yazılmadı).
            # Yeni bir iskelet kayıt açmak YANLIŞ BİRLEŞTİRME riskidir; atla.
            continue
        kopya = _olay_guvenli(olay)
        rec.setdefault("olaylar", [])
        anahtar = _olay_anahtar(kopya)
        if any(_olay_anahtar(mevcut) == anahtar for mevcut in rec["olaylar"][-MAX_OLAY:]):
            continue
        rec["olaylar"].append(kopya)
        eklendi += 1
        if len(rec["olaylar"]) > MAX_OLAY:
            del rec["olaylar"][:-MAX_OLAY]
        rec["son_gorulme"] = _simdi()
    return eklendi


# =====================================================================
# YAZMA: SNAPSHOT'LAR (geometri / kırılım / terminal)
# =====================================================================

def snapshot_ekle(
    defter: Dict[str, Any],
    stable_id: Optional[str],
    tur: str,
    snapshot: Dict[str, Any],
) -> bool:
    """Bir kayda anlamlı bir snapshot ekler (birth hariç).

    `tur`: "geometri" | "kirilim" | "terminal"
    Aynı (tur, bar_time) tekrar yazılmaz -> tam_yeniden replay'de şişmez.
    """
    rec = kayit_getir(defter, stable_id)
    if rec is None or not snapshot:
        return False
    bar_time = snapshot.get("bar_time")
    rec.setdefault("snapshotlar", [])
    for mevcut in rec["snapshotlar"][-MAX_SNAPSHOT:]:
        if mevcut.get("tur") == tur and mevcut.get("bar_time") == bar_time:
            return False
    rec["snapshotlar"].append({
        "tur": tur,
        "bar_time": bar_time,
        "alanlar": snapshot.get("alanlar", {}),
    })
    if len(rec["snapshotlar"]) > MAX_SNAPSHOT:
        del rec["snapshotlar"][:-MAX_SNAPSHOT]
    rec["son_gorulme"] = _simdi()
    return True


# =====================================================================
# YAZMA: TERMINAL
# =====================================================================

def kirilim_turu(state: Optional[str]) -> Optional[str]:
    """Motor state'ini history durumuna çevirir (kırılım yolu)."""
    if not state:
        return None
    if state == "RETEST_BEKLENIYOR" or state == "RETEST_EDILIYOR":
        return DURUM_RETEST
    if state in ("KIRILIM_HAZIRLIGI", "KIRILIM_ADAYI", "KIRILIM_DENEMESI"):
        return DURUM_KIRILIM
    return None


def terminal_durumu(state: Optional[str]) -> bool:
    """Bu state history açısından terminal mi? (sonuç bağlanabilir olmalı)"""
    if not state:
        return False
    try:
        from patterns.constants import f_is_terminal
        return bool(f_is_terminal(state))
    except Exception:
        # Konservatif varsayılan: sınıflandırma yapılamıyorsa terminal sayma.
        return False


def terminal_ekle(defter: Dict[str, Any], stable_id: Optional[str], state: Optional[str],
                  snapshot: Optional[Dict[str, Any]] = None) -> bool:
    """Kaydı terminal işaretler ve terminal snapshot'ını ekler."""
    rec = kayit_getir(defter, stable_id)
    if rec is None or not terminal_durumu(state):
        return False
    if snapshot:
        snapshot_ekle(defter, stable_id, "terminal", snapshot)
    rec["durum"] = DURUM_TERMINAL
    rec["terminal_state"] = state
    rec["terminal_zamani"] = _simdi()
    rec["son_gorulme"] = _simdi()
    return True


# =====================================================================
# YAZMA: SONUÇ BAĞI (outcome link)
# =====================================================================

def sonuc_bagla(defter: Dict[str, Any], stable_id: Optional[str], sonuc: Dict[str, Any]) -> bool:
    """Karne sonucunu kayda bağlar. Sonuç KİLİTLİ sayılır: retention onu silmez."""
    rec = kayit_getir(defter, stable_id)
    if rec is None or not isinstance(sonuc, dict):
        return False
    rec["sonuc"] = dict(sonuc)
    rec["sonuc_zamani"] = _simdi()
    return True


# =====================================================================
# OKUMA: KİMLİK EŞLEŞTİRME (bar-time alignment)
# =====================================================================

def _aday_kandidate(kayit: Dict[str, Any], delta: int) -> Any:
    """Persist edilmiş doğum snapshot'ından, `delta` ile taşınmış geçici
    bir PatternCandidate üretir.

    Matematik DEĞİŞTİRİLMEZ: `identity_compatible` ve `continuity_score`
    aynen çağrılır. Tek yapılan, kaydın bar indekslerini bugünkü pencere
    koordinat sistemine taşımaktır (fiyatlar olduğu gibi kalır).
    """
    from patterns.candidate import PatternCandidate

    alanlar = (kayit.get("dogum") or {}).get("alanlar") or {}
    aday = PatternCandidate()
    aday.valid = True
    # Sözleşme: identity alanları birebir taşınır.
    for alan in schema.IDENTITY_FIELDS:
        if alan in alanlar:
            setattr(aday, alan, alanlar[alan])
    # Bar indeksleri taşınır; fiyat/skorlar zaten doğru koordinatta.
    for alan in BAR_ALANLARI:
        deger = getattr(aday, alan, None)
        if isinstance(deger, int) and not isinstance(deger, bool):
            setattr(aday, alan, deger + delta)
    return aday


def eslestir(engine: Any, candidate: Any, kullanilan: Optional[Iterable[str]] = None,
             stock: Optional[str] = None, tf: Optional[str] = None,
             data_dir: Optional[str] = None) -> Optional[str]:
    """Registry'den candidate ile aynı formation'ın stable_id'sini bulur.

    Akış (sıra önemli):
      1. Defter yüklenir. Boş/bozuksa -> None (Faz 1 yolu devrede kalır).
      2. Yalnızca AÇIK (terminal olmayan) kayıtlar değerlendirilir.
         Bu, Faz 1'in "motor belleğindeki duruma göre ele" kuralından
         KATI olarak güvenlidir: çoklu formasyonda motor belleği 2. formasyonu
         taşıdığında 1.'nin kaydı hâlâ açık görünür.
      3. Bir scan'de aynı stable_id iki kez kullanılamaz (`kullanilan`).
      4. Doğum barı bugünkü pencerede BULUNMALI (güvenlik kuralı 1).
         Bulunamıyorsa kayıt atlanır -> hiç eşleşme tercih edilir.
      5. `delta` hesaplanır, kayıt taşınır, DEĞİŞTİRİLMEMİŞ
         `identity_compatible` + `continuity_score` uygulanır.
      6. Eşik >= 60 sağlanan ve en yüksek skoru alan kayıt kazanır
         (beraberlikte en yeni doğum -> deterministik).
    """
    if stock is None or tf is None:
        key = getattr(engine, "_key", None)
        if not key:
            return None
        stock, tf = str(key).rsplit("_", 1)
    if getattr(candidate, "stable_id", None):
        # Zaten kimliği bilinen bir candidate yeniden eşleştirilmez.
        return None
    try:
        defter = yukle(stock, tf, data_dir)
        kayitlar_map = _kayitlar(defter)
        if not kayitlar_map:
            return None
        haric = set(kullanilan or ())
        idx = getattr(engine, "index_values", None)

        from patterns.selection import identity_compatible, continuity_score

        en_iyi: Optional[Tuple[float, str]] = None
        for sid, rec in kayitlar_map.items():
            if sid in haric:
                continue
            if rec.get("durum") == DURUM_TERMINAL:
                continue  # terminal kimliği yeni formasyona ASLA taşınmaz
            dogum = rec.get("dogum") or {}
            kayitli_bar_time = dogum.get("bar_time")
            kayitli_bar_index = dogum.get("bar_index")
            if not kayitli_bar_time or not isinstance(kayitli_bar_index, int):
                continue  # Faz 1 anchor biçimi: bu matcher onu değerlendirmez
            simdiki = _konum_bul(idx, kayitli_bar_time)
            if simdiki is None:
                continue  # doğum barı pencerede değil -> eşleşme yok
            delta = int(simdiki) - int(kayitli_bar_index)
            aday = _aday_kandidate(rec, delta)
            if not identity_compatible(candidate, aday):
                continue
            skor = continuity_score(engine, candidate, aday)
            if skor < 60.0:
                continue
            yeni = (float(skor), str(rec.get("ilk_gorulme") or ""))
            if en_iyi is None or yeni[0] > en_iyi[0] or (
                    yeni[0] == en_iyi[0] and yeni[1] > en_iyi[1]):
                en_iyi = (float(skor), sid)
        return en_iyi[1] if en_iyi else None
    except Exception:
        # Registry okunamaz/hata verirse Faz 1 yoluna düşülür.
        return None


# =====================================================================
# RETENTION
# =====================================================================

def _silme_onceligi(rec: Dict[str, Any]) -> int:
    """Retention silme önceliği: YÜKSEK değer = önce silinir.

    Sıralama mantığı (en değerli korunur):
      0 — Sonucu bağlanmış kayıt: ASLA silinmez. Outcome link Faz 2.5'in
          tek değerli çıktısıdır; retention onu yok etmemeli.
      3 — Sonucusuz terminal kayıt: en az değerli, önce gider.
      2 — Açık kayıt: yaşayan formasyon; yalnızca zorunluysa silinir.
    """
    if rec.get("sonuc"):
        return 0
    if rec.get("durum") == DURUM_TERMINAL:
        return 3
    return 2


def _retention_temizle(defter: Dict[str, Any]) -> int:
    """Defteri sınırler içinde tutar. Silinen kayıt sayısını döner.

    Silme sırası: en düşük değerli (sonucusuz terminal) önce gider; aynı
    grupta en eski `ilk_gorulme` önce silinir. Sonucu bağlı kayıt hiçbir
    koşulda silinmez.
    """
    kayitlar_map = _kayitlar(defter)
    if len(kayitlar_map) <= MAX_KAYIT:
        return 0
    sirali = sorted(
        kayitlar_map.values(),
        key=lambda r: (-_silme_onceligi(r), str(r.get("ilk_gorulme") or "")),
    )
    silinecek = sirali[: len(kayitlar_map) - MAX_KAYIT]
    for rec in silinecek:
        kayitlar_map.pop(rec.get("stable_id"), None)
    return len(silinecek)


def temizle(stock: str, tf: str, data_dir: Optional[str] = None) -> int:
    """Retention'ı diske uygular."""
    try:
        defter = yukle(stock, tf, data_dir)
        silinen = _retention_temizle(defter)
        if silinen:
            kaydet(defter, data_dir)
        return silinen
    except Exception:
        return 0


# =====================================================================
# SAĞLIK RAPORU (startup kontrolü)
# =====================================================================

def saglik_raporu(data_dir: Optional[str] = None) -> Dict[str, Any]:
    """Defterlerin sağlık raporu: kaç dosya, kaç kayıt, kaçı bozuk.

    Bot hiçbir koşulda çökmez: bozuk dosyalar listelenir, exception sızmaz.
    Startup'ta yalnızca BİLGİ/LOG amaçlıdır — registry zaten lazy okunur,
    bu adım olmadan da history korunur.
    """
    import glob as _glob
    from .paths import FORMATION_HISTORY_ALT_DOSYA
    kok = data_dir if data_dir is not None else _data_dir()
    klasor = os.path.join(kok, FORMATION_HISTORY_ALT_DOSYA)
    rapor: Dict[str, Any] = {"dosya": 0, "kayit": 0, "bozuk": [], "yol": klasor}
    if not os.path.isdir(klasor):
        return rapor
    for dosya in sorted(_glob.glob(os.path.join(klasor, "*.json"))):
        rapor["dosya"] += 1
        try:
            with open(dosya, "r", encoding="utf-8") as f:
                veri = json.load(f)
            recs = veri.get("kayitlar") if isinstance(veri, dict) else None
            if isinstance(recs, dict):
                rapor["kayit"] += len(recs)
            else:
                rapor["bozuk"].append(os.path.basename(dosya))
        except Exception:
            rapor["bozuk"].append(os.path.basename(dosya))
    return rapor
