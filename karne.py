"""Haftalık doğruluk karnesi — sinyal defteri + ileri performans (TAMAMEN YEREL).

Neden bu modül: "bu hafta kaç formasyon bulundu, kaçı kırılımdan sonra pozitif
gitti / negatif gitti?" sorusunun ölçülmüş cevabı hiçbir yerde tutulmuyordu.

Tasarım kararları:
  * **Supabase/uzak store GEREKTİRMEZ.** Defter `DATA_DIR/karne_defteri.json`
    (tek dosya, atomik yazım). Bot Supabase'siz çalışırken de karne tam çalışır.
  * **Ağ GEREKTİRMEZ (defter için).** Ölçüm, botun bellekteki mevcut serilerinden
    (`deque_manager`) yapılır; yeni veri indirilmez.
  * **Deftere iki olay tipi yazılır:**
      - `formasyon`: canlı formasyon ilk görüldüğünde (hisse/TF/formasyon TTL'i ile
        tekilleştirilir) -> "kaç formasyon bulundu" sayıları.
      - `kirilim`: kırılım teyit edildiğinde (giriş = teyit barının kapanışı,
        yön, kalite, ATR) -> "kırılımdan sonra ne oldu" performansı.
      - `olay`: retest/tamamlanma/başarısız kırılım -> haftalık huni sayıları.
  * **Karne, Cuma gün sonu mesajının ALTINA eklenir** (main.py `_haftalik_karne_ekle`).
    Haftada bir kez gönderilir; kaçırılırsa `/karne` komutu her zaman çalışır.

Performans ölçütü (kayıt anında saklanan giriş fiyatı + ATR ile):
  * Her bar için lehte (MFE) / alehte (MAE) hareket hesaplanır, ATR'ye normalize edilir.
  * İlk dokunuş yarışı: lehte `KARNE_HEDEF_ATR` ÖNCE gelirse "hedef"; alehte
    `KARNE_STOP_ATR` önce gelirse "stop"; ikisi de olmazsa "nötr" (ufuk sonu).
  * Aynı barda ikisi de dokunduysa muhafazakâr sayılır -> "stop".
  * Yön doğruluğu ayrıca raporlanır: ufuk sonu kapanış, kırılım yönünde mi?
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

import pandas as pd

from config import (DATA_DIR, ISTANBUL_TZ, KARNE_FORMASYON_TTL_SAAT, KARNE_GUNU,
                    KARNE_HEDEF_ATR, KARNE_HORIZON_BAR, KARNE_SAKLAMA_GUN, KARNE_STOP_ATR)

logger = logging.getLogger(__name__)

KARNE_DOSYA = "karne_defteri.json"
KARNE_SURUM = 1
# Durumlar
DURUM_HEDEF = "hedef"
DURUM_STOP = "stop"
DURUM_NOTR = "nötr"
DURUM_BEKLIYOR = "bekliyor"
DURUM_OLCULEMEDI = "ölçülemedi"

DURUM_TR = {
    DURUM_HEDEF: "hedefe ulaştı",
    DURUM_STOP: "stop oldu",
    DURUM_NOTR: "nötr kaldı",
    DURUM_BEKLIYOR: "henüz sürüyor",
    DURUM_OLCULEMEDI: "ölçülemedi (seri yok)",
}


# === YARDIMCILAR ==========================================================

def istanbul(ts) -> pd.Timestamp:
    """Damgayı Europe/Istanbul pd.Timestamp'e normalize eder."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        return ISTANBUL_TZ.localize(ts.to_pydatetime())
    return ts.tz_convert(ISTANBUL_TZ)


def hafta_damgasi(an: datetime) -> str:
    """ISO hafta anahtarı: '2026-W40' (gönderim tekilliği için)."""
    yil, hafta, _ = an.isocalendar()
    return f"{yil}-W{hafta:02d}"


def karne_gunu_mu(an: datetime) -> bool:
    """Bugün karne günü mü? (varsayılan: Cuma; KARNE_GUNU env ile değişir)."""
    return an.weekday() == max(0, min(6, int(KARNE_GUNU)))


def atr_hesapla(df: Optional[pd.DataFrame], periyot: int = 14) -> Optional[float]:
    """Serinin SON `periyot` barı üzerinden ortalama gerçek aralık (ATR).

    Kayıt anında hesaplanır ve saklanır: karne ileride, seri değişse bile aynı
    ATR eşikleriyle değerlendirsin (yeniden üretilebilirlik).
    """
    if df is None or len(df) < 2:
        return None
    try:
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        onceki = close.shift(1)
        tr = pd.concat([(high - low), (high - onceki).abs(), (low - onceki).abs()], axis=1).max(axis=1)
        tr = tr.dropna()
        if len(tr) == 0:
            return None
        return float(tr.tail(max(2, periyot)).mean())
    except Exception as exc:  # noqa: BLE001 - telemetri botu durdurmasın
        logger.debug("ATR hesaplanamadı: %s", exc)
        return None


def _dizine_konum(df: pd.DataFrame, bar_zamani) -> Optional[int]:
    """Bar damgasının serideki konumu (tam eşleşme; yoksa <= en yakın)."""
    if df is None or len(df) == 0:
        return None
    try:
        hedef = istanbul(bar_zamani)
        idx = df.index
        if not isinstance(idx, pd.DatetimeIndex):
            idx = pd.DatetimeIndex(pd.to_datetime(idx, utc=True))
        if idx.tz is None:
            idx = idx.tz_localize(ISTANBUL_TZ)
        else:
            idx = idx.tz_convert(ISTANBUL_TZ)
        if hedef < idx[0]:
            return None
        konum = int(idx.searchsorted(hedef, side="right")) - 1
        return konum if 0 <= konum < len(idx) else None
    except Exception:  # noqa: BLE001
        return None


# === SİNYAL DEFTERİ =======================================================

class KarneDefteri:
    """Yerel JSON sinyal defteri (Supabase'siz).

    Veri yapısı:
        {"surum": 1,
         "kayitlar": {"<id>": {...}, ...},
         "formasyon_zamanlari": {"THYAO|1h|Üçgen": "<iso>", ...},
         "son_karne_gonderim": "2026-W40"}
    """

    def __init__(self, data_dir: str = None, dosya: str = None):
        self.data_dir = data_dir or DATA_DIR
        self.dosya = dosya or os.path.join(self.data_dir, KARNE_DOSYA)
        self._kayitlar: Dict[str, dict] = {}
        self._formasyon_zamanlari: Dict[str, str] = {}
        self.son_karne_gonderim: Optional[str] = None
        self.yukle()

    # --- kalıcılık (yalnız yerel dosya) ---
    def yukle(self) -> int:
        try:
            if not os.path.exists(self.dosya):
                return 0
            with open(self.dosya, "r", encoding="utf-8") as f:
                ham = json.load(f)
            if isinstance(ham, dict):
                kayitlar = ham.get("kayitlar")
                if isinstance(kayitlar, dict):
                    self._kayitlar = {k: v for k, v in kayitlar.items() if isinstance(v, dict)}
                zamanlar = ham.get("formasyon_zamanlari")
                if isinstance(zamanlar, dict):
                    self._formasyon_zamanlari = {str(k): str(v) for k, v in zamanlar.items()}
                skg = ham.get("son_karne_gonderim")
                self.son_karne_gonderim = skg if isinstance(skg, str) else None
            logger.info("Karne defteri yüklendi: %d kayıt (%s)", len(self._kayitlar), self.dosya)
            return len(self._kayitlar)
        except Exception as exc:  # noqa: BLE001 - bozuk dosya botu durdurmasın
            logger.warning("Karne defteri okunamadı (%s) - boş defterle devam: %s", self.dosya, exc)
            return 0

    def kaydet(self) -> bool:
        """Atomik yazım. Supabase'e YAZMAZ (bilinçli: kullanıcı isteği)."""
        try:
            os.makedirs(os.path.dirname(self.dosya) or ".", exist_ok=True)
            gecici = self.dosya + ".tmp"
            with open(gecici, "w", encoding="utf-8") as f:
                json.dump({
                    "surum": KARNE_SURUM,
                    "kayitlar": self._kayitlar,
                    "formasyon_zamanlari": self._formasyon_zamanlari,
                    "son_karne_gonderim": self.son_karne_gonderim,
                }, f, ensure_ascii=False, default=str)
            os.replace(gecici, self.dosya)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Karne defteri yazılamadı: %s", exc)
            return False

    # --- kayıt ---
    def _ekle(self, kimlik: str, kayit: dict) -> bool:
        if not kimlik or kimlik in self._kayitlar:
            return False
        self._kayitlar[kimlik] = kayit
        return True

    def formasyon_kaydet(self, stock: str, tf: str, pattern: str, state: str,
                         quality: float, bar_zamani, now: datetime = None) -> bool:
        """Canlı formasyonu sayar. Aynı hisse/TF/formasyon TTL içinde tekrar sayılmaz."""
        now = now or datetime.now(ISTANBUL_TZ)
        anahtar = f"{stock}|{tf}|{pattern}"
        onceki = self._formasyon_zamanlari.get(anahtar)
        if onceki:
            try:
                gecmis = datetime.fromisoformat(onceki)
                if gecmis.tzinfo is None:
                    gecmis = ISTANBUL_TZ.localize(gecmis)
                if (now - gecmis) < timedelta(hours=max(1, KARNE_FORMASYON_TTL_SAAT)):
                    return False
            except (TypeError, ValueError):
                pass
        self._formasyon_zamanlari[anahtar] = now.isoformat()
        eklendi = self._ekle(f"{stock}|{tf}|F|{istanbul(now).isoformat()}", {
            "tip": "formasyon",
            "stock": stock,
            "tf": tf,
            "pattern": pattern,
            "state": state,
            "quality": _sayi(quality),
            "bar_time": str(bar_zamani),
            "kayit_zaman": now.isoformat(),
            "hafta": hafta_damgasi(now),
        })
        if eklendi:
            self.kaydet()
        return eklendi

    def kirilim_kaydet(self, stock: str, tf: str, pattern: str, state: str, dir: int,
                       entry: Optional[float], atr: Optional[float], quality: float,
                       bar_zamani, mtf_destek: bool = False, now: datetime = None) -> bool:
        """Kırılım teyidini (performans ölçülecek sinyal) kaydeder."""
        if dir not in (1, -1) or entry in (None, 0):
            return False
        now = now or datetime.now(ISTANBUL_TZ)
        bar_iso = istanbul(bar_zamani).isoformat()
        eklendi = self._ekle(f"{stock}|{tf}|K|{bar_iso}", {
            "tip": "kirilim",
            "stock": stock,
            "tf": tf,
            "pattern": pattern,
            "state": state,
            "dir": int(dir),
            "entry": float(entry),
            "atr": _sayi(atr),
            "quality": _sayi(quality),
            "mtf_destek": bool(mtf_destek),
            "bar_time": bar_iso,
            "kayit_zaman": now.isoformat(),
            "hafta": hafta_damgasi(now),
        })
        if eklendi:
            self.kaydet()
        return eklendi

    def olay_kaydet(self, stock: str, tf: str, state: str, bar_zamani,
                    now: datetime = None) -> bool:
        """Huni olayı: retest / tamamlandı / başarısız (performans ölçülmez)."""
        now = now or datetime.now(ISTANBUL_TZ)
        bar_iso = istanbul(bar_zamani).isoformat()
        eklendi = self._ekle(f"{stock}|{tf}|O|{state}|{bar_iso}", {
            "tip": "olay",
            "stock": stock,
            "tf": tf,
            "state": state,
            "bar_time": bar_iso,
            "kayit_zaman": now.isoformat(),
            "hafta": hafta_damgasi(now),
        })
        if eklendi:
            self.kaydet()
        return eklendi

    # --- bakım ---
    def buda(self, now: datetime = None, saklama_gun: int = None) -> int:
        """Eski kayıtları atar (dosya sınırsız büyümesin). Silinen sayısını döner."""
        now = now or datetime.now(ISTANBUL_TZ)
        sinir = now - timedelta(days=max(7, int(saklama_gun or KARNE_SAKLAMA_GUN)))
        silinen = []
        for kimlik, kayit in self._kayitlar.items():
            try:
                zaman = datetime.fromisoformat(str(kayit.get("kayit_zaman") or ""))
                if zaman.tzinfo is None:
                    zaman = ISTANBUL_TZ.localize(zaman)
                if zaman < sinir:
                    silinen.append(kimlik)
            except (TypeError, ValueError):
                continue  # tarihi okunamayan kaydı silme (veri kaybına yol açma)
        for kimlik in silinen:
            del self._kayitlar[kimlik]
        if silinen:
            self.kaydet()
            logger.info("Karne defteri budandı: %d kayıt (%d günden eski)", len(silinen), saklama_gun or KARNE_SAKLAMA_GUN)
        return len(silinen)

    # --- haftalık gönderim işareti ---
    def karne_gonderildi_mi(self, hafta: str) -> bool:
        return self.son_karne_gonderim == hafta

    def karne_gonderildi_isaretle(self, hafta: str) -> None:
        self.son_karne_gonderim = hafta
        self.kaydet()

    # --- sorgular ---
    def kayitlar(self) -> List[dict]:
        return [dict(v) for v in self._kayitlar.values()]

    def aralikta(self, baslangic: datetime, bitis: datetime = None) -> List[dict]:
        """kayit_zaman'ı aralıkta olan kayıtlar (kayıt anı bazlı pencere)."""
        bitis = bitis or datetime.now(ISTANBUL_TZ)
        sonuc = []
        for kayit in self._kayitlar.values():
            try:
                zaman = datetime.fromisoformat(str(kayit.get("kayit_zaman") or ""))
                if zaman.tzinfo is None:
                    zaman = ISTANBUL_TZ.localize(zaman)
            except (TypeError, ValueError):
                continue
            if baslangic <= zaman <= bitis:
                sonuc.append(dict(kayit))
        return sonuc

    def boyut(self) -> int:
        return len(self._kayitlar)


def _sayi(deger) -> Optional[float]:
    try:
        return round(float(deger), 4)
    except (TypeError, ValueError):
        return None


# === PERFORMANS ÖLÇÜMÜ ====================================================

def sinyal_sonucu(kayit: dict, df: Optional[pd.DataFrame], now: datetime = None,
                  hedef_atr: float = None, stop_atr: float = None,
                  horizon: int = None) -> Optional[dict]:
    """Kırılım kaydının ileri performansı (bar bar MFE/MAE + ilk dokunuş yarışı).

    df: sinyalin timeframe'indeki seri (kapanmış barlar). None/eksikse None döner.
    """
    if df is None or len(df) == 0 or kayit.get("tip") != "kirilim":
        return None
    konum = _dizine_konum(df, kayit.get("bar_time"))
    if konum is None:
        return None
    entry = float(kayit.get("entry") or 0)
    if entry <= 0:
        return None
    atr = kayit.get("atr")
    atr = float(atr) if atr else None
    yon = int(kayit.get("dir") or 0)
    if yon not in (1, -1):
        return None
    if atr is None or atr <= 0:
        # ATR yoksa yüzde bazlı eşikler (ATR'yi %1 kabul et): kayıt yine değerli.
        atr = entry * 0.01
    hedef_atr = KARNE_HEDEF_ATR if hedef_atr is None else hedef_atr
    stop_atr = KARNE_STOP_ATR if stop_atr is None else stop_atr
    horizon = KARNE_HORIZON_BAR if horizon is None else horizon

    ileri = df.iloc[konum + 1: konum + 1 + max(1, int(horizon))]
    if len(ileri) == 0:
        return {"durum": DURUM_BEKLIYOR, "mfe_pct": None, "mae_pct": None,
                "mfe_atr": None, "mae_atr": None, "son_pct": None, "bar_sayisi": 0,
                "hedef_bar": None, "stop_bar": None}

    mfe = mae = 0.0
    hedef_bar = stop_bar = None
    son_kapanis = entry
    for i, (_, bar) in enumerate(ileri.iterrows(), start=1):
        high = float(bar["high"])
        low = float(bar["low"])
        if yon == 1:
            lehte = (high - entry) / entry
            alehte = (entry - low) / entry
        else:
            lehte = (entry - low) / entry
            alehte = (high - entry) / entry
        lehte = max(lehte, 0.0)
        alehte = max(alehte, 0.0)
        mfe, mae = max(mfe, lehte), max(mae, alehte)
        # İlk dokunuş yarışı (aynı barda ikisi de varsa muhafazakâr: stop)
        if stop_bar is None and alehte >= stop_atr * atr / entry:
            stop_bar = i
        if hedef_bar is None and lehte >= hedef_atr * atr / entry:
            hedef_bar = i
        son_kapanis = float(bar["close"])

    if hedef_bar is not None and (stop_bar is None or hedef_bar < stop_bar):
        durum = DURUM_HEDEF
    elif stop_bar is not None:
        durum = DURUM_STOP
    else:
        durum = DURUM_NOTR
    son_pct = (son_kapanis - entry) / entry * yon
    return {
        "durum": durum,
        "mfe_pct": round(mfe * 100, 2),
        "mae_pct": round(mae * 100, 2),
        "mfe_atr": round(mfe * entry / atr, 2),
        "mae_atr": round(mae * entry / atr, 2),
        "son_pct": round(son_pct * 100, 2),
        "bar_sayisi": int(len(ileri)),
        "hedef_bar": hedef_bar,
        "stop_bar": stop_bar,
    }


# === RAPOR ================================================================

def karne_hesapla(kayitlar: List[dict], saglayici: Callable[[str, str], Optional[pd.DataFrame]],
                  now: datetime = None) -> dict:
    """Kayıt listesinden karne metriklerini üretir (saf hesap; dosya/ağ yok).

    saglayici(stock, tf) -> seri (kapanmış barlar) veya None.
    """
    now = now or datetime.now(ISTANBUL_TZ)
    formasyonlar = [k for k in kayitlar if k.get("tip") == "formasyon"]
    kirilimlar = [k for k in kayitlar if k.get("tip") == "kirilim"]
    olaylar = [k for k in kayitlar if k.get("tip") == "olay"]

    tf_sayilari: Dict[str, int] = {}
    hisse_sayilari: Dict[str, int] = {}
    for k in formasyonlar:
        tf_sayilari[k["tf"]] = tf_sayilari.get(k["tf"], 0) + 1
        hisse_sayilari[k["stock"]] = hisse_sayilari.get(k["stock"], 0) + 1

    sonuclar = []
    olculemedi = 0
    for k in kirilimlar:
        seri = None
        try:
            seri = saglayici(k["stock"], k["tf"])
        except Exception as exc:  # noqa: BLE001 - sağlayıcı hatası karneyi düşürmesin
            logger.debug("Karne seri sağlayıcı hatası (%s %s): %s", k.get("stock"), k.get("tf"), exc)
        sonuc = sinyal_sonucu(k, seri, now=now)
        if sonuc is None:
            olculemedi += 1
            continue
        sonuclar.append((k, sonuc))

    def _say(kosul) -> int:
        return sum(1 for _, s in sonuclar if kosul(s))

    yon_yukari = sum(1 for k in kirilimlar if int(k.get("dir") or 0) == 1)
    hedef = _say(lambda s: s["durum"] == DURUM_HEDEF)
    stop = _say(lambda s: s["durum"] == DURUM_STOP)
    notr = _say(lambda s: s["durum"] == DURUM_NOTR)
    bekleyen = _say(lambda s: s["durum"] == DURUM_BEKLIYOR)
    degerlendirilen = hedef + stop + notr
    pozitif = _say(lambda s: (s["son_pct"] or 0) > 0.05)
    negatif = _say(lambda s: (s["son_pct"] or 0) < -0.05)
    yatay = max(0, degerlendirilen - pozitif - negatif)

    def _ort(alan):
        degerler = [s[alan] for _, s in sonuclar if s.get(alan) is not None]
        return round(sum(degerler) / len(degerler), 2) if degerler else None

    # TF ve kalite kırılımı (pozitif/n)
    tf_performans: Dict[str, Dict[str, int]] = {}
    kalite_performans: Dict[str, Dict[str, int]] = {}
    for k, s in sonuclar:
        if s["durum"] == DURUM_BEKLIYOR:
            continue
        poz = 1 if (s["son_pct"] or 0) > 0.05 else 0
        tf_performans.setdefault(k["tf"], {"poz": 0, "n": 0})
        tf_performans[k["tf"]]["n"] += 1
        tf_performans[k["tf"]]["poz"] += poz
        q = k.get("quality")
        if q is None:
            continue
        etiket = "q≥80" if q >= 80 else ("q70–79" if q >= 70 else "q<70")
        kalite_performans.setdefault(etiket, {"poz": 0, "n": 0})
        kalite_performans[etiket]["n"] += 1
        kalite_performans[etiket]["poz"] += poz

    # Öne çıkanlar: ufuk sonu getiriye göre sıralı
    siralama = [(k, s) for k, s in sonuclar if s.get("son_pct") is not None]
    siralama.sort(key=lambda ks: ks[1]["son_pct"], reverse=True)
    en_iyi = [x for x in siralama if (x[1].get("son_pct") or 0) > 0.05][:3]
    en_kotu = [x for x in siralama[::-1] if (x[1].get("son_pct") or 0) < -0.05][:3]

    huni: Dict[str, int] = {}
    for o in olaylar:
        huni[o["state"]] = huni.get(o["state"], 0) + 1

    return {
        "formasyon_toplam": len(formasyonlar),
        "tf_sayilari": tf_sayilari,
        "hisse_sayilari": hisse_sayilari,
        "hisse_cesidi": len(hisse_sayilari),
        "kirilim_toplam": len(kirilimlar),
        "yon_yukari": yon_yukari,
        "yon_asagi": len(kirilimlar) - yon_yukari,
        "hedef": hedef,
        "stop": stop,
        "notr": notr,
        "bekleyen": bekleyen,
        "degerlendirilen": degerlendirilen,
        "olculemedi": olculemedi,
        "pozitif": pozitif,
        "negatif": negatif,
        "yatay": yatay,
        "ort_mfe_pct": _ort("mfe_pct"),
        "ort_mae_pct": _ort("mae_pct"),
        "ort_mfe_atr": _ort("mfe_atr"),
        "ort_son_pct": _ort("son_pct"),
        "tf_performans": tf_performans,
        "kalite_performans": kalite_performans,
        "en_iyi": en_iyi,
        "en_kotu": en_kotu,
        "huni": huni,
        "kayit_sayisi": len(kayitlar),
    }


def _sar(tokens: List[str], genislik: int = 64) -> List[str]:
    """Token listesini satır genişliğine göre paketler (Telegram'da okunur kalsın)."""
    satirlar, mevcut = [], ""
    for tok in tokens:
        aday = f"{mevcut} · {tok}" if mevcut else tok
        if len(aday) > genislik and mevcut:
            satirlar.append(mevcut)
            mevcut = tok
        else:
            mevcut = aday
    if mevcut:
        satirlar.append(mevcut)
    return satirlar


def karne_metni(metrik: dict, baslik: str = "HAFTALIK DOĞRULUK KARNESİ",
                pencere_metni: str = "", gun_sayisi: int = 5) -> str:
    """Metrikleri Telegram mesajına çevirir (gün sonu mesajının altına eklenir)."""
    satirlar = [f"📊 {baslik}" + (f" · {pencere_metni}" if pencere_metni else ""),
                f"{gun_sayisi} seans · defter: {metrik['kayit_sayisi']} kayıt (yerel dosya)"]

    # --- formasyon ---
    satirlar.append("")
    satirlar.append(f"🔍 Formasyon tespiti: {metrik['formasyon_toplam']}")
    if metrik["formasyon_toplam"]:
        tf_metin = " · ".join(f"{_tf_tr(tf)} {adet}" for tf, adet in
                              sorted(metrik["tf_sayilari"].items(), key=lambda x: -x[1]))
        satirlar.append(" " + tf_metin)
        hisse_tokenlari = [f"{h} {n}" for h, n in
                           sorted(metrik["hisse_sayilari"].items(), key=lambda x: (-x[1], x[0]))]
        satirlar.append(" Hisse: " + f"({metrik['hisse_cesidi']} hisse)")
        satirlar.extend(" " + s for s in _sar(hisse_tokenlari))

    # --- kırılım performansı ---
    satirlar.append("")
    if metrik["kirilim_toplam"] == 0:
        satirlar.append("⚡ Kırılım sinyali: 0 (bu pencerede teyitli kırılım yok)")
    else:
        satirlar.append(f"⚡ Kırılım sinyali: {metrik['kirilim_toplam']} "
                        f"(yukarı {metrik['yon_yukari']} · aşağı {metrik['yon_asagi']})")
        if metrik["degerlendirilen"]:
            satirlar.append(f" {KARNE_HORIZON_BAR} bar içinde: hedef {metrik['hedef']} · "
                            f"nötr {metrik['notr']} · stop {metrik['stop']}")
            oran = metrik['pozitif'] * 100.0 / metrik["degerlendirilen"]
            satirlar.append(f" Kırılım yönünde kapatan: {metrik['pozitif']}/"
                            f"{metrik['degerlendirilen']} (%{oran:.0f}) · "
                            f"ters {metrik['negatif']} · yatay {metrik['yatay']}")
            if metrik["ort_mfe_pct"] is not None:
                satirlar.append(f" Ort. maks. lehte +%{metrik['ort_mfe_pct']:.1f} · "
                                f"alehte −%{metrik['ort_mae_pct']:.1f}")
        if metrik["bekleyen"]:
            satirlar.append(f" ⏳ {metrik['bekleyen']} sinyal henüz {KARNE_HORIZON_BAR} barı doldurmadı")
        if metrik["olculemedi"]:
            satirlar.append(f" ℹ️ {metrik['olculemedi']} sinyal ölçülemedi (seri cache'te yok)")
        if metrik["tf_performans"]:
            parcalar = [f"{_tf_tr(tf)} {v['poz']}/{v['n']}" for tf, v in
                        sorted(metrik["tf_performans"].items())]
            satirlar.append(" TF (yönünde/n): " + " · ".join(parcalar))
        if metrik["kalite_performans"]:
            sirali_kalite = sorted(metrik["kalite_performans"].items(),
                                   key=lambda kv: _KALITE_SIRA.get(kv[0], 9))
            parcalar = [f"{etiket} {v['poz']}/{v['n']}" for etiket, v in sirali_kalite]
            satirlar.append(" Kalite: " + " · ".join(parcalar))
        for etiket, grup in (("En iyi", metrik["en_iyi"]), ("En kötü", metrik["en_kotu"])):
            if grup:
                parcalar = [f"{k['stock']} {k['tf']} {'%+' if s['son_pct'] >= 0 else '%-'}"
                            f"{abs(s['son_pct']):.1f}" for k, s in grup]
                satirlar.append(f" {etiket}: " + " · ".join(parcalar))

    # --- huni ---
    if metrik["huni"]:
        parcalar = [f"{_state_tr(s)} {n}" for s, n in
                    sorted(metrik["huni"].items(), key=lambda x: -x[1])]
        satirlar.append("")
        satirlar.append(f"🔁 Huni: kırılım {metrik['kirilim_toplam']} → " + " · ".join(parcalar))

    # --- uyarı ---
    if metrik["degerlendirilen"] and metrik["degerlendirilen"] < 30:
        satirlar.append("")
        satirlar.append(f"⚠️ n={metrik['degerlendirilen']} küçük: oranlar için 30+ sinyal birikmeli")
    satirlar.append("ℹ️ Veriler yerel dosyada (Supabase gerekmez) · /karne ile istediğin an al")
    return "\n".join(satirlar)


_KALITE_SIRA = {"q≥80": 0, "q70–79": 1, "q<70": 2}
_TF_TR = {"1h": "1 saatlik", "2h": "2 saatlik", "4h": "4 saatlik", "1d": "günlük"}
_STATE_TR = {
    "KIRILIM_TEYITLI": "teyitli kırılım",
    "RETEST_BASARILI": "retest başarılı",
    "FORMASYON_TAMAMLANDI": "tamamlanan",
    "BASARISIZ_KIRILIM": "başarısız kırılım",
}


def _tf_tr(tf: str) -> str:
    return _TF_TR.get(str(tf).lower(), str(tf))


def _state_tr(state: str) -> str:
    return _STATE_TR.get(str(state), str(state))


def pencere(baslangic: datetime, bitis: datetime) -> str:
    """'29.09–03.10.2026' biçiminde pencere etiketi."""
    if baslangic.year == bitis.year:
        return f"{baslangic.strftime('%d.%m')}–{bitis.strftime('%d.%m.%Y')}"
    return f"{baslangic.strftime('%d.%m.%y')}–{bitis.strftime('%d.%m.%y')}"


def hafta_baslangici(an: datetime) -> datetime:
    """İçinde bulunulan haftanın pazartesi 00:00'ı (İstanbul)."""
    gun_basi = an.replace(hour=0, minute=0, second=0, microsecond=0)
    return gun_basi - timedelta(days=gun_basi.weekday())


def karne_uret(defter: KarneDefteri, saglayici: Callable[[str, str], Optional[pd.DataFrame]],
               now: datetime = None, gun_sayisi: int = None, baslik: str = None) -> str:
    """Kayıtlardan rapor metni üretir.

    gun_sayisi=None -> içinde bulunulan hafta (pazartesi'den bugüne).
    gun_sayisi=N    -> son N gün.
    """
    now = now or datetime.now(ISTANBUL_TZ)
    if gun_sayisi is None:
        baslangic = hafta_baslangici(now)
        baslik = baslik or "HAFTALIK DOĞRULUK KARNESİ"
    else:
        baslangic = now - timedelta(days=max(1, int(gun_sayisi)))
        baslik = baslik or f"SON {int(gun_sayisi)} GÜN DOĞRULUK KARNESİ"
    kayitlar = defter.aralikta(baslangic, now)
    metrik = karne_hesapla(kayitlar, saglayici, now=now)
    seans = max(1, len(pd.bdate_range(baslangic.date(), now.date())))
    return karne_metni(metrik, baslik=baslik, pencere_metni=pencere(baslangic, now), gun_sayisi=seans)
