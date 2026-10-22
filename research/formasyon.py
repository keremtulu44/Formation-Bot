"""Formasyon yaşam döngüsü ölçümü — `frm` ve `frm_olay` tabloları.

Neden bu modül var
------------------
`research/kayit.py` bugüne kadar OB, FVG, MS ve VP domainlerini ölçtü; **formasyon
hattı yoktu**. `lifecycle_export` adı yanıltıcıdır: hacim motorunun alanıdır.

Formasyonun tek tanığı `state/formation_history.py` defteridir ve o defter **canlı
bot** tarafından yazılır. Bu modül aynı motoru (`ArgentEngine`) arşiv üzerinde
yeniden oynatıp defterin **offline** karşılığını üretir. Yeni matematik yoktur:
motorun kendi kararları okunur, hiçbir eşik değiştirilmez.

Anti-lookahead ve anti-dairesellik
----------------------------------
* Bir formasyonun satırı, **o formasyonun ölümünden sonra** yazılır.
* **Mesafe bloğu kırılım anına kadar** olan barlardan hesaplanır. Kırılım sonrası
  fiyat zaten sınırın ötesindedir; o barları katmak mesafeyi her zaman 0 yapar ve
  "yaklaştı" bilgisini yok eder.
* Sonuç (`teyit_sonrasi_mfe/mae`) teyitten **sonraki** barlardan gelir. İki blok
  aynı pencerede hesaplanmaz — yoksa "yaklaşan formasyon tepki verdi" totoloji olur.

Motorun izlenmesi
-----------------
`_process_bar` çalışma zamanında sarılır (monkeypatch). `patterns/` içinde **tek
satır değişmez**; sarmalayıcı her barın sonunda durumu okur ve `finally` ile geri
alınır. Canlı bot etkilenmez: sarma yalnız ölçüm sürecinde açıktır.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

__all__ = ["formasyon_kosu", "FORMASYON_KOLONLARI"]

#: Kırılım sonrası seyir pencereleri (bar) — `olcum.HORIZONLAR`/`UZUN_PENCERE` ailesi.
TEYIT_PENCERESI = 12
UZUN_TEYIT_PENCERESI = 40

_TERMINAL = ("FORMASYON_TAMAMLANDI", "BASARISIZ_KIRILIM", "FORMASYON_GECERSIZ")
_OLU = _TERMINAL + ("KIRILIM_TEYIT_ALAMADI",)

_FAZ_GEOMETRI = ("ADAY_OLUSUYOR", "GEOMETRI_ADAYI", "FORMASYON_TANIMLANDI",
                 "OLGUNLASIYOR", "SIKISMA_GUCLENIYOR", "KIRILIM_HAZIRLIGI")
_FAZ_KIRILIM = ("KIRILIM_DENEMESI", "KIRILIM_ADAYI", "KIRILIM_TEYITLI")
_FAZ_RETEST = ("RETEST_BEKLENIYOR", "RETEST_EDILIYOR", "RETEST_BASARILI")


def _yuvarla(deger: Any, basamak: int = 6) -> Any:
    if deger is None:
        return None
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(sayi):
        return None
    return round(sayi, basamak)


def _bar_time(index_values: Any, bar: int | None) -> str | None:
    if index_values is None or bar is None:
        return None
    try:
        if 0 <= int(bar) < len(index_values):
            return str(index_values[int(bar)])
    except (TypeError, ValueError):
        return None
    return None


def _epizot(signaller: Sequence[bool]) -> int:
    """Ardışık True bloklarını sayar (`olcum._yaklasma_epizotlari` ile aynı mantık)."""
    sayi = 0
    onceki = False
    for deger in signaller:
        if deger and not onceki:
            sayi += 1
        onceki = deger
    return sayi


def _ilk_bar(signaller: Sequence[bool]) -> int | None:
    for i, deger in enumerate(signaller):
        if deger:
            return i
    return None


def _argmin(dizi: Sequence[float | None]) -> int | None:
    en_iyi = None
    en_iyi_i = None
    for i, v in enumerate(dizi):
        if v is None or not math.isfinite(v):
            continue
        if en_iyi is None or v < en_iyi:
            en_iyi, en_iyi_i = v, i
    return en_iyi_i


def _temiz(dizi: Sequence[float | None]) -> list[float]:
    return [v for v in dizi if v is not None and math.isfinite(v)]


def _atr_dizi(frame: Any) -> list[float | None]:
    from patterns.indicators import calculate_atr

    try:
        return [None if v is None or not math.isfinite(float(v)) else float(v)
                for v in calculate_atr(frame, 14).tolist()]
    except Exception:  # noqa: BLE001 - ATR yoksa ölçüm null döner, koşu durmaz
        return [None] * len(frame)


def _segmentler(trace: Sequence[tuple]) -> dict[str, dict[str, Any]]:
    """Bar izini `stable_id` segmentlerine böler.

    Motor tek aktif formasyon taşır; aynı `stable_id` korunurken segment sürer.
    Kimlik değiştiğinde önceki segment kapanır.
    """
    segmentler: dict[str, dict[str, Any]] = {}
    for kayit in trace:
        b, state, sid = kayit[0], kayit[1], kayit[2]
        if not sid:
            continue
        seg = segmentler.get(sid)
        if seg is None:
            segmentler[sid] = seg = {"sid": sid, "ilk_bar": b, "son_bar": b,
                                     "barlar": [], "durumlar": []}
        seg["son_bar"] = b
        seg["barlar"].append(b)
        seg["durumlar"].append(state)
    return segmentler


def _faz_sayaci(durumlar: Sequence[str]) -> dict[str, int]:
    sayac = {"geometri": 0, "kirilim": 0, "retest": 0, "diger": 0}
    for d in durumlar:
        if d in _FAZ_GEOMETRI:
            sayac["geometri"] += 1
        elif d in _FAZ_KIRILIM:
            sayac["kirilim"] += 1
        elif d in _FAZ_RETEST:
            sayac["retest"] += 1
        else:
            sayac["diger"] += 1
    return sayac


def _rol_mesafe(rol_grup: Mapping[tuple, Sequence[Mapping[str, Any]]],
                fiyat_by_swing: Mapping[tuple, float],
                bar: int, referans: float,
                atr: float | None) -> tuple[float | None, float | None, str | None]:
    """Belirli bir barda **açık olan** PH/PL seviyelerine en yakın mesafe.

    `structural_role_final` KULLANILMAZ: rol el değiştirir, final değer
    tarihsel atamaları kaybeder. Yalnızca o barda açık olan aralık sayılır.
    """
    if not atr or atr <= 0 or not rol_grup:
        return None, None, None
    en_ph = None
    en_pl = None
    for (kapsam, kimlik), araliklar in rol_grup.items():
        if str(kapsam).upper() != "EXTERNAL":
            continue
        fiyat = fiyat_by_swing.get((kapsam, kimlik))
        if fiyat is None:
            continue
        for aralik in araliklar:
            ilk = aralik.get("rol_ilk_bar")
            son = aralik.get("rol_son_bar")
            if ilk is None or bar < int(ilk):
                continue
            if son is not None and bar > int(son):
                continue
            rol = str(aralik.get("rol") or "")
            mesafe = abs(float(fiyat) - float(referans)) / atr
            if rol == "PH":
                en_ph = mesafe if en_ph is None else min(en_ph, mesafe)
            elif rol == "PL":
                en_pl = mesafe if en_pl is None else min(en_pl, mesafe)
            break
    ucu = None
    if en_ph is not None and (en_pl is None or en_ph <= en_pl):
        ucu = "PH"
    elif en_pl is not None:
        ucu = "PL"
    return en_ph, en_pl, ucu


def _zone_kesisim(zone_rows: Iterable[Mapping[str, Any]], fiyat: float | None,
                  bar: int | None) -> dict[str, Any]:
    """Kırılım anında fiyatın içinde bulunduğu **canlı** OB/FVG zone'ları."""
    sonuc = {"ob": False, "fvg": False, "sayi": 0}
    if fiyat is None or bar is None:
        return sonuc
    for z in zone_rows:
        try:
            alt = float(z["zone_lower"])
            ust = float(z["zone_upper"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (alt <= float(fiyat) <= ust):
            continue
        dogum = z.get("dogum_index")
        terminal = z.get("terminal_index")
        if dogum is not None and bar < int(dogum):
            continue
        if terminal is not None and bar > int(terminal):
            continue
        sonuc["sayi"] += 1
        if str(z.get("family")) == "OB":
            sonuc["ob"] = True
        elif str(z.get("family")) == "FVG":
            sonuc["fvg"] = True
    return sonuc


def formasyon_kosu(
    frame: Any,
    *,
    symbol: str = "",
    timeframe: str = "",
    profile: str = "Dengeli",
    rol_grup: Mapping[tuple, Sequence[Mapping[str, Any]]] | None = None,
    fiyat_by_swing: Mapping[tuple, float] | None = None,
    vp_history: Any = None,
    zone_rows: Sequence[Mapping[str, Any]] = (),
    ms_olaylari: Sequence[tuple[int, int]] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Bir seriyi formasyon motoruyla replay eder.

    Döndürür: ``(frm_satirlari, frm_olay_satirlari, meta)``.
    """
    from patterns.lifecycle import ArgentEngine

    if frame is None or len(frame) == 0:
        return [], [], {"formasyon_sayisi": 0, "formasyon_olay_sayisi": 0}

    atr = _atr_dizi(frame)
    # Çerçeve `_normalize_frame` çıktısıdır: RangeIndex + `timestamp` kolonu.
    # Bar zamanı MUTLAK olmalı; pencere indeksi kimlik değildir.
    if hasattr(frame, "columns") and "timestamp" in getattr(frame, "columns", ()):
        index_values = list(frame["timestamp"])
    else:
        index_values = list(frame.index)
    high = frame["high"].to_numpy(dtype=float).tolist()
    low = frame["low"].to_numpy(dtype=float).tolist()
    close = frame["close"].to_numpy(dtype=float).tolist()

    trace: list[tuple] = []
    orijinal = ArgentEngine._process_bar

    def _izleyen(self, b):  # noqa: ANN001 - motor iç imzası
        orijinal(self, b)
        a = self.active
        sid = getattr(a, "stable_id", None) if getattr(a, "valid", False) else None
        if sid:
            trace.append((
                b, self.pattern_state, sid,
                getattr(a, "upper_now", None), getattr(a, "lower_now", None),
                getattr(a, "upper_touches", None), getattr(a, "lower_touches", None),
                getattr(a, "hb1", None), getattr(a, "hp1", None),
                getattr(a, "hb2", None), getattr(a, "hp2", None),
                getattr(a, "lb1", None), getattr(a, "lp1", None),
                getattr(a, "lb2", None), getattr(a, "lp2", None),
                getattr(a, "pattern_type", None), getattr(a, "family", None),
                getattr(a, "classic_dir", None),
                getattr(a, "has_pole", None), getattr(a, "pole_dir", None),
                getattr(a, "pole_magnitude", None), getattr(a, "pole_efficiency", None),
                getattr(a, "pole_quality", None), getattr(a, "pole_duration", None),
                getattr(a, "raw_quality", None), getattr(a, "geometry_atr", None),
                getattr(a, "start_width", None), getattr(a, "current_width", None),
                getattr(a, "contraction", None), getattr(a, "progress", None),
            ))

    ArgentEngine._process_bar = _izleyen
    try:
        engine = ArgentEngine(profile=profile)
        snap = engine.process(frame, tam_yeniden=True)
    finally:
        ArgentEngine._process_bar = orijinal

    olaylar = [e for e in (getattr(snap, "events", None) or []) if isinstance(e, dict)]
    segmentler = _segmentler(trace)
    if not segmentler:
        return [], [], {"formasyon_sayisi": 0, "formasyon_olay_sayisi": len(olaylar)}

    olay_by_sid: dict[str, list[dict[str, Any]]] = {}
    for e in olaylar:
        sid = e.get("stable_id")
        if sid:
            olay_by_sid.setdefault(sid, []).append(e)

    kirilim_snap: dict[str, dict[str, Any]] = {}
    for y in (getattr(engine, "_p2_geo", None) or []):
        if y.get("tur") == "kirilim" and y.get("stable_id"):
            kirilim_snap[y["stable_id"]] = y.get("alanlar") or {}

    from research.olcum import YAKINLIK_IZGARA, vp_ornek

    frm_satirlari: list[dict[str, Any]] = []
    frm_olay_satirlari: list[dict[str, Any]] = []
    for sid in sorted(segmentler, key=lambda s: segmentler[s]["ilk_bar"]):
        seg = segmentler[sid]
        ilk, son = seg["ilk_bar"], seg["son_bar"]
        durumlar, barlar = seg["durumlar"], seg["barlar"]
        if not barlar:
            continue
        sid_olaylar = olay_by_sid.get(sid, [])

        # Ölüm anı: TERMİNAL state'e İLK giriş. Sonrası "ceset" — motor
        # formasyonu değiştirene kadar aynı state'te kalır ve ömür/süre
        # ölçümlerini şişirir.
        #
        # KESİM `_TERMINAL` İLE YAPILIR, `_OLU` İLE DEĞİL:
        # `KIRILIM_TEYIT_ALAMADI` ölü sayılır ama NİHAİ değildir — motor aynı
        # formasyonla yeniden kırılım deneyebilir. Orada kesmek, çok denemeli
        # formasyonları "1 deneme"ye indirir (AEFES 1h: 2+ denemeli 24 formasyon
        # kayboluyordu). Bu, FRM-07'yi sistematik olarak yanlış yapıyordu.
        olu_idx = next((i for i, d in enumerate(durumlar) if d in _TERMINAL), None)
        if olu_idx is not None:
            etkin_durumlar = durumlar[:olu_idx + 1]
            etkin_barlar = barlar[:olu_idx + 1]
        else:
            etkin_durumlar, etkin_barlar = durumlar, barlar
        kesme_bar = etkin_barlar[-1]
        # Segment neden bitti? Üç ayrı olgu karıştırılmamalı.
        if olu_idx is not None:
            bitis_sebebi = "TERMINAL"
        elif int(son) >= int(getattr(frame, "shape", [0])[0]) - 1:
            bitis_sebebi = "VERI_SONU"
        else:
            bitis_sebebi = "YERINE_GECEN"

        kirilim = kirilim_snap.get(sid) or {}
        kirilim_bar = kirilim.get("break_snapshot_bar")
        kirilim_bar = int(kirilim_bar) if kirilim_bar is not None else None

        dogum_kaydi = next(k for k in trace if k[2] == sid)

        # --- bar bazlı gözlemler (yalnız kırılımdan ÖNCE) ---
        kayitlar = [k for k in trace if k[2] == sid]
        if kirilim_bar is not None:
            kayitlar = [k for k in kayitlar if k[0] < kirilim_bar] or kayitlar[:1]

        def _cizgi(k, x1, y1, x2, y2, x):
            if None in (x1, y1, x2, y2):
                return None
            from patterns.mathutil import f_line_price

            return f_line_price(int(x1), float(y1), int(x2), float(y2), int(x))

        ust_yakin, alt_yakin = [], []
        ust_asim, alt_asim = [], []
        ust_kap, alt_kap = [], []
        for k in kayitlar:
            b = k[0]
            a_b = atr[b] if 0 <= b < len(atr) else None
            y_ust = _cizgi(k, k[7], k[8], k[9], k[10], b)
            y_alt = _cizgi(k, k[11], k[12], k[13], k[14], b)
            if not a_b or y_ust is None or y_alt is None:
                for dizi in (ust_yakin, alt_yakin, ust_asim, alt_asim, ust_kap, alt_kap):
                    dizi.append(None)
                continue
            ust_yakin.append(max(0.0, y_ust - high[b]) / a_b)
            alt_yakin.append(max(0.0, low[b] - y_alt) / a_b)
            ust_asim.append(max(0.0, high[b] - y_ust) / a_b)
            alt_asim.append(max(0.0, y_alt - low[b]) / a_b)
            ust_kap.append(max(0.0, y_ust - close[b]) / a_b)
            alt_kap.append(max(0.0, close[b] - y_alt) / a_b)

        uy, ay = _temiz(ust_yakin), _temiz(alt_yakin)
        iy, ia = _argmin(ust_yakin), _argmin(alt_yakin)
        satir: dict[str, Any] = {
            "stable_id": sid,
            "symbol": symbol,
            "timeframe": timeframe,
            "pattern_type": dogum_kaydi[15],
            "family": dogum_kaydi[16],
            "classic_dir": dogum_kaydi[17],
            "has_pole": dogum_kaydi[18],
            "pole_dir": dogum_kaydi[19],
            "pole_magnitude": _yuvarla(dogum_kaydi[20]),
            "pole_efficiency": _yuvarla(dogum_kaydi[21]),
            "pole_quality": _yuvarla(dogum_kaydi[22]),
            "pole_duration": dogum_kaydi[23],
            "raw_quality_dogum": _yuvarla(dogum_kaydi[24]),
            "geometry_atr_dogum": _yuvarla(dogum_kaydi[25]),
            "start_width_dogum": _yuvarla(dogum_kaydi[26]),
            "dogum_bar_time": _bar_time(index_values, ilk),
            "dogum_bar": ilk,
            "son_bar": son,
            "olcum_son_bar": int(kesme_bar),
            "omur_bar": int(kesme_bar) - int(ilk) + 1,
            "terminal_state": durumlar[-1],
            "bitis_sebebi": bitis_sebebi,
            "acik": bitis_sebebi == "VERI_SONU",
            "terminal_mi": bitis_sebebi == "TERMINAL",
            "olay_sayisi": len(sid_olaylar),
            "kirilim_var": kirilim_bar is not None,
            "frm_yakinlik_ust_fitil_atr": _yuvarla(min(uy)) if uy else None,
            "frm_yakinlik_alt_fitil_atr": _yuvarla(min(ay)) if ay else None,
            "frm_yakinlik_ust_kapanis_atr": _yuvarla(min(_temiz(ust_kap))) if _temiz(ust_kap) else None,
            "frm_yakinlik_alt_kapanis_atr": _yuvarla(min(_temiz(alt_kap))) if _temiz(alt_kap) else None,
            "frm_asim_ust_fitil_atr": _yuvarla(max(_temiz(ust_asim))) if _temiz(ust_asim) else None,
            "frm_asim_alt_fitil_atr": _yuvarla(max(_temiz(alt_asim))) if _temiz(alt_asim) else None,
            "frm_yakinlik_ust_bar_time": _bar_time(index_values, kayitlar[iy][0] if iy is not None else None),
            "frm_yakinlik_alt_bar_time": _bar_time(index_values, kayitlar[ia][0] if ia is not None else None),
            "frm_mesafe_olcum_bar": len(kayitlar),
        }

        # --- öncül hareket (FRM-01): doğumdan ÖNCEKİ 20 barın getirisi ---
        # `has_pole` yalnızca direk tabanlı formasyonlarda (bayrak/flama) doludur;
        # üçgenlerde hep False. "Öncül hareket var mı" sorusu bu yüzden fiyat
        # getirisiyle ölçülür: kapanış(doğum-1) − kapanış(doğum-21), ATR cinsinden.
        satir["frm_oncul_getiri_20bar_atr"] = (
            _yuvarla((close[ilk - 1] - close[ilk - 21]) / atr[ilk - 1])
            if ilk >= 21 and atr[ilk - 1] else None)
        satir["frm_oncul_getiri_5bar_atr"] = (
            _yuvarla((close[ilk - 1] - close[ilk - 6]) / atr[ilk - 1])
            if ilk >= 6 and atr[ilk - 1] else None)

        for esik in YAKINLIK_IZGARA:
            etiket = f"{int(round(esik * 100)):03d}"
            uygun_ust = [v is not None and v <= esik for v in ust_yakin]
            uygun_alt = [v is not None and v <= esik for v in alt_yakin]
            satir[f"frm_yakin_ust_{etiket}_bar"] = int(sum(1 for v in uygun_ust if v))
            satir[f"frm_yakin_ust_{etiket}_epizot"] = _epizot(uygun_ust)
            satir[f"frm_yakin_alt_{etiket}_bar"] = int(sum(1 for v in uygun_alt if v))
            satir[f"frm_yakin_alt_{etiket}_epizot"] = _epizot(uygun_alt)

        temas_ust = [v is not None and v <= 0.0 for v in ust_yakin]
        temas_alt = [v is not None and v <= 0.0 for v in alt_yakin]
        satir["frm_temas_ust_epizot"] = _epizot(temas_ust)
        satir["frm_temas_alt_epizot"] = _epizot(temas_alt)
        satir["frm_temas_ust_ilk_gecikme_bar"] = _ilk_bar(temas_ust)
        satir["frm_temas_alt_ilk_gecikme_bar"] = _ilk_bar(temas_alt)

        # Daralma: son gözlenen genişlik / doğum genişliği (kırılıma kadarki barlar).
        son_kayit = kayitlar[-1] if kayitlar else dogum_kaydi
        satir["current_width_son"] = _yuvarla(son_kayit[27])
        satir["contraction_son"] = _yuvarla(son_kayit[28])
        satir["progress_son"] = _yuvarla(son_kayit[29])
        try:
            if dogum_kaydi[26] and son_kayit[27] is not None:
                satir["daralma_orani"] = _yuvarla(1.0 - (float(son_kayit[27]) / float(dogum_kaydi[26])))
        except (TypeError, ValueError, ZeroDivisionError):
            satir["daralma_orani"] = None

        faz = _faz_sayaci(etkin_durumlar)
        satir["frm_faz_geometri_bar"] = faz["geometri"]
        satir["frm_faz_kirilim_bar"] = faz["kirilim"]
        satir["frm_faz_retest_bar"] = faz["retest"]
        satir["frm_faz_gecis_sayisi"] = int(
            sum(1 for i in range(1, len(etkin_durumlar))
                if etkin_durumlar[i] != etkin_durumlar[i - 1]))

        # İki ayrı sayım: motorun "denemesi" state'i (zayıf girişim) ile
        # kırılım fazına her giriş (denemesi + adayı). Kullanıcı "kaç kez
        # denedi" derken ikincisini kasteder; ikisi de yazılır ki karışmasın.
        deneme_bayrak = [d == "KIRILIM_DENEMESI" for d in etkin_durumlar]
        girisim_bayrak = [d in ("KIRILIM_DENEMESI", "KIRILIM_ADAYI") for d in etkin_durumlar]
        satir["frm_kirilim_deneme"] = _epizot(girisim_bayrak)
        satir["frm_kirilim_zayif_deneme"] = _epizot(deneme_bayrak)
        satir["frm_kirilim_deneme_var"] = bool(any(girisim_bayrak))
        satir["frm_kirilim_ilk_deneme_gecikme_bar"] = _ilk_bar(girisim_bayrak)
        teyit_idx = next((i for i, d in enumerate(etkin_durumlar) if d == "KIRILIM_TEYITLI"), None)
        satir["frm_teyit_deneme_no"] = (
            _epizot(girisim_bayrak[:teyit_idx]) if teyit_idx is not None else None)
        satir["frm_kirilim_teyitli_var"] = teyit_idx is not None

        ut_degerler = [k[5] for k in trace if k[2] == sid and k[5] is not None]
        lt_degerler = [k[6] for k in trace if k[2] == sid and k[6] is not None]
        satir["upper_touches_son"] = ut_degerler[-1] if ut_degerler else None
        satir["lower_touches_son"] = lt_degerler[-1] if lt_degerler else None
        satir["frm_pivot_temas_max"] = max(ut_degerler + lt_degerler, default=None)
        satir["frm_pivot_ezilme_var"] = bool(
            any(ut_degerler[i] < ut_degerler[i - 1] for i in range(1, len(ut_degerler)))
            or any(lt_degerler[i] < lt_degerler[i - 1] for i in range(1, len(lt_degerler))))

        # --- kırılım bloğu (defter alanları birebir) ---
        for alan in ("frozen_upper_boundary_at_break", "frozen_lower_boundary_at_break",
                     "frozen_break_buffer", "frozen_retest_tolerance",
                     "frozen_atr_at_break", "break_snapshot_bar", "break_snapshot_price",
                     "break_snapshot_direction", "break_strength", "break_volume_score",
                     "break_confirmation_strength", "frozen_raw_quality", "quality_frozen"):
            satir[alan] = kirilim.get(alan)
        satir["break_buffer_atr"] = _yuvarla(
            kirilim.get("frozen_break_buffer") / kirilim.get("frozen_atr_at_break")
        ) if kirilim.get("frozen_break_buffer") and kirilim.get("frozen_atr_at_break") else None
        satir["retest_tolerans_atr"] = _yuvarla(
            kirilim.get("frozen_retest_tolerance") / kirilim.get("frozen_atr_at_break")
        ) if kirilim.get("frozen_retest_tolerance") and kirilim.get("frozen_atr_at_break") else None

        teyit_bar = etkin_barlar[teyit_idx] if teyit_idx is not None else None
        satir["teyit_bar_time"] = _bar_time(index_values, teyit_bar)
        satir["break_gecikme_bar"] = (
            int(teyit_bar) - kirilim_bar if teyit_bar is not None and kirilim_bar is not None
            else None)

        retest_barlar = [etkin_barlar[i] for i, d in enumerate(etkin_durumlar) if d in _FAZ_RETEST]
        satir["retest_var"] = "RETEST_BASARILI" in etkin_durumlar
        satir["retest_derinlik_atr"] = None
        satir["retest_gecikme_bar"] = (
            int(retest_barlar[0]) - int(teyit_bar)
            if retest_barlar and teyit_bar is not None else None)
        if retest_barlar and kirilim.get("break_snapshot_direction") is not None:
            yon = int(kirilim["break_snapshot_direction"])
            sinir = (kirilim.get("frozen_upper_boundary_at_break") if yon == 1
                     else kirilim.get("frozen_lower_boundary_at_break"))
            a_b = atr[retest_barlar[0]]
            if sinir is not None and a_b:
                if yon == 1:
                    derinlik = max(max(0.0, float(sinir) - low[b]) / a_b for b in retest_barlar)
                else:
                    derinlik = max(max(0.0, high[b] - float(sinir)) / a_b for b in retest_barlar)
                satir["retest_derinlik_atr"] = _yuvarla(derinlik)

        # --- teyit sonrası seyir (sonuç bloğu) ---
        if teyit_bar is not None and kirilim.get("break_snapshot_direction") is not None:
            yon = int(kirilim["break_snapshot_direction"])
            ref = close[int(teyit_bar)]
            a_b = atr[int(teyit_bar)]
            sonra = [b for b in etkin_barlar if b > int(teyit_bar)]
            if a_b and sonra:
                kisa = sonra[:TEYIT_PENCERESI]
                uzun = sonra[:UZUN_TEYIT_PENCERESI]
                if yon == 1:
                    satir["frm_teyit_sonrasi_mfe_atr"] = _yuvarla(max((high[b] - ref) / a_b for b in kisa))
                    satir["frm_teyit_sonrasi_mfe_uzun_atr"] = _yuvarla(max((high[b] - ref) / a_b for b in uzun))
                    satir["frm_teyit_sonrasi_mae_atr"] = _yuvarla(max((ref - low[b]) / a_b for b in kisa))
                else:
                    satir["frm_teyit_sonrasi_mfe_atr"] = _yuvarla(max((ref - low[b]) / a_b for b in kisa))
                    satir["frm_teyit_sonrasi_mfe_uzun_atr"] = _yuvarla(max((ref - low[b]) / a_b for b in uzun))
                    satir["frm_teyit_sonrasi_mae_atr"] = _yuvarla(max((high[b] - ref) / a_b for b in kisa))
        # Geçersizleşmeden ÖNCEKİ state: GECERSIZ'e İLK girişin bir öncesi.
        # `durumlar[-2]` yanıltır — motor ölü formasyonu birkaç bar taşır.
        g_idx = next((i for i, d in enumerate(durumlar) if d == "FORMASYON_GECERSIZ"), None)
        satir["frm_gecersiz_state"] = (
            durumlar[g_idx - 1] if g_idx is not None and g_idx > 0 else None)

        # --- MS: doğum ve kırılım anındaki en yakın korunan seviye ---
        satir["frm_dogum_ph_atr"] = satir["frm_dogum_pl_atr"] = satir["frm_dogum_rol_ucu"] = None
        satir["frm_kirilim_ms_uyum"] = None
        if rol_grup and fiyat_by_swing:
            ph, pl, ucu = _rol_mesafe(rol_grup, fiyat_by_swing, ilk, close[ilk], atr[ilk])
            satir["frm_dogum_ph_atr"] = _yuvarla(ph)
            satir["frm_dogum_pl_atr"] = _yuvarla(pl)
            satir["frm_dogum_rol_ucu"] = ucu
            if kirilim_bar is not None:
                _f = float(kirilim.get("break_snapshot_price") or close[kirilim_bar])
                _, _, ucu2 = _rol_mesafe(rol_grup, fiyat_by_swing, kirilim_bar, _f, atr[kirilim_bar])
                yon = kirilim.get("break_snapshot_direction")
                if ucu2 is not None and yon is not None:
                    satir["frm_kirilim_ms_uyum"] = bool(
                        (int(yon) == 1 and ucu2 == "PH") or (int(yon) == -1 and ucu2 == "PL"))

        # --- MS BOS ile aynı bar mı? (FRM-11) ---
        satir["frm_teyit_ms_bos_ayni_bar"] = None
        satir["frm_teyit_ms_bos_ayni_yon"] = None
        satir["frm_teyit_ms_bos_gecikme_bar"] = None
        if teyit_bar is not None and ms_olaylari:
            yon = kirilim.get("break_snapshot_direction")
            en_yakin = min(ms_olaylari, key=lambda x: abs(int(x[0]) - int(teyit_bar)))
            fark = int(en_yakin[0]) - int(teyit_bar)
            satir["frm_teyit_ms_bos_gecikme_bar"] = fark if abs(fark) <= 10 else None
            satir["frm_teyit_ms_bos_ayni_bar"] = bool(fark == 0)
            satir["frm_teyit_ms_bos_ayni_yon"] = bool(
                fark == 0 and yon is not None and int(en_yakin[1]) == int(yon))

        if zone_rows and kirilim_bar is not None:
            kesisim = _zone_kesisim(zone_rows, kirilim.get("break_snapshot_price"), kirilim_bar)
            satir["frm_kirilim_zone_var"] = bool(kesisim["sayi"])
            satir["frm_kirilim_ob_var"] = kesisim["ob"]
            satir["frm_kirilim_fvg_var"] = kesisim["fvg"]

        if vp_history is not None:
            for etiket, bar in (("dogum", ilk),
                                ("olgunlasma", next((etkin_barlar[i] for i, d in enumerate(etkin_durumlar)
                                                     if d == "OLGUNLASIYOR"), None)),
                                ("teyit", teyit_bar),
                                ("retest", retest_barlar[0] if retest_barlar else None)):
                if bar is None:
                    continue
                ornek = vp_ornek(vp_history, int(bar))
                satir[f"frm_vp_rvol_{etiket}"] = ornek.get("vp_rvol")
                satir[f"frm_vp_usable_{etiket}"] = ornek.get("vp_volume_usable")

        frm_satirlari.append(satir)

        # Teyit sınıflandırması EVENT TYPE ile değil STATE ile yapılır:
        # COUNTER_BREAK hem "karşı yönlü kırılım adayı" hem "karşı yönlü teyit"
        # için üretilir; tip tek başına ayırt etmez.
        teyit_oncesi = True
        for e in sorted(sid_olaylar, key=lambda x: (x.get("bar") if x.get("bar") is not None else -1)):
            if str(e.get("state") or "") == "KIRILIM_TEYITLI":
                teyit_oncesi = False
            tip = str(e.get("type") or "")
            frm_olay_satirlari.append({
                "stable_id": sid,
                "symbol": symbol,
                "timeframe": timeframe,
                "olay_type": tip,
                "olay_name": e.get("name"),
                "direction": e.get("direction"),
                "quality": _yuvarla(e.get("quality")),
                "fiyat": _yuvarla(e.get("price")),
                "bar": e.get("bar"),
                # `time` motorun indeks değeridir (normalize çerçevede int);
                # mutlak zaman `index_values` üzerinden çözülür.
                "bar_time": _bar_time(index_values, e.get("bar")),
                "state": e.get("state"),
                "teyit_oncesi": teyit_oncesi,
            })

    return frm_satirlari, frm_olay_satirlari, {
        "formasyon_sayisi": len(frm_satirlari),
        "formasyon_olay_sayisi": len(frm_olay_satirlari),
    }


#: Rapor katmanının okuyacağı kolonlar (JSONL tam satır taşır; bu liste süzmedir).
FORMASYON_KOLONLARI: tuple[str, ...] = (
    "symbol", "timeframe", "stable_id", "pattern_type", "family", "classic_dir",
    "dogum_bar_time", "omur_bar", "terminal_state", "acik", "terminal_mi", "kirilim_var",
    "frm_yakinlik_ust_fitil_atr", "frm_yakinlik_alt_fitil_atr",
    "frm_yakinlik_ust_kapanis_atr", "frm_yakinlik_alt_kapanis_atr",
    "frm_asim_ust_fitil_atr", "frm_asim_alt_fitil_atr",
    "frm_temas_ust_epizot", "frm_temas_alt_epizot",
    "frm_faz_geometri_bar", "frm_faz_kirilim_bar", "frm_faz_retest_bar",
    "frm_faz_gecis_sayisi", "frm_kirilim_deneme", "frm_teyit_deneme_no",
    "frm_kirilim_deneme_var", "upper_touches_son", "lower_touches_son",
    "frm_pivot_temas_max", "frm_pivot_ezilme_var",
    "break_snapshot_bar", "break_snapshot_price", "break_snapshot_direction",
    "break_strength", "break_volume_score", "break_confirmation_strength",
    "break_gecikme_bar", "retest_var", "retest_gecikme_bar", "retest_derinlik_atr",
    "frm_teyit_sonrasi_mfe_atr", "frm_teyit_sonrasi_mfe_uzun_atr",
    "frm_teyit_sonrasi_mae_atr", "frm_dogum_ph_atr", "frm_dogum_pl_atr",
    "frm_dogum_rol_ucu", "frm_kirilim_ms_uyum", "frm_kirilim_zone_var",
    "frm_kirilim_ob_var", "frm_kirilim_fvg_var", "frm_gecersiz_state",
    "frm_vp_rvol_dogum", "frm_vp_rvol_olgunlasma", "frm_vp_rvol_teyit",
    "frm_vp_rvol_retest",
)
