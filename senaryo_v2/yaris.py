"""Gölge v2 simetrik (Long + Short) yarış ve nedensel çıkış simülatörü."""

from __future__ import annotations

import math

from .modeller import (
    BLOK_MIN_HEIGHT_ATR,
    FREN_ARDISIK_STOP,
    FREN_SOGUMA_BAR,
    MAX_BEKLEME_LIMIT,
    TEZ_IPTAL_BAR,
    UFUK_VARSAYILAN_BAR,
    VP_MAX_TERS_BASINC,
    AdayOlay,
    BarDurum,
    PlanKartV2,
    SeriVerisi,
    YarisSonucuV2,
)


def _duvar_dokunuyor_mu(b: BarDurum, z: object, yon: str) -> bool:
    """Önceki kapanışta bilinen aynı banda temas ve kapanışta aşılamama."""
    return (b.low <= z.upper and b.high >= z.lower and
            (b.close < z.upper if yon == "long" else b.close > z.lower))


def _ters_baski_mi(b: BarDurum, yon: str) -> bool:
    """S11: VP baskısı ters yönde güçlü mü? (yalnız volume_usable iken)."""
    if not b.vp_volume_usable or b.vp_pressure_5 is None:
        return False
    p5 = float(b.vp_pressure_5)
    if yon == "long":
        return p5 < -VP_MAX_TERS_BASINC
    return p5 > VP_MAX_TERS_BASINC


def _tek_yarisi_simule_et(
    barlar: tuple[BarDurum, ...],
    *,
    olay_bar_idx: int,
    dolum_idx: int,
    start_scan_idx: int,
    yon: str,
    giris: float,
    stop: float,
    hedef: float | None,
    atr_baz: float,
    ufuk_bar: int,
    intrabar: bool,
    tez_iptal: bool,
    fill_bar_stop_already_hit: bool = False,
    fill_bar_stop_px: float | None = None,
    duvar_iptal: bool = False,
    baski_iptal: bool = False,
) -> tuple[float | None, float | None, str, int]:
    """Tek bir çıkış konfigürasyonu için (pnl_atr, pnl_r, neden, cozulme_bar_offset) döndürür.

    duvar_iptal (S07+S04): karşı OB/FVG bandına 2 ardışık bar dokunup bandı
    kapanışla aşamama (sürtünme) → kapanışta çıkış (DUVAR_IPTAL).
    baski_iptal (S11): VP baskısı 2 ardışık bar ters yönde güçlü kalırsa
    (yalnız volume_usable iken) → kapanışta çıkış (BASKI_IPTAL).
    Her ikisi de stop/hedef intrabar kontrollerinden SONRA (kapanışta) işler;
    hedef aynı barda önce gelmişse hedef kazanır.
    """
    n = len(barlar)
    risk = abs(giris - stop)
    if fill_bar_stop_already_hit:
        cikis = float(fill_bar_stop_px if fill_bar_stop_px is not None else stop)
        pnl = (cikis - giris) if yon == "long" else (giris - cikis)
        return (
            round(pnl / atr_baz, 4),
            round(pnl / risk, 4) if risk > 1e-9 else None,
            "STOP_DOLUM_BARI",
            dolum_idx - olay_bar_idx,
        )

    bitis_idx = min(n - 1, dolum_idx + ufuk_bar)
    sansurlu = (dolum_idx + ufuk_bar) > (n - 1)
    if dolum_idx >= n - 1 or bitis_idx < start_scan_idx:
        return None, None, "SANSURLU", 0

    onceki_duvarlar = {}
    baski_sayac = 0
    for k in range(start_scan_idx, bitis_idx + 1):
        b = barlar[k]
        iptal_pencere = tez_iptal and (1 <= (k - olay_bar_idx) <= TEZ_IPTAL_BAR)

        cikis: float | None = None
        neden = ""

        if intrabar:
            if yon == "long":
                if b.open <= stop:
                    cikis, neden = b.open, "STOP_GAP"
                elif b.low <= stop:
                    cikis, neden = stop, "STOP"
                elif iptal_pencere and b.ms_bos_down_now:
                    cikis, neden = b.close, "TEZ_IPTAL_BOS"
                elif hedef is not None and b.high >= hedef:
                    cikis, neden = hedef, "HEDEF"
            else:
                if b.open >= stop:
                    cikis, neden = b.open, "STOP_GAP"
                elif b.high >= stop:
                    cikis, neden = stop, "STOP"
                elif iptal_pencere and b.ms_bos_up_now:
                    cikis, neden = b.close, "TEZ_IPTAL_BOS"
                elif hedef is not None and b.low <= hedef:
                    cikis, neden = hedef, "HEDEF"
        else:
            if yon == "long":
                if b.close <= stop:
                    cikis, neden = b.close, "STOP_CLOSE"
                elif iptal_pencere and b.ms_bos_down_now:
                    cikis, neden = b.close, "TEZ_IPTAL_BOS"
                elif hedef is not None and b.close >= hedef:
                    cikis, neden = b.close, "HEDEF"
            else:
                if b.close >= stop:
                    cikis, neden = b.close, "STOP_CLOSE"
                elif iptal_pencere and b.ms_bos_up_now:
                    cikis, neden = b.close, "TEZ_IPTAL_BOS"
                elif hedef is not None and b.close <= hedef:
                    cikis, neden = b.close, "HEDEF"

        # İşlem-içi iptal: yalnız stop/hedef/tez bu barda tetiklenmediyse (kapanışta).
        if cikis is None and duvar_iptal:
            # Önceki kapanışta mevcut bandı kullan: temas barında terminal
            # olmuş FVG dahi biliniyordu. İkinci temas aynı bandı izler.
            prev = barlar[k - 1]
            bands = prev.blok_bear if yon == "long" else prev.blok_bull
            candidates = { (z.family, z.available_index, z.lower, z.upper): z
                          for z in bands if z.height_atr >= BLOK_MIN_HEIGHT_ATR }
            candidates.update(onceki_duvarlar)
            touched = {key: z for key, z in candidates.items()
                       if _duvar_dokunuyor_mu(b, z, yon)}
            if touched.keys() & onceki_duvarlar.keys():
                cikis, neden = b.close, "DUVAR_IPTAL"
            onceki_duvarlar = touched
        if cikis is None and baski_iptal:
            if _ters_baski_mi(b, yon):
                baski_sayac += 1
                if baski_sayac >= 2:
                    cikis, neden = b.close, "BASKI_IPTAL"
            else:
                baski_sayac = 0

        if cikis is not None:
            pnl = (cikis - giris) if yon == "long" else (giris - cikis)
            return (
                round(pnl / atr_baz, 4),
                round(pnl / risk, 4) if risk > 1e-9 else None,
                neden,
                k - dolum_idx,
            )

    b_son = barlar[bitis_idx]
    pnl = (b_son.close - giris) if yon == "long" else (giris - b_son.close)
    neden_son = "SANSURLU" if sansurlu else "ZAMAN_STOPU"
    return (
        round(pnl / atr_baz, 4),
        round(pnl / risk, 4) if risk > 1e-9 else None,
        neden_son,
        bitis_idx - dolum_idx,
    )


def _saf_yol_metrikleri(
    barlar: tuple[BarDurum, ...],
    *,
    dolum_idx: int,
    yon: str,
    giris: float,
    atr_baz: float,
    ufuk_bar: int,
) -> tuple[float | None, float | None, float | None, bool]:
    """Stopsuz/hedefsiz saf H-barlık MFE, MAE ve H-kapanış ATR getirisi."""
    n = len(barlar)
    sansurlu = (dolum_idx + ufuk_bar) > (n - 1)
    if dolum_idx >= n - 1:
        return None, None, None, True
    bitis_idx = min(n - 1, dolum_idx + ufuk_bar)
    pencere = barlar[dolum_idx + 1 : bitis_idx + 1]
    if not pencere:
        return None, None, None, True

    if yon == "long":
        max_fav = max((b.high - giris) for b in pencere)
        max_adv = max((giris - b.low) for b in pencere)
        kap_ret = barlar[bitis_idx].close - giris
    else:
        max_fav = max((giris - b.low) for b in pencere)
        max_adv = max((b.high - giris) for b in pencere)
        kap_ret = giris - barlar[bitis_idx].close

    return (
        round(max_fav / atr_baz, 4),
        round(max_adv / atr_baz, 4),
        round(kap_ret / atr_baz, 4),
        sansurlu,
    )


def _mod2_limit_doldur(
    barlar: tuple[BarDurum, ...],
    *,
    olay_idx: int,
    yon: str,
    limit_px: float,
    stop: float,
) -> tuple[bool, int, float | None, bool, float | None]:
    """Mod 2 için 1..3 barlık limit dolum simülasyonu (muhafazakar dolum-barı stop kontrolü)."""
    n = len(barlar)
    son = min(n - 1, olay_idx + MAX_BEKLEME_LIMIT)
    for k in range(olay_idx + 1, son + 1):
        b = barlar[k]
        if yon == "long":
            if b.low <= limit_px:
                giris_gercek = min(limit_px, b.open)
                stop_hit = (b.low <= stop)
                stop_px = b.open if b.open <= stop else stop
                return True, k, float(giris_gercek), stop_hit, float(stop_px)
        else:
            if b.high >= limit_px:
                giris_gercek = max(limit_px, b.open)
                stop_hit = (b.high >= stop)
                stop_px = b.open if b.open >= stop else stop
                return True, k, float(giris_gercek), stop_hit, float(stop_px)
    return False, 0, None, False, None


def yarisi_yurut(
    seri: SeriVerisi,
    olay: AdayOlay,
    plan: PlanKartV2,
    *,
    ufuk_bar: int = UFUK_VARSAYILAN_BAR,
) -> YarisSonucuV2:
    """Bir plan kartını tüm çıkış ölçüm eksenlerinde (1.5 ATR, 2.0 ATR, Yapısal, Close/Intrabar, Tez İptali) yarıştırır."""
    barlar = seri.barlar
    i = olay.bar_index
    atr_baz = olay.atr_tf

    if plan.mod == "mod2":
        if plan.limit_fiyat is None:
            return YarisSonucuV2(
                olay_id=olay.olay_id,
                mod=plan.mod,
                tampon_atr=plan.tampon_atr,
                ufuk_bar=ufuk_bar,
                dolduruldu=False,
                dolum_bar_offset=0,
                giris_gercek=None,
                stop_gercek=plan.stop,
                risk_gercek_atr=plan.risk_atr,
                pnl_15_intra_iptal_atr=None,
                pnl_15_intra_iptal_r=None,
                neden_15_intra_iptal="BLOK_YOK",
                bar_15_intra_iptal=0,
                pnl_15_intra_ham_atr=None,
                pnl_15_intra_ham_r=None,
                neden_15_intra_ham="BLOK_YOK",
                pnl_15_close_iptal_atr=None,
                neden_15_close_iptal="BLOK_YOK",
                pnl_20_intra_iptal_atr=None,
                pnl_20_intra_iptal_r=None,
                neden_20_intra_iptal="BLOK_YOK",
                pnl_20_intra_ham_atr=None,
                pnl_20_intra_ham_r=None,
                pnl_yap_intra_iptal_atr=None,
                pnl_yap_intra_iptal_r=None,
                neden_yap_intra_iptal="BLOK_YOK",
                pnl_yap_intra_ham_atr=None,
                pnl_yap_intra_ham_r=None,
                neden_yap_intra_ham="BLOK_YOK",
                pnl_yap_close_iptal_atr=None,
                pnl_yap_close_iptal_r=None,
                neden_yap_close_iptal="BLOK_YOK",
                mfe_atr=None,
                mae_atr=None,
                kapanis_h_atr=None,
                sansurlu=False,
                sonuc_meta={"mod2_uygun": False},
            )
        doldu, d_idx, giris_g, fill_stop, fill_stop_px = _mod2_limit_doldur(
            barlar,
            olay_idx=i,
            yon=olay.yon,
            limit_px=plan.limit_fiyat,
            stop=plan.stop,
        )
        if not doldu or giris_g is None:
            return YarisSonucuV2(
                olay_id=olay.olay_id,
                mod=plan.mod,
                tampon_atr=plan.tampon_atr,
                ufuk_bar=ufuk_bar,
                dolduruldu=False,
                dolum_bar_offset=0,
                giris_gercek=None,
                stop_gercek=plan.stop,
                risk_gercek_atr=plan.risk_atr,
                pnl_15_intra_iptal_atr=None,
                pnl_15_intra_iptal_r=None,
                neden_15_intra_iptal="LIMIT_DOLMADI",
                bar_15_intra_iptal=0,
                pnl_15_intra_ham_atr=None,
                pnl_15_intra_ham_r=None,
                neden_15_intra_ham="LIMIT_DOLMADI",
                pnl_15_close_iptal_atr=None,
                neden_15_close_iptal="LIMIT_DOLMADI",
                pnl_20_intra_iptal_atr=None,
                pnl_20_intra_iptal_r=None,
                neden_20_intra_iptal="LIMIT_DOLMADI",
                pnl_20_intra_ham_atr=None,
                pnl_20_intra_ham_r=None,
                pnl_yap_intra_iptal_atr=None,
                pnl_yap_intra_iptal_r=None,
                neden_yap_intra_iptal="LIMIT_DOLMADI",
                pnl_yap_intra_ham_atr=None,
                pnl_yap_intra_ham_r=None,
                neden_yap_intra_ham="LIMIT_DOLMADI",
                pnl_yap_close_iptal_atr=None,
                pnl_yap_close_iptal_r=None,
                neden_yap_close_iptal="LIMIT_DOLMADI",
                mfe_atr=None,
                mae_atr=None,
                kapanis_h_atr=None,
                sansurlu=False,
                sonuc_meta={"mod2_uygun": True},
            )
        dolum_idx = d_idx
        start_scan_idx = d_idx + 1
        giris = giris_g
        dolum_offset = d_idx - i
    else:
        dolum_idx = i
        start_scan_idx = i + 1
        giris = plan.giris
        dolum_offset = 0
        fill_stop = False
        fill_stop_px = None

    stop = plan.stop
    risk_atr = abs(giris - stop) / atr_baz if atr_baz > 0 else 0.0
    sgn = 1.0 if olay.yon == "long" else -1.0
    hedef_15 = giris + sgn * 1.5 * atr_baz
    hedef_20 = giris + sgn * 2.0 * atr_baz
    hedef_yap = plan.hedef_yapisal
    if hedef_yap is not None:
        if (olay.yon == "long" and hedef_yap <= giris) or (olay.yon == "short" and hedef_yap >= giris):
            hedef_yap = None

    # A. 1.5 ATR
    p15_ii_atr, p15_ii_r, n15_ii, b15_ii = _tek_yarisi_simule_et(
        barlar,
        olay_bar_idx=i,
        dolum_idx=dolum_idx,
        start_scan_idx=start_scan_idx,
        yon=olay.yon,
        giris=giris,
        stop=stop,
        hedef=hedef_15,
        atr_baz=atr_baz,
        ufuk_bar=ufuk_bar,
        intrabar=True,
        tez_iptal=True,
        fill_bar_stop_already_hit=fill_stop,
        fill_bar_stop_px=fill_stop_px,
    )
    p15_ih_atr, p15_ih_r, n15_ih, _ = _tek_yarisi_simule_et(
        barlar,
        olay_bar_idx=i,
        dolum_idx=dolum_idx,
        start_scan_idx=start_scan_idx,
        yon=olay.yon,
        giris=giris,
        stop=stop,
        hedef=hedef_15,
        atr_baz=atr_baz,
        ufuk_bar=ufuk_bar,
        intrabar=True,
        tez_iptal=False,
        fill_bar_stop_already_hit=fill_stop,
        fill_bar_stop_px=fill_stop_px,
    )
    p15_ci_atr, _, n15_ci, _ = _tek_yarisi_simule_et(
        barlar,
        olay_bar_idx=i,
        dolum_idx=dolum_idx,
        start_scan_idx=start_scan_idx,
        yon=olay.yon,
        giris=giris,
        stop=stop,
        hedef=hedef_15,
        atr_baz=atr_baz,
        ufuk_bar=ufuk_bar,
        intrabar=False,
        tez_iptal=True,
    )

    # B. 2.0 ATR
    p20_ii_atr, p20_ii_r, n20_ii, _ = _tek_yarisi_simule_et(
        barlar,
        olay_bar_idx=i,
        dolum_idx=dolum_idx,
        start_scan_idx=start_scan_idx,
        yon=olay.yon,
        giris=giris,
        stop=stop,
        hedef=hedef_20,
        atr_baz=atr_baz,
        ufuk_bar=ufuk_bar,
        intrabar=True,
        tez_iptal=True,
        fill_bar_stop_already_hit=fill_stop,
        fill_bar_stop_px=fill_stop_px,
    )
    p20_ih_atr, n20_ih_r, _, _ = _tek_yarisi_simule_et(
        barlar,
        olay_bar_idx=i,
        dolum_idx=dolum_idx,
        start_scan_idx=start_scan_idx,
        yon=olay.yon,
        giris=giris,
        stop=stop,
        hedef=hedef_20,
        atr_baz=atr_baz,
        ufuk_bar=ufuk_bar,
        intrabar=True,
        tez_iptal=False,
        fill_bar_stop_already_hit=fill_stop,
        fill_bar_stop_px=fill_stop_px,
    )

    # C. Yapısal hedef (varsa)
    if hedef_yap is not None:
        py_ii_atr, py_ii_r, ny_ii, _ = _tek_yarisi_simule_et(
            barlar,
            olay_bar_idx=i,
            dolum_idx=dolum_idx,
            start_scan_idx=start_scan_idx,
            yon=olay.yon,
            giris=giris,
            stop=stop,
            hedef=hedef_yap,
            atr_baz=atr_baz,
            ufuk_bar=ufuk_bar,
            intrabar=True,
            tez_iptal=True,
            fill_bar_stop_already_hit=fill_stop,
            fill_bar_stop_px=fill_stop_px,
        )
        py_ih_atr, py_ih_r, ny_ih, _ = _tek_yarisi_simule_et(
            barlar,
            olay_bar_idx=i,
            dolum_idx=dolum_idx,
            start_scan_idx=start_scan_idx,
            yon=olay.yon,
            giris=giris,
            stop=stop,
            hedef=hedef_yap,
            atr_baz=atr_baz,
            ufuk_bar=ufuk_bar,
            intrabar=True,
            tez_iptal=False,
            fill_bar_stop_already_hit=fill_stop,
            fill_bar_stop_px=fill_stop_px,
        )
        py_ci_atr, py_ci_r, ny_ci, _ = _tek_yarisi_simule_et(
            barlar,
            olay_bar_idx=i,
            dolum_idx=dolum_idx,
            start_scan_idx=start_scan_idx,
            yon=olay.yon,
            giris=giris,
            stop=stop,
            hedef=hedef_yap,
            atr_baz=atr_baz,
            ufuk_bar=ufuk_bar,
            intrabar=False,
            tez_iptal=True,
        )
    else:
        py_ii_atr = py_ii_r = py_ih_atr = py_ih_r = py_ci_atr = py_ci_r = None
        ny_ii = ny_ih = ny_ci = "HEDEF_YOK"

    mfe, mae, kap_h, sansurlu = _saf_yol_metrikleri(
        barlar,
        dolum_idx=dolum_idx,
        yon=olay.yon,
        giris=giris,
        atr_baz=atr_baz,
        ufuk_bar=ufuk_bar,
    )

    return YarisSonucuV2(
        olay_id=olay.olay_id,
        mod=plan.mod,
        tampon_atr=plan.tampon_atr,
        ufuk_bar=ufuk_bar,
        dolduruldu=True,
        dolum_bar_offset=dolum_offset,
        giris_gercek=float(giris),
        stop_gercek=float(stop),
        risk_gercek_atr=round(float(risk_atr), 4),
        pnl_15_intra_iptal_atr=p15_ii_atr,
        pnl_15_intra_iptal_r=p15_ii_r,
        neden_15_intra_iptal=n15_ii,
        bar_15_intra_iptal=b15_ii,
        pnl_15_intra_ham_atr=p15_ih_atr,
        pnl_15_intra_ham_r=p15_ih_r,
        neden_15_intra_ham=n15_ih,
        pnl_15_close_iptal_atr=p15_ci_atr,
        neden_15_close_iptal=n15_ci,
        pnl_20_intra_iptal_atr=p20_ii_atr,
        pnl_20_intra_iptal_r=p20_ii_r,
        neden_20_intra_iptal=n20_ii,
        pnl_20_intra_ham_atr=p20_ih_atr,
        pnl_20_intra_ham_r=n20_ih_r,
        pnl_yap_intra_iptal_atr=py_ii_atr,
        pnl_yap_intra_iptal_r=py_ii_r,
        neden_yap_intra_iptal=ny_ii,
        pnl_yap_intra_ham_atr=py_ih_atr,
        pnl_yap_intra_ham_r=py_ih_r,
        neden_yap_intra_ham=ny_ih,
        pnl_yap_close_iptal_atr=py_ci_atr,
        pnl_yap_close_iptal_r=py_ci_r,
        neden_yap_close_iptal=ny_ci,
        mfe_atr=mfe,
        mae_atr=mae,
        kapanis_h_atr=kap_h,
        sansurlu=sansurlu,
        sonuc_meta={"mod2_uygun": True} if plan.mod == "mod2" else None,
    )


def fren_etiketle(
    olaylar: list[AdayOlay],
    sonuclar_by_id: dict[str, YarisSonucuV2],
    *,
    yalniz_kapilar_acik: bool = True,
) -> dict[str, bool]:
    """Nedensel 3-ardışık stop frenini hesaplar: yalnız olay anında KAPANMIŞ işlemlerden sayar."""
    ardisik_stop = 0
    fren_bitis_bar = -1
    kapanis_kuyrugu: list[tuple[int, bool]] = []  # (exit_bar, is_stop)
    etiket: dict[str, bool] = {}

    for olay in sorted(olaylar, key=lambda o: o.bar_index):
        if yalniz_kapilar_acik and not olay.tum_kapilar_ok:
            etiket[olay.olay_id] = False
            continue

        # Yalnız olay.bar_index anında veya öncesinde KAPANMIŞ işlemleri işle (anti-lookahead)
        kalan: list[tuple[int, bool]] = []
        yeni_kapanan: list[tuple[int, bool]] = []
        for exit_bar, is_stop in kapanis_kuyrugu:
            if exit_bar <= olay.bar_index:
                yeni_kapanan.append((exit_bar, is_stop))
            else:
                kalan.append((exit_bar, is_stop))
        kapanis_kuyrugu = kalan
        for exit_bar, is_stop in sorted(yeni_kapanan, key=lambda x: x[0]):
            if is_stop:
                ardisik_stop += 1
                if ardisik_stop >= FREN_ARDISIK_STOP:
                    fren_bitis_bar = max(fren_bitis_bar, exit_bar + FREN_SOGUMA_BAR)
                    ardisik_stop = 0
            else:
                ardisik_stop = 0

        frende_mi = olay.bar_index <= fren_bitis_bar
        etiket[olay.olay_id] = frende_mi

        if not frende_mi:
            sonuc = sonuclar_by_id.get(olay.olay_id)
            if sonuc is not None and sonuc.dolduruldu and sonuc.neden_15_intra_iptal != "SANSURLU":
                exit_bar = olay.bar_index + sonuc.dolum_bar_offset + sonuc.bar_15_intra_iptal
                is_stop = sonuc.neden_15_intra_iptal.startswith("STOP")
                kapanis_kuyrugu.append((exit_bar, is_stop))

    return etiket
