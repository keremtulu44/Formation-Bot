# -*- coding: utf-8 -*-
"""İleri test kaydı — iddiaları kanıta çeviren gölge defter.

NEDEN VAR
---------
2026-10-25 ölçümü şunu gösterdi: karta basılan "devamlılık" bilgisi tek bir
bayrağa indirgeniyordu (kama + üst zaman dilimi aynı yönde) ve bu **örneklem
dışında hiç sınanmadı**. Arşivdeki her sayı örneklem İÇİ ölçümdü; "taze" denen
50 sembollük koşu ise arşivin %100 alt kümesiydi. Yani elimizde iddia vardı,
kanıt yoktu (`docs/arastirma/PUANLAMA_MIMARISI_2026-10-25.md` §11).

Bu modül o boşluğu kapatır: **gönderilen her uyarıyı** kaydeder, 24 bar sonra
sonucunu arşivden hesaplar. Kimseye mesaj atmaz, hiçbir parametreyi değiştirmez,
hiçbir eşiği ayarlamaz. Yalnız kayıt tutar ve öneri metni üretir.

KARAR KURALI — ÖNCEDEN YAZILI (§11.4)
-------------------------------------
Kural, sonuç görülmeden buraya yazıldı; sonradan değiştirilirse test anlamını
yitirir:

  1. Her uyarıda `bayrak` (kama + üst TF aynı yönde) ve `puan` kaydedilir.
  2. Sonuç, uyarının kendi zaman diliminde 24 bar sonra okunur.
  3. Ölçü: yön lehine yüzde getiri (kırılım fiyatından, 24. bar kapanışına).
  4. Taban: **aynı defterdeki bayraksız uyarılar** (aynı dönem, aynı evren,
     aynı TF karışımı). Ayrı bir "rastgele giriş" simülasyonu kurulmaz; canlı
     karşılaştırma kendi kontrolünü taşır.
  5. 8–12 hafta sonra: bayraklı grubun ortalaması bayraksız gruptan
     **≥ +3 yüzde puanı** fazlaysa bayrak kalır; değilse kaldırılır.
  6. İki gruptan biri `MIN_GOZLEM`in altındaysa **hüküm yok** — "az veriyle
     karar verme" hatasına düşülmez.

Bu modül kararı **uygulamaz**: `ozet()` yalnız "kalıyor / kaldırılmalı / yetersiz"
der. Kart değişikliği yine kullanıcı onayıyla yapılır.

SINIRLAR
--------
* Bar verisi çağırandan gelir (ağ çağrısı `gece()` içinde, tek yerde).
* Kayıt tutmak botu durdurmaz: tüm I/O hataları yutulur ve loga yazılır.
* Defter tepeden sınırlıdır (`AZAMI_KAYIT`); en eski sonuçlu kayıtlar düşer.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

# --- sözleşme sabitleri ------------------------------------------------------
BAR_SAYISI = 24            # sonuç kaç bar sonra okunur
ESIK_FAZLA_PUAN = 3.0      # yüzde puanı: bayraklı grup en az bu kadar fazla vermeli
MIN_GOZLEM = 100           # grup başına en az gözlem (altında hüküm yok)
AZAMI_KAYIT = 5000         # defter tavanı
AZAMI_GECE_IS = 40         # bir gecede en fazla kaç kaydın sonucu hesaplanır

DOSYA = "ileri_test.json"
SUPABASE_KEY = "state:ileri_test"

#: Zaman dilimi → bar kaç saat? (olgunluk hesabı için)
_TF_SAAT = {"1h": 1, "2h": 2, "4h": 4, "1d": 24}

_KILIT = threading.Lock()
_DEFTER: Optional[Dict[str, Any]] = None


# --- saf hesap ---------------------------------------------------------------

def bayrak(data: Dict) -> bool:
    """Test edilen iddia: kama ailesi + üst zaman dilimi aynı yönde.

    Tek bayrak olması bilinçli: puan/bant/mesafe kombinasyonları ölçümde bu
    bayrağın üstüne hiçbir şey eklemedi (§11). Test edilecek tek şey bu.
    """
    try:
        import devamlilik as dev
        aile = dev.aile_coz(data.get("pattern_name"))
    except Exception:  # noqa: BLE001 - hesap modülü yoksa bayrak kapalı
        return False
    try:
        uyum = int(float(data.get("mtf_uyum") or 0))
    except (TypeError, ValueError):
        uyum = 0
    return aile == "Kama" and uyum > 0


def _fiyat(deger) -> Optional[float]:
    try:
        f = float(deger)
    except (TypeError, ValueError):
        return None
    return f if f == f and f > 0 else None


def _bar_zamani(data: Dict) -> Optional[str]:
    """Uyarının dayandığı KAPANMIŞ barın zamanı (ISO). Yoksa kayıt yok.

    Bar zamanı uydurulmaz: 24 barlık pencere yanlış yerden başlarsa sonuç
    ölçüm değil gürültü olur.
    """
    for alan in ("bar_kapanis", "bar_time", "timestamp"):
        ham = data.get(alan)
        if isinstance(ham, datetime):
            return ham.isoformat()
        metin = str(ham or "").strip()
        if metin:
            return metin
    return None


def kayit_olustur(data: Dict, *, simdi: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """Uyarı verisinden defter kaydı. Zorunlu alan eksikse `None` (kayıt yok).

    Zorunlu: sembol, zaman dilimi, yön (±1), kırılım fiyatı, bar zamanı.
    """
    sembol = str(data.get("stock_name") or "").strip().upper()
    tf = str(data.get("timeframe") or "").strip().lower()
    try:
        yon = int(data.get("break_dir") or 0)
    except (TypeError, ValueError):
        yon = 0
    giris = _fiyat(data.get("break_price")) or _fiyat(data.get("critical_price_level"))
    bar = _bar_zamani(data)
    if not sembol or not tf or yon not in (1, -1) or giris is None or not bar:
        return None

    puan = None
    aile = None
    try:
        import devamlilik as dev
        aile = dev.aile_coz(data.get("pattern_name"))
        puan = dev.devamlilik_puani(data.get("pattern_name"), data.get("mtf_uyum"),
                                    data.get("bant_mesafe_atr"))
    except Exception:  # noqa: BLE001 - puan yoksa kayıt yine tutulur
        pass

    return {
        "anahtar": f"{sembol}|{tf}|{bar}",
        "sembol": sembol,
        "tf": tf,
        "desen": str(data.get("pattern_name") or ""),
        "aile": aile,
        "yon": yon,
        "giris": giris,
        "bar": bar,
        "durum": str(data.get("state") or ""),
        "puan": puan,                       # yalnız log: kartta gösterilmiyor
        "bayrak": bayrak(data),
        "mtf_uyum": data.get("mtf_uyum"),
        "mtf_destek": bool(data.get("mtf_destek")),
        "olusturma": (simdi or datetime.now()).isoformat(timespec="seconds"),
        "sonuc": None,
    }


def olgun_mu(kayit: Dict, *, simdi: Optional[datetime] = None,
             bar_sayisi: int = BAR_SAYISI) -> bool:
    """24 barlık pencere doldu mu (kaba zaman kontrolü, ağ çağrısından önce)."""
    saat = _TF_SAAT.get(str(kayit.get("tf") or "").lower())
    if saat is None:
        return True                    # bilinmeyen TF: veri katmanı karar verir
    try:
        bar = datetime.fromisoformat(str(kayit.get("bar")))
    except (TypeError, ValueError):
        return False
    if bar.tzinfo is None:
        bar = bar.replace(tzinfo=(simdi or datetime.now()).tzinfo)
    bitis = bar + timedelta(hours=saat * bar_sayisi)
    return (simdi or datetime.now()) >= bitis


def sonuc_hesapla(kayit: Dict, df: Any, *, bar_sayisi: int = BAR_SAYISI) -> Optional[Dict[str, Any]]:
    """Barın 24 bar sonrasındaki sonucu. Pencere dolmadıysa `None`.

    Ölçü: yön lehine yüzde getiri (girişten 24. bar kapanışına). `en_iyi` ve
    `en_kotu` aynı yönde en iyi/en kötü gezinme — karar ölçüsü değil, teşhis.
    """
    if df is None or len(df) == 0:
        return None
    try:
        bar = datetime.fromisoformat(str(kayit.get("bar")))
        giris = float(kayit.get("giris"))
        yon = int(kayit.get("yon"))
    except (TypeError, ValueError):
        return None
    if giris <= 0 or yon not in (1, -1):
        return None

    try:
        index = df.index
        if getattr(index, "tz", None) is not None and bar.tzinfo is None:
            bar = bar.tz_localize(index.tz)
        elif getattr(index, "tz", None) is None and bar.tzinfo is not None:
            bar = bar.tz_convert(None)
        sonraki = df[index > bar]
    except Exception:  # noqa: BLE001 - bozuk indeks ölçümü engeller
        return None
    if len(sonraki) < bar_sayisi:
        return None

    pencere = sonraki.iloc[:bar_sayisi]
    try:
        son_kapanis = float(pencere["close"].iloc[-1])
        en_yuksek = float(pencere["high"].max())
        en_dusuk = float(pencere["low"].min())
    except Exception:  # noqa: BLE001
        return None

    yuzde = (son_kapanis - giris) / giris * 100.0 * yon
    if yon > 0:
        en_iyi = (en_yuksek - giris) / giris * 100.0
        en_kotu = (giris - en_dusuk) / giris * 100.0
    else:
        en_iyi = (giris - en_dusuk) / giris * 100.0
        en_kotu = (en_yuksek - giris) / giris * 100.0
    return {
        "kapanis": round(son_kapanis, 4),
        "yuzde": round(yuzde, 3),
        "en_iyi": round(en_iyi, 3),
        "en_kotu": round(en_kotu, 3),
        "devam": bool(yuzde > 0),
        "bar": int(len(pencere)),
    }


# --- defter (kalıcılık) ------------------------------------------------------

def _defter_bos() -> Dict[str, Any]:
    return {"kayitlar": [], "son_gece": "", "kayit_zamani": ""}


def _birlestir(mevcut: Iterable[Dict], yeni: Iterable[Dict]) -> List[Dict]:
    """Anahtar bazında birleştirir; dolu sonuç boş sonucu EZMEZ."""
    sonuc: Dict[str, Dict] = {}
    for kaynak in (mevcut or [], yeni or []):
        for kayit in kaynak:
            if not isinstance(kayit, dict):
                continue
            anahtar = str(kayit.get("anahtar") or "")
            if not anahtar:
                continue
            eski = sonuc.get(anahtar)
            if eski is None:
                sonuc[anahtar] = kayit
                continue
            # Sonucu olan kopya kazanır; yeni alanlar yine de eklenir.
            birlesik = dict(eski)
            birlesik.update({k: v for k, v in kayit.items() if v is not None})
            if eski.get("sonuc"):
                birlesik["sonuc"] = eski["sonuc"]
            sonuc[anahtar] = birlesik
    return list(sonuc.values())


def _kirp(kayitlar: List[Dict]) -> List[Dict]:
    """Tavan aşılırsa önce SONUÇLU en eski kayıtlar düşer."""
    if len(kayitlar) <= AZAMI_KAYIT:
        return kayitlar
    sonuclu = sorted((k for k in kayitlar if k.get("sonuc")),
                     key=lambda k: str(k.get("olusturma") or ""))
    fazla = len(kayitlar) - AZAMI_KAYIT
    atilacak = {id(k) for k in sonuclu[:fazla]}
    return [k for k in kayitlar if id(k) not in atilacak]


def defter_yolu(data_dir: Optional[str] = None) -> str:
    if data_dir is None:
        from config import DATA_DIR
        data_dir = DATA_DIR
    return os.path.join(data_dir, DOSYA)


def defter_yukle(*, store=None, data_dir: Optional[str] = None) -> Dict[str, Any]:
    """Yerel dosya + Supabase birleşimi. Hata botu durdurmaz."""
    defter = _defter_bos()
    try:
        from state.paths import yeni_snapshot  # noqa: F401  (API uyumu)
    except Exception:  # noqa: BLE001
        pass
    try:
        with open(defter_yolu(data_dir), "r", encoding="utf-8") as dosya:
            yerel = json.load(dosya)
        if isinstance(yerel, dict):
            defter = yerel
    except (OSError, ValueError):
        pass
    if store is not None:
        try:
            uzak = store.get_many([SUPABASE_KEY]) or {}
            uzak_veri = uzak.get(SUPABASE_KEY)
            if isinstance(uzak_veri, dict):
                defter["kayitlar"] = _birlestir(defter.get("kayitlar") or [],
                                                uzak_veri.get("kayitlar") or [])
                if str(uzak_veri.get("son_gece") or "") > str(defter.get("son_gece") or ""):
                    defter["son_gece"] = uzak_veri.get("son_gece")
        except Exception as exc:  # noqa: BLE001 - yedek okunamazsa yerelle devam
            logger.debug("İleri test defteri uzak yedeği okunamadı: %s", exc)
    if not isinstance(defter.get("kayitlar"), list):
        defter["kayitlar"] = []
    return defter


def defter_kaydet(defter: Dict, *, store=None, data_dir: Optional[str] = None) -> bool:
    """İki yere bağımsız yazar; hiçbir I/O hatası çağıranı düşürmez."""
    defter["kayitlar"] = _kirp(list(defter.get("kayitlar") or []))
    defter["kayit_zamani"] = datetime.now().isoformat(timespec="seconds")
    yazildi = False
    try:
        yol = defter_yolu(data_dir)
        os.makedirs(os.path.dirname(yol) or ".", exist_ok=True)
        gecici = yol + ".tmp"
        with open(gecici, "w", encoding="utf-8") as dosya:
            json.dump(defter, dosya, ensure_ascii=False)
        os.replace(gecici, yol)
        yazildi = True
    except OSError as exc:
        logger.debug("İleri test defteri yazılamadı: %s", exc)
    if store is not None:
        try:
            store.upsert(SUPABASE_KEY, defter)
        except Exception as exc:  # noqa: BLE001
            logger.debug("İleri test defteri uzak yedeğe yazılamadı: %s", exc)
    return yazildi


def _defter_al(*, store=None, data_dir: Optional[str] = None) -> Dict[str, Any]:
    global _DEFTER
    if _DEFTER is None:
        _DEFTER = defter_yukle(store=store, data_dir=data_dir)
    return _DEFTER


def kaydet(data: Dict, *, store=None, data_dir: Optional[str] = None,
           simdi: Optional[datetime] = None) -> bool:
    """Gönderilen uyarıyı deftere ekler (aynı anahtar iki kez yazılmaz)."""
    kayit = kayit_olustur(data, simdi=simdi)
    if kayit is None:
        return False
    with _KILIT:
        defter = _defter_al(store=store, data_dir=data_dir)
        kayitlar = defter.get("kayitlar") or []
        if any(k.get("anahtar") == kayit["anahtar"] for k in kayitlar):
            return False
        kayitlar.append(kayit)
        defter["kayitlar"] = kayitlar
        yazildi = defter_kaydet(defter, store=store, data_dir=data_dir)
    tabloya_yaz([kayit], store)
    return yazildi


def sifirla() -> None:
    """Testler için bellek önbelleğini temizler (üretimde çağrılmaz)."""
    global _DEFTER
    with _KILIT:
        _DEFTER = None


# --- gece işi ----------------------------------------------------------------

def tablo_satiri(kayit: Dict) -> Dict[str, Any]:
    """Defter kaydı → `public.ileri_test` satırı (PostgREST gövdesi)."""
    def _tf_iso(deger):
        try:
            return datetime.fromisoformat(str(deger)).isoformat()
        except (TypeError, ValueError):
            return None

    return {
        "anahtar": kayit.get("anahtar"),
        "sembol": kayit.get("sembol"),
        "tf": kayit.get("tf"),
        "desen": kayit.get("desen"),
        "aile": kayit.get("aile"),
        "yon": kayit.get("yon"),
        "giris": kayit.get("giris"),
        "bar_time": _tf_iso(kayit.get("bar")),
        "durum": kayit.get("durum"),
        "puan": kayit.get("puan"),
        "bayrak": bool(kayit.get("bayrak")),
        "mtf_uyum": kayit.get("mtf_uyum"),
        "mtf_destek": kayit.get("mtf_destek"),
        "sonuc": kayit.get("sonuc"),
    }


def tabloya_yaz(kayitlar: Iterable[Dict], store) -> int:
    """Kayıtları `ileri_test` tablosuna yazar (upsert). Hata botu düşürmez.

    JSON defter birincil kayıt olarak kalır; tablo SQL ile sorgulanabilsin diye
    aynası tutulur. Tablo yoksa/izin yoksa sessizce atlanır.
    """
    if store is None:
        return 0
    satirlar = [tablo_satiri(k) for k in kayitlar if isinstance(k, dict)]
    satirlar = [s for s in satirlar if s.get("anahtar") and s.get("bar_time")]
    if not satirlar:
        return 0
    try:
        cevap = store.request_table(
            "ileri_test", "POST", json=satirlar,
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
    except Exception as exc:  # noqa: BLE001 - ayna yazımı ölçümü engellememeli
        logger.debug("İleri test tablosuna yazılamadı: %s", exc)
        return 0
    return len(satirlar) if cevap is not None else 0


def _varsayilan_getir(sembol: str, tf: str):
    """Sembolün bar verisi: 1d ise günlük, değilse 1h → resample."""
    import data as _data

    if tf == "1d":
        return _data.fetch_yfinance_1d(sembol, period="6mo")
    ham = _data.fetch_yfinance_1h(sembol, period="1mo", with_status=False)
    if ham is None or len(ham) == 0:
        return None
    setler = _data.resample_all_timeframes(ham)
    return setler.get(tf, ham)


def gece(*, store=None, data_dir: Optional[str] = None,
         simdi: Optional[datetime] = None,
         getir: Optional[Callable[[str, str], Any]] = None,
         azami: int = AZAMI_GECE_IS,
         rapor_yolu: Optional[str] = None) -> Dict[str, Any]:
    """Olgunlaşan kayıtların sonucunu hesaplar. Mesaj GÖNDERMEZ, eşik DEĞİŞTİRMEZ.

    `getir(sembol, tf)` enjekte edilebilir: testler ağa çıkmaz.
    """
    simdi = simdi or datetime.now()
    getir = getir or _varsayilan_getir
    with _KILIT:
        defter = _defter_al(store=store, data_dir=data_dir)
        kayitlar = defter.get("kayitlar") or []
        bekleyen = [k for k in kayitlar
                    if not k.get("sonuc") and olgun_mu(k, simdi=simdi)]
        # En eski önce: gecikmiş kayıtlar birikmesin.
        bekleyen.sort(key=lambda k: str(k.get("bar") or ""))
        isler = bekleyen[:max(0, int(azami))]

        onbellek: Dict[tuple, Any] = {}
        hesaplanan = 0
        hata = 0
        for kayit in isler:
            anahtar = (kayit["sembol"], kayit["tf"])
            if anahtar not in onbellek:
                try:
                    onbellek[anahtar] = getir(kayit["sembol"], kayit["tf"])
                except Exception as exc:  # noqa: BLE001 - tek sembol işi düşürmez
                    logger.debug("İleri test verisi alınamadı (%s): %s", anahtar, exc)
                    onbellek[anahtar] = None
            df = onbellek[anahtar]
            sonuc = sonuc_hesapla(kayit, df)
            if sonuc is None:
                hata += 1
                continue
            kayit["sonuc"] = sonuc
            hesaplanan += 1

        defter["son_gece"] = simdi.date().isoformat()
        metin = ozet(kayitlar)
        defter_kaydet(defter, store=store, data_dir=data_dir)
        tabloya_yaz([k for k in isler if k.get("sonuc")], store)

    if rapor_yolu:
        try:
            os.makedirs(os.path.dirname(rapor_yolu) or ".", exist_ok=True)
            with open(rapor_yolu, "w", encoding="utf-8") as dosya:
                dosya.write(metin)
        except OSError as exc:
            logger.debug("İleri test raporu yazılamadı: %s", exc)

    istatistik = {"bekleyen": len(bekleyen), "islenen": len(isler),
                  "hesaplanan": hesaplanan, "veri_yok": hata}
    logger.info("İleri test gece işi: %s", istatistik)
    return {"istatistik": istatistik, "ozet": metin}


# --- özet / öneri ------------------------------------------------------------

def _ort(degerler: List[float]) -> Optional[float]:
    return sum(degerler) / len(degerler) if degerler else None


def ozet(kayitlar: List[Dict]) -> str:
    """Defterin durumu + ÖNCEDEN yazılmış kurala göre öneri. Mesaj atmaz."""
    sonuclu = [k for k in kayitlar if isinstance(k.get("sonuc"), dict)]
    bayrakli = [k["sonuc"]["yuzde"] for k in sonuclu if k.get("bayrak")]
    digerleri = [k["sonuc"]["yuzde"] for k in sonuclu if not k.get("bayrak")]
    ort_b, ort_d = _ort(bayrakli), _ort(digerleri)

    satirlar = ["# İleri test — durum", ""]
    satirlar.append(f"- Kayıt: {len(kayitlar)} · sonucu olan: {len(sonuclu)} · "
                    f"bekleyen: {len(kayitlar) - len(sonuclu)}")
    satirlar.append("- Kural (sonuç görülmeden yazıldı): bayraklı grup ≥ "
                    f"+{ESIK_FAZLA_PUAN:g} yüzde puanı fazla verirse kalır; grup "
                    f"başına en az {MIN_GOZLEM} gözlem şart.")
    satirlar.append("")
    satirlar.append("| Grup | n | ort. 24 bar (yön lehine %) |")
    satirlar.append("|---|---|---|")
    satirlar.append(f"| bayraklı (kama + üst TF aynı yönde) | {len(bayrakli)} | "
                    + ("—" if ort_b is None else f"{ort_b:+.2f}") + " |")
    satirlar.append(f"| diğer (aynı dönem, aynı defter) | {len(digerleri)} | "
                    + ("—" if ort_d is None else f"{ort_d:+.2f}") + " |")
    satirlar.append("")

    if len(bayrakli) < MIN_GOZLEM or len(digerleri) < MIN_GOZLEM:
        eksik = MIN_GOZLEM - min(len(bayrakli), len(digerleri))
        satirlar.append(f"**Hüküm yok.** Grup başına {MIN_GOZLEM} gözlem gerekli; "
                        f"en az {max(0, eksik)} gözlem daha birikmeli. "
                        "Bu satır bir öneri değil, bekleme durumudur.")
        return "\n".join(satirlar)

    fazla = (ort_b or 0.0) - (ort_d or 0.0)
    satirlar.append(f"**Fazla: {fazla:+.2f} puan** (eşik {ESIK_FAZLA_PUAN:+g})")
    satirlar.append("")
    if fazla >= ESIK_FAZLA_PUAN:
        satirlar.append("**Öneri: bayrak kalsın.** Kural gereği eşik aşıldı; "
                        "kart/sıralama değişikliği YİNE kullanıcı onayıyla yapılır.")
    else:
        satirlar.append("**Öneri: bayrak kaldırılsın.** Eşik aşılmadı; bayrak "
                        "kartta/sıralamada kalmayı hak etmiyor. Uygulama yine "
                        "kullanıcı onayıyla.")
    return "\n".join(satirlar)
