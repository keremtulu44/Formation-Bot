"""Gölge v2 simetrik (Long + Short) yarış ve nedensel çıkış simülatörü."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

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
from .surec import (
    SurecGozcusu,
    SurecGozlem,
    SurecOzeti,
    SurecPolitikasi,
    YonetimDurumu,
    surec_ozetle,
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


@dataclass(frozen=True, slots=True)
class YarisIzi:
    """Tek bir yarışın tam sonucu: çıkış + (istenirse) işlem-içi gözlem dizisi."""

    pnl_atr: float | None
    pnl_r: float | None
    neden: str
    cozulme_offset: int               # dolum barından itibaren (dolum barında çıkış = 0)
    cikis_fiyat: float | None = None
    cikis_idx: int | None = None
    gozlemler: tuple[SurecGozlem, ...] = ()
    mfe_r: float | None = None        # çıkışa kadar (çıkış dahil) en iyi R — yalnız gözcü varken
    mae_r: float | None = None        # çıkışa kadar en kötü R (pozitif büyüklük)
    mfe_bar: int | None = None
    stop_son: float | None = None     # çıkış anında geçerli stop (taşınmış olabilir)
    stop_tasindi: bool = False
    hedef_goruldu: bool = False       # hedefe değildi ama politika işlemi sürdürdü


def surecli_yaris(
    barlar: Sequence[BarDurum],
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
    dolum_bari_kapanisi: bool = False,
    risk_baz: float | None = None,
    gozcu: SurecGozcusu | None = None,
    politikalar: Sequence[SurecPolitikasi] = (),
    cikis_modu: str = "kapanis",
) -> YarisIzi:
    """Tek çıkış konfigürasyonunu bar bar yarıştırır; işlem açıkken süreci izleyebilir.

    Bir barın zaman sırası (her zaman bu sırayla, geleceğe bakmadan):

    0. Önceki kapanışta "sonraki açılışta çık" kararı verildiyse bu barın açılışında çıkılır.
    1. Bar içi (yalnız `intrabar=True`): açılış boşluğu stopu → stop → hedef. Stop ile hedef
       aynı barda ise sıra bilinmediğinden stop kazanır (muhafazakâr).
    2. Kapanış: 1-3 bar ters EXTERNAL BOS tez iptali, sonra `duvar_iptal` / `baski_iptal`,
       sonra gözcü + politikalar. Kapanış kararları bar içi hedefi EZEMEZ: hedef aynı barda
       daha önce dolmuştur.
    3. Politikanın taşıdığı stop yalnız lehe taşınır ve SONRAKİ bardan geçerlidir.

    `dolum_bari_kapanisi=True` (Mod 2): dolum, `dolum_idx` barının içinde gerçekleşti; o barın
    kapanışı işleme dahildir, bu yüzden kapanış adımı (2) dolum barında da işler. Bar içi
    stop o barda `fill_bar_stop_already_hit` ile muhafazakâr biçimde ayrıca verilir.

    `risk_baz`: R paydası. Verilmezse `|giris - stop|`. Mod 2'de açılış boşluğuyla limitten
    daha iyi fiyattan dolan emirde gerçek `|giris - stop|` sıfıra yaklaşabilir ve R'yi
    patlatır; pozisyon planlanan riske göre boyutlandığı için payda planlanan risktir.

    `cikis_modu`: politika çıkışı `"kapanis"` (sinyal barının kapanışı; iyimser) veya
    `"sonraki_acilis"` (bir sonraki barın açılışı; uygulanabilir) fiyatından yapılır.
    """
    if cikis_modu not in ("kapanis", "sonraki_acilis"):
        raise ValueError(f"Bilinmeyen cikis_modu: {cikis_modu}")
    if politikalar and gozcu is None:
        raise ValueError("Politikalar gözleme göre karar verir; gozcu zorunludur")

    n = len(barlar)
    d = 1 if yon == "long" else -1
    risk = float(risk_baz) if risk_baz is not None else abs(giris - stop)
    gozlemler: list[SurecGozlem] = []
    st = float(stop)
    hdf = hedef
    hedef_goruldu = False

    def _iz(cikis: float | None, neden: str, idx: int | None, offset: int) -> YarisIzi:
        if cikis is None:
            return YarisIzi(None, None, neden, offset)
        pnl = d * (float(cikis) - giris)
        return YarisIzi(
            pnl_atr=round(pnl / atr_baz, 4),
            pnl_r=round(pnl / risk, 4) if risk > 1e-9 else None,
            neden=neden,
            cozulme_offset=offset,
            cikis_fiyat=float(cikis),
            cikis_idx=idx,
            gozlemler=tuple(gozlemler),
            mfe_r=gozcu.mfe_r if gozcu is not None else None,
            mae_r=gozcu.mae_r if gozcu is not None else None,
            mfe_bar=gozcu.mfe_bar if gozcu is not None else None,
            stop_son=st,
            stop_tasindi=(st != float(stop)),
            hedef_goruldu=hedef_goruldu,
        )

    if fill_bar_stop_already_hit:
        cikis = float(fill_bar_stop_px if fill_bar_stop_px is not None else stop)
        if gozcu is not None:
            gozcu.cikisi_isle(cikis, 0)
        # Çıkış dolum barındadır: dolumdan itibaren 0 bar (olay barına göre ölçülmez).
        return _iz(cikis, "STOP_DOLUM_BARI", dolum_idx, 0)

    bitis_idx = min(n - 1, dolum_idx + ufuk_bar)
    sansurlu = (dolum_idx + ufuk_bar) > (n - 1)
    ilk_idx = dolum_idx if dolum_bari_kapanisi else start_scan_idx
    if dolum_idx >= n - 1 or bitis_idx < ilk_idx:
        return _iz(None, "SANSURLU", None, 0)

    durum = (
        YonetimDurumu(yon_int=d, giris=float(giris), risk=risk, atr_baz=float(atr_baz), stop_ilk=float(stop), stop=st, hedef=hdf)
        if politikalar
        else None
    )
    onceki_duvarlar: dict = {}
    baski_sayac = 0
    bekleyen_cikis: str | None = None

    for k in range(ilk_idx, bitis_idx + 1):
        b = barlar[k]
        dolum_bari = dolum_bari_kapanisi and k == dolum_idx
        cikis: float | None = None
        neden = ""
        bekleyen_stop: float | None = None
        kapanista_goruldu = False

        # 0) Önceki kapanışta verilen piyasa çıkışı: bu barın açılışı.
        if bekleyen_cikis is not None:
            cikis, neden = b.open, bekleyen_cikis
        # 1) Bar içi: boşluk -> stop -> hedef.
        elif intrabar and not dolum_bari:
            tasindi = st != float(stop)
            if d * (b.open - st) <= 0:
                cikis, neden = b.open, ("IZ_STOP_GAP" if tasindi else "STOP_GAP")
            elif d * ((b.low if d == 1 else b.high) - st) <= 0:
                cikis, neden = st, ("IZ_STOP" if tasindi else "STOP")
            elif hdf is not None and d * ((b.high if d == 1 else b.low) - hdf) >= 0:
                karar = None
                if durum is not None:
                    durum.stop, durum.hedef, durum.bar = st, hdf, b
                    karar = next(
                        (c for c in (p.hedefte(durum) for p in politikalar) if c is not None and c.hedefi_kaldir),
                        None,
                    )
                if karar is None:
                    cikis, neden = hdf, "HEDEF"
                else:
                    hedef_goruldu = True
                    durum.hedef_goruldu = True
                    hdf = None
                    bekleyen_stop = karar.yeni_stop
        elif not intrabar:
            if d * (b.close - st) <= 0:
                cikis, neden = b.close, "STOP_CLOSE"
            elif hdf is not None and d * (b.close - hdf) >= 0:
                cikis, neden = b.close, "HEDEF"

        # 2) Kapanış kararları (bar içi çıkış olmadıysa).
        if cikis is None:
            iptal_pencere = tez_iptal and (0 <= (k - dolum_idx) <= TEZ_IPTAL_BAR)
            if iptal_pencere and (b.ms_bos_down_now if d == 1 else b.ms_bos_up_now):
                cikis, neden = b.close, "TEZ_IPTAL_BOS"

        if cikis is None and duvar_iptal and not dolum_bari:
            # Önceki kapanışta mevcut bandı kullan: temas barında terminal
            # olmuş FVG dahi biliniyordu. İkinci temas aynı bandı izler.
            prev = barlar[k - 1]
            bands = prev.blok_bear if yon == "long" else prev.blok_bull
            candidates = {(z.family, z.available_index, z.lower, z.upper): z
                          for z in bands if z.height_atr >= BLOK_MIN_HEIGHT_ATR}
            candidates.update(onceki_duvarlar)
            touched = {key: z for key, z in candidates.items()
                       if _duvar_dokunuyor_mu(b, z, yon)}
            if touched.keys() & onceki_duvarlar.keys():
                cikis, neden = b.close, "DUVAR_IPTAL"
            onceki_duvarlar = touched
        if cikis is None and baski_iptal and not dolum_bari:
            if _ters_baski_mi(b, yon):
                baski_sayac += 1
                if baski_sayac >= 2:
                    cikis, neden = b.close, "BASKI_IPTAL"
            else:
                baski_sayac = 0

        if cikis is None and gozcu is not None:
            g = gozcu.gozle(k, stop=st, hedef=hdf, dolum_bari=dolum_bari)
            gozlemler.append(g)
            kapanista_goruldu = True
            if durum is not None:
                durum.stop, durum.hedef, durum.bar = st, hdf, b
                if durum.en_iyi_kapanis is None or d * (b.close - durum.en_iyi_kapanis) > 0:
                    durum.en_iyi_kapanis = b.close
                cikis_nedeni: str | None = None
                for p in politikalar:
                    karar = p.kapanista(g, durum)
                    if karar is None:
                        continue
                    if karar.yeni_stop is not None:
                        bekleyen_stop = (
                            float(karar.yeni_stop)
                            if bekleyen_stop is None
                            else (max(bekleyen_stop, float(karar.yeni_stop)) if d == 1 else min(bekleyen_stop, float(karar.yeni_stop)))
                        )
                    if karar.hedefi_kaldir:
                        hdf = None
                    if karar.cik and cikis_nedeni is None:
                        cikis_nedeni = karar.neden or p.ad.upper()
                if cikis_nedeni is not None:
                    if cikis_modu == "kapanis":
                        cikis, neden = b.close, cikis_nedeni
                    else:
                        bekleyen_cikis = cikis_nedeni

        if cikis is not None:
            if gozcu is not None and not kapanista_goruldu:
                gozcu.cikisi_isle(cikis, k - dolum_idx)
            return _iz(cikis, neden, k, k - dolum_idx)

        # 3) Taşınan stop yalnız lehe ve bir sonraki bardan itibaren geçerlidir.
        if bekleyen_stop is not None:
            st = max(st, bekleyen_stop) if d == 1 else min(st, bekleyen_stop)

    b_son = barlar[bitis_idx]
    return _iz(b_son.close, "SANSURLU" if sansurlu else "ZAMAN_STOPU", bitis_idx, bitis_idx - dolum_idx)


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
    dolum_bari_kapanisi: bool = False,
    risk_baz: float | None = None,
) -> tuple[float | None, float | None, str, int]:
    """Tek bir çıkış konfigürasyonu için (pnl_atr, pnl_r, neden, cozulme_bar_offset) döndürür.

    `surecli_yaris`'ın gözcüsüz, politikasız sığ görünümüdür; zaman sırası orada tanımlıdır.

    duvar_iptal (S07+S04): karşı OB/FVG bandına 2 ardışık bar dokunup bandı
    kapanışla aşamama (sürtünme) → kapanışta çıkış (DUVAR_IPTAL).
    baski_iptal (S11): VP baskısı 2 ardışık bar ters yönde güçlü kalırsa
    (yalnız volume_usable iken) → kapanışta çıkış (BASKI_IPTAL).
    Kapanış çıkışlarının hepsi (tez iptali dahil) stop/hedef bar içi kontrollerinden
    SONRA işler; hedef aynı barda önce gelmişse hedef kazanır.
    """
    iz = surecli_yaris(
        barlar,
        olay_bar_idx=olay_bar_idx,
        dolum_idx=dolum_idx,
        start_scan_idx=start_scan_idx,
        yon=yon,
        giris=giris,
        stop=stop,
        hedef=hedef,
        atr_baz=atr_baz,
        ufuk_bar=ufuk_bar,
        intrabar=intrabar,
        tez_iptal=tez_iptal,
        fill_bar_stop_already_hit=fill_bar_stop_already_hit,
        fill_bar_stop_px=fill_bar_stop_px,
        duvar_iptal=duvar_iptal,
        baski_iptal=baski_iptal,
        dolum_bari_kapanisi=dolum_bari_kapanisi,
        risk_baz=risk_baz,
    )
    return iz.pnl_atr, iz.pnl_r, iz.neden, iz.cozulme_offset


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


LIMIT_DOLDU: str = "DOLDU"
LIMIT_DOLMADI: str = "LIMIT_DOLMADI"
LIMIT_IPTAL_BOS: str = "LIMIT_IPTAL_BOS"


def _mod2_limit_doldur(
    barlar: tuple[BarDurum, ...],
    *,
    olay_idx: int,
    yon: str,
    limit_px: float,
    stop: float,
) -> tuple[str, int, float | None, bool, float | None]:
    """Mod 2 için 1..3 barlık limit dolum simülasyonu (muhafazakar dolum-barı stop kontrolü).

    Döndürür: (durum, dolum_idx, giris, dolum_barinda_stop, stop_fiyati).

    Emir beklerken bir bar ters EXTERNAL BOS/CHoCH ile kapanırsa tez, açık işlemde olduğu
    gibi ölmüştür: bekleyen emir iptal edilir (`LIMIT_IPTAL_BOS`). Dolum bar içinde,
    kapanıştan önce gerçekleştiği için aynı barın kapanışındaki BOS dolumu geri almaz;
    o durum dolum barı kapanışındaki tez iptaliyle yarışta ele alınır.
    """
    n = len(barlar)
    son = min(n - 1, olay_idx + MAX_BEKLEME_LIMIT)
    for k in range(olay_idx + 1, son + 1):
        b = barlar[k]
        if yon == "long":
            if b.low <= limit_px:
                giris_gercek = min(limit_px, b.open)
                stop_hit = (b.low <= stop)
                stop_px = b.open if b.open <= stop else stop
                return LIMIT_DOLDU, k, float(giris_gercek), stop_hit, float(stop_px)
            if b.ms_bos_down_now:
                return LIMIT_IPTAL_BOS, 0, None, False, None
        else:
            if b.high >= limit_px:
                giris_gercek = max(limit_px, b.open)
                stop_hit = (b.high >= stop)
                stop_px = b.open if b.open >= stop else stop
                return LIMIT_DOLDU, k, float(giris_gercek), stop_hit, float(stop_px)
            if b.ms_bos_up_now:
                return LIMIT_IPTAL_BOS, 0, None, False, None
    return LIMIT_DOLMADI, 0, None, False, None


def _islemsiz_sonuc(olay: AdayOlay, plan: PlanKartV2, ufuk_bar: int, neden: str, *, mod2_uygun: bool) -> YarisSonucuV2:
    """Pozisyon açılmayan Mod 2 sonuçları (blok yok / limit dolmadı / bekleyen emir iptal)."""
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
        neden_15_intra_iptal=neden,
        bar_15_intra_iptal=0,
        pnl_15_intra_ham_atr=None,
        pnl_15_intra_ham_r=None,
        neden_15_intra_ham=neden,
        pnl_15_close_iptal_atr=None,
        neden_15_close_iptal=neden,
        pnl_20_intra_iptal_atr=None,
        pnl_20_intra_iptal_r=None,
        neden_20_intra_iptal=neden,
        pnl_20_intra_ham_atr=None,
        pnl_20_intra_ham_r=None,
        pnl_yap_intra_iptal_atr=None,
        pnl_yap_intra_iptal_r=None,
        neden_yap_intra_iptal=neden,
        pnl_yap_intra_ham_atr=None,
        pnl_yap_intra_ham_r=None,
        neden_yap_intra_ham=neden,
        pnl_yap_close_iptal_atr=None,
        pnl_yap_close_iptal_r=None,
        neden_yap_close_iptal=neden,
        mfe_atr=None,
        mae_atr=None,
        kapanis_h_atr=None,
        sansurlu=False,
        sonuc_meta={"mod2_uygun": mod2_uygun},
        risk_r_atr=plan.risk_atr,
    )


def yarisi_yurut(
    seri: SeriVerisi,
    olay: AdayOlay,
    plan: PlanKartV2,
    *,
    ufuk_bar: int = UFUK_VARSAYILAN_BAR,
    bar_olaylari: Mapping[int, Sequence[Any]] | None = None,
    surec_izle: bool = True,
) -> YarisSonucuV2:
    """Bir plan kartını tüm çıkış ölçüm eksenlerinde (1.5 ATR, 2.0 ATR, Yapısal, Close/Intrabar, Tez İptali) yarıştırır.

    `surec_izle=True` iken birincil yarış (2.0 ATR hedef, intrabar, tez iptali açık — `net15_20_r`
    bundan türer) işlem açıkken her kapanışta gözlenir ve özeti `sonuc.surec`'e yazılır. Gözcü
    sonucu değiştirmez. `bar_olaylari` (bar indeksi -> o barda doğan aday olaylar) verilirse
    işlem sırasında sistemin kendi ürettiği lehte/karşı adaylar da kayda girer.
    """
    barlar = seri.barlar
    i = olay.bar_index
    atr_baz = olay.atr_tf
    stop = plan.stop
    mod2 = plan.mod == "mod2"

    if mod2:
        if plan.limit_fiyat is None:
            return _islemsiz_sonuc(olay, plan, ufuk_bar, "BLOK_YOK", mod2_uygun=False)
        durum, d_idx, giris_g, fill_stop, fill_stop_px = _mod2_limit_doldur(
            barlar,
            olay_idx=i,
            yon=olay.yon,
            limit_px=plan.limit_fiyat,
            stop=stop,
        )
        if durum != LIMIT_DOLDU or giris_g is None:
            return _islemsiz_sonuc(olay, plan, ufuk_bar, durum, mod2_uygun=True)
        dolum_idx = d_idx
        giris = giris_g
        # Pozisyon planlanan (limit - stop) riskine göre boyutlanır; boşlukla daha iyi fiyattan
        # dolmak riski küçültür ama R paydasını değiştirmez (aksi halde ±70R artefaktı doğar).
        risk_baz = abs(float(plan.limit_fiyat) - stop)
    else:
        dolum_idx = i
        giris = plan.giris
        fill_stop = False
        fill_stop_px = None
        risk_baz = abs(giris - stop)

    dolum_offset = dolum_idx - i
    risk_atr = abs(giris - stop) / atr_baz if atr_baz > 0 else 0.0
    risk_r_atr = risk_baz / atr_baz if atr_baz > 0 else 0.0
    sgn = 1.0 if olay.yon == "long" else -1.0
    hedef_15 = giris + sgn * 1.5 * atr_baz
    hedef_20 = giris + sgn * 2.0 * atr_baz
    hedef_yap = plan.hedef_yapisal
    if hedef_yap is not None:
        if (olay.yon == "long" and hedef_yap <= giris) or (olay.yon == "short" and hedef_yap >= giris):
            hedef_yap = None

    ortak = dict(
        olay_bar_idx=i,
        dolum_idx=dolum_idx,
        start_scan_idx=dolum_idx + 1,
        yon=olay.yon,
        giris=giris,
        stop=stop,
        atr_baz=atr_baz,
        ufuk_bar=ufuk_bar,
        risk_baz=risk_baz,
        # Mod 2'de dolum bar içindedir: o barın kapanışı işleme dahildir (kapanış stop'u,
        # tez iptali ve gözlem dolum barında da işler).
        dolum_bari_kapanisi=mod2,
    )
    bar_ici = dict(ortak, intrabar=True, fill_bar_stop_already_hit=fill_stop, fill_bar_stop_px=fill_stop_px)
    kapanis = dict(ortak, intrabar=False)

    # A. 1.5 ATR
    p15_ii_atr, p15_ii_r, n15_ii, b15_ii = _tek_yarisi_simule_et(barlar, hedef=hedef_15, tez_iptal=True, **bar_ici)
    p15_ih_atr, p15_ih_r, n15_ih, _ = _tek_yarisi_simule_et(barlar, hedef=hedef_15, tez_iptal=False, **bar_ici)
    p15_ci_atr, _, n15_ci, _ = _tek_yarisi_simule_et(barlar, hedef=hedef_15, tez_iptal=True, **kapanis)

    # B. 2.0 ATR — birincil yarış; işlem açıkken süreç gözlenir (sonucu değiştirmez).
    gozcu = (
        SurecGozcusu(
            barlar,
            yon=olay.yon,
            giris=giris,
            risk=risk_baz,
            atr_baz=atr_baz,
            tez_seviyesi=olay.zemin_tavan,
            frm_stable_id=barlar[i].frm_stable_id,
            dolum_idx=dolum_idx,
            olay_bar_idx=i,
            bar_olaylari=bar_olaylari,
            kendi_olay_id=olay.olay_id,
        )
        if surec_izle
        else None
    )
    iz20 = surecli_yaris(barlar, hedef=hedef_20, tez_iptal=True, gozcu=gozcu, **bar_ici)
    p20_ii_atr, p20_ii_r, n20_ii, b20_ii = iz20.pnl_atr, iz20.pnl_r, iz20.neden, iz20.cozulme_offset
    p20_ih_atr, p20_ih_r, _, _ = _tek_yarisi_simule_et(barlar, hedef=hedef_20, tez_iptal=False, **bar_ici)
    surec: SurecOzeti | None = None
    if gozcu is not None and iz20.pnl_r is not None and iz20.neden != "SANSURLU":
        surec = surec_ozetle(iz20.gozlemler, mfe_r=iz20.mfe_r, mae_r=iz20.mae_r, mfe_bar=iz20.mfe_bar)

    # C. Yapısal hedef (varsa)
    if hedef_yap is not None:
        py_ii_atr, py_ii_r, ny_ii, _ = _tek_yarisi_simule_et(barlar, hedef=hedef_yap, tez_iptal=True, **bar_ici)
        py_ih_atr, py_ih_r, ny_ih, _ = _tek_yarisi_simule_et(barlar, hedef=hedef_yap, tez_iptal=False, **bar_ici)
        py_ci_atr, py_ci_r, ny_ci, _ = _tek_yarisi_simule_et(barlar, hedef=hedef_yap, tez_iptal=True, **kapanis)
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
        pnl_20_intra_ham_r=p20_ih_r,
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
        sonuc_meta={"mod2_uygun": True} if mod2 else None,
        bar_20_intra_iptal=b20_ii,
        risk_r_atr=round(float(risk_r_atr), 4),
        surec=surec,
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
