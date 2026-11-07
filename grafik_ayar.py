"""Otomatik Telegram grafikleri için yan etkisiz ortak şalter sözleşmesi.

Elle istenen /grafik bu şalterden bağımsızdır. Eski sürümler ``yok`` dışındaki
her değeri açık saydığı için bilinmeyen değerleri geriye uyumlu biçimde açık
bırakıyoruz; kurulum doktoru bunlar için uyarır.
"""

GRAFIK_KAPALI_DEGERLER = frozenset({
    "", "yok", "0", "false", "off", "no", "none", "hayir", "hayır", "kapali", "kapalı",
})
GRAFIK_ACIK_DEGERLER = frozenset({"alarm", "1", "true", "on", "yes", "evet", "acik", "açık"})


def otomatik_grafik_acik(deger: str | None) -> bool:
    """Yaygın kapalı yazımlarını ve yalnız boşluk içeren değeri kapalı say."""
    return str(deger or "").strip().lower() not in GRAFIK_KAPALI_DEGERLER
