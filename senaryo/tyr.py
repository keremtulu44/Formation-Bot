"""TYR — Toplu Yeniden Yorum: **saf** hükmü fonksiyonu (G4).

Girdi değimezse çıktı değişmez; çerçeve/fiyat okumaz — tüm sayılar girdide
gelir. Kural seti plan belgesinde önceden kayıtlıdır (§3, §5):

* **RET**  — zemin BREACHED/BELOW_FLOOR (tez seviyesi öldü) veya planda
  taze karşıt BOS/CHOCH geldi (tez iptali).
* **UYGUN** — kapı açık + taze karşıt yok + olgunluk (desteğe mesafe ≤ 1 ATR
  veya formasyon olgun) + çelişki ≤ 1.
* **BEKLE** — geri kalan her şey (sessizlik varsayılandır).

Çıktı: ``Hukum`` — tek satır hüküm + kanıt sayacı; sıfat yok.
"""

from __future__ import annotations

from dataclasses import dataclass

from .modeller import Hukum
from .zincir import G1Durum, G2Durum, MSUyari

MESAFE_ESIGI_ATR = 1.0     # plan §3: seviyeye ≤ 1 ATR → olgunluk
CELLIKKI_TAVANI = 1        # 2+ çelişki → BEKLE (sığ kapı)


@dataclass(frozen=True, slots=True)
class TyrDurum:
    """TYR'nin saf girdisi — as-of, ≤ t verisinden türetilmiş sayılar."""

    sembol: str
    tf: str
    t: str
    g1: G1Durum
    ms: tuple[MSUyari, ...] = ()
    g2: G2Durum = G2Durum()
    planda: bool = False          # açık plan/tez var mı (iptal kuralı için)
    ek_celiski: int = 0           # diğer ölçülen çelişkiler (ör. karakter tersi)
    olgunluk_genis: bool = False  # B5 (FAZ9): zenginlik-köprüsü ile olgunluk


def tyr_hukmu(d: TyrDurum) -> Hukum:
    g1 = d.g1
    taze_karsi = [u for u in d.ms if u.taze and u.yon == "down"]
    taze_destekleyen = [u for u in d.ms if u.taze and u.yon == "up"]

    # --- RET: tez öldü ------------------------------------------------------
    if g1.kapali:
        return Hukum(
            sembol=d.sembol, tf=d.tf, t=d.t, hukum="RET",
            lehte=0, celisi=len(taze_karsi) + 1,
            gerekce=f"G1 kapandi: zemin {g1.zemin} — tez seviyesi öldü",
        )
    if d.planda and taze_karsi:
        return Hukum(
            sembol=d.sembol, tf=d.tf, t=d.t, hukum="RET",
            lehte=0, celisi=len(taze_karsi),
            gerekce=f"planda ters yapı: {taze_karsi[0].tip} {taze_karsi[0].yas_bar} bar önce",
        )

    # --- sayaçlar -----------------------------------------------------------
    lehte = 0
    if g1.kapi_acik:
        lehte += 1
    if not taze_karsi:
        lehte += 1
    mesafe = g1.mesafe_atr
    olgunluk = (mesafe is not None and mesafe <= MESAFE_ESIGI_ATR) or (
        d.g2.aktif and d.g2.olgun
    )
    # B5 (FAZ9, opt-in §9): zenginlik-köprüsü — onaylı zemin + taze MS desteği
    # birlikte olgunluk kapısını açar (yalnız UYGUN hücresi; RET/bekle değişmez).
    if d.olgunluk_genis and g1.onayli and taze_destekleyen:
        olgunluk = True
    if olgunluk:
        lehte += 1
    if g1.onayli:
        lehte += 1
    if taze_destekleyen:
        lehte += 1
    celisi = len(taze_karsi) + max(0, d.ek_celiski)

    # --- BEKLE: kapı kapalı / uyarı sürüyor / çelişki -----------------------
    if not g1.kapi_acik:
        return Hukum(
            sembol=d.sembol, tf=d.tf, t=d.t, hukum="BEKLE",
            lehte=lehte, celisi=celisi,
            gerekce=f"G1 kapisi kapali (zemin {g1.zemin}) — motor susar",
        )
    if taze_karsi:
        return Hukum(
            sembol=d.sembol, tf=d.tf, t=d.t, hukum="BEKLE",
            lehte=lehte, celisi=celisi,
            gerekce=f"taze karsi uyari suruyor ({len(taze_karsi)} olay)",
        )
    if celisi > CELLIKKI_TAVANI:
        return Hukum(
            sembol=d.sembol, tf=d.tf, t=d.t, hukum="BEKLE",
            lehte=lehte, celisi=celisi,
            gerekce=f"celiski {celisi} > {CELLIKKI_TAVANI}",
        )

    # --- UYGUN: kapı açık + uyarı yok + olgunluk ---------------------------
    if olgunluk:
        return Hukum(
            sembol=d.sembol, tf=d.tf, t=d.t, hukum="UYGUN",
            lehte=lehte, celisi=celisi,
            gerekce=(f"G1 {g1.zemin}, mesafe "
                     f"{f'{mesafe:.2f} ATR' if mesafe is not None else 'bilinmiyor'}, "
                     f"taze karsi 0"),
        )

    return Hukum(
        sembol=d.sembol, tf=d.tf, t=d.t, hukum="BEKLE",
        lehte=lehte, celisi=celisi,
        gerekce="olgunluk yok: desteğe mesafe > 1 ATR ve formasyon olgun değil",
    )
