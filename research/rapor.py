"""Gözlem satırlarını kullanıcının araştırma sorularının cevabına çevirir.

Rapor ilkeleri:

* **Her hücrede ``n`` ve güven etiketi vardır.** ``analytics/backtest.py``
  ile aynı eşikler kullanılır (``YETERLI_N=30``, ``KISMI_N=15``); altındaki
  hücreler ``ZAYIF`` işaretlenir. Domain x zaman dilimi x yön x kova
  çaprazları hızla inceldiği için n'siz yüzde yanıltıcıdır.
* **Sansürlü gözlem başarı sayılmaz.** "Henüz kırılmadı" ile "başarılı
  direnç" ayrıdır; sansürlü paydalar ayrıca raporlanır.
* **Belirsiz yön ayrı kovadır.** Zone'un iki kenarına birden değen barlarda
  kenar-ancored ölçüm yapılamaz; bunlar ``OLCULEMEDI`` olarak gösterilir,
  ne yukarı ne aşağı sonuca karıştırılır.
* **Eşik ızgarası raporlanır.** Tek eşik seçip yalnız onu göstermek sonuç
  seçmek olurdu; ``ESIK_IZGARA`` tamamı tabloya girer.

Hacim kendi soru seti değil **koşullandırma değişkenidir**: aynı ölçüm
hacim çeyreklerine bölünerek tekrarlanır ve fark gösterilir.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from research import olcum

__all__ = [
    "YETERLI_N",
    "KISMI_N",
    "guven_etiketi",
    "oran",
    "yuzde",
    "ozet_tablo",
    "soru_ob_fvg_deneme",
    "soru_ob_fvg_gecilme_ve_tepki",
    "soru_kenar_yonlu_tepki",
    "soru_yukseklik_sekil",
    "soru_ms_devamlilik",
    "soru_ph_pl",
    "soru_wh_wl",
    "soru_hacim_kosullandirma",
    "rapor_uret",
]

#: ``analytics/backtest.py`` ile aynı güven eşikleri.
YETERLI_N = 30
KISMI_N = 15


def guven_etiketi(n: int) -> str:
    """Örneklem büyüklüğünden güven etiketi üretir."""
    n = int(n or 0)
    if n >= YETERLI_N:
        return "YETERLI"
    if n >= KISMI_N:
        return "KISMI"
    return "ZAYIF"


def oran(pay: int, payda: int) -> float | None:
    """Payda sıfırsa ``None``. Sıfırı %0 gibi göstermek yanıltıcı olur."""
    if not payda:
        return None
    return float(pay) / float(payda)


def yuzde(deger: float | None) -> str:
    if deger is None:
        return "-"
    return f"%{deger * 100:.1f}"


def _tablo(basliklar: Sequence[str], satirlar: Iterable[Sequence[Any]]) -> str:
    """Basit Markdown tablosu. Boş tablo için uyarı satırı üretir."""
    satirlar = list(satirlar)
    if not satirlar:
        return "_(veri yok)_\n"
    genislik = [len(str(b)) for b in basliklar]
    bicimlenmis: list[list[str]] = []
    for satir in satirlar:
        hucre = ["-" if h is None else (f"{h:.3f}" if isinstance(h, float) else str(h)) for h in satir]
        hucre += [""] * (len(basliklar) - len(hucre))
        bicimlenmis.append(hucre)
        for i, h in enumerate(hucre):
            genislik[i] = max(genislik[i], len(h))
    cizgi = "|".join("-" * (g + 2) for g in genislik)
    ust = "| " + " | ".join(str(b).ljust(g) for b, g in zip(basliklar, genislik)) + " |"
    govde = "\n".join("| " + " | ".join(h.ljust(g) for h, g in zip(s, genislik)) + " |" for s in bicimlenmis)
    return f"{ust}\n|{cizgi}|\n{govde}\n"


def _grupla(df: pd.DataFrame, anahtarlar: Sequence[str]) -> Iterable[tuple[Any, pd.DataFrame]]:
    if df is None or len(df) == 0:
        return []
    mevcut = [k for k in anahtarlar if k in df.columns]
    if not mevcut:
        return []
    # observed=True: kategorik kolonlarda (pd.cut çıktıları) gözlenmeyen
    # kombinasyonlar için boş satır üretmeyi keser; pandas'in gelecekteki
    # varsayılanı budur ve FutureWarning'i de kaldırır.
    if len(mevcut) == 1:
        for deger, alt in df.groupby(mevcut[0], dropna=False, observed=True):
            yield deger, alt
        return
    for deger, alt in df.groupby(mevcut, dropna=False, observed=True):
        yield deger, alt


def ozet_tablo(df: pd.DataFrame, anahtarlar: Sequence[str], hesaplar: Mapping[str, Any]) -> str:
    """Genel çapraz özet: her grup için ``hesaplar`` sözlüğündeki değerler.

    ``hesaplar`` değeri ya bir kolon adı (ortalaması alınır) ya da
    ``(filtre_fn, "sayı")`` biçiminde bir orandır. Her satıra ``n`` ve güven
    etiketi otomatik eklenir.
    """
    satirlar: list[list[Any]] = []
    basliklar = list(anahtarlar) + ["n", "guven"] + list(hesaplar.keys())
    for deger, alt in _grupla(df, anahtarlar):
        degerler = list(deger) if isinstance(deger, tuple) else [deger]
        satir: list[Any] = list(degerler) + [len(alt), guven_etiketi(len(alt))]
        for ad, kural in hesaplar.items():
            if callable(kural):
                sayi = int(kural(alt).sum()) if len(alt) else 0
                satir.append(yuzde(oran(sayi, len(alt))))
            elif isinstance(kural, str) and kural in alt.columns:
                seri = pd.to_numeric(alt[kural], errors="coerce").dropna()
                satir.append(round(float(seri.mean()), 3) if len(seri) else None)
            else:
                satir.append(None)
        satirlar.append(satir)
    return _tablo(basliklar, satirlar)


# ---------------------------------------------------------------------------
# Soru 1: OB/FVG TEK denemede mi çok denemede mi doluyor/geçiliyor?
# ---------------------------------------------------------------------------
def soru_ob_fvg_deneme(zone_df: pd.DataFrame, dokunus_df: pd.DataFrame) -> str:
    """Zone başına epizot sayısının dağılımı ve tek-çok deneme payı.

    Önemli: hiç temas etmemiş zone'lar ``build_touch_episodes`` tarafından
    epizot üretmez, dolayısıyla payda **zone tablosundan** alınır. Yalnız
    dokunus tablosu kullanılsaydı "hiç denenmedi" sınıfı tamamen kaybolurdu.
    """
    if zone_df is None or len(zone_df) == 0:
        return "_(zone verisi yok)_\n"
    if "epizot_sayisi" not in zone_df.columns and dokunus_df is not None and len(dokunus_df):
        sayim = dokunus_df.groupby("zone_id").size()
        zone_df = zone_df.copy()
        zone_df["epizot_sayisi"] = zone_df["zone_id"].map(sayim).fillna(0).astype(int)
    hesaplar = {
        "tek_deneme": lambda g: (g["epizot_sayisi"] == 1),
        "2_deneme": lambda g: (g["epizot_sayisi"] == 2),
        "3plus_deneme": lambda g: (g["epizot_sayisi"] >= 3),
        "hic_deneme": lambda g: (g["epizot_sayisi"] == 0),
        "ort_epizot": "epizot_sayisi",
    }
    return ozet_tablo(zone_df, ["timeframe", "family"], hesaplar)


# ---------------------------------------------------------------------------
# Soru 2: %kaçı geçildi, %kaçı tepki aldı (zaman dilimine göre)
# ---------------------------------------------------------------------------
def soru_ob_fvg_gecilme_ve_tepki(zone_df: pd.DataFrame, dokunus_df: pd.DataFrame) -> str:
    """Zone seviyesinde geçilme, dokunuş seviyesinde tepki oranları.

    ``native_price_violation`` OB'de ``gap_through`` ve
    ``fill_cancel_threshold`` için, FVG'de kapanış ihlali için True olur.
    ``native_full_fill`` OB tarafında yapısal olarak **her zaman False**'tır
    (``replay_ob_zones`` kaldırma anında sabit False yazar), bu yüzden OB için
    geçilme göstergesi olarak ``native_price_violation`` ve terminal kategorisi
    kullanılır; FVG için ``native_full_fill`` geçerlidir.
    """
    if zone_df is None or len(zone_df) == 0:
        return "_(zone verisi yok)_\n"
    z = zone_df.copy()
    z["sansursuz"] = ~z["sansur"].astype(bool)
    hesaplar = {
        "temas_var": lambda g: g["temas_var"].astype(bool),
        "gecildi_violation": lambda g: g["native_price_violation"].astype(bool),
        "full_fill": lambda g: g["native_full_fill"].astype(bool),
        "sansur_payi": lambda g: g["sansur"].astype(bool),
        "ort_omur_bar": "omur_bar",
        "ort_yukseklik_atr": "yukseklik_atr",
    }
    cikti = "### Zone seviyesi: temas / geçilme / dolum\n\n"
    cikti += ozet_tablo(z, ["timeframe", "family"], hesaplar)

    if dokunus_df is not None and len(dokunus_df):
        d = dokunus_df.copy()
        hesaplar2 = {
            "yon_tepki_CALISTI": lambda g: g["yon_tepki_sinifi"] == "CALISTI",
            "yon_tepki_AZ": lambda g: g["yon_tepki_sinifi"] == "AZ",
            "yon_tepki_YOK": lambda g: g["yon_tepki_sinifi"] == "YOK",
            "yon_tepki_TERS": lambda g: g["yon_tepki_sinifi"] == "TERS",
        "ort_yon_h12_atr": "yon_h12",
        "ort_yon_uzun_tepe_h40": "yon_uzun_tepe_atr",
    }
        cikti += "\n### Dokunuş seviyesi: beklenen yönde tepki (zone yönü)\n\n"
        cikti += ozet_tablo(d, ["timeframe", "family"], hesaplar2)
    return cikti


# ---------------------------------------------------------------------------
# Soru 3: Kenar-ancored tepki (üst kenar -> aşağı, alt kenar -> yukarı)
# ---------------------------------------------------------------------------
def soru_kenar_yonlu_tepki(dokunus_df: pd.DataFrame) -> str:
    """Dokunulan kenardan ölçülen tepki; belirsiz kenarlar ayrı satırda.

    ``TUM_ZONE`` ve ``ZONE_ICI`` yönü belirlenemeyen temaslar olduğundan
    ``OLCULEMEDI`` sınıfında toplanır ve ne yukarı ne aşağı sonuca katılır.
    Bu satırların büyüklüğü başlı başına bir bulgudur: fiyatın zone'u tek
    barda baştan sona kat ettiği durumların oranını verir.
    """
    if dokunus_df is None or len(dokunus_df) == 0:
        return "_(dokunuş verisi yok)_\n"
    d = dokunus_df.copy()
    hesaplar = {
        "tepki_CALISTI": lambda g: g["kenar_tepki_sinifi"] == "CALISTI",
        "tepki_AZ": lambda g: g["kenar_tepki_sinifi"] == "AZ",
        "tepki_YOK": lambda g: g["kenar_tepki_sinifi"] == "YOK",
        "tepki_TERS": lambda g: g["kenar_tepki_sinifi"] == "TERS",
        "OLCULEMEDI": lambda g: g["kenar_tepki_sinifi"] == "OLCULEMEDI",
        "ort_kenar_h12": "kenar_h12",
        "ort_kenar_tepe": "kenar_tepe_atr",
        "ort_kenar_uzun_tepe": "kenar_uzun_tepe_atr",
    }
    cikti = ozet_tablo(d, ["timeframe", "family", "dokunulan_kenar"], hesaplar)

    esik_tablo: list[list[Any]] = []
    for tf, alt in _grupla(d, ["timeframe"]):
        satir = [tf, len(alt), guven_etiketi(len(alt))]
        for esik in olcum.ESIK_IZGARA:
            etiket = str(int(round(esik * 100))).zfill(3)
            kolon = f"kenar_asim_{etiket}"
            if kolon in alt.columns:
                seri = alt[kolon].dropna()
                satir.append(yuzde(oran(int(seri.astype(bool).sum()), len(seri))) if len(seri) else None)
            else:
                satir.append(None)
        esik_tablo.append(satir)
    cikti += "\n### Kenar-ancored: ATR eşik ızgarası aşım oranı (h12)\n\n"
    cikti += _tablo(
        ["timeframe", "n", "guven"] + [f">={e:g} ATR" for e in olcum.ESIK_IZGARA],
        esik_tablo,
    )
    return cikti


# ---------------------------------------------------------------------------
# Soru 4: Yüksek zone tepkisi AYIRT EDİCİ mi, anlık mı yavaş-kalıcı mı?
# ---------------------------------------------------------------------------
def soru_yukseklik_sekil(dokunus_df: pd.DataFrame) -> str:
    """Yükseklik kovasına göre tepki şekli.

    Ayrımın ölçüsü üç alanın birlikte okunmasıdır:

    ``pay_5``
        12 barlık tepenin ne kadarı ilk 5 barda gerçekleşti. Yüksek değer
        **anlık** tepkidir.
    ``h12_decay``
        Tepenin ne kadarı 12. barda geri verildi. Yüksek değer **solma**.
    ``uzun_tepe_atr / tepe_atr``
        40 barlık tepe 12 barlık tepeden belirgin büyükse tepki **yavaş ama
        kalıcı**dır; oran ~1 ise tepki erken bitmiştir.

    Yalnız ``pay_5`` veya yalnız ``decay`` okumak yanıltır: anlık-ve-solan ile
    yavaş-ve-kalıcı ancak ikisinin birlikte görülmesiyle ayrılır.
    """
    if dokunus_df is None or len(dokunus_df) == 0:
        return "_(dokunuş verisi yok)_\n"
    d = dokunus_df.copy()
    d["tepe_orani"] = d.apply(
        lambda r: (r["yon_uzun_tepe_atr"] / r["yon_tepe_atr"])
        if (r.get("yon_tepe_atr") and r["yon_tepe_atr"] > 0 and pd.notna(r.get("yon_uzun_tepe_atr")))
        else math.nan,
        axis=1,
    )
    hesaplar = {
        "ort_pay_5": "yon_pay_5",
        "ort_pay_3": "yon_pay_3",
        "ort_h12_decay": "yon_h12_decay",
        "ort_tepe_h12": "yon_tepe_atr",
        "ort_uzun_tepe_h40": "yon_uzun_tepe_atr",
        "uzun/ana_tepe_orani": "tepe_orani",
        "tepki_CALISTI": lambda g: g["yon_tepki_sinifi"] == "CALISTI",
    }
    cikti = ozet_tablo(d, ["timeframe", "family", "yukseklik_kovasi"], hesaplar)
    cikti += (
        "\n_Okuma: `ort_pay_5` yüksek + `uzun/ana_tepe_orani` ~1 -> **anlık**; "
        "`ort_pay_5` düşük + oran >>1 -> **yavaş ama kalıcı**._\n\n"
        "_`ort_h12_decay` 1'den büyükse pencere, tepenin altına kapanmıştır "
        "(kapanış referansın ters tarafında); bu \"tepki verdi sonra tamamen "
        "geri verdi\" demektir, ölçüm hatası değildir._\n"
    )
    return cikti


# ---------------------------------------------------------------------------
# Soru 5: MS BOS/CHOCH yönü ile tepki uyuşuyor mu, ne kadar devam etti?
# ---------------------------------------------------------------------------
def soru_ms_devamlilik(event_df: pd.DataFrame) -> str:
    """Scope (external/internal) x event tipi x yön kırılımında devamlılık.

    Kullanıcı ``internal`` kapsamının da ayrıca analiz edilmesini istedi; bu
    yüzden ``scope`` her tablonun ilk kırılımıdır. ``uyum`` alanı tepkinin
    event yönünde olup olmadığını, ``devamlilik_sinifi`` ne kadar devam
    ettiğini verir; ``outcome`` motorun kendi takip kararıdır ve bağımsız
    çapraz kontrol olarak ayrıca gösterilir.
    """
    if event_df is None or len(event_df) == 0:
        return "_(event verisi yok)_\n"
    e = event_df.copy()
    hesaplar = {
        "uyumlu": lambda g: g["uyum"] == "UYUMLU",
        "CALISTI": lambda g: g["devamlilik_sinifi"] == "CALISTI",
        "AZ_DEVAM": lambda g: g["devamlilik_sinifi"] == "AZ_DEVAM",
        "DEVAM_YOK": lambda g: g["devamlilik_sinifi"] == "DEVAM_YOK",
        "TERS": lambda g: g["devamlilik_sinifi"] == "TERS",
        "sansur": lambda g: g["sansur"].astype(bool),
        "ort_devam_h12": "devam_h12",
        "ort_ters_h12": "ters_h12",
    }
    cikti = "### Scope x event tipi\n\n"
    cikti += ozet_tablo(e, ["timeframe", "scope", "event_type"], hesaplar)
    cikti += "\n### Scope x yön (BOS/CHOCH ayrımıyla)\n\n"
    bos_choch = e[e["event_type"].isin(["EVENT_BOS", "EVENT_CHOCH"])] if "event_type" in e.columns else e
    cikti += ozet_tablo(bos_choch, ["timeframe", "scope", "event_type", "direction"], hesaplar)
    cikti += "\n### Motorun kendi outcome kararı (çapraz kontrol)\n\n"
    cikti += ozet_tablo(e, ["timeframe", "scope", "outcome"], {"adet": lambda g: g["event_uid"].notna()})
    return cikti


# ---------------------------------------------------------------------------
# Soru 6: PH/PL direnç/destek olarak karakterize edilebilir mi?
# ---------------------------------------------------------------------------
def soru_ph_pl(swing_df: pd.DataFrame) -> str:
    """PH/PL için deneme sıklığı x engelleme oranı.

    "Çok denenen mi az denenen mi daha güvenilir" sorusu deneme epizot
    sayısına göre kovalanarak cevaplanır. Kovalar ön-tanımlıdır. ``engelledi``
    üç değerlidir; ``None`` (sansürlü) ayrı sütunda gösterilir ve payda
    yalnız kararı verilebilir satırlardan oluşur.
    """
    if swing_df is None or len(swing_df) == 0:
        return "_(swing verisi yok)_\n"
    s = swing_df.copy()
    s = s[s["rol"].isin(["PH", "PL"])] if "rol" in s.columns else s
    if len(s) == 0:
        return "_(PH/PL rol aralığı bulunamadı)_\n"

    def deneme_kovasi(g: pd.DataFrame) -> pd.Series:
        n = pd.to_numeric(g.get("deneme_epizot_025"), errors="coerce").fillna(0)
        return pd.cut(n, bins=[-1, 0, 1, 3, 10**9], labels=["0_deneme", "1_deneme", "2-3_deneme", "4plus_deneme"])

    s["deneme_kovasi"] = deneme_kovasi(s)
    kararli = s[s["engelledi_025"].notna()]
    kararsiz = s[s["engelledi_025"].isna()]
    hesaplar = {
        "engelledi": lambda g: g["engelledi_025"].astype(bool),
        "engellemedi": lambda g: ~g["engelledi_025"].astype(bool),
        "ort_deneme_epizot": "deneme_epizot_025",
        "ort_deneme_bar": "deneme_bar_025",
        "ort_rol_sure_bar": "rol_sure_bar",
        "ort_bars_to_break": "bars_to_break_from_rol",
    }
    cikti = "### Kararı verilebilir satırlar (sansürsüz)\n\n"
    cikti += ozet_tablo(kararli, ["timeframe", "scope", "rol", "deneme_kovasi"], hesaplar)

    # Kararsız (sansürlü) satırlar AYRI tablodur. Önceki sürüm bu sütunu
    # kararlı tablonun içinde `lambda g: True` ile üretiyordu; alt küme
    # zaten `notna()` ile süzüldüğü için kolon yapısal olarak %100 çıkıyor
    # ve bilgi taşımıyordu. Payda kaybı burada görünür olmalı.
    if len(kararsiz):
        cikti += "\n### Karar verilemeyen satırlar (sağdan sansürlü — payda dışı)\n\n"
        cikti += ozet_tablo(kararsiz, ["timeframe", "scope", "rol", "deneme_kovasi"], {
            "ort_deneme_epizot": "deneme_epizot_025",
            "ort_rol_sure_bar": "rol_sure_bar",
        })

    # Eşik duyarlılığı: 0.25 kullanıcının seçimi, 0.15 ve 0.50 kontrol.
    duyarlilik: list[list[Any]] = []
    for esik in olcum.DENEME_ESIKLERI:
        etiket = str(int(round(esik * 100))).zfill(3)
        kolon = f"engelledi_{etiket}"
        if kolon not in s.columns:
            continue
        for tf, alt in _grupla(s, ["timeframe"]):
            seri = alt[kolon].dropna()
            duyarlilik.append([
                f"{esik:g} ATR", tf, len(alt), guven_etiketi(len(seri)),
                yuzde(oran(int(seri.astype(bool).sum()), len(seri))) if len(seri) else None,
                int(len(alt) - len(seri)),
            ])
    cikti += "\n### Yaklaşma eşiği duyarlılığı (0.25 ana; 0.15 / 0.50 kontrol)\n\n"
    cikti += _tablo(["esik", "timeframe", "n_satir", "guven", "engelledi_orani", "kararsiz_adet"], duyarlilik)
    return cikti


# ---------------------------------------------------------------------------
# Soru 7: WL/WH %kaçı ziyaret/süpürüldü ve ne kadar sürede ulaşıldı?
# ---------------------------------------------------------------------------
def soru_wh_wl(swing_df: pd.DataFrame) -> str:
    """WH/WL için ziyaret, süpürme ve seviyeye ulaşma süresi.

    ``ziyaret`` = ön-tanımlı eşik bandına en az bir epizot girmesi.
    ``supuruldu`` = seviyenin kapanışla aşılması. ``bars_to_break_from_rol``
    rol atamasından kırılıma kadar geçen native bar sayısıdır; süre sorusunun
    cevabı ortanca ve çeyreklerle verilir çünkü dağılım ağır kuyrukludur.
    """
    if swing_df is None or len(swing_df) == 0:
        return "_(swing verisi yok)_\n"
    s = swing_df.copy()
    s = s[s["rol"].isin(["WH", "WL"])] if "rol" in s.columns else s
    if len(s) == 0:
        return "_(WH/WL rol aralığı bulunamadı)_\n"

    hesaplar = {
        "ziyaret_epizot": lambda g: pd.to_numeric(g.get("deneme_epizot_025"), errors="coerce").fillna(0) > 0,
        "supuruldu": lambda g: g["kirilim_bar"].notna(),
        "hic_ulasilmadi": lambda g: g["kirilim_bar"].isna(),
        "sansur": lambda g: g["sansur"].astype(bool),
        "ort_deneme_epizot": "deneme_epizot_025",
    }
    cikti = ozet_tablo(s, ["timeframe", "scope", "rol"], hesaplar)

    sure_tablo: list[list[Any]] = []
    if "bars_to_break_from_rol" in s.columns:
        for (tf, rol), alt in _grupla(s, ["timeframe", "rol"]):
            seri = pd.to_numeric(alt["bars_to_break_from_rol"], errors="coerce").dropna()
            if len(seri) == 0:
                sure_tablo.append([tf, rol, 0, "ZAYIF", None, None, None, None])
                continue
            sure_tablo.append([
                tf, rol, len(seri), guven_etiketi(len(seri)),
                round(float(seri.quantile(0.25)), 1),
                round(float(seri.median()), 1),
                round(float(seri.quantile(0.75)), 1),
                round(float(seri.mean()), 1),
            ])
    cikti += "\n### Seviyeye ulaşma süresi (native bar; rol atamasından itibaren)\n\n"
    cikti += _tablo(["timeframe", "rol", "n", "guven", "q25", "ortanca", "q75", "ortalama"], sure_tablo)

    # EVENT_SWEEP çapraz kontrolü: motorun kendi süpürme kaydı.
    return cikti


def sweep_capraz_kontrol(event_df: pd.DataFrame) -> str:
    """``EVENT_SWEEP`` kayıtlarıyla WL/WH süpürme bulgusunu çapraz doğrular."""
    if event_df is None or len(event_df) == 0 or "event_type" not in event_df.columns:
        return "_(event verisi yok)_\n"
    e = event_df[event_df["event_type"] == "EVENT_SWEEP"]
    hesaplar = {
        "uyumlu": lambda g: g["uyum"] == "UYUMLU" if "uyum" in g.columns else pd.Series(dtype=bool),
        "CALISTI": lambda g: g["devamlilik_sinifi"] == "CALISTI",
        "ort_devam_h12": "devam_h12",
    }
    return ozet_tablo(e, ["timeframe", "scope", "direction"], hesaplar)


# ---------------------------------------------------------------------------
# Hacim: kendi soru seti değil, koşullandırma değişkeni
# ---------------------------------------------------------------------------
def soru_hacim_kosullandirma(dokunus_df: pd.DataFrame, event_df: pd.DataFrame) -> str:
    """Aynı ölçümü hacim çeyreklerine bölerek farkı gösterir.

    Hacim ayrı bir hipotez olarak değil, diğer soruların **koşulu** olarak
    ele alınır. ``vp_volume_usable=False`` satırlar (örneğin hacmi olmayan
    endeksler) düşürülmez; ``KULLANILAMAZ`` kovasında ayrıca gösterilir ki
    payda kaybı görünür olsun.
    """
    cikti = ""
    if dokunus_df is not None and len(dokunus_df) and "vp_rvol" in dokunus_df.columns:
        d = dokunus_df.copy()
        kullanilabilir = d["vp_volume_usable"].astype("boolean").fillna(False).astype(bool) if "vp_volume_usable" in d.columns else pd.Series([True] * len(d), index=d.index)
        d["hacim_kovasi"] = "KULLANILAMAZ"
        rvol = pd.to_numeric(d["vp_rvol"], errors="coerce")
        gecerli = kullanilabilir & rvol.notna()
        if gecerli.sum() > 0:
            try:
                ceyrek = pd.qcut(rvol[gecerli], 4, labels=["Q1_dusuk", "Q2", "Q3", "Q4_yuksek"], duplicates="drop")
                d.loc[gecerli, "hacim_kovasi"] = ceyrek.astype(str)
            except ValueError:
                d.loc[gecerli, "hacim_kovasi"] = "TEK_CEYREK"
        hesaplar = {
            "tepki_CALISTI": lambda g: g["yon_tepki_sinifi"] == "CALISTI",
            "ort_yon_h12": "yon_h12",
            "ort_pay_5": "yon_pay_5",
            "ort_h12_decay": "yon_h12_decay",
            "ort_rvol": "vp_rvol",
        }
        cikti += "### Dokunuş tepkisi x hacim çeyreği (rvol)\n\n"
        cikti += ozet_tablo(d, ["timeframe", "hacim_kovasi"], hesaplar)

    if event_df is not None and len(event_df) and "vp_rvol" in event_df.columns:
        e = event_df.copy()
        kullanilabilir = e["vp_volume_usable"].astype("boolean").fillna(False).astype(bool) if "vp_volume_usable" in e.columns else pd.Series([True] * len(e), index=e.index)
        e["hacim_kovasi"] = "KULLANILAMAZ"
        rvol = pd.to_numeric(e["vp_rvol"], errors="coerce")
        gecerli = kullanilabilir & rvol.notna()
        if gecerli.sum() > 0:
            try:
                ceyrek = pd.qcut(rvol[gecerli], 4, labels=["Q1_dusuk", "Q2", "Q3", "Q4_yuksek"], duplicates="drop")
                e.loc[gecerli, "hacim_kovasi"] = ceyrek.astype(str)
            except ValueError:
                e.loc[gecerli, "hacim_kovasi"] = "TEK_CEYREK"
        hesaplar2 = {
            "CALISTI": lambda g: g["devamlilik_sinifi"] == "CALISTI",
            "uyumlu": lambda g: g["uyum"] == "UYUMLU",
            "ort_devam_h12": "devam_h12",
        }
        cikti += "\n### MS event devamlılığı x hacim çeyreği\n\n"
        cikti += ozet_tablo(e, ["timeframe", "hacim_kovasi"], hesaplar2)
    return cikti or "_(hacim koşullandırması için yeterli alan yok)_\n"


def rapor_uret(
    tablolar: Mapping[str, pd.DataFrame],
    *,
    sembol_sayisi: int = 0,
    havuz_disi: Sequence[str] = (),
    notlar: Sequence[str] = (),
) -> str:
    """Tüm soruları tek Markdown raporda toplar."""
    zone = tablolar.get("zone")
    dokunus = tablolar.get("dokunus")
    swing = tablolar.get("swing")
    event = tablolar.get("event")
    meta = tablolar.get("meta")

    bolumler: list[str] = []
    bolumler.append("# Formation-Bot Arşiv Araştırma Raporu\n")
    # Uzunluk/okunurluk (kullanıcı: "çıktı gereksiz uzuyorsa çözüm var mı"):
    # bu dosya TABLO EKİDİR — ham aggregatlar soru başına bölümlenir ve yüzlerce
    # satır sürer. Okunabilir özet + yorum ayrı belgededir; raporun başına
    # konan bu işaret, karar için okuyanı ekteki tablolara indirmeden yönlendirir.
    bolumler.append(
        "> Bu dosya tablo ekidir: ham aggregatlar soru başına bölümlenir.\n"
        "> Okunabilir özet ve yorum: `docs/ARASTIRMA_SONUCLARI.md`.\n"
        "> Yalnız karar için okuyan, aşağıdaki tablolara inmeden özetle yetinebilir.\n")
    bolumler.append(
        f"Kaynak: `backfill_data/` (365 gün derin çekim) · Sembol: {sembol_sayisi} · "
        f"Havuz dışı: {', '.join(havuz_disi) or 'yok'}\n"
    )
    if meta is not None and len(meta):
        bolumler.append("\n## Kapsam\n")
        # Kapsam tablosu elle kurulur: `ozet_tablo` sayısal ortalama alır ve
        # "symbol" gibi metin kolonlarında "-" üretir. Burada doğru olan
        # değer *ayrık sembol sayısı*dır.
        kapsam_satirlari: list[list[Any]] = []

        def _toplam(alt: pd.DataFrame, kolon: str) -> int | None:
            """Eksik/tamamı-NaN kolonda çökmek yerine ``None`` döndürür.

            ``int(NaN)`` ``ValueError`` verir ve tek bir eksik alan tüm raporu
            düşürürdü. Meta satırları farklı koşu sürümlerinden gelebileceği
            için kolon yokluğu normal bir durumdur.
            """
            if kolon not in alt.columns:
                return None
            seri = pd.to_numeric(alt[kolon], errors="coerce").dropna()
            return int(seri.sum()) if len(seri) else None

        def _ortalama(alt: pd.DataFrame, kolon: str) -> int | None:
            if kolon not in alt.columns:
                return None
            seri = pd.to_numeric(alt[kolon], errors="coerce").dropna()
            return int(seri.mean()) if len(seri) else None

        for tf, alt in _grupla(meta, ["timeframe"]):
            ms_hatali = int(alt["ms_hata"].notna().sum()) if "ms_hata" in alt.columns else 0
            kapsam_satirlari.append([
                tf,
                alt["symbol"].nunique() if "symbol" in alt.columns else None,
                _ortalama(alt, "bar_sayisi"),
                _toplam(alt, "zone_sayisi"),
                _toplam(alt, "epizot_sayisi"),
                _toplam(alt, "swing_sayisi"),
                _toplam(alt, "event_sayisi"),
                _toplam(alt, "rol_araligi_sayisi"),
                ms_hatali,
            ])
        bolumler.append(_tablo(
            ["timeframe", "sembol", "ort_bar", "toplam_zone", "toplam_epizot",
             "toplam_swing", "toplam_event", "toplam_rol_araligi", "ms_hatali_seri"],
            kapsam_satirlari,
        ))
    if notlar:
        bolumler.append("\n## Yöntem notları\n")
        for n in notlar:
            bolumler.append(f"- {n}\n")

    bolumler.append("\n## Soru 1 — OB/FVG tek denemede mi çok denemede mi?\n")
    bolumler.append(soru_ob_fvg_deneme(zone, dokunus))

    bolumler.append("\n## Soru 2 — %kaçı geçildi, %kaçı tepki aldı?\n")
    bolumler.append(soru_ob_fvg_gecilme_ve_tepki(zone, dokunus))

    bolumler.append("\n## Soru 3 — Kenar-ancored tepki (ATR)\n")
    bolumler.append(soru_kenar_yonlu_tepki(dokunus))

    bolumler.append("\n## Soru 4 — Yüksek zone ayırt edici mi, tepki anlık mı kalıcı mı?\n")
    bolumler.append(soru_yukseklik_sekil(dokunus))

    bolumler.append("\n## Soru 5 — MS BOS/CHOCH: yön ile tepki uyuşuyor mu?\n")
    bolumler.append(soru_ms_devamlilik(event))

    bolumler.append("\n## Soru 6 — PH/PL direnç/destek mi, çok denenen mi az denenen mi?\n")
    bolumler.append(soru_ph_pl(swing))

    bolumler.append("\n## Soru 7 — WH/WL %kaçı ziyaret/süpürüldü, ne kadar sürede?\n")
    bolumler.append(soru_wh_wl(swing))
    bolumler.append("\n### EVENT_SWEEP çapraz kontrolü\n")
    bolumler.append(sweep_capraz_kontrol(event))

    bolumler.append("\n## Hacim — koşullandırma değişkeni\n")
    bolumler.append(soru_hacim_kosullandirma(dokunus, event))

    return "".join(bolumler)
