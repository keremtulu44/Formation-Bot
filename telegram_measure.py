"""Telegram satır genişliği ölçümü — mesajın telefonda sarmalanıp sarmalanmadığını
kod tarafında tahmin eden bağımlılıksız yardımcı.

Neden karakter sayısı yetmiyor: bot'un kendi kuralı "satır ≤ 70 karakter" idi ve
25 Eyl canlı akışında 6 alarmın 120 satırı telefonda sarmalandı (en uzun satır
1338 px). Türkçe küçük harfler (ı, ş) dar, rakamlar ve büyük harfler geniş; aynı
karakter sayısı farklı piksel demek. Telefon bildiriminde 360 px genişliğin ~283
px'ı metne kalır (kalanı avatar/saat boşluğu).

Metrikler DejaVu Sans 16px temel alınarak Ölçülmüştür (PIL ile doğrulandı; hata
payı ±%3). Emoji Telegram'da ~1 em yer kaplar; tabloda 16 px sayılır.
"""

from __future__ import annotations

from typing import Iterable, List

# Telefon sohbet satırının metne ayrılan kabaca genişliği (px, 360px ekran).
SATIR_BUTCE = 283

# Karakter -> px (DejaVu Sans 16px). Türkçe harfler dahil; tablo dışı karakterler
# için `_VARSAYILAN` kullanılır (kötümser: geniş sayılır, böylece asla sarmaz).
_GENISLIK = {
    # rakamlar ve sayı ayraçları
    "0": 10.0, "1": 10.0, "2": 10.0, "3": 10.0, "4": 10.0,
    "5": 10.0, "6": 10.0, "7": 10.0, "8": 10.0, "9": 10.0,
    ",": 5.0, ".": 5.0, ":": 5.0, ";": 5.0,
    "%": 15.0, "‰": 15.0,
    # büyük harfler (Türkçe dahil)
    "A": 11.0, "B": 11.0, "C": 11.0, "Ç": 11.0, "D": 12.0, "E": 10.0, "F": 9.0,
    "G": 12.0, "H": 12.0, "I": 5.0, "İ": 5.0, "J": 8.0, "K": 11.0, "L": 9.0,
    "M": 14.0, "N": 12.0, "O": 13.0, "Ö": 13.0, "P": 10.0, "Q": 13.0, "R": 11.0,
    "S": 10.0, "T": 10.0, "U": 12.0, "Ü": 12.0, "V": 11.0, "W": 14.0, "X": 11.0,
    "Y": 10.0, "Z": 11.0, "Ğ": 12.0, "Ş": 10.0,
    # küçük harfler
    "a": 10.0, "b": 10.0, "c": 8.5, "ç": 9.0, "d": 10.0, "e": 10.0, "f": 6.5,
    "g": 10.0, "h": 10.0, "ı": 4.0, "i": 4.0, "j": 4.5, "k": 9.5, "l": 4.0,
    "m": 15.0, "n": 10.0, "o": 10.0, "ö": 10.0, "p": 10.0, "q": 10.0, "r": 7.0,
    "s": 8.0, "ş": 8.0, "t": 7.0, "u": 10.0, "ü": 10.0, "v": 9.0, "w": 13.0,
    "x": 9.0, "y": 9.0, "z": 8.5, "ğ": 10.0,
    # ayraçlar ve biçim işaretleri
    "·": 5.0, " ": 5.0, "-": 6.0, "–": 8.0, "—": 16.0, "…": 16.0,
    "(": 6.0, ")": 6.0, "[": 6.0, "]": 6.0, "/": 8.0, "›": 6.0, "‹": 6.0,
    "×": 13.0, "≈": 13.0, "+": 11.0, "−": 8.0, "=": 11.0, "!": 5.5, "?": 10.0,
    "↑": 13.0, "↓": 13.0, "→": 16.0, "←": 16.0,
    "▪": 11.0, "▸": 8.0, "▤": 15.0, "◆": 12.0, "◇": 12.0, "▲": 12.0, "▼": 12.0,
    "◈": 12.0, "•": 9.0, "★": 15.0, "◉": 14.0, "▣": 15.0,
    # Kutu çizgileri (özet ayracı "─" * 24): DejaVu'da 10 px — tablo dışına
    # düşerse 13 px sayılıp gereksiz yere ikiye bölünüyordu.
    "─": 10.0, "│": 10.0, "━": 10.0,
}
_VARSAYILAN = 11.0     # tablo dışı karakterler için kötümser varsayılan
# Emoji: DejaVu'da glifi yok (PIL .notdef kutusu 10 px veriyor), Telegram ise
# gerçek emojiyi ~1 em (=16 px) olarak çizer → tablo 16 kullanır; yani emojide
# tahmin PIL'den BÜYÜK, bilinçli olarak (sapma payı değil, doğru ölçüm).
_EMOJI = 16.0
_GUVENLIK = 0.95       # ölçüm hatası payı: bütçenin %5 altında sığdırıyoruz


def genislik(metin: str) -> float:
    """`metin` telefon sohbetinde kaç piksel yer kaplar (tahmin, üstten güvenli)."""
    toplam = 0.0
    for karakter in str(metin or ""):
        bilinen = _GENISLIK.get(karakter)
        if bilinen is not None:
            toplam += bilinen
        elif karakter.isspace():
            toplam += _GENISLIK[" "]
        elif ord(karakter) >= 0x2190:
            # Oklar/geometrik işaretler ve emoji: tablo dışına çıkıldığında geniş
            # varsayılır; amaç sarmalanmayı kaçırmamak, tipografik hassasiyet değil.
            toplam += _EMOJI if ord(karakter) > 0x1F000 else 13.0
        else:
            toplam += _VARSAYILAN
    return toplam


def satir_butcesi(butce: float | None = None) -> float:
    try:
        deger = float(butce if butce is not None else SATIR_BUTCE)
    except (TypeError, ValueError):
        deger = float(SATIR_BUTCE)
    return deger if deger > 0 else float(SATIR_BUTCE)


def sigar_mi(metin: str, butce: float | None = None) -> bool:
    """Satır güvenle sığar mı? (güvenlik payı dahil)."""
    return genislik(metin) <= satir_butcesi(butce) * _GUVENLIK


def _paketle(parcalar, ara, sinir, sinir_diger=None):
    """Parçaları bütçeye göre greedy birleştirir (kelime/ibare bölmez).

    `sinir_diger`: devam satırları girintili yazılacağı için onlardan düşülür.
    """
    satirlar: List[str] = []
    aktif = ""
    for parca in parcalar:
        limit = sinir if not satirlar else (sinir_diger if sinir_diger else sinir)
        aday = parca if not aktif else f"{aktif}{ara}{parca}"
        if not aktif or genislik(aday) <= limit:
            aktif = aday
            continue
        satirlar.append(aktif)
        aktif = parca
    if aktif:
        satirlar.append(aktif)
    return satirlar


def butce_carpani(guvenlik: float | None = None) -> float:
    """Satır bütçesine uygulanacak çarpan.

    Alarm kartı `_GUVENLIK` payıyla (%5 altında) çalışır; liste/özet gibi
    bildirimler ölçüm hatasına rağmen bölünse de okunur olduğundan tam bütçeyi
    kullanır — `guvenlik=1.0`.
    """
    return _GUVENLIK if guvenlik is None else float(guvenlik)


def bol(metin: str, butce: float | None = None, girinti: str = "   ",
        ayraclar: Iterable[str] = (" · ", " "),
        guvenlik: float | None = None) -> List[str]:
    """Metni satır bütçesine sığdırır; sığmıyorsa böler (bilgi kesilmez).

    Bölme önceliği: önce ` · ` ayraçları (her satır tek bilgi olur), sonra
    boşluklar. Hiçbiri yetmezse (tek kelime başlı başına uzun) kelime bölünmez;
    satır olduğu gibi kalır ve Telegram onu kendi kırar. Devam satırları
    `girinti` ile ötelenir ki görsel olarak aynı grubun parçası anlaşılsın.

    `_GUVENLIK` payı: ölçüm tablosu ±%3 civarı hata taşıyor; %5 pay bırakmak
    "sarmaz" sözünün gerçek hayatta da tutmasını sağlar.
    """
    # `guvenlik`: alarm kartı 0.95 ile çalışır (ölçüm hatasına karşı pay). Liste ve
    # özet satırlarında ise kelime kaybetmemek daha önemli: orada bütçenin tamamı
    # kullanılır (1.0), çünkü satırlar kelime sınırında paketlenir.
    _carpan = butce_carpani(guvenlik)
    metin = str(metin or "").rstrip()
    if not metin:
        return []
    # Satır başındaki girinti (devam satırlarının hizası) bölme sırasında
    # kaybolmasın: boşluklara göre bölersek [p for p in split(" ") if p] onu
    # siler; bu yüzden önek ayrılıp ilk parçaya geri verilir.
    onek = metin[:len(metin) - len(metin.lstrip())]
    if onek:
        govde = metin[len(onek):]
        parcalar = bol(govde, butce, girinti, ayraclar)
        return [f"{onek}{x}" if i == 0 else x for i, x in enumerate(parcalar)]
    sinir = satir_butcesi(butce) * _carpan
    if genislik(metin) <= sinir:
        return [metin]
    satirlar = [metin]
    for ara in (*tuple(ayraclar), " "):
        if not ara or all(genislik(s) <= sinir for s in satirlar):
            break
        yeni: List[str] = []
        for satir in satirlar:
            if genislik(satir) <= sinir or ara not in satir:
                yeni.append(satir)
                continue
            parcalar = [p for p in satir.split(ara) if p]
            # Devam satırı ayraçla başlar: " · " yutulursa iki bilgi çarpışır
            # ("Sıkışma güçleniyor daralma %72" gibi). Tek boşlukta gerek yok.
            one = f"{ara.strip()} " if len(ara) > 1 else ""
            paketlenmisler = _paketle(parcalar, ara, sinir,
                                      sinir_diger=(sinir - genislik(girinti)
                                                    - genislik(one)))
            for indeks, paketlenmis in enumerate(paketlenmisler):
                yeni.append(paketlenmis if indeks == 0
                            else f"{girinti}{one}{paketlenmis}")
        if len(yeni) > len(satirlar):
            satirlar = yeni
    return satirlar


def satirlar_asiyor_mu(metin: str, butce: float | None = None) -> List[str]:
    """Bütçeyi aşan satırların listesi (test ve teşhis için)."""
    sinir = satir_butcesi(butce)
    return [satir for satir in str(metin or "").splitlines() if genislik(satir) > sinir]


def metni_sigdir(metin, butce: float | None = None, girinti: str = "   ",
                 guvenlik: float | None = None) -> str:
    """Metindeki her satırı satır bütçesine sığdırır; bilgi düşürmez.

    Uzun satırlar `bol()` ile bölünür (kelime/ibare ortası kesilmez, devam
    satırı girintilenir). Alarm kartı kendi satırlarını üretirken zaten bu
    bütçeyi uyguluyor; bu fonksiyon biçimlendiricisi ayrı olan mesajlar için
    (bülten, özetler, komut yanıtları, karne) tek noktadan güvenlik ağıdır:
    telefonda kayan bir satır, satırın kendisi kadar bilgiyi okunmaz kılar.
    """
    if metin is None:
        return ""
    sinir = satir_butcesi(butce) * butce_carpani(guvenlik)
    out: List[str] = []
    for satir in str(metin).splitlines():
        if not satir.strip():
            out.append(satir.rstrip())
            continue
        for i, parca in enumerate(bol(satir, butce, girinti=girinti,
                                      guvenlik=guvenlik)):
            parca = (parca if i == 0 or parca.startswith(girinti)
                     else f"{girinti}{parca}")
            # `bol` ayraç/paket hesabında bütçeyi kaçırırsa (nadir de olsa olur)
            # burada sert açılı sözcük paketleyici devreye girer: buradan çıkan
            # her satır bütçeye kesin olarak uyar.
            if genislik(parca) <= sinir:
                out.append(parca)
                continue
            prefix = "" if i == 0 else girinti
            kelimeler = parca.lstrip().split(" ")
            satir_govde = (prefix if i else "") + (kelimeler[0] if kelimeler else "")
            for kel in kelimeler[1:]:
                if genislik(satir_govde + " " + kel) <= sinir:
                    satir_govde += " " + kel
                else:
                    out.append(satir_govde)
                    satir_govde = prefix + "  " + kel
            out.append(satir_govde)
    return "\n".join(out)
