"""Eğitim kareleri + lejant dili + ◇ ikinci tur — tek sayfalık özet pano (2026-11-08).

NE ÜRETİR
---------
`docs/gorseller/ok_egitim_lejant_2026_11_08/`
  * `01_egitim_karesi_garan.png` — replay/eğitim karesi; direnç katmanı (▼) çizili
  * `00_pano.png`                — tek sayfa: lejant önce/sonra · kare · ◇ eğrisi

KAYNAKLAR
---------
* Lejant "ÖNCE" satırları: HEAD (75d5214) `grafik/panels.py` ile aynı karelerden
  üretildi (`_kare` + `grafik.ciz` → `meta["metin"]["lejant"]`); metinler burada
  birebir saklandı ki pano kod değişmeden yeniden üretilebilsin.
* Lejant "SONRA" satırları: script çalışırken CANLI koddan üretilir.
* ◇ eğrisi: `research/stabil_cizgi_seyreltme_olcum.py` çıktıları
  (`/tmp/ok_cizgi_ikinci_tur.csv`) — yoksa ölçümü önce çalıştırın.

REPLAY
------
    PYTHONPATH=. .venv/bin/python research/stabil_cizgi_seyreltme_olcum.py
    PYTHONPATH=. .venv/bin/python research/ok_egitim_ozet_pano.py
"""
from __future__ import annotations

import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch

import grafik
from research.replay_egitim import _soru_goruntusu, soru_sec
from research.stabil_ok_ornek_gorseller import _kare

CIKTI = "docs/gorseller/ok_egitim_lejant_2026_11_08"
ZEMIN, METIN, SOLUK = "#0d1117", "#e6edf3", "#8b949e"
YESIL, TURUNCU, VURGU = "#3fb950", "#f0883e", "#58a6ff"

# HEAD (75d5214) koduyla üretilmiş lejant satırları — bkz. docstring.
ONCE = {
    "AGHOL": "kapanmış mum · yeşil boş = yükselen · kırmızı dolu = düşen · "
             "┄ Stabil direnç · ▼ direnç dönüşü (turuncu) · ▽ direnç momentumu (turuncu) · "
             "┄ BOS dış · kutular: OB FVG · ▨ dolan kısım · ┈ %50 ortası · "
             "şerit: rvol(20) · yerel hesap · yapı: BOS/CHoCH dış",
    "GARAN": "kapanmış mum · yeşil boş = yükselen · kırmızı dolu = düşen · "
             "┄ Stabil direnç · ┈ CHoCH dış · ┄ BOS dış · ┈ seviye (PH/PL/WH/WL sağda)",
}
ONCE_ATLANAN = {"AGHOL": 0, "GARAN": 6}

# ◇ sayıları: 3 bar ve 10 bar geçmiş ölçüm (§10.3), gerisi bu turun ölçümü.
EGRI = [(3, 737, "eski"), (10, 591, "§10"), (20, 486, "bugün"), (30, 433, "S1"),
        (40, 396, "S2"), (50, 364, "S6"), (60, 335, "S7")]
ESIK = 389


def _kutu(ax, x, y, w, h, *, kenar, yuz="none"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                linewidth=1.1, edgecolor=kenar, facecolor=yuz,
                                transform=ax.transAxes, clip_on=False))


def lejant_sonra(sembol: str, gun: str) -> tuple[str, int]:
    snap = _kare(sembol, gun)
    _, meta = grafik.ciz(snap, "1d", secenekler={
        "cikti": f"/tmp/_pano_{sembol}.png", "etiket_detay": False, "serit": None})
    lej = meta["metin"]["lejant"]
    lej = lej if isinstance(lej, list) else [lej]
    return " ".join(lej), int(meta["lejant_atlanan"])


def egitim_karesi() -> tuple[str, dict]:
    s = soru_sec("GARAN")
    snap = _soru_goruntusu(s, "1d")
    yol = os.path.join(CIKTI, "01_egitim_karesi_garan.png")
    _, meta = grafik.ciz(snap, "1d", secenekler={"cikti": yol, "etiket_detay": False})
    direnc = (meta["cizgiler"] or {}).get("stabil_direnc") or {}
    print(f"eğitim karesi: ▼ {direnc.get('donus_isaret')} · seviye {direnc.get('son_seviye')}")
    return yol, direnc


SATIR_ADI = {   # tabloda sığan kısa adlar
    "S0 · 20 bar (bugün)": "S0 · 20 bar (bugün)",
    "S1 · 30 bar": "S1 · 30 bar",
    "S2 · 40 bar": "S2 · 40 bar",
    "S6 · 50 bar": "S6 · 50 bar",
    "S7 · 60 bar": "S7 · 60 bar",
    "S8 · 40 bar + rvol≥1,5 deler": "S8 · 40 bar + rvol",
    "S3 · seviye başına 1": "S3 · seviye başına 1",
    "S4 · rvol ≥ 1,0": "S4 · yalnız rvol≥1",
    "S5 · 20 bar + seviye başına 1": "S5 · 20 bar + seviye",
}


# AGHOL satırı panoda KISALTILIR: yalnız değişen bölüm ("… önce/sonra"). Tam
# satırlar `meta["metin"]["lejant"]`ta; kısaltma panonun sığması için.
AGHOL_ONCE = ("… · ┄ Stabil direnç · ▼ direnç dönüşü (turuncu) · ▽ direnç momentumu (turuncu) · "
              "┄ BOS dış · kutular: OB FVG · ▨ dolan kısım …")
AGHOL_SONRA = ("… · ┄ Stabil destek (yeşil) · ┄ Stabil direnç (turuncu) · ▼ dönüş = sinyal · "
               "▲ geri alım = yapı · boş = momentum · ◇ = uyarı · ┄ BOS dış · kutular: OB FVG · "
               "▨ dolan kısım · şerit: rvol(20) · yapı: BOS/CHoCH dış")


def pano(kare_yolu: str, direnc: dict) -> str:
    garan, garan_atlanan = lejant_sonra("GARAN", "2026-09-21")
    df = pd.read_csv("/tmp/ok_cizgi_ikinci_tur.csv")

    fig = plt.figure(figsize=(11.5, 17.0), dpi=110, facecolor=ZEMIN)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off(); ax.set_facecolor(ZEMIN)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    ax.text(0.5, 0.991, "EĞİTİM KARESİ + LEJANT DİLİ + ◇ İKİNCİ TUR",
            ha="center", va="top", color=METIN, fontsize=17, fontweight="bold")
    ax.text(0.5, 0.968,
            "Formation-Bot · 8 Kasım 2026 · günlük grafik · replay ile ölçüldü · "
            "kütle: 50 sembol / 25.051 bar",
            ha="center", va="top", color=SOLUK, fontsize=10)

    # ---------- 1 · lejant dili ----------
    ax.text(0.055, 0.941, "1 · LEJANT DİLİ: lejant, ölçümün söylediğini yazıyor",
            color=VURGU, fontsize=12.5, fontweight="bold")
    y = 0.921
    for ad, once, sonra, not_ in (
            ("GARAN · 21.09.2026 — yoğun kare (kırpıcı testi)",
             ONCE["GARAN"], garan, f"sığmayan madde {garan_atlanan} (önce 6)"),
            ("AGHOL · 01.04.2025 — direnç katmanı karede",
             AGHOL_ONCE, AGHOL_SONRA, "sığmayan madde 0")):
        ax.text(0.055, y, ad, color=METIN, fontsize=9.4, fontweight="bold"); y -= 0.018
        ax.text(0.055, y, "ÖNCE", color="#8b949e", fontsize=8.4, fontweight="bold")
        for parca in textwrap.wrap(once, width=127):
            ax.text(0.108, y, parca, color="#9aa4ae", fontsize=7.9); y -= 0.0132
        y -= 0.0165
        ax.text(0.055, y, "SONRA", color=YESIL, fontsize=8.4, fontweight="bold")
        for parca in textwrap.wrap(sonra, width=127):
            ax.text(0.108, y, parca, color=METIN, fontsize=7.9); y -= 0.0132
        ax.text(0.055, y - 0.001, not_, color=SOLUK, fontsize=7.6)
        y -= 0.028

    # ---------- 2 · eğitim karesi ----------
    ax.text(0.055, 0.645, "2 · EĞİTİM KARESİ: direnç katmanı artık replay yolunda da çiziliyor",
            color=VURGU, fontsize=12.5, fontweight="bold")
    gen = 0.52
    yuk = gen * 11.5 * 0.75 / 17.0
    img_ax = fig.add_axes([(1 - gen) / 2, 0.337, gen, yuk])
    img_ax.imshow(plt.imread(kare_yolu)); img_ax.set_axis_off()
    ax.text(0.5, 0.328,
            f"GARAN replay karesi · ▼ dönüş {direnc.get('donus_isaret')} işaret · "
            f"direnç {direnc.get('son_seviye'):.2f} · ┄ dikey deneme "
            f"{direnc.get('dikey_deneme_isaret')} · canlı /grafik ile aynı köprü,\n"
            "aynı nedensel kesim; kare yalnız kesitte kapanmış mumları görür.\n"
            "İşaret dili: ▲ = yapı olayı (geri alım) · ▼ = sinyal-dereceli olay (dönüş) · "
            "◇ = yapı uyarısı · boş = momentum",
            ha="center", va="top", color=SOLUK, fontsize=8.6)

    # ---------- 3 · ◇ eğrisi ----------
    ax.text(0.055, 0.285, "3 · ◇ İKİNCİ TUR: soğuma kaç bar olmalı?", color=VURGU,
            fontsize=12.5, fontweight="bold")
    eax = fig.add_axes([0.062, 0.082, 0.40, 0.182])
    eax.set_facecolor("#161b22")
    xs = [p_[0] for p_ in EGRI]; ys = [p_[1] for p_ in EGRI]
    eax.plot(xs, ys, color=VURGU, lw=2)
    eax.scatter(xs, ys, s=26, color=VURGU, zorder=3)
    eax.axhline(ESIK, color=TURUNCU, ls="--", lw=1)
    eax.text(1.5, ESIK - 46, "eşik 389 — bugünkü 486'dan ek %20 kazanç", color=TURUNCU,
             fontsize=7.0, ha="left")
    kaymalar = {3: (16, -12), 10: (0, -16), 20: (-12, -16), 30: (0, 9),
                40: (0, 9), 50: (0, -16), 60: (0, 9)}
    for x, yy, ad in EGRI:
        eax.annotate(f"{yy} · {ad}", (x, yy), textcoords="offset points",
                     xytext=kaymalar.get(x, (0, 9)), ha="center", color=METIN, fontsize=7.4)
    eax.set_xlabel("zayıf ◇ soğuması (bar)", color=SOLUK, fontsize=8)
    eax.set_ylabel("günlük 50 sembolde ◇", color=SOLUK, fontsize=8)
    eax.tick_params(colors=SOLUK, labelsize=7.4)
    for sp in eax.spines.values():
        sp.set_color("#30363d")
    eax.set_ylim(280, 840); eax.set_xlim(0, 66)
    eax.grid(alpha=0.13, color=SOLUK)

    ax.text(0.525, 0.252, "ölçülen seçenekler", color=METIN, fontsize=9.6, fontweight="bold")
    ax.text(0.525, 0.236, "güçlü ◇ 189 · ▲ ve momentum dokunulmadı", color=SOLUK, fontsize=7.8)
    basliklar = ["kural", "◇", "zayıf", "medyan", "en çok", "atılanın öncü%"]
    yerler = [0.525, 0.702, 0.748, 0.802, 0.858, 0.912]
    for x, b in zip(yerler, basliklar):
        ax.text(x, 0.216, b, color=SOLUK, fontsize=7.6)
    ANAHTAR = ("S0", "S1", "S2", "S6", "S7", "S4")
    y = 0.198
    for _, r in df[df.kural.str.startswith(ANAHTAR)].iterrows():
        gecti = (r.toplam <= ESIK and r.bost_sembol <= 1 and r.guclu == 189
                 and r.oncu_oran <= 40)
        renk = METIN if r.kural.startswith("S0") else (YESIL if gecti else "#78828c")
        degerler = [SATIR_ADI.get(r.kural, r.kural), f"{int(r.toplam)}", f"{int(r.zayif)}",
                    f"{r.medyan:.0f}", f"{int(r.en_yogun)}", f"{r.oncu_oran:.0f}"]
        for x, d in zip(yerler, degerler):
            ax.text(x, y, d, color=renk, fontsize=7.6)
        y -= 0.0158
    ax.text(0.525, y - 0.020,
            "Tablo dışı: S3 seviye başına 1 → 650 · S5 20 bar + seviye → 486\n"
            "(ek kazanç yok) · S8 40 bar + rvol≥1,5 → 396 (fark yok).",
            color="#78828c", fontsize=7.8, va="top")
    ax.text(0.525, y - 0.042,
            "Yeşil = kilitli eşikleri geçen tek aday: 50 bar → 364 (bugüne göre −%25, 3 bar'a\n"
            "göre −%51). 40 bar eşiği 7 işaretle kaçırıyor; 50/60 bar geçiyor ama kazanç azalıyor.\n"
            "Atılanların ~%26'sı 20 bar içinde bir ▲ ile öncülenmiş — kesilen sınıf, bugün de\n"
            "gürültü sayılan sınıfın ta kendisi. Kural bu turda UYGULANMADI: karar sizde.",
            color=SOLUK, fontsize=8.2, va="top")

    ax.text(0.525, 0.009,
            "Ölçüm: research/stabil_cizgi_seyreltme_olcum.py",
            color="#6e7681", fontsize=7.4)
    yol = os.path.join(CIKTI, "00_pano.png")
    fig.savefig(yol, facecolor=ZEMIN)
    plt.close(fig)
    return yol


def main() -> int:
    os.makedirs(CIKTI, exist_ok=True)
    yol, direnc = egitim_karesi()
    print(pano(yol, direnc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
