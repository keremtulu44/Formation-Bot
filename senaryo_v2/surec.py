"""Gölge v2 işlem-içi süreç izleme — açık işlemin her kapanışında domainleri yeniden okur.

Sorun ("süreç içinde körlük"): yarış döngüsü dolumdan sonra yalnız OHLC'yi iki donmuş
fiyata (stop / hedef) karşılaştırıyordu. `BarDurum` her bar için Stabil, Market Structure,
formasyon, OB/FVG ve VP durumunu as-of taşıdığı hâlde bunların hiçbiri işlem sırasında
okunmuyor, kaydedilmiyordu; tek işlem-içi sinyal (1-3 bar ters EXTERNAL BOS) D7'de 648
işlemde 0 kez tetiklenmişti.

Bu modül üç parça verir:

1. `SurecGozcusu` — bar kapanışında **nedensel** gözlem (`SurecGozlem`): açık R, çıkışa
   kadar MFE/MAE, domain olay etiketleri ve tezin durumu. Yalnız o barın ve bir önceki
   kapanışın `BarDurum`'unu okur; geleceğe bakmaz.
2. Tez durumu — `TEZ_BEKLIYOR` / `TEZ_TEYITLI` / `TEZ_SINANIYOR` / `TEZ_BOZULDU`
   (sözleşme §5: "aç-kapat değil, tez yaşar veya ölür").
3. Politika kancası (`SurecPolitikasi`) — gözleme göre çıkış / stop taşıma / hedefi sürme.

Varsayılan politika YOKTUR: gözcü tek başına sonucu değiştirmez, yalnız görür ve yazar.
Her politika opt-in'dir ve `research/golge_v2_surec_olcum.py` içinde eşleşmiş replay ile
yarışır (sözleşme §5 "Korunma: önce gölge defterde yarışır, kazanan kurala girer").

Kutup uyarısı: bir olayın kutbu (`lehte` / `aleyhte`) katmanın **söylediği yöndür**,
ölçülmüş ileri beklenti değildir. Ölçüm, "aleyhte" görünen gözlemlerin çoğundan sonra
bile kalan yolun brüt beklentisinin pozitif kaldığını gösterdi; etiket tek başına çıkış
gerekçesi sayılmaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from patterns.constants import (
    ST_BREAK_CANDIDATE,
    ST_BREAK_CONFIRMED,
    ST_BREAK_FAILED,
    ST_BREAK_TIMEOUT,
    ST_COMPLETED,
    ST_RETEST_OK,
    ST_RETEST_WAIT,
    ST_RETESTING,
)

from .modeller import (
    BLOK_MIN_HEIGHT_ATR,
    VP_MAX_TERS_BASINC,
    VP_MIN_RVOL,
    BarDurum,
)

# ---------------------------------------------------------------------------
# Tez durumu
# ---------------------------------------------------------------------------
TEZ_BEKLIYOR: str = "BEKLIYOR"      # girildi, giriş gerekçesi henüz onaylanmadı
TEZ_TEYITLI: str = "TEYITLI"        # gerekçe onaylandı (kırılım teyidi / lehte yapı kırılımı)
TEZ_SINANIYOR: str = "SINANIYOR"    # fiyat tez seviyesinin ters tarafında kapattı / retest sürüyor
TEZ_BOZULDU: str = "BOZULDU"        # gerekçe çöktü (kalıcı; işlem stop görmemiş olsa da)
TEZ_KISA: dict[str, str] = {TEZ_BEKLIYOR: "B", TEZ_TEYITLI: "T", TEZ_SINANIYOR: "S", TEZ_BOZULDU: "X"}

# Tez seviyesinin ters tarafında bu kadar ARDIŞIK kapanış tezi bozar. Formasyon
# motorunun 2s/4s/1g için kullandığı geri-dönüş teyidiyle (2 bar) aynı ölçü.
SEVIYE_BOZULMA_BAR: int = 2

# ---------------------------------------------------------------------------
# Olay sözlüğü (etiket -> kutup). MS_* ve ADAY_* etiketleri sonekten çözülür.
# ---------------------------------------------------------------------------
LEHTE: int = 1
ALEYHTE: int = -1
NOTR: int = 0

OLAY_KUTBU: dict[str, int] = {
    # Formasyon yaşam döngüsü (işlemin doğduğu formasyon kimliği ve yönünde)
    "FRM_TEYIT": LEHTE,            # KIRILIM_TEYITLI
    "FRM_RETEST_OK": LEHTE,        # RETEST_BASARILI
    "FRM_RETEST_BEKLE": NOTR,      # RETEST_BEKLENIYOR
    "FRM_TAMAM": NOTR,             # FORMASYON_TAMAMLANDI (retest penceresi doldu)
    "FRM_RETEST": ALEYHTE,         # RETEST_EDILIYOR (sınıra dönüldü / içeri kapanış)
    "FRM_TEYITSIZ": ALEYHTE,       # KIRILIM_TEYIT_ALAMADI
    "FRM_BASARISIZ": ALEYHTE,      # BASARISIZ_KIRILIM
    "FRM_KARSI_KIRILIM": ALEYHTE,  # aynı formasyon ters yöne kırdı
    "FRM_KAYIP": NOTR,             # formasyon kimliği değişti / kayboldu
    # Tez seviyesi (planın `zemin_tavan` seviyesi; stop bunun 0.5 ATR ötesindedir)
    "SEVIYE_ICI": ALEYHTE,         # kapanış tez seviyesinin ters tarafında
    "SEVIYE_GERI_ALINDI": LEHTE,   # içeri kapanıştan sonra yeniden doğru tarafta kapanış
    # Stabil karşı seviye
    "SR_KARSI_RED": ALEYHTE,       # karşı Stabil çizgisine değdi, kapanışla aşamadı
    "SR_KARSI_ASILDI": LEHTE,      # karşı Stabil çizgisi kapanışla aşıldı
    # OB / FVG
    "BLOK_DUVAR": ALEYHTE,         # karşı banda değdi, kapanışla aşamadı
    "BLOK_ASILDI": LEHTE,          # karşı bant kapanışla aşıldı
    "BLOK_DESTEK_KAYBI": ALEYHTE,  # aynı yönlü bant kapanışla kaybedildi
    # Hacim katılımı
    "VP_TERS_BASKI": ALEYHTE,
    "VP_LEHTE_BASKI": LEHTE,
    "VP_DUSUK_KATILIM": NOTR,
    # Fiyat yolu
    "FIYAT_TERS_KAPANIS": ALEYHTE,
    "FIYAT_ZARARDA": ALEYHTE,      # kapanış girişin zarar tarafında
    "FIYAT_YARIM_R": LEHTE,        # çıkışa kadar ilk kez >= +0.5R görüldü
    "FIYAT_BIR_R": LEHTE,          # çıkışa kadar ilk kez >= +1R görüldü
}

_FRM_GECIS_ETIKETI: dict[str, str] = {
    ST_BREAK_CONFIRMED: "FRM_TEYIT",
    ST_RETEST_WAIT: "FRM_RETEST_BEKLE",
    ST_RETESTING: "FRM_RETEST",
    ST_RETEST_OK: "FRM_RETEST_OK",
    ST_BREAK_TIMEOUT: "FRM_TEYITSIZ",
    ST_BREAK_FAILED: "FRM_BASARISIZ",
    ST_COMPLETED: "FRM_TAMAM",
}
_FRM_KIRILIM_GIRISI = frozenset({ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED})
_FRM_TEYITLI_DURUMLAR = frozenset({ST_BREAK_CONFIRMED, ST_RETEST_WAIT, ST_RETEST_OK})
_MS_YAPI_KIRILIMI = frozenset({"BOS", "CHOCH"})


def olay_kutbu(etiket: str) -> int:
    """Etiketin kutbu: +1 lehte, -1 aleyhte, 0 nötr. Bilinmeyen etiket nötrdür."""
    kutup = OLAY_KUTBU.get(etiket)
    if kutup is not None:
        return kutup
    if etiket.startswith("ADAY_LEHTE") or etiket.endswith("_LEHTE"):
        return LEHTE
    if etiket.startswith("ADAY_KARSI") or etiket.endswith("_TERS"):
        return ALEYHTE
    return NOTR


# ---------------------------------------------------------------------------
# Gözlem
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class SurecGozlem:
    """Açık işlemin tek bir kapanmış barda gördüğü durum (nedensel, as-of)."""

    k: int                            # dolumdan sonraki kapanış sayacı (Mod 2 dolum barı kapanışı = 0)
    bar_index: int
    acik_r: float                     # kapanışa göre açık R
    mfe_r: float                      # bu kapanışa kadar görülen en iyi R (bar içi dahil)
    mae_r: float                      # bu kapanışa kadar görülen en kötü R (pozitif büyüklük)
    stop_mesafe_atr: float            # kapanıştan geçerli stopa uzaklık (ATR)
    hedef_mesafe_atr: float | None    # kapanıştan hedefe uzaklık (ATR); hedef yoksa None
    tez: str                          # TEZ_* durumu
    olaylar: tuple[str, ...]          # bu barda görülen süreç etiketleri
    lehte: int                        # bu bardaki lehte etiket sayısı
    aleyhte: int                      # bu bardaki aleyhte etiket sayısı


@dataclass(frozen=True, slots=True)
class SurecOzeti:
    """Bir yarışın işlem-içi süreç özeti (CSV satırına yazılan sığ görünüm)."""

    gozlem_n: int                 # işlem açıkken kaç kapanış görüldü (0 = ilk barda bar içi çıkış)
    mfe_r: float | None           # ÇIKIŞA KADAR en iyi R (10 barlık saf yol değil)
    mae_r: float | None           # ÇIKIŞA KADAR en kötü R (pozitif büyüklük)
    mfe_bar: int | None           # en iyi R'nin ilk görüldüğü kapanış sayacı
    tez_son: str                  # çıkıştan önceki son tez durumu ("" = hiç gözlem yok)
    tez_yolu: str                 # kapanış kapanış tez durumu, ör. "BTTSX"
    teyit_bar: int | None         # tezin ilk TEYITLI olduğu kapanış
    sinama_bar: int | None        # tezin ilk SINANIYOR olduğu kapanış
    bozulma_bar: int | None       # tezin BOZULDU olduğu kapanış
    lehte_n: int
    aleyhte_n: int
    olay_izi: str                 # "1:FRM_TEYIT,VP_LEHTE_BASKI|3:SEVIYE_ICI" biçiminde kompakt iz

    @classmethod
    def bos(cls) -> "SurecOzeti":
        return cls(0, None, None, None, "", "", None, None, None, 0, 0, "")


def surec_ozetle(
    gozlemler: Sequence[SurecGozlem],
    *,
    mfe_r: float | None,
    mae_r: float | None,
    mfe_bar: int | None,
) -> SurecOzeti:
    """Gözlem dizisini tek satırlık özete indirger; MFE/MAE çıkış barını da kapsar."""
    if not gozlemler:
        return SurecOzeti(
            0,
            round(mfe_r, 4) if mfe_r is not None else None,
            round(mae_r, 4) if mae_r is not None else None,
            mfe_bar,
            "",
            "",
            None,
            None,
            None,
            0,
            0,
            "",
        )

    def _ilk(durum: str) -> int | None:
        return next((g.k for g in gozlemler if g.tez == durum), None)

    iz = "|".join(f"{g.k}:{','.join(g.olaylar)}" for g in gozlemler if g.olaylar)
    return SurecOzeti(
        gozlem_n=len(gozlemler),
        mfe_r=round(mfe_r, 4) if mfe_r is not None else None,
        mae_r=round(mae_r, 4) if mae_r is not None else None,
        mfe_bar=mfe_bar,
        tez_son=gozlemler[-1].tez,
        tez_yolu="".join(TEZ_KISA.get(g.tez, "?") for g in gozlemler),
        teyit_bar=_ilk(TEZ_TEYITLI),
        sinama_bar=_ilk(TEZ_SINANIYOR),
        bozulma_bar=_ilk(TEZ_BOZULDU),
        lehte_n=sum(g.lehte for g in gozlemler),
        aleyhte_n=sum(g.aleyhte for g in gozlemler),
        olay_izi=iz,
    )


# ---------------------------------------------------------------------------
# Gözcü
# ---------------------------------------------------------------------------
class SurecGozcusu:
    """Tek bir açık işlemi bar kapanışlarında izleyen durumlu, nedensel gözcü.

    `gozle(idx, ...)` yalnız işlem o barın kapanışına sağ ulaştıysa çağrılmalıdır.
    Bar içi çıkışlarda (stop / hedef) çıkış barı gözlenmez; MFE/MAE'ye katkısı
    `cikisi_isle` ile ayrıca işlenir.
    """

    __slots__ = (
        "_barlar", "_d", "_giris", "_risk", "_atr", "_seviye", "_frm_id", "_dolum_idx",
        "_bar_olaylari", "_kendi_olay_id", "mfe_r", "mae_r", "mfe_bar", "_ici_seri",
        "_teyit", "_bozuldu", "_yarim_r", "_bir_r", "_frm_onceki", "_frm_kayip",
    )

    def __init__(
        self,
        barlar: Sequence[BarDurum],
        *,
        yon: str,
        giris: float,
        risk: float,
        atr_baz: float,
        tez_seviyesi: float | None,
        frm_stable_id: str,
        dolum_idx: int,
        olay_bar_idx: int | None = None,
        bar_olaylari: Mapping[int, Sequence[Any]] | None = None,
        kendi_olay_id: str = "",
    ) -> None:
        self._barlar = barlar
        self._d = 1 if yon == "long" else -1
        self._giris = float(giris)
        self._risk = max(float(risk), 1e-9)
        self._atr = max(float(atr_baz), 1e-9)
        self._seviye = float(tez_seviyesi) if tez_seviyesi is not None else None
        self._frm_id = str(frm_stable_id or "")
        self._dolum_idx = int(dolum_idx)
        self._bar_olaylari = bar_olaylari
        self._kendi_olay_id = kendi_olay_id
        self.mfe_r = 0.0
        self.mae_r = 0.0
        self.mfe_bar: int | None = None
        self._ici_seri = 0
        self._teyit = False
        self._bozuldu = False
        self._yarim_r = False
        self._bir_r = False
        # Formasyonun "önceki durumu" OLAY barındaki durumdur; geçişler buna göre ölçülür
        # (Mod 2'de olay ile dolum arasındaki geçiş, dolum barı kapanışında görülür).
        ref_idx = self._dolum_idx if olay_bar_idx is None else int(olay_bar_idx)
        baslangic = barlar[ref_idx] if 0 <= ref_idx < len(barlar) else None
        ayni_frm = baslangic is not None and bool(self._frm_id) and baslangic.frm_stable_id == self._frm_id
        self._frm_onceki = baslangic.frm_state if ayni_frm else ""
        self._frm_kayip = False
        # Gecikmiş teyitli kırılım / retest girişlerinde tez olay barında zaten teyitlidir.
        if ayni_frm and baslangic.frm_break_dir == self._d and baslangic.frm_state in _FRM_TEYITLI_DURUMLAR:
            self._teyit = True

    # -- yardımcılar ---------------------------------------------------------
    def _r(self, fiyat: float) -> float:
        return self._d * (float(fiyat) - self._giris) / self._risk

    def _uclari_isle(self, iyi_fiyat: float, kotu_fiyat: float, k: int) -> None:
        iyi = self._r(iyi_fiyat)
        kotu = -self._r(kotu_fiyat)
        if iyi > self.mfe_r:
            self.mfe_r = iyi
            self.mfe_bar = k
        if kotu > self.mae_r:
            self.mae_r = kotu

    def cikisi_isle(self, cikis_fiyat: float, k: int) -> None:
        """Bar içi çıkış fiyatını MFE/MAE'ye işler (çıkış barının geri kalanı bilinmez)."""
        self._uclari_isle(cikis_fiyat, cikis_fiyat, k)

    # -- katman okuyucuları --------------------------------------------------
    def _formasyon(self, b: BarDurum, olaylar: list[str]) -> bool:
        """Formasyon etiketlerini ekler; bu barda retest sürüyorsa True döndürür."""
        if not self._frm_id or self._frm_kayip:
            return False
        if b.frm_stable_id != self._frm_id:
            self._frm_kayip = True
            olaylar.append("FRM_KAYIP")
            return False
        durum = b.frm_state
        degisti = durum != self._frm_onceki
        self._frm_onceki = durum
        if b.frm_break_dir == self._d:
            if degisti:
                etiket = _FRM_GECIS_ETIKETI.get(durum)
                if etiket is not None:
                    olaylar.append(etiket)
            return durum == ST_RETESTING
        if b.frm_break_dir == -self._d and degisti and durum in _FRM_KIRILIM_GIRISI:
            olaylar.append("FRM_KARSI_KIRILIM")
        return False

    def _market_structure(self, b: BarDurum, olaylar: list[str]) -> tuple[bool, bool]:
        """(lehte yapı kırılımı var, ters EXTERNAL yapı kırılımı var)."""
        lehte_kirilim = False
        ters_dis_kirilim = False
        for ev in b.ms_olaylar:
            kapsam, tip, yon_s = ev.split(":")
            lehte = int(yon_s) == self._d
            olaylar.append(f"MS_{kapsam}_{tip}_{'LEHTE' if lehte else 'TERS'}")
            if tip in _MS_YAPI_KIRILIMI:
                if lehte:
                    lehte_kirilim = True
                elif kapsam == "EXT":
                    ters_dis_kirilim = True
        # `ms_olaylar` doldurulmamış (elle kurulmuş) barlarda eski bayraklar tek kaynaktır.
        if not b.ms_olaylar:
            if (b.ms_bos_down_now if self._d == 1 else b.ms_bos_up_now):
                olaylar.append("MS_EXT_BOS_TERS")
                ters_dis_kirilim = True
            if (b.ms_bos_up_now if self._d == 1 else b.ms_bos_down_now):
                olaylar.append("MS_EXT_BOS_LEHTE")
                lehte_kirilim = True
        return lehte_kirilim, ters_dis_kirilim

    def _stabil(self, b: BarDurum, olaylar: list[str]) -> None:
        seviye = b.r_level if self._d == 1 else b.s_level
        if seviye is None or not (b.low <= seviye <= b.high):
            return
        asildi = (b.close > seviye) if self._d == 1 else (b.close < seviye)
        olaylar.append("SR_KARSI_ASILDI" if asildi else "SR_KARSI_RED")

    def _bloklar(self, b: BarDurum, onceki: BarDurum, olaylar: list[str]) -> None:
        # Önceki kapanışta canlı bantlar: bu barda terminal olsa bile o an biliniyordu.
        karsi = onceki.blok_bear if self._d == 1 else onceki.blok_bull
        duvar = asildi = False
        for z in karsi:
            if z.height_atr < BLOK_MIN_HEIGHT_ATR or not (b.low <= z.upper and b.high >= z.lower):
                continue
            if (b.close >= z.upper) if self._d == 1 else (b.close <= z.lower):
                asildi = True
            else:
                duvar = True
        if duvar:
            olaylar.append("BLOK_DUVAR")
        if asildi:
            olaylar.append("BLOK_ASILDI")
        ayni = onceki.blok_bull if self._d == 1 else onceki.blok_bear
        for z in ayni:
            if z.height_atr < BLOK_MIN_HEIGHT_ATR:
                continue
            if self._d == 1 and onceki.close >= z.lower and b.close < z.lower:
                olaylar.append("BLOK_DESTEK_KAYBI")
                break
            if self._d == -1 and onceki.close <= z.upper and b.close > z.upper:
                olaylar.append("BLOK_DESTEK_KAYBI")
                break

    def _hacim(self, b: BarDurum, olaylar: list[str]) -> None:
        if not b.vp_volume_usable:
            return
        if b.vp_pressure_5 is not None:
            yonlu = self._d * float(b.vp_pressure_5)
            if yonlu < -VP_MAX_TERS_BASINC:
                olaylar.append("VP_TERS_BASKI")
            elif yonlu > VP_MAX_TERS_BASINC:
                olaylar.append("VP_LEHTE_BASKI")
        if b.vp_rvol is not None and float(b.vp_rvol) < VP_MIN_RVOL:
            olaylar.append("VP_DUSUK_KATILIM")

    def _adaylar(self, idx: int, olaylar: list[str]) -> None:
        if self._bar_olaylari is None:
            return
        gorulen: set[str] = set()
        for o in self._bar_olaylari.get(idx, ()):
            if getattr(o, "olay_id", "") == self._kendi_olay_id:
                continue
            taraf = "LEHTE" if (1 if o.yon == "long" else -1) == self._d else "KARSI"
            gorulen.add(f"ADAY_{taraf}")
            if getattr(o, "sinyal_sinifi", "") == "BIRINCIL":
                gorulen.add(f"ADAY_{taraf}_BIRINCIL")
        olaylar.extend(sorted(gorulen))

    # -- ana gözlem ----------------------------------------------------------
    def gozle(
        self,
        idx: int,
        *,
        stop: float,
        hedef: float | None,
        dolum_bari: bool = False,
    ) -> SurecGozlem:
        """Bar `idx` kapanışında gözlem üretir (işlem bu kapanışa sağ ulaşmış olmalı).

        `dolum_bari=True` (Mod 2): dolum bar içinde gerçekleşti; barın dolumdan önceki
        uçları işleme ait olmayabilir, bu yüzden MFE/MAE'ye yalnız kapanış işlenir.
        """
        b = self._barlar[idx]
        onceki = self._barlar[idx - 1] if idx > 0 else b
        k = idx - self._dolum_idx
        if dolum_bari:
            self._uclari_isle(b.close, b.close, k)
        elif self._d == 1:
            self._uclari_isle(b.high, b.low, k)
        else:
            self._uclari_isle(b.low, b.high, k)

        olaylar: list[str] = []
        retest_suruyor = self._formasyon(b, olaylar)
        lehte_kirilim, ters_dis_kirilim = self._market_structure(b, olaylar)

        icerde = False
        if self._seviye is not None:
            icerde = (b.close < self._seviye) if self._d == 1 else (b.close > self._seviye)
            if icerde:
                self._ici_seri += 1
                olaylar.append("SEVIYE_ICI")
            else:
                if self._ici_seri > 0:
                    olaylar.append("SEVIYE_GERI_ALINDI")
                self._ici_seri = 0

        self._stabil(b, olaylar)
        self._bloklar(b, onceki, olaylar)
        self._hacim(b, olaylar)
        self._adaylar(idx, olaylar)

        acik_r = self._r(b.close)
        if not dolum_bari and self._d * (b.close - onceki.close) < 0:
            olaylar.append("FIYAT_TERS_KAPANIS")
        if acik_r < 0:
            olaylar.append("FIYAT_ZARARDA")
        if not self._yarim_r and self.mfe_r >= 0.5:
            self._yarim_r = True
            olaylar.append("FIYAT_YARIM_R")
        if not self._bir_r and self.mfe_r >= 1.0:
            self._bir_r = True
            olaylar.append("FIYAT_BIR_R")

        # Tez durumu: bozulma kalıcıdır; teyit bir kez görülünce sınama bitince geri döner.
        if "FRM_TEYIT" in olaylar or "FRM_RETEST_OK" in olaylar or lehte_kirilim:
            self._teyit = True
        if "FRM_BASARISIZ" in olaylar or ters_dis_kirilim or self._ici_seri >= SEVIYE_BOZULMA_BAR:
            self._bozuldu = True
        if self._bozuldu:
            tez = TEZ_BOZULDU
        elif icerde or retest_suruyor:
            tez = TEZ_SINANIYOR
        elif self._teyit:
            tez = TEZ_TEYITLI
        else:
            tez = TEZ_BEKLIYOR

        lehte = sum(1 for e in olaylar if olay_kutbu(e) > 0)
        aleyhte = sum(1 for e in olaylar if olay_kutbu(e) < 0)
        return SurecGozlem(
            k=k,
            bar_index=idx,
            acik_r=round(acik_r, 4),
            mfe_r=round(self.mfe_r, 4),
            mae_r=round(self.mae_r, 4),
            stop_mesafe_atr=round(self._d * (b.close - float(stop)) / self._atr, 4),
            hedef_mesafe_atr=(round(self._d * (float(hedef) - b.close) / self._atr, 4) if hedef is not None else None),
            tez=tez,
            olaylar=tuple(olaylar),
            lehte=lehte,
            aleyhte=aleyhte,
        )


# ---------------------------------------------------------------------------
# Politika kancası
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class YonetimDurumu:
    """Yarış motorunun politikalara açtığı, işlem boyunca yaşayan durum."""

    yon_int: int
    giris: float
    risk: float
    atr_baz: float
    stop_ilk: float
    stop: float
    hedef: float | None
    hedef_goruldu: bool = False
    en_iyi_kapanis: float | None = None
    bar: BarDurum | None = None       # az önce kapanan bar (politikalar as-of domain okuyabilsin)
    hafiza: dict[str, Any] = field(default_factory=dict)

    def r_fiyati(self, r: float) -> float:
        """Girişe göre `r` R uzaklıktaki fiyat (lehte yön pozitif)."""
        return self.giris + self.yon_int * r * self.risk

    def atr_fiyati(self, atr: float) -> float:
        """Girişe göre `atr` ATR uzaklıktaki fiyat (lehte yön pozitif)."""
        return self.giris + self.yon_int * atr * self.atr_baz


@dataclass(frozen=True, slots=True)
class SurecKarari:
    """Bir politikanın kararı. Stop yalnız lehe taşınır ve SONRAKİ bardan geçerlidir."""

    cik: bool = False
    neden: str = ""
    yeni_stop: float | None = None
    hedefi_kaldir: bool = False


class SurecPolitikasi:
    """İşlem-içi yönetim politikası arayüzü. Varsayılan: hiçbir şey yapma (yalnız izle)."""

    ad: str = "izle"

    def kapanista(self, g: SurecGozlem, d: YonetimDurumu) -> SurecKarari | None:
        """Bar kapanışında çağrılır; `None` = karar yok."""
        return None

    def hedefte(self, d: YonetimDurumu) -> SurecKarari | None:
        """Hedefe bar içinde değildiğinde çağrılır; `None` = hedeften çık (varsayılan)."""
        return None


@dataclass(frozen=True, slots=True)
class OlaydaCik(SurecPolitikasi):
    """Verilen etiketlerden biri kapanışta görülürse çık."""

    etiketler: frozenset[str]
    neden: str
    ad: str = "olayda_cik"
    en_erken_k: int = 0

    def kapanista(self, g: SurecGozlem, d: YonetimDurumu) -> SurecKarari | None:
        if g.k >= self.en_erken_k and not self.etiketler.isdisjoint(g.olaylar):
            return SurecKarari(cik=True, neden=self.neden)
        return None


@dataclass(frozen=True, slots=True)
class TezDurumundaCik(SurecPolitikasi):
    """Tez verilen durumlardan birine girdiğinde çık."""

    durumlar: frozenset[str]
    neden: str
    ad: str = "tez_durumunda_cik"

    def kapanista(self, g: SurecGozlem, d: YonetimDurumu) -> SurecKarari | None:
        if g.tez in self.durumlar:
            return SurecKarari(cik=True, neden=self.neden)
        return None


@dataclass(frozen=True, slots=True)
class KarKoruma(SurecPolitikasi):
    """Çıkışa kadar MFE `tetik_r`'ye ulaşınca stopu `giriş + kilit_r·R`'ye çek."""

    tetik_r: float
    kilit_r: float = 0.0
    ad: str = "kar_koruma"

    def __post_init__(self) -> None:
        if self.kilit_r < 0 or self.tetik_r <= self.kilit_r:
            raise ValueError("kilit_r >= 0 ve tetik_r > kilit_r olmalı")

    def kapanista(self, g: SurecGozlem, d: YonetimDurumu) -> SurecKarari | None:
        if g.mfe_r >= self.tetik_r:
            return SurecKarari(yeni_stop=d.r_fiyati(self.kilit_r))
        return None


@dataclass(frozen=True, slots=True)
class HedefteIzSur(SurecPolitikasi):
    """Hedefe değince çıkma: hedefi kaldır, stopu `kilit_atr`'ye kilitle, sonra iz sür.

    `iz_atr` verilirse her kapanışta stop `en iyi kapanış − iz_atr·ATR`'ye (yalnız lehe)
    çekilir; verilmezse yalnız kilit kalır ve işlem ufuk sonuna kadar taşınır.
    """

    kilit_atr: float
    iz_atr: float | None = None
    ad: str = "hedefte_iz_sur"

    def hedefte(self, d: YonetimDurumu) -> SurecKarari | None:
        return SurecKarari(hedefi_kaldir=True, yeni_stop=d.atr_fiyati(self.kilit_atr))

    def kapanista(self, g: SurecGozlem, d: YonetimDurumu) -> SurecKarari | None:
        if not d.hedef_goruldu or self.iz_atr is None or d.en_iyi_kapanis is None:
            return None
        return SurecKarari(yeni_stop=d.en_iyi_kapanis - d.yon_int * self.iz_atr * d.atr_baz)


@dataclass(frozen=True, slots=True)
class HedefteYapiIzSur(SurecPolitikasi):
    """Hedefe değince çıkma: stopu kilitle, sonra iç yapının korunan seviyesini izle.

    İz seviyesi, o kapanışta Market Structure'ın bildirdiği iç korunan dip (long) /
    tepe (short) seviyesidir; `tampon_atr` kadar ötesine konur. Yapı seviyesi yoksa
    yalnız kilit kalır.

    Motorun bildirdiği seviye fiyatın TERS tarafında kalabilir (kırıldığı hâlde yeniden
    atanmamış bayat swing; düzeltilmemiş bölünme öncesinden kalan seviye — ör. fiyat 4.2
    iken "korunan dip" 15.3). Kapanışın ötesine konan stop iz sürmez, işlemi bir sonraki
    açılışta kapatır; bu yüzden yalnız kapanışın doğru tarafındaki seviye iz kabul edilir.
    """

    kilit_atr: float = 1.0
    tampon_atr: float = 0.10
    ad: str = "hedefte_yapi_iz_sur"

    def hedefte(self, d: YonetimDurumu) -> SurecKarari | None:
        return SurecKarari(hedefi_kaldir=True, yeni_stop=d.atr_fiyati(self.kilit_atr))

    def kapanista(self, g: SurecGozlem, d: YonetimDurumu) -> SurecKarari | None:
        if not d.hedef_goruldu or d.bar is None:
            return None
        seviye = d.bar.ms_int_protected_low if d.yon_int == 1 else d.bar.ms_int_protected_high
        if seviye is None:
            return None
        yeni_stop = float(seviye) - d.yon_int * self.tampon_atr * d.atr_baz
        if d.yon_int * (d.bar.close - yeni_stop) <= 0:
            return None
        return SurecKarari(yeni_stop=yeni_stop)
