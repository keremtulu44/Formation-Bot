"""Arşiv ölçümünü canlı metne bağlayan AMPİRİK REFERANS katmanı.

## Neden var

Kart/`/tara` metni yalnız "şu an ne oldu" bilgisini taşıyordu (kırılan seviye,
kapanış, kalite, temas). Oysa `docs/arastirma/` altında aynı kurulumun arşivde
nasıl sonuçlandığı ölçülmüş durumda. Bu modül o ölçümü, **olayın kendi
özelliklerine koşullu** tek satıra çevirir: aynı TF'de her alarmda tekrarlanan
sabit bir dipnot değil, o an ayırt edici olan sayı.

## Sözleşme (bozulmaması gereken kurallar)

1. **Uydurma yok.** Buradaki her sayı `docs/arastirma/` tablolarından elle
   alınmıştır; kaynağı `KAYNAK_TABLOLARI` içinde satır adıyla yazılıdır.
   Tabloda olmayan bir kesit (ör. 2h FVG yükseklik kovası) için satır ÜRETİLMEZ.
2. **n metinde görünür.** Ölçüm tabanı olmadan oran yazılmaz; okuyan kişi
   sayının kaç gözleme dayandığını görür.
3. **Tahmin değil, betimleme.** Çıktı "beklenen getiri" değil "arşivde şu
   kurulumda şu davranış gözlendi" cümlesidir. `al/sat/hedef/stop/kâr/zarar`
   gibi tavsiye fiilleri bu modülde geçmez (test ile korunur).
4. **Tek kaynak.** Sayılar yalnız burada durur; biçimleyici (kart, /tara) sayı
   hesaplamaz, yalnız buradan gelen metni basar.
5. **Sessizlik yeğdir.** Koşul sağlanmıyorsa satır dönmez. Kartı doldurmak için
   ilgisiz ölçüm basılmaz.

## Ölçüm tabanı

176 sembol × 4 zaman dilimi = 704 seri; intraday arşiv 2025-05-07 → 2026-10-19,
günlük arşiv 2024-10-21 → 2026-10-19. Bu tek bir rejim penceresidir; rejim
değişiminde (özellikle yön asimetrisi) sayılar dönebilir. Motor parametreleri
("Dengeli" profil) değiştirilmedi.

## Bilinçli yaklaşımlar

* **RVOL çeyreği** arşivde gözlem dağılımından kesilmiştir; canlı `rvol`
  değeri çeyrek ortalamasına **en yakın** çeyreğe atanır ve metinde `≈`
  ile işaretlenir. Kesin çeyrek sınırı canlı tarafta yeniden üretilemediği
  için bu bir yaklaşımdır — gizlenmez.
* **Zone yüksekliği** `(üst - alt) / ATR` olarak, arşivdeki tanımla aynı
  biçimde hesaplanır; kova tablosu 1d FVG ölçümüdür (n=6285) ve metinde bu
  taban adıyla birlikte yazılır, "tüm aileler için geçerli" denmez.
* **MS devamı** ölçümü 12 bar / ATR penceresindedir; kapsam (dış/iç), tip
  (BOS/CHoCH) ve yön ayrımı tabloda ayrı ayrı vardır.
"""

from __future__ import annotations

from dataclasses import dataclass

OLCUM_SURUMU = "arsiv-2026-10"
OLCUM_TABANI = "176 sembol × 4 TF (704 seri)"
OLCUM_KAYNAGI = "docs/arastirma/ARASTIRMA_BULGULARI.md · FORMASYON_SONUCLARI.md"

KAYNAK_TABLOLARI = {
    "frm_terminal": "FORMASYON_SONUCLARI FRM-15",
    "frm_teyit_mfe": "FORMASYON_SONUCLARI FRM-16",
    "frm_ters": "FORMASYON_SONUCLARI FRM-17",
    "frm_retest": "FORMASYON_SONUCLARI FRM-12",
    "frm_retest_derinlik": "FORMASYON_SONUCLARI FRM-13",
    "frm_uyum": "FORMASYON_SONUCLARI FRM-20",
    "frm_zone": "FORMASYON_SONUCLARI FRM-19",
    "zone_tepki": "ARASTIRMA_BULGULARI Soru 2",
    "zone_yukseklik": "ARASTIRMA_BULGULARI Soru 4 (1d FVG, n=6285)",
    "zone_rvol": "ARASTIRMA_BULGULARI Hacim — dokunuş tepkisi × rvol çeyreği",
    "ms_devam": "ARASTIRMA_BULGULARI Soru 5 (scope × tip × yön)",
}

TF_KISA = {"1h": "1s", "2h": "2s", "4h": "4s", "1d": "1g"}

# --- Formasyon (FRM) referansları -----------------------------------------
# Taban: teyit almış formasyonlar; 12 bar / ATR penceresi.
FRM_TERMINAL = {"n": 32321, "tamamlandi": 76.2, "basarisiz": 19.1, "gecersiz": 4.7}
FRM_TEYIT_MFE = {"n": 24618, "medyan_atr": 1.23, "medyan_omur_bar": 11}
FRM_TERS = {"n": 6186, "medyan_atr": 2.83}
FRM_RETEST = {"n": 28624, "oran": 34.9, "medyan_bar": 1}
FRM_RETEST_DERINLIK = (
    (0.25, 1989, 60.8),      # < 0.25 ATR
    (0.50, 1448, 50.8),      # 0.25–0.50 ATR
    (None, 6554, 33.2),      # >= 0.50 ATR
)
FRM_UYUM = {"uyumlu": (15724, 79.7), "uyumsuz": (13573, 73.1), "fark_puan": 6.6}
FRM_ZONE = {"zone_var": (11905, 75.9), "zone_yok": (20232, 77.0),
            "ob_var": (11249, 75.7), "fvg_var": (859, 79.0)}

# --- Zone (OB/FVG) referansları -------------------------------------------
# Aile × TF: geçerli sonuç n, ortalama MFE/MAE/NET (ATR, 12 bar).
ZONE_OLCUM = {
    ("OB", "1h"): (90199, 2.0054, 2.0846),
    ("OB", "2h"): (54113, 2.0001, 2.1184),
    ("OB", "4h"): (33516, 2.0397, 2.2219),
    ("OB", "1d"): (18020, 2.0071, 2.1046),
    ("FVG", "2h"): (21679, 2.1112, 1.9693),
    ("FVG", "4h"): (14830, 2.1264, 2.1316),
    ("FVG", "1d"): (6139, 1.9725, 2.1383),
}
# Soru 2: dokunuşta beklenen yönde >=1 ATR tepki; zone'un kendisi ise geçilir.
ZONE_TEPKI = {"dokunus_tepki_pct": (65.0, 66.5), "gecilme_pct": (85.4, 93.6),
              "fvg_tam_dolum_pct": (40.3, 42.6),
              # Dokunuş seviyesi tabanı (ARASTIRMA_BULGULARI Soru 2): 4 TF toplamı.
              "dokunus_n": 240484}

# Soru 4 — zone yüksekliği kovaları (1d FVG, n=6285): üst sınır, n, CALISTI %.
YUKSEKLIK_KOVALARI = (
    (0.5, 3276, 64.3, "geri verir"),
    (1.0, 1989, 64.7, ""),
    (2.0, 858, 67.8, ""),
    (None, 162, 71.0, "kalıcı"),
)

# Hacim — dokunuş tepkisi × rvol çeyreği: (n, CALISTI %, ort. yön h12 ATR, ort. rvol)
RVOL_KOVALARI = {
    "1h": (((28912, 66.6, 1.988, 0.124), (15425, 71.9, 2.255, 0.897),
            (18341, 67.3, 2.095, 1.448), (23479, 61.3, 1.811, 3.501))),
    "2h": (((15803, 69.6, 2.169, 0.470), (20880, 67.8, 2.094, 0.882),
            (17949, 65.9, 2.051, 1.431), (16451, 60.4, 1.808, 3.295))),
    "4h": (((6740, 70.1, 2.272, 0.427), (11561, 67.7, 2.115, 0.901),
            (13730, 66.1, 2.081, 1.437), (11928, 61.0, 1.868, 3.173))),
    "1d": (((3489, 63.9, 1.884, 0.503), (7079, 67.7, 2.060, 0.882),
            (4923, 63.6, 1.940, 1.411), (3086, 62.0, 1.821, 2.972))),
}

# MS devamı — (TF, kapsam, tip, yön) → (n, CALISTI %, ort. devam h12 ATR)
# kapsam: "DIS" (EXTERNAL) / "IC" (INTERNAL); tip: "BOS" / "CHOCH";
# yön: "UP" / "DOWN". Yön bilinmiyorsa `MS_TIP` (kapsam × tip) kullanılır.
MS_TIP = {
    ("1h", "DIS", "BOS"): (8430, 67.3, 2.284),
    ("1h", "DIS", "CHOCH"): (3185, 68.4, 2.294),
    ("1h", "IC", "BOS"): (15837, 67.2, 2.273),
    ("1h", "IC", "CHOCH"): (5812, 66.5, 2.177),
    ("2h", "DIS", "BOS"): (5225, 67.0, 2.318),
    ("2h", "DIS", "CHOCH"): (2071, 68.5, 2.373),
    ("2h", "IC", "BOS"): (9983, 67.2, 2.271),
    ("2h", "IC", "CHOCH"): (3714, 69.2, 2.283),
    ("4h", "DIS", "BOS"): (3387, 71.0, 2.500),
    ("4h", "DIS", "CHOCH"): (1300, 70.8, 2.403),
    ("4h", "IC", "BOS"): (6505, 68.2, 2.408),
    ("4h", "IC", "CHOCH"): (2455, 70.0, 2.407),
    ("1d", "DIS", "BOS"): (1777, 68.9, 2.284),
    ("1d", "DIS", "CHOCH"): (694, 66.3, 2.093),
    ("1d", "IC", "BOS"): (3236, 68.0, 2.300),
    ("1d", "IC", "CHOCH"): (1253, 64.8, 2.026),
}
MS_YON = {
    ("1h", "DIS", "BOS", "UP"): (4254, 67.6, 2.436),
    ("1h", "DIS", "BOS", "DOWN"): (4176, 67.0, 2.128),
    ("1h", "DIS", "CHOCH", "UP"): (1537, 69.7, 2.477),
    ("1h", "DIS", "CHOCH", "DOWN"): (1648, 67.2, 2.123),
    ("1h", "IC", "BOS", "UP"): (7776, 67.2, 2.428),
    ("1h", "IC", "BOS", "DOWN"): (8061, 67.1, 2.124),
    ("1h", "IC", "CHOCH", "UP"): (2890, 68.4, 2.391),
    ("1h", "IC", "CHOCH", "DOWN"): (2922, 64.6, 1.965),
    ("2h", "DIS", "BOS", "UP"): (2615, 69.6, 2.582),
    ("2h", "DIS", "BOS", "DOWN"): (2610, 64.4, 2.054),
    ("2h", "DIS", "CHOCH", "UP"): (1009, 72.5, 2.764),
    ("2h", "DIS", "CHOCH", "DOWN"): (1062, 64.7, 2.001),
    ("2h", "IC", "BOS", "UP"): (4910, 69.4, 2.527),
    ("2h", "IC", "BOS", "DOWN"): (5073, 65.1, 2.024),
    ("2h", "IC", "CHOCH", "UP"): (1825, 72.1, 2.620),
    ("2h", "IC", "CHOCH", "DOWN"): (1889, 66.5, 1.958),
    ("4h", "DIS", "BOS", "UP"): (1651, 75.0, 2.827),
    ("4h", "DIS", "BOS", "DOWN"): (1736, 67.3, 2.189),
    ("4h", "DIS", "CHOCH", "UP"): (650, 70.8, 2.680),
    ("4h", "DIS", "CHOCH", "DOWN"): (650, 70.9, 2.126),
    ("4h", "IC", "BOS", "UP"): (3112, 72.2, 2.779),
    ("4h", "IC", "BOS", "DOWN"): (3393, 64.6, 2.069),
    ("4h", "IC", "CHOCH", "UP"): (1220, 72.2, 2.741),
    ("4h", "IC", "CHOCH", "DOWN"): (1235, 67.9, 2.077),
    ("1d", "DIS", "BOS", "UP"): (873, 77.5, 2.820),
    ("1d", "DIS", "BOS", "DOWN"): (904, 60.6, 1.759),
    ("1d", "DIS", "CHOCH", "UP"): (308, 72.7, 2.672),
    ("1d", "DIS", "CHOCH", "DOWN"): (386, 61.1, 1.629),
    ("1d", "IC", "BOS", "UP"): (1569, 76.1, 2.871),
    ("1d", "IC", "BOS", "DOWN"): (1667, 60.4, 1.756),
    ("1d", "IC", "CHOCH", "UP"): (615, 72.4, 2.566),
    ("1d", "IC", "CHOCH", "DOWN"): (638, 57.5, 1.503),
}

#: Ölçüm ailesi → basılabilecek satır anahtarları.
#:
#: Neden gerekli (kullanıcı kararı 2026-10-22): aynı kartta İKİ farklı yüzde
#: görmek okumayı bozuyordu. "Kırılım tuttu %76" (formasyon sonucu) ile
#: "devam etti %75" (MS olayı) ayrı soruların cevabı; yan yana gelince hangisi
#: neyin ölçüsü olduğu anlaşılmıyor. Bu yüzden her alarm YALNIZ kendi ailesinin
#: ölçümünü basar.
#:
#: * `FRM`  — formasyon alarmı (kırılım teyitli / retest / geçersizleşme)
#: * `MS`   — market structure olayı (BOS/CHoCH)
#: * `ZONE` — OB/FVG teması
#: Boş aile ("") eski davranışı korur: kısıt yok (geri dönüş yolu).
AILE_OLCU = {
    "FRM": ("uyum", "retest", "temel", "hareket"),
    "MS": ("ms",),
    "ZONE": ("zone", "yukseklik", "rvol"),
}

# Önerilen satır sırası: küçük numara önce basılır.
#: Satır önceliği — aile süzgecinden SONRA, aile içinde sıralama belirler.
#: FRM'de sıra kullanıcı kararını izler: önce "tuttu mu", sonra "ne kadar
#: gitti", sonra rol uyumu, en sonda geri çekilme oranı.
ONCELIK = {
    "ms": 0,
    "temel": 1,
    "hareket": 2,
    "uyum": 3,
    "retest": 4,
    "zone": 5,
    "yukseklik": 6,
    "rvol": 7,
}


def _say(x: float, basamak: int = 1) -> str:
    """Türkçe ondalık: `2.4` → `2,4`. Binlik ayırıcı kullanılmaz."""
    metin = f"{float(x):.{basamak}f}"
    return metin.replace(".", ",")


def _yuzde(x: float, basamak: int = 0) -> str:
    return "%" + _say(x, basamak)


def rvol_kovasi(tf: str, rvol: float | None) -> tuple[int, tuple] | None:
    """Canlı `rvol` değerini arşivdeki çeyrek ortalamasına en yakın kovaya atar.

    Kesin çeyrek sınırları canlı tarafta yeniden üretilemediği için yaklaşımdır
    (çağıran metinde `≈` ile işaretler). Eşit uzaklıkta alt kova seçilir.
    """
    kovalar = RVOL_KOVALARI.get(str(tf or "").lower())
    if kovalar is None or rvol is None:
        return None
    try:
        deger = float(rvol)
    except (TypeError, ValueError):
        return None
    if deger <= 0:
        return None
    uzakliklar = [abs(deger - kova[3]) for kova in kovalar]
    indeks = min(range(len(kovalar)), key=lambda i: uzakliklar[i])
    return indeks, kovalar[indeks]


def yukseklik_kovasi(yukseklik_atr: float | None) -> tuple[tuple, int] | None:
    """Zone yüksekliğini (ATR) arşiv kovasına yerleştirir (1d FVG tablosu)."""
    if yukseklik_atr is None:
        return None
    try:
        deger = float(yukseklik_atr)
    except (TypeError, ValueError):
        return None
    if deger <= 0:
        return None
    for indeks, (ust, n, calisti, notu) in enumerate(YUKSEKLIK_KOVALARI):
        if ust is None or deger < ust:
            return (ust, n, calisti, notu), indeks
    return None


def ms_referansi(tf: str, kapsam: str | None, tip: str | None,
                 yon: str | None = None) -> tuple[int, float, float] | None:
    """MS olayı için (n, CALISTI %, ort. devam ATR); tabloda yoksa None."""
    zaman = str(tf or "").lower()
    kapsam_k = str(kapsam or "").upper()
    tip_k = str(tip or "").upper()
    yon_k = str(yon or "").upper()
    if kapsam_k in {"EXTERNAL", "DIS"}:
        kapsam_k = "DIS"
    elif kapsam_k in {"INTERNAL", "IC"}:
        kapsam_k = "IC"
    if tip_k not in {"BOS", "CHOCH"}:
        return None
    if yon_k in {"UP", "DOWN"}:
        kayit = MS_YON.get((zaman, kapsam_k, tip_k, yon_k))
        if kayit is not None:
            return kayit
    return MS_TIP.get((zaman, kapsam_k, tip_k))


def zone_referansi(aile: str, tf: str) -> tuple[int, float, float] | None:
    """OB/FVG × TF için (n, ortalama MFE, ortalama MAE), ATR."""
    return ZONE_OLCUM.get((str(aile or "").upper(), str(tf or "").lower()))


@dataclass(frozen=True, slots=True)
class Kurulum:
    """Karttaki tek bir olayın ölçümle eşleşecek özellikleri.

    Her alan isteğe bağlıdır: veri yoksa ilgili satır üretilmez. `None` "ölçüm
    yok" demektir, "sıfır" değildir.
    """

    tf: str = ""
    yon: int = 0                      # +1 yukarı, -1 aşağı, 0 bilinmiyor
    atr: float | None = None
    bolge_top: float | None = None     # olayın dokunduğu/geçtiği zone (alarm TF)
    bolge_alt: float | None = None
    rvol: float | None = None          # alarm TF'sinin son barı
    retest_seen: bool | None = None
    zone_icinde: bool | None = None    # fiyat kırılım anında OB/FVG içinde mi
    ph: float | None = None            # en yakın korunan tepe (PH)
    pl: float | None = None            # en yakın korunan dip (PL)
    break_price: float | None = None
    ms_kapsam: str | None = None       # "EXTERNAL" / "INTERNAL"
    ms_tip: str | None = None          # "BOS" / "CHOCH"
    ms_yon: str | None = None          # "UP" / "DOWN"
    #: Ölçüm ailesi: "FRM" | "MS" | "ZONE" | "" (kısıtsız). Kart yalnız kendi
    #: ailesinin ölçümünü basar; iki ayrı yüzde yan yana gelmez (bkz. AILE_OLCU).
    aile: str = ""


def _ms_satiri(k: Kurulum) -> tuple[str, int] | None:
    if not k.ms_tip:
        return None
    kayit = ms_referansi(k.tf, k.ms_kapsam, k.ms_tip, k.ms_yon)
    if kayit is None:
        return None
    n, calisti, devam = kayit
    # Sade dil (2026-10-22): kısaltma yok. "BOS ↑dış devam %75 n1651" yerine
    # kesitin adı düz Türkçe: BOS → "kırılım", CHoCH → "dönüş". Sayı yine
    # kapsam×tip×yön kesitinden gelir (tablo satırı seçimi değişmedi).
    tur = "dönüşün" if str(k.ms_tip).upper() == "CHOCH" else "kırılımın"
    return (f"◇ {n} {tur} {_yuzde(calisti)}'i sürdü", ONCELIK["ms"])


def _uyum_satiri(k: Kurulum) -> tuple[str, int] | None:
    """Kırılım yönü en yakın korunan seviye ile uyumlu mu (FRM-20)."""
    if not k.yon or k.break_price is None:
        return None
    fiyat = float(k.break_price)
    ph, pl = k.ph, k.pl
    if ph is None and pl is None:
        return None
    uyumlu: bool | None = None
    if k.yon > 0:
        if ph is not None and ph > fiyat and (pl is None or pl <= fiyat):
            uyumlu = True
        elif pl is not None and pl > fiyat:
            uyumlu = False
    else:
        if pl is not None and pl < fiyat and (ph is None or ph >= fiyat):
            uyumlu = True
        elif ph is not None and ph < fiyat:
            uyumlu = False
    if uyumlu is None:
        return None
    anahtar = "uyumlu" if uyumlu else "uyumsuz"
    n, oran = FRM_UYUM[anahtar]
    # "rol uyumlu %80 n15724" → "rol uyumlu %80 · 15724": `n` kısaltması
    # okunmuyordu; taban sayı olarak, oran yüzde olarak yazılır.
    return (f"◇ rol {anahtar} {_yuzde(oran)} · {n}", ONCELIK["uyum"])


def _yukseklik_satiri(k: Kurulum) -> tuple[str, int] | None:
    if k.atr is None or k.bolge_top is None or k.bolge_alt is None:
        return None
    try:
        atr = float(k.atr)
        yukseklik = abs(float(k.bolge_top) - float(k.bolge_alt))
    except (TypeError, ValueError):
        return None
    if atr <= 0 or yukseklik <= 0:
        return None
    kova = yukseklik_kovasi(yukseklik / atr)
    if kova is None:
        return None
    (ust, n, calisti, notu), _ = kova
    kat = yukseklik / atr
    # "ATR" bir formül adı; "normalin x katı" aynı şeyi herkesin anlayacağı
    # biçimde söyler (kullanıcı kararı 2026-10-22).
    if ust is None:
        etiket = "bölge normalin 2 katından geniş"
    elif ust <= 0.5:
        etiket = "bölge normalin yarısından dar"
    else:
        etiket = f"bölge {_say(kat, 1)} kat"
    return (f"◇ {etiket} · {_yuzde(calisti)} ({n})", ONCELIK["yukseklik"])


def _rvol_satiri(k: Kurulum) -> tuple[str, int] | None:
    if k.rvol is None:
        return None
    kova = rvol_kovasi(k.tf, k.rvol)
    if kova is None:
        return None
    indeks, (n, calisti, _ort_yon, ort_rvol) = kova
    # Yalnız ayrışan uçlar basılır: alt çeyrek en iyi, üst çeyrek en kötü.
    if indeks not in {0, 3}:
        return None
    # "Q4 RVOL %61" yerine "hacim yüksekken %61 sürdü": çeyrek numarası ve
    # kısaltma kullanıcıya bir şey söylemiyordu.
    if indeks == 3:
        return (f"◇ hacim yüksekken {_yuzde(calisti)} sürdü", ONCELIK["rvol"])
    return (f"◇ hacim düşükken {_yuzde(calisti)} sürdü", ONCELIK["rvol"])


def _zone_satiri(k: Kurulum) -> tuple[str, int] | None:
    """Dokunuşta beklenen yönde tepki (Soru 2) — zone ailesinin taban ölçüsü.

    Eski satır "zone içi %75,9 / zone dışı %77,0 tamam" idi. Bu iki grup
    arasındaki fark **1,1 puan**: yorum kurmaya yetmez, kart yerini boşa
    harcıyordu (bkz. KANIT_ESIKLERI "zone" eşiği ±2 → hiçbir zaman geçmez).
    Yerine ölçülmüş dokunuş tepkisi basılır.
    """
    if k.zone_icinde is None and k.bolge_top is None:
        return None
    alt, ust = ZONE_TEPKI["dokunus_tepki_pct"]
    # Aralığın ALT ucu yazılır: "%65-66 tepki" demek yerine tek sayı, ve
    # iyimser uç (%66,5) değil muhafazakâr uç (%65,0) basılır.
    tepki = alt
    n = ZONE_TEPKI.get("dokunus_n")
    if n:
        return (f"◇ {n} temasta {_yuzde(tepki)} tepki", ONCELIK["zone"])
    return (f"◇ temaslarda {_yuzde(tepki)} tepki", ONCELIK["zone"])


def _retest_satiri(k: Kurulum) -> tuple[str, int] | None:
    if k.retest_seen is None or k.retest_seen:
        # Retest gördüyse ölçüm retest DERİNLİĞİNE bağlıdır (FRM-13); derinlik
        # kartta ölçülmediği için sabit bir oran basmak yanıltıcı olurdu.
        return None
    return (f"◇ geri çekilme {_yuzde(FRM_RETEST['oran'])} · {FRM_RETEST['n']}",
            ONCELIK["retest"])


def _temel_satiri(k: Kurulum) -> tuple[str, int] | None:
    """Formasyon sonucu (FRM-15): kırılım tuttu mu?

    "tamamlandı %76" ifadesi yanıltıcıydı: motorun `FORMASYON_TAMAMLANDI`
    durumu "hedefe ulaştı" demek DEĞİL — "kırılım teyit aldı ve fiyat formasyon
    bandına geri dönmedi" demek (patterns/lifecycle.py). Sade karşılığı
    "tuttu" (kullanıcı kararı 2026-10-22).
    """
    return (f"◇ {FRM_TERMINAL['n']} formasyon · "
            f"{_yuzde(FRM_TERMINAL['tamamlandi'])} tuttu", ONCELIK["temel"])


def _hareket_satiri(k: Kurulum) -> tuple[str, int] | None:
    """Tutan kırılım ne kadar gidiyor (FRM-16) — TL ve yüzde olarak.

    Kullanıcı geri bildirimi (2026-10-22): "tutanlardan 1,2 kat ne demek onu da
    ben anlamadım". Ölçüm 1,23 ATR (medyan, 12 mum, tutan 24618 formasyon);
    ATR ve fiyat canlıysa aynı sayı TL ve % olarak yazılır — okumak için
    ATR bilmek gerekmez.
    """
    if k.atr is None:
        return None
    try:
        atr = float(k.atr)
    except (TypeError, ValueError):
        return None
    if atr <= 0:
        return None
    kat = FRM_TEYIT_MFE["medyan_atr"]
    tl = atr * kat
    fiyat = None
    if k.break_price is not None:
        try:
            fiyat = float(k.break_price)
        except (TypeError, ValueError):
            fiyat = None
    if fiyat and fiyat > 0:
        oran = tl / fiyat * 100.0
        return (f"◇ tutunca ~{_say(tl, 2)} TL · {_yuzde(oran, 1)}",
                ONCELIK["hareket"])
    return (f"◇ tutunca ~{_say(kat, 1)} kat", ONCELIK["hareket"])


def olcum_satirlari(k: Kurulum, *, azami: int = 2) -> list[str]:
    """Kuruluma en uygun ölçüm satırlarını öncelik sırasıyla döndürür.

    En çok `azami` satır döner; hiçbir koşul sağlanmazsa boş liste. Çağıran
    taraf satır genişliğini `telegram_measure` ile ayrıca denetler.
    """
    if not str(k.tf or "").strip():
        # Zaman dilimi yoksa hangi tabloya bakılacağı bilinmiyor → ölçüm yok.
        return []
    ureticiler = {
        "ms": _ms_satiri,
        "uyum": _uyum_satiri,
        "yukseklik": _yukseklik_satiri,
        "rvol": _rvol_satiri,
        "zone": _zone_satiri,
        "retest": _retest_satiri,
        "temel": _temel_satiri,
        "hareket": _hareket_satiri,
    }
    aile = str(k.aile or "").strip().upper()
    izin = AILE_OLCU.get(aile)
    adaylar = []
    for anahtar, uretici in ureticiler.items():
        if izin is not None and anahtar not in izin:
            continue
        satir = uretici(k)
        if satir is not None:
            adaylar.append(satir)
    secilen = [a for a in adaylar if a is not None]
    secilen.sort(key=lambda x: x[1])
    return [metin for metin, _ in secilen[:max(0, int(azami))]]


def komut_metni() -> str:
    """`/olcum` yanıtı: katmanın hangi sayıyı hangi koşulda bastığını özetler.

    Sayılar tablolardan türetilir (elle yeniden yazılmaz); böylece tablo
    güncellenince komut metni de aynı kalır. Satırlar telefon satır bütçesine
    (283 px) sığacak biçimde kısa tutulur — `_satir_butcesi` testi doğrular.
    """
    tepki_alt, tepki_ust = ZONE_TEPKI["dokunus_tepki_pct"]
    gecilme_alt, gecilme_ust = ZONE_TEPKI["gecilme_pct"]
    dolum_alt, dolum_ust = ZONE_TEPKI["fvg_tam_dolum_pct"]
    uyum_n, uyum_oran = FRM_UYUM["uyumlu"]
    uyumsuz_n, uyumsuz_oran = FRM_UYUM["uyumsuz"]
    zone_var_n, zone_var_oran = FRM_ZONE["zone_var"]
    zone_yok_n, zone_yok_oran = FRM_ZONE["zone_yok"]
    yuksek_n, yuksek_oran, _ = YUKSEKLIK_KOVALARI[-1][1:]
    rvol_q4 = RVOL_KOVALARI["4h"][3]
    rvol_q1 = RVOL_KOVALARI["4h"][0]
    bos_up = MS_YON[("4h", "DIS", "BOS", "UP")]
    bos_down = MS_YON[("4h", "DIS", "BOS", "DOWN")]

    satirlar = [
        f"◇ Arşiv ölçümü · {OLCUM_SURUMU}",
        OLCUM_TABANI,
        "Karttaki ◇ satırlarının kaynağı",
        "",
        "Zone (OB/FVG), dokunuşta:",
        f"· ≥1 ATR tepki %{_say(tepki_alt)}–%{_say(tepki_ust)}",
        f"· %{_say(gecilme_alt)}–%{_say(gecilme_ust)} kadarı geçilir",
        f"· FVG tam dolum %{_say(dolum_alt)}–%{_say(dolum_ust)}",
        "",
        "Formasyon, teyitten sonra 12 bar:",
        f"· tamamlandı %{_say(FRM_TERMINAL['tamamlandi'])}"
        f" (n {FRM_TERMINAL['n']})",
        f"· başarısız %{_say(FRM_TERMINAL['basarisiz'])}"
        f" · geçersiz %{_say(FRM_TERMINAL['gecersiz'])}",
        f"· medyan {_say(FRM_TEYIT_MFE['medyan_atr'])} ATR"
        f" (n {FRM_TEYIT_MFE['n']})",
        f"· ters medyan {_say(FRM_TERS['medyan_atr'])} ATR"
        f" (n {FRM_TERS['n']})",
        f"· retest %{_say(FRM_RETEST['oran'], 1)}"
        f" (n {FRM_RETEST['n']})",
        "",
        "Ayrıştırıcılar (tamamlanma):",
        f"· role uyumlu %{_say(uyum_oran)} (n {uyum_n})",
        f"· role uyumsuz %{_say(uyumsuz_oran)} (n {uyumsuz_n})",
        f"· zone içinde %{_say(zone_var_oran)} (n {zone_var_n})",
        f"· zone dışında %{_say(zone_yok_oran)} (n {zone_yok_n})",
        f"· ≥2 ATR bölge %{_say(yuksek_oran)} (n {yuksek_n})",
        f"· yüksek RVOL %{_say(rvol_q4[1])} (n {rvol_q4[0]})",
        f"· düşük RVOL %{_say(rvol_q1[1])} (n {rvol_q1[0]})",
        "",
        f"MS 4s dış BOS ↑ %{_say(bos_up[1])} (n {bos_up[0]})",
        f"   ↓ %{_say(bos_down[1])} (n {bos_down[0]})",
        "",
        "Sınır: tek rejim, 12 bar/ATR;",
        "maliyet/pozisyon/kalibrasyon yok.",
        "Yatırım tavsiyesi değildir.",
        "Kaynak: docs/arastirma/",
        "AMPIRIK_REFERANS.md",
    ]
    return "\n".join(satirlar)
