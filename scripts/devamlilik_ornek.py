# -*- coding: utf-8 -*-
"""Puan karttan kalktı — örnek kart metinleri + görsel.

SALT OKUNUR. Hiçbir ağ çağrısı yapmaz, Telegram'a bir şey göndermez.

Ne üretir:
  docs/gorseller/devamlilik_ornek_kartlar.png   (görsel: 4 kart + önce/sonra)
  var/replay/devamlilik_ornek.md                (düz metin örnekleri)

Metinler **gerçek üretim kodundan** gelir: `notifier.TelegramNotifier.format_message`.
Yani görselde gördüğün satırlar canlıda çıkacak satırlardır; elle yazılmadı.

NEDEN BU DOSYA VAR
------------------
2026-10-25 ölçümü (docs/arastirma/PUANLAMA_MIMARISI_2026-10-25.md §11–§12):
0–100 devamlılık puanı tek bir bayrağa ("kama & üst TF aynı yönde") indirgeniyor,
ondan türeyen yüksek/normal/zayıf etiketi ise ölçümün taşımadığı bir hüküm
veriyordu. Kartta ne sayı ne etiket kaldı. Kalan tek bilgi — üst zaman dilimi
aynı yönde mi — kartın kendi üst-TF satırında, olgu olarak yazılıyor.

Kullanım:
    python scripts/devamlilik_ornek.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import notifier as N  # noqa: E402
import devamlilik as dev  # noqa: E402

CIKTI_PNG = REPO / "docs/gorseller/devamlilik_ornek_kartlar.png"
CIKTI_MD = REPO / "var/replay/devamlilik_ornek.md"


def kart(stock: str, desen: str, tf: str, kapanis: float, kirilan: float,
         mtf: int, mesafe: float, destek: bool = True, kalite: float = 85.0,
         guc: int = 78, yon: int = 1, saat: Tuple[int, int] = (11, 30)) -> Dict:
    """Gerçekçi alert_data: canlıda main.py'nin ürettiği alanların aynısı."""
    return {
        "stock_name": stock, "timeframe": tf, "pattern_name": desen,
        "state": "KIRILIM_TEYITLI", "break_dir": yon,
        "critical_price_level": kirilan, "candle_close_price": kapanis,
        "close_price": kapanis, "confidence_score": kalite, "break_strength": guc,
        "mtf_uyum": mtf, "bant_mesafe_atr": mesafe, "mtf_destek": destek,
        "upper_touches": 4, "lower_touches": 3, "retest_seen": False,
        "age_bars": 18, "bar_kapandi": True,
        "timestamp": datetime(2026, 10, 12, saat[0], saat[1]),
    }


# Dört örnek, kartın söyleyebildiği üç üst-TF hâlini kapsar:
#   aynı yönde · yön uyumu yok · onay yok
ORNEKLER: List[Tuple[str, Dict]] = [
    ("Kama · üst TF aynı yönde", kart(
        "THYAO", "Yükselen Kama", "1h", 302.35, 302.00, mtf=4, mesafe=0.2)),
    ("Kama · üst TF ters/yönsüz (4s→1g)", kart(
        "ASELS", "Alçalan Kama", "4h", 88.40, 87.10, mtf=0, mesafe=0.7)),
    ("Üçgen · üst TF aynı yönde", kart(
        "GARAN", "Simetrik Üçgen", "2h", 121.60, 120.50, mtf=4, mesafe=0.8)),
    ("Üçgen · üst TF onayı yok", kart(
        "EREGL", "Yükselen Üçgen", "1h", 34.90, 33.20, mtf=0, mesafe=2.6,
        destek=False)),
]


def metin_uret() -> List[Tuple[str, str, Dict]]:
    """(etiket, gerçek kart metni, veri) üçlüsü."""
    n = N.TelegramNotifier()
    cikti = []
    for etiket, data in ORNEKLER:
        cikti.append((etiket, n.format_message(data), data))
    return cikti


def _eski_metin(yeni: str, data: Dict) -> str:
    """2026-10-25 ÖNCESİ kart: iki satır fazla (etiket + gerekçe).

    Tarihsel karşılaştırma için *yeniden kurulmuş* metin; üretimde artık böyle
    iki satır yok. Değerler, kaldırılan kodun son hâliyle aynı mantıktan gelir.
    """
    puan = dev.devamlilik_puani(data.get("pattern_name"), data.get("mtf_uyum"),
                                data.get("bant_mesafe_atr"))
    aile = dev.aile_coz(data.get("pattern_name"))
    if puan is None or aile is None:
        return yeni
    etiket = "yüksek" if (aile == "Kama" and int(data.get("mtf_uyum") or 0) > 0) \
        else ("zayıf" if aile == "Üçgen" else "normal")
    aile_kucuk = "kama" if aile == "Kama" else "üçgen"
    uyumlu = int(data.get("mtf_uyum") or 0) > 0
    gerekce = aile_kucuk + (" · trend uyumlu" if uyumlu else " · trend zayıf")
    satirlar = yeni.split("\n")
    # Başlık (2 satır) + "· kapanış …" satırından sonra boş satır açıp ekle.
    ekle = satirlar.index("") if "" in satirlar else len(satirlar)
    return "\n".join(satirlar[:ekle] + ["", f"· Devamlılık: {etiket}",
                                       f"· {gerekce}"] + satirlar[ekle:])


def png_uret(satirlar: List[Tuple[str, str, Dict]]) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    duzenli = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    kalin = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    f_baslik = ImageFont.truetype(kalin, 30)
    f_alt = ImageFont.truetype(duzenli, 17)
    f_kart = ImageFont.truetype(duzenli, 19)
    f_kart_kalin = ImageFont.truetype(kalin, 19)
    f_etiket = ImageFont.truetype(kalin, 16)

    ARKA = (246, 247, 249)
    BALON = (255, 255, 255)
    METIN = (28, 32, 38)
    SOLUK = (120, 128, 138)
    VURGU = (16, 122, 87)
    KENAR = (219, 224, 230)

    GEN, BOS = 1180, 34
    ic_gen = GEN - 2 * BOS

    # ölçüm: iki sütun
    sutun_gen = (ic_gen - 24) // 2
    satir_yuk = 26

    def sari(metin: str, font, gen: int) -> List[str]:
        kelimeler, out, k = metin.split(" "), [], ""
        for w in kelimeler:
            den = (k + " " + w).strip()
            if font.getlength(den) <= gen - 28:
                k = den
            else:
                out.append(k)
                k = w
        out.append(k)
        return out

    bloklar = []
    for etiket, metin, data in satirlar:
        wrapped = []
        for ham in metin.split("\n"):
            if not ham.strip():
                wrapped.append("")
                continue
            wrapped.extend(sari(ham, f_kart, sutun_gen))
        yuk = 56 + len(wrapped) * satir_yuk + 16
        bloklar.append((etiket, wrapped, yuk, data))

    # önce/sonra
    etiket0, metin0, data0 = satirlar[0]
    eski0 = _eski_metin(metin0, data0)
    eski_wrapped = []
    for ham in eski0.split("\n"):
        if not ham.strip():
            eski_wrapped.append("")
        else:
            eski_wrapped.extend(sari(ham, f_kart, sutun_gen))
    yuk_kiyas = 60 + max(len(eski_wrapped), len(bloklar[0][1])) * satir_yuk + 20

    # toplam yükseklik
    baslik_yuk = 172
    grid_satir = [bloklar[0:2], bloklar[2:4]]
    y_grid = sum(max(b[2] for b in s) + 26 for s in grid_satir)
    yukseklik = baslik_yuk + y_grid + yuk_kiyas + 170

    img = Image.new("RGB", (GEN, yukseklik), ARKA)
    d = ImageDraw.Draw(img)

    # başlık
    d.text((BOS, 34), "Puan karttan kalktı — kart örnekleri", font=f_baslik, fill=METIN)
    d.text((BOS, 76),
           "Ne sayı ne kalite etiketi. Kalan bilgi olgu olarak yazılıyor: "
           "üst zaman dilimi aynı yönde mi?",
           font=f_alt, fill=SOLUK)
    d.text((BOS, 102),
           "Ölçüm (§11): 0–100 puan tek bayrağa indirgeniyordu; aynı kapsamda fark "
           "≤0,1 puandı. Sayı ek bilgi taşımıyordu.",
           font=f_alt, fill=SOLUK)
    d.text((BOS, 128),
           "yüksek/normal/zayıf etiketi de ölçümün taşımadığı bir hüküm veriyordu "
           "(örneklem dışı sınanmadı).",
           font=f_alt, fill=SOLUK)

    def balon(x, y, gen, yuk):
        d.rounded_rectangle([x, y, x + gen, y + yuk], radius=16, fill=BALON,
                            outline=KENAR, width=1)

    y = baslik_yuk
    for sira, grup in enumerate(grid_satir):
        h = max(b[2] for b in grup)
        for j, (etiket, wrapped, _, data) in enumerate(grup):
            x = BOS + j * (sutun_gen + 24)
            d.text((x + 4, y), etiket.upper(), font=f_etiket, fill=VURGU)
            balon(x, y + 22, sutun_gen, h - 22)
            yy = y + 40
            for satir in wrapped:
                if satir.startswith("▲"):
                    d.text((x + 14, yy), satir, font=f_kart_kalin, fill=METIN)
                else:
                    d.text((x + 14, yy), satir, font=f_kart, fill=METIN)
                yy += satir_yuk
        y += h + 26

    # önce / sonra
    y += 12
    d.text((BOS, y), "AYNI OLAY · ÖNCE / SONRA", font=f_etiket, fill=VURGU)
    y += 26
    for j, (bas, govde, renk) in enumerate((("ÖNCE (2026-10-25 öncesi)", eski_wrapped, SOLUK),
                                            ("SONRA (bugün)", bloklar[0][1], VURGU))):
        x = BOS + j * (sutun_gen + 24)
        d.text((x + 4, y), bas, font=f_etiket, fill=renk)
        balon(x, y + 22, sutun_gen, yuk_kiyas - 40)
        yy = y + 40
        for satir in govde:
            d.text((x + 14, yy), satir, font=f_kart, fill=METIN)
            yy += satir_yuk

    # alt bilgi
    y = yukseklik - 128
    d.text((BOS, y), "Kartta kalan bilgiler", font=f_etiket, fill=VURGU)
    for i, (ad, aciklama) in enumerate((
            ("aile + üst TF yönü", "kama · aynı yönde / uyum yok"),
            ("arşiv ölçümü", "n ile: 1651 kırılımın %75'i"),
            ("yapı ve bölgeler", "BOS/CHoCH · OB-FVG seviyesi"))):
        x = BOS + i * 372
        d.rounded_rectangle([x, y + 26, x + 352, y + 96], radius=10, fill=BALON,
                            outline=KENAR, width=1)
        d.text((x + 14, y + 36), ad, font=f_kart_kalin, fill=METIN)
        d.text((x + 14, y + 62), aciklama, font=f_alt, fill=SOLUK)

    CIKTI_PNG.parent.mkdir(parents=True, exist_ok=True)
    img.save(CIKTI_PNG)
    return CIKTI_PNG


def main() -> int:
    satirlar = metin_uret()

    md = ["# Puan karttan kalktı — örnek kart metinleri\n",
          "Üretim kodu (`notifier.format_message`) ile üretildi; elle yazılmadı.\n",
          "Kartta ne 0–100 sayı ne yüksek/normal/zayıf etiketi var. Ölçüm "
          "(`docs/arastirma/PUANLAMA_MIMARISI_2026-10-25.md` §11): puan tek bir "
          "bayrağa indirgeniyordu (aynı kapsamda fark ≤0,1); etiket ise örneklem "
          "dışı sınanmamış bir kalite hükmüydü. Kalan tek bilgi — üst zaman dilimi "
          "aynı yönde mi — kartın kendi üst-TF satırında olgu olarak yazılıyor.\n"]
    for etiket, metin, data in satirlar:
        puan = dev.devamlilik_puani(data.get("pattern_name"), data.get("mtf_uyum"),
                                    data.get("bant_mesafe_atr"))
        md.append(f"\n## {etiket} (log: {puan}/100 — kartta görünmez)\n")
        md.append("```")
        md.append(metin.rstrip())
        md.append("```")

    md.append("\n## Önce / sonra (aynı olay)\n")
    md.append("**Önce** (etiket + gerekçe satırı vardı):\n```")
    md.append(_eski_metin(satirlar[0][1], satirlar[0][2]).rstrip())
    md.append("```")
    md.append("**Sonra** (bugün):\n```")
    md.append(satirlar[0][1].rstrip())
    md.append("```")
    CIKTI_MD.parent.mkdir(parents=True, exist_ok=True)
    CIKTI_MD.write_text("\n".join(md), encoding="utf-8")

    png = png_uret(satirlar)
    print("\n".join(md[:6]))
    print(f"\nGörsel: {png}")
    print(f"Metin : {CIKTI_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
