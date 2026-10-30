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

#: Satır bütçesi tek kaynaktan (`telegram_measure`): uzun detay satırı bölünmek
#: yerine sığan en bilgili hâline kısalır (2026-10-23).
from telegram_measure import SATIR_BUTCE, genislik  # noqa: E402

_KART_ESIK_PX = float(SATIR_BUTCE) * 0.95 - 6.0

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
    "FRM": ("uyum", "detay", "temel", "hareket"),
    "MS": ("ms",),
    "ZONE": ("zone", "yukseklik", "rvol"),
}

# Önerilen satır sırası: küçük numara önce basılır.
#: Karşılaştırma TABANLARI — her ölçüm kendi ailesinin tabanıyla kıyaslanır.
#:
#: * `ms`, `rvol`, `yukseklik`, `zone` → **dokunuş tabanı %65,5** (Soru 2
#:   aralığının alt ucu). Bu ölçümler "temas sonrası ne oldu" sorusunun
#:   cevabıdır; tabanları da aynı evrendir.
#: * `uyum` → **formasyon tabanı %75,0** (FRM-15 %76,2; muhafazakâr yuvarlanmış).
#:   Rol uyumu formasyon ailesinin ölçümüdür; dokunuş tabanıyla kıyaslamak
#:   onu yapay olarak "güçlü lehte" gösterirdi (79,7 − 65,5 = +14,2), oysa
#:   formasyon tabanına göre fark +4,7 puandır ve eşiği (5) GEÇMEZ.
#:
#: Taban yanlış seçilirse hüküm de yanlış olur; bu yüzden ölçüm→taban eşlemesi
#: tek yerde ve testle korunur.
KANIT_TABANLARI = {
    "ms": 65.5,
    "rvol": 65.5,
    "yukseklik": 65.5,
    "zone": 65.5,
    "uyum": 75.0,
}
#: Geriye dönük ad (tek taban varmış gibi okuyan çağıranlar için).
KANIT_TABANI = KANIT_TABANLARI["ms"]

#: Ölçüm başına "kanıt eşiği" (puan). Kural: eşik, o ölçümün kendi yayılımının
#: YARISIDIR (muhafazakâr yuvarlanmış). Etki eşiğin altındaysa ölçüm **nötr**dür
#: ve hükme girmez — böylece "%4 fark var ama kanıtlanmadı" gibi cümleler
#: kendiliğinden elenir. Gerekçeler: docs/tasarim/TAHMIN_UYGULAMA_PLANI.md §1.
KANIT_ESIKLERI = {
    "ms": 5.0,        # 32 hücre %57,5–77,5 → yayılım 20, yarısı 10; muhafazakâr 5
    "rvol": 4.0,      # Q1–Q4 farkı 9,2 (2h) · 9,1 (4h)
    "yukseklik": 3.0,  # kova yayılımı %64,3–71,0
    "uyum": 5.0,      # uyumlu/uyumsuz farkı 6,6
    "zone": 2.0,      # fark 1,1 → HİÇBİR ZAMAN geçmez (bilerek: kanıt yok)
}

#: Küçük örneklem eşiği: altındaki hücre hükme GİRMEZ (sadece kartdan basılmaz
#: değil — beklenti hükmünde de sayılmaz).
KANIT_MIN_N = 300

#: Nadir kesit eşiği (2026-10-22 kararı, kullanıcı: "nadir senaryo yorum yapmak
#: doğru olmaz yazılsın"). Tabanı bu sayının altında olan ölçümde ORAN basılmaz;
#: satır `◇ nadir (162) · yorum yok` olur. Sebep: 162 gözlemde %71 ile %60
#: arasındaki fark gürültüdür (GA95 genişliği ~±7 puan) ve kart onu "sonuç"
#: gibi okutuyordu.
NADIR_ESIK = 300


def _nadir(n: int) -> str:
    """Nadir kesit satırı: sayı yazılır, yorum yazılmaz."""
    return f"◇ nadir ({n}) · yorum yok"


#: Satır önceliği — aile süzgecinden SONRA, aile içinde sıralama belirler.
#: FRM'de sıra kullanıcı kararını izler: önce "tuttu mu", sonra "ne kadar
#: gitti", sonra rol uyumu, en sonda geri çekilme oranı.
ONCELIK = {
    "ms": 0,
    "temel": 1,
    # `detay` 2026-10-28'den beri GERİ ÇEKİLME satırıdır (FRM-12) ve KENDİ
    # tabanını yazar:
    #   ◇ benzer 32.321 · %76'sı sürdü
    #   ◇ geri çekilme %35 (28.624)
    # Eski biçim tek satırda iki farklı tablonun yüzdesini birleştiriyordu
    # (`%76'sı devam etti · %35 geri`) ve 76+35 toplamı gibi okunuyordu.
    "detay": 2,
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


def _binlik(n: int) -> str:
    """`32321` → `32.321`: örnek sayısı okunur olsun (Türkçe binlik ayırıcı)."""
    return f"{int(n):,}".replace(",", ".")


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
    if int(n) < NADIR_ESIK:
        return (_nadir(int(n)), ONCELIK["ms"])
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
    if int(n) < NADIR_ESIK:
        return (_nadir(int(n)), ONCELIK["uyum"])
    # 2026-10-28: taban biçimi diğer ölçü satırlarıyla AYNI — binlik ayırıcı ve
    # parantez (`◇ rol uyumlu %80 (15.724)`). Eski `· 15724` ham sayıydı ve
    # "%80 15724 ne?" diye okunuyordu.
    return (_sigan([
        f"◇ rol {anahtar} {_yuzde(oran)} ({_binlik(int(n))})",
        f"◇ rol {anahtar} {_yuzde(oran)}",
    ]), ONCELIK["uyum"])


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
    if n and int(n) < NADIR_ESIK:
        return (_nadir(int(n)), ONCELIK["yukseklik"])
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
    #
    # 2026-10-28 (kullanıcı): "fiil kalsın ama anlam pek düzgün değil".
    # Haklı: tablodaki sütun `tepki_CALISTI` — ölçülen şey dokunuş sonrası
    # BEKLENEN YÖNDE TEPKİ, "kırılımın sürmesi" değil. "sürdü" yanlış fiildi,
    # "%61" de öznesiz kalıyordu ("neyin %61'i?"). Doğrusu "tepki verdi"dir.
    # Taban (n) sığmadığı için satırda yazılmaz; `/olcum` tabanı verir
    # (`· hacim yüksek %61,0 (n 11.928)`) — taban gizlenmiyor, komuta taşındı.
    yuzde = _yuzde(calisti)
    if indeks == 3:
        return (_sigan([
            f"◇ hacim yüksekken {yuzde} tepki verdi",     # 285 px → sığmaz
            f"◇ hacim yüksek: {yuzde} tepki verdi",       # 261 px
            f"◇ hacim yüksek {yuzde} tepki verdi",        # 256 px
        ]), ONCELIK["rvol"])
    return (_sigan([
        f"◇ hacim düşükken {yuzde} tepki verdi",          # 277 px → sığmaz
        f"◇ hacim düşük: {yuzde} tepki verdi",            # 252 px
        f"◇ hacim düşük {yuzde} tepki verdi",             # 247 px
    ]), ONCELIK["rvol"])


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
        # 2026-10-28: taban binlik ayırıcıyla (`240.484`), diğer ölçü
        # satırlarıyla aynı biçim.
        return (f"◇ {_binlik(int(n))} temasta {_yuzde(tepki)} tepki", ONCELIK["zone"])
    return (f"◇ temaslarda {_yuzde(tepki)} tepki", ONCELIK["zone"])


def _retest_satiri(k: Kurulum) -> tuple[str, int] | None:
    """2026-10-23: geri çekilme oranı detay satırına taşındı; ayrı satır yok."""
    return None


def _retest_satiri_eski(k: Kurulum) -> tuple[str, int] | None:
    if k.retest_seen is None or k.retest_seen:
        # Retest gördüyse ölçüm retest DERİNLİĞİNE bağlıdır (FRM-13); derinlik
        # kartta ölçülmediği için sabit bir oran basmak yanıltıcı olurdu.
        return None
    if int(FRM_RETEST["n"]) < NADIR_ESIK:
        return (_nadir(int(FRM_RETEST["n"])), ONCELIK["retest"])
    return (f"◇ geri çekilme {_yuzde(FRM_RETEST['oran'])} · {FRM_RETEST['n']}",
            ONCELIK["retest"])


def _sigan(adaylar: list[str]) -> str:
    """Bütçeye sığan İLK aday; hiçbiri sığmazsa en kısası (en son aday).

    Kart satırı 283 px; aşan satır telefonda sarmalanıp bilgiyi bölüyordu.
    Kelime seçimi bütçeye göre yapılır, kırpma yapılmaz.
    """
    for aday in adaylar:
        if genislik(aday) <= _KART_ESIK_PX:
            return aday
    return adaylar[-1]


def _temel_satiri(k: Kurulum) -> tuple[str, int] | None:
    """Formasyon ölçümünün ilk satırı: örnek sayısı + devam oranı (FRM-15).

    2026-10-28 — KULLANICI GERİ BİLDİRİMİ: kartta `%76` ile `%35` yan yana
    duruyordu ve "76+35=111" diye okunuyordu. Sebep iki sayının FARKLI
    tablolardan gelmesiydi (76 → FRM-15 n=32.321, 35 → FRM-12 n=28.624) ama
    ikisi de tek satırdaydı. Artık her satır TEK taban taşır ve taban aynı
    satırda yazılır:

        ◇ benzer 32.321 · %76'sı sürdü      ← bu satırın tabanı 32.321
        ◇ geri çekilme %35 (28.624)         ← bu satırın tabanı 28.624

    "sürdü" = kırılım teyit aldı ve bant içine dönmedi (hedefe ulaştı DEĞİL).
    """
    n = int(FRM_TERMINAL["n"])
    if n < NADIR_ESIK:
        return None
    devam = _yuzde(FRM_TERMINAL["tamamlandi"])
    return (_sigan([
        f"◇ benzer {_binlik(n)} · {devam}'sı sürdü",
        f"◇ benzer {_binlik(n)} · {devam} sürdü",
        f"◇ benzer {_binlik(n)} kurulum",
    ]), ONCELIK["temel"])


def _detay_satiri(k: Kurulum) -> tuple[str, int] | None:
    """Geri çekilme satırı (FRM-12): oran + KENDİ tabanı tek satırda.

    2026-10-28: eskiden `%76'sı devam etti · %35 geri` biçimindeydi; iki ayrı
    tablonun yüzdesi aynı satırda durduğu için toplam sanılıyordu. Artık ayrı
    satır ve taban parantezde. Yalnız `retest_seen is False` iken basılır:
    geri çekilme GÖRÜLDÜYSE ölçüm derinliğe bağlıdır (FRM-13), sabit oran
    basmak yanıltıcı olurdu (uydurma yok).
    """
    if k.retest_seen is not False:
        return None
    n = int(FRM_RETEST["n"])
    if n < NADIR_ESIK:
        return (_nadir(n), ONCELIK["detay"])
    oran = _yuzde(FRM_RETEST["oran"])
    return (_sigan([
        f"◇ geri çekilme {oran} ({_binlik(n)})",
        f"◇ geri çekilme {oran}",
    ]), ONCELIK["detay"])


def _uyum_orani(k: Kurulum) -> tuple[str, float] | None:
    """(uyumlu|uyumsuz, oran) — kırılım yönü en yakın korunan seviyeyle uyumlu mu."""
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
    if int(n) < NADIR_ESIK:
        return None
    return anahtar, oran


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
    # 2026-10-23 (kullanıcı): "tutunca" hangi koşulda olduğunu söylemiyordu ve
    # sayı HEDEF gibi okunuyordu. Ölçüm, tutan kırılımın lehte TEPE mesafesidir
    # (medyan, FRM-16): "tutarsa tepe ~1,19 TL (+%1,7)".
    if fiyat and fiyat > 0:
        oran = tl / fiyat * 100.0
        return (f"◇ tutarsa tepe ~{_say(tl, 2)} TL (+{_yuzde(oran, 1)})",
                ONCELIK["hareket"])
    return (f"◇ tutarsa tepe normalin {_say(kat, 1)} katı", ONCELIK["hareket"])


# --- beklenti hükmü (tasarım: docs/tasarim/TAHMIN_KATMANI.md) --------------
#
# NE YAPMIYOR: yön tahmini vermiyor. MFE ≈ MAE (ikisi de ~2 ATR) ve NET %95 GA
# 11 hücrenin 10'unda sıfırı içeriyor; yani "yukarı gider / aşağı gelir"
# cümlesinin kanıtı YOK. Bu katman yalnız "geçmişte bu kurulum nasıl bitti"
# der ve çelişkiyi sayar.
#
# HÜKÜM TEK KELİME: devam · tek kanıt · kararsız · yön kanıtı yok.
# Sıfat yok (`zayıf`, `güçlü`, `muhtemel`): gücü SAYI söyler (kaç lehte,
# kaç aleyhte). Aynı satırda hem oran hem sıfat olunca hangisinin ne olduğu
# okunmuyordu (kullanıcı kararı 2026-10-22).


def _kanit(ad: str, oran: float, n: int, esik: float,
           *, yon: str = "") -> tuple[str, int] | None:
    """Tek ölçümü kanıt olarak sınıflar: (taraf, puan) ya da None (nötr).

    `taraf`: "lehte" | "aleyhte". Puan: tabandan sapma (işaretli).
    """
    if int(n) < KANIT_MIN_N:
        return None                    # küçük örneklem hükme girmez
    puan = oran - KANIT_TABANLARI.get(ad, KANIT_TABANI)
    if abs(puan) < esik:
        return None                    # nötr: gürültü, hükme girmez
    return (("lehte" if puan > 0 else "aleyhte"), int(round(abs(puan))))


def beklenti(k: Kurulum) -> tuple[str, list[str], list[str]]:
    """(hüküm, lehte adları, aleyhte adları).

    Hüküm tablosu (tasarım §5):
      ≥2 lehte, 0 aleyhte → `devam`
      1 lehte, 0 aleyhte  → `tek kanıt`
      ≥1 lehte, ≥1 aleyhte → `kararsız`
      0 lehte, 0 aleyhte  → `yön kanıtı yok`

    Not: "yalnız aleyhte kanıt" da `yön kanıtı yok` döner — lehte taraf boş
    olduğu için "devam" denemez; aleyhte ölçümün adı yine yazılır.
    """
    if not str(k.tf or "").strip():
        return ("yön kanıtı yok", [], [])
    lehte: list[str] = []
    aleyhte: list[str] = []

    # 1) MS devamı — kapsam × tip × yön hücresi.
    kayit = None
    if k.ms_kapsam and k.ms_tip:
        kapsam = "DIS" if str(k.ms_kapsam).upper().startswith(("EXT", "DIS")) else "IC"
        tip = "CHOCH" if "CHOCH" in str(k.ms_tip).upper() else "BOS"
        anahtar = (str(k.tf).lower(), kapsam, tip,
                   {"UP": "UP", "DOWN": "DOWN"}.get(str(k.ms_yon or "").upper(), ""))
        kayit = MS_YON.get(anahtar) or MS_TIP.get(anahtar[:3])
    if kayit:
        n, oran, _devam = kayit
        sinif = _kanit("ms", oran, n, KANIT_ESIKLERI["ms"])
        if sinif:
            (lehte if sinif[0] == "lehte" else aleyhte).append("kırılım devamı")

    # 2) Bölge yüksekliği — yalnız ≥2 kat kovası (n=162 < 300 → girmez, dürüst).
    if k.atr and k.bolge_top is not None and k.bolge_alt is not None:
        try:
            kat = (float(k.bolge_top) - float(k.bolge_alt)) / float(k.atr)
        except (TypeError, ValueError, ZeroDivisionError):
            kat = None
        if kat is not None:
            for ust, n, oran, _notu in YUKSEKLIK_KOVALARI:
                if (ust is None and kat >= 2.0) or (ust is not None and kat < ust):
                    sinif = _kanit("yukseklik", oran, n, KANIT_ESIKLERI["yukseklik"])
                    if sinif:
                        (lehte if sinif[0] == "lehte" else aleyhte).append("bölge genişliği")
                    break

    # 3) Hacim çeyreği — yalnız uçlar (≈Q1 / ≈Q4).
    if k.rvol is not None:
        kova = _rvol_kovasi(k.tf, k.rvol)
        if kova is not None:
            indeks, (n, oran, _yon, _ort) = kova
            if indeks in (0, 3):
                sinif = _kanit("rvol", oran, n, KANIT_ESIKLERI["rvol"])
                if sinif:
                    (lehte if sinif[0] == "lehte" else aleyhte).append(
                        "hacim yüksek" if indeks == 3 else "hacim düşük")

    # 4) Rol uyumu — fark 6,6 puan, eşik 5 → sınırda kalır (bilerek).
    if k.yon and (k.ph is not None or k.pl is not None):
        uyumlu = None
        try:
            if k.yon > 0 and k.ph is not None:
                uyumlu = True              # yukarı kırılım + üstte korunan tepe
            elif k.yon < 0 and k.pl is not None:
                uyumlu = True
            else:
                uyumlu = False
        except (TypeError, ValueError):
            uyumlu = None
        if uyumlu is not None:
            n, oran = FRM_UYUM["uyumlu" if uyumlu else "uyumsuz"]
            sinif = _kanit("uyum", oran, n, KANIT_ESIKLERI["uyum"])
            if sinif:
                (lehte if sinif[0] == "lehte" else aleyhte).append("rol uyumu")

    if len(lehte) >= 2 and not aleyhte:
        hukum = "devam"
    elif len(lehte) == 1 and not aleyhte:
        hukum = "tek kanıt"
    elif lehte and aleyhte:
        hukum = "kararsız"
    else:
        hukum = "yön kanıtı yok"
    return (hukum, lehte, aleyhte)


def beklenti_satirlari(k: Kurulum) -> list[str]:
    """Karta girecek beklenti satırları; kanıt yoksa BOŞ liste.

    Kural (tasarım §8): yön kanıtı yoksa satır basılmaz — boş satır yerine
    yokluk. `kararsız` durumunda aleyhte olanın ADI yazılır; sıfat yazılmaz.
    """
    hukum, lehte, aleyhte = beklenti(k)
    if hukum == "yön kanıtı yok":
        return []
    satirlar = [f"◇ beklenti: {hukum}"]
    parcalar = []
    if lehte:
        parcalar.append(f"{len(lehte)} ölçüm lehte")
    if aleyhte:
        parcalar.append(f"{len(aleyhte)} aleyhte")
    if parcalar:
        satirlar.append("◇ " + " · ".join(parcalar))
    if aleyhte:
        satirlar.append(f"◇ aleyhte: {', '.join(aleyhte)}")
    return satirlar


def _rvol_kovasi(tf: str, rvol: float | None):  # noqa: D401 - kısa yardımcı
    """RVOL'ü en yakın çeyrek kovasına atar: (indeks, kova) ya da None."""
    if rvol is None:
        return None
    kovalar = RVOL_KOVALARI.get(str(tf or "").lower())
    if not kovalar:
        return None
    try:
        deger = float(rvol)
    except (TypeError, ValueError):
        return None
    en_yakin = None
    for indeks, kova in enumerate(kovalar):
        ortalama = kova[3]
        fark = abs(deger - float(ortalama))
        if en_yakin is None or fark < en_yakin[0]:
            en_yakin = (fark, indeks, kova)
    return (en_yakin[1], en_yakin[2]) if en_yakin else None


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
        "detay": _detay_satiri,
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
    """`/olcum` yanıtı: kartın bastığı sayıların kaynağı ve koşulu.

    Kart 2026-10-22'de sade dile geçti; komut metni de aynı dili konuşur —
    aksi hâlde `/olcum` karta uymayan bir sözlük gösteriyordu (`ATR`, `RVOL`,
    `retest`, `tamamlandı`). Sayılar tablolardan türetilir, elle yazılmaz.
    Satırlar telefon bütçesine (283 px) sığar; test doğrular.
    """
    tepki_alt, tepki_ust = ZONE_TEPKI["dokunus_tepki_pct"]
    gecilme_alt, gecilme_ust = ZONE_TEPKI["gecilme_pct"]
    dolum_alt, dolum_ust = ZONE_TEPKI["fvg_tam_dolum_pct"]
    uyum_n, uyum_oran = FRM_UYUM["uyumlu"]
    uyumsuz_n, uyumsuz_oran = FRM_UYUM["uyumsuz"]
    yuksek_n, yuksek_oran, _ = YUKSEKLIK_KOVALARI[-1][1:]
    rvol_q4 = RVOL_KOVALARI["4h"][3]
    rvol_q1 = RVOL_KOVALARI["4h"][0]
    bos_up = MS_YON[("4h", "DIS", "BOS", "UP")]
    bos_down = MS_YON[("4h", "DIS", "BOS", "DOWN")]
    mfe = FRM_TEYIT_MFE

    satirlar = [
        f"◇ Arşiv ölçümü · {OLCUM_SURUMU}",
        OLCUM_TABANI,
        "Karttaki ◇ satırlarının kaynağı",
        "",
        "Formasyon (FRM ailesi):",
        # Kart 2026-10-28: her ölçü satırı KENDİ tabanını yazar; iki ayrı
        # tablonun yüzdesi aynı satırda durmaz. Komut aynı dili konuşur.
        f"· benzer {_binlik(int(FRM_TERMINAL['n']))}"
        f" · %{_say(FRM_TERMINAL['tamamlandi'])} sürdü",
        f"  %{_say(FRM_TERMINAL['basarisiz'])} geri döndü",
        f"  %{_say(FRM_TERMINAL['gecersiz'])} bozuldu",
        # "sürdü" = kırılım teyit aldı ve bandın içine dönmedi; "hedefe
        # ulaştı" DEĞİL. Kart da bu yüzden "tamamlandı" yazmıyor.
        "  sürdü = bandın içine dönmedi",
        "· tutarsa tepe (lehte):",
        f"  normalin {_say(mfe['medyan_atr'])} katı (n {_binlik(int(mfe['n']))})",
        "  TL karşılığı kartta yazılır",
        # Ayrı satır + kendi tabanı: kartta `◇ geri çekilme %35 (28.624)`.
        f"· geri çekilme %{_say(FRM_RETEST['oran'], 1)}"
        f" (n {_binlik(int(FRM_RETEST['n']))})",
        "  ayrı taban (FRM-12)",
        f"· rol uyumlu %{_say(uyum_oran)} (n {_binlik(int(uyum_n))})",
        f"· uyumsuz %{_say(uyumsuz_oran)} (n {_binlik(int(uyumsuz_n))})",
        "",
        "Yön olayı (MS ailesi):",
        f"· 4s kırılım yukarı %{_say(bos_up[1])} (n {_binlik(int(bos_up[0]))})",
        f"· aşağı %{_say(bos_down[1])} (n {_binlik(int(bos_down[0]))})",
        "· kart: 'N olayın %X'i sürdü'",
        "",
        "Bölge teması (ZONE ailesi):",
        f"· {_binlik(int(ZONE_TEPKI['dokunus_n']))} temasta"
        f" %{_say(tepki_alt)} tepki",
        f"· %{_say(gecilme_alt)}–%{_say(gecilme_ust)} kadarı geçilir",
        f"· boşluk tam dolum %{_say(dolum_alt)}–%{_say(dolum_ust)}",
        f"· geniş bölge %{_say(yuksek_oran)} (n {_binlik(int(yuksek_n))})",
        "  küçük örneklem, betimleyici",
        f"· hacim yüksek %{_say(rvol_q4[1])} (n {_binlik(int(rvol_q4[0]))})",
        f"· hacim düşük %{_say(rvol_q1[1])} (n {_binlik(int(rvol_q1[0]))})",
        "",
        f"Kartta n < {NADIR_ESIK}: oran yok:",
        "· '◇ nadir (n) · yorum yok'",
        "",
        "Sınır: tek rejim, 12 mum;",
        "maliyet/pozisyon/kalibrasyon yok",
        "Yatırım tavsiyesi değildir.",
        "Kaynak: docs/arastirma/",
        "AMPIRIK_REFERANS.md",
    ]
    return "\n".join(satirlar)
