# -*- coding: utf-8 -*-
"""Devamlılık puanı testleri.

SALT HESAP: ağ yok, dosya yok, motor yok. Yalnız `devamlilik.py` sözleşmesi.

Kapsanan sözleşme:
  * ölçek 5…95, asla 100 (100 "kesin" demek olurdu)
  * kapsam dışı aile → None / boş kart satırı (uydurma sayı yok)
  * eksik girdi → nötr (hata vermez, puanı şişirmez)
  * etkileşim yalnız kamada (üçgende MTF ek etki yapmaz)
  * mesafe monoton: yakın > orta > 1–2 > >2
  * aynı girdi → aynı puan (deterministik)
  * bant sınırları ve sıralaması tutarlı

Kullanım:
    python -m pytest test_devamlilik.py -q
"""

from __future__ import annotations

import devamlilik as dev


def test_olcek_sinirlari():
    """En iyi ve en kötü girdi bile 5…95 arasında kalır."""
    en_iyi = dev.devamlilik_puani("Yükselen Kama", mtf_uyum=4, bant_mesafe_atr=0.0)
    en_kotu = dev.devamlilik_puani("Alçalan Üçgen", mtf_uyum=0, bant_mesafe_atr=9.0)
    # mesafe küçültmesi 0,50 (2026-10-25): en iyi hücre 94, 95 değil.
    assert en_iyi == 94
    assert en_kotu is not None and en_kotu >= dev.PUAN_MIN
    assert en_iyi <= dev.PUAN_MAX
    assert all(dev.devamlilik_puani("Kama", m, x) < 100
               for m in (0, 2, 4) for x in (0.0, 0.5, 1.5, 5.0))


def test_orta_nokta_rastgele():
    """Üçgen + kötü mesafe dışında, sıfır etki 50'ye denk gelir."""
    # üçgen (aile etkisi var) yerine nötr durum: kapsam dışı None döner.
    assert dev.devamlilik_puani("Bayrak", 4, 0.1) is None


def test_kapsam_disi_aile():
    """Bayrak/Flama ölçülmedi: puan yok, kart satırı yok."""
    for ad in ("Bayrak", "Flama", "", None, "Bilinmeyen"):
        assert dev.devamlilik_puani(ad, 4, 0.1) is None
        assert dev.bant(None) == ""


def test_aile_cozma():
    assert dev.aile_coz("Yükselen Kama") == "Kama"
    assert dev.aile_coz("Alçalan Kama") == "Kama"
    assert dev.aile_coz("Simetrik Üçgen") == "Üçgen"
    assert dev.aile_coz("Yükselen Üçgen") == "Üçgen"
    assert dev.aile_coz("Kama") == "Kama"
    assert dev.aile_coz("Flama") is None


def test_kama_her_zaman_ucgenden_yuksek():
    """Aynı MTF ve mesafede kama > üçgen (ölçülen +6,1 puanlık fark)."""
    for mtf in (0, 2, 4):
        for mesafe in (0.1, 0.5, 1.5, 3.0):
            k = dev.devamlilik_puani("Kama", mtf, mesafe)
            u = dev.devamlilik_puani("Üçgen", mtf, mesafe)
            assert k > u, (mtf, mesafe, k, u)


def test_etkilesim_yalniz_kamada():
    """MTF 4 kamayı yükseltir; üçgende etki YOK (ölçüm böyle)."""
    assert dev.devamlilik_puani("Kama", 4, 1.5) > dev.devamlilik_puani("Kama", 3, 1.5)
    assert dev.devamlilik_puani("Üçgen", 4, 1.5) == dev.devamlilik_puani("Üçgen", 3, 1.5)


def test_mesafe_monoton():
    """Yakın giriş her zaman uzaktan iyi; aile farkından bağımsız."""
    for aile in ("Kama", "Üçgen"):
        yakin = dev.devamlilik_puani(aile, 2, 0.2)
        orta = dev.devamlilik_puani(aile, 2, 0.7)
        uzak1 = dev.devamlilik_puani(aile, 2, 1.5)
        uzak2 = dev.devamlilik_puani(aile, 2, 3.0)
        assert yakin >= orta >= uzak1 >= uzak2, (aile, yakin, orta, uzak1, uzak2)
        assert yakin > uzak2


def test_eksik_girdi_notr():
    """Eksik/bozuk girdi hata vermez, puanı da şişirmez."""
    temel = dev.devamlilik_puani("Kama", 0, 1.5)
    assert dev.devamlilik_puani("Kama", None, 1.5) == temel
    assert dev.devamlilik_puani("Kama", 0, None) == temel
    assert dev.devamlilik_puani("Kama", "abc", "xyz") == temel  # type: ignore[arg-type]
    assert dev.devamlilik_puani("Kama", float("nan"), float("nan")) == temel


def test_bant_sinirlari():
    assert dev.bant(95) == "yüksek"
    assert dev.bant(85) == "yüksek"
    assert dev.bant(84) == "iyi"
    assert dev.bant(65) == "iyi"
    assert dev.bant(64) == "normal"
    assert dev.bant(45) == "normal"
    assert dev.bant(44) == "zayıf"
    assert dev.bant(5) == "zayıf"


def test_bant_sirasi_puan_ile_uyumlu():
    """Bant sırası puan sırasıyla çelişmez."""
    sira = {"zayıf": 0, "normal": 1, "iyi": 2, "yüksek": 3}
    onceki = -1
    for p in range(dev.PUAN_MIN, dev.PUAN_MAX + 1):
        s = sira[dev.bant(p)]
        assert s >= onceki
        onceki = s


def test_puan_kartta_yok():
    """2026-10-25 (§11–§12): puan ve kalite etiketi karttan tamamen kalktı.

    Puan tek bir bayrağa indirgeniyordu (fark ≤0,1); ondan türeyen
    yüksek/normal/zayıf etiketi de ölçümün taşımadığı bir hükümdü. Kullanıcıya
    aktarılan yüzeyde artık ne sayı ne etiket var.
    """
    import notifier
    metin = notifier.TelegramNotifier().format_message(_ornek_veri())
    assert "Devamlılık" not in metin
    assert "formasyon kalitesi" not in metin
    # `devamlilik.py` kullanıcıya metin üreten fonksiyon taşımaz: puan saf hesap.
    for ad in ("kart_satiri", "kart_gerekcesi", "gerekce", "devamlilik_etiketi"):
        assert not hasattr(dev, ad), ad


def test_ust_tf_satiri_yonu_soyler():
    """Üst TF satırı yön uyumunu söyler; yön bilinmiyorsa 'aynı yönde' DEMEZ.

    `mtf_destek` yalnız "üst TF'de aktif formasyon var" demek. Eskiden onay
    sayılıp "4 saatlik de aynı yönde" yazılıyordu; ters yönlü üst TF'de de aynı
    cümle kuruluyordu (yanlış iddia).
    """
    import notifier
    ortak = dict(_ornek_veri())
    ortak.update({"mtf_destek": True, "mtf_uyum": 4})
    assert "· 4 saatlik de aynı yönde" in notifier.TelegramNotifier().format_message(ortak)
    ortak2 = dict(_ornek_veri())
    ortak2.update({"mtf_destek": True, "mtf_uyum": 0})
    metin = notifier.TelegramNotifier().format_message(ortak2)
    assert "· 4 saatlik: yön uyumu yok" in metin
    assert "aynı yönde" not in metin
    ortak3 = dict(_ornek_veri())
    ortak3.update({"mtf_destek": False, "mtf_uyum": 0})
    assert "· 4 saatlik onayı yok" in notifier.TelegramNotifier().format_message(ortak3)


def test_ust_tf_satiri_piksel_butcesine_sigar():
    """Üst TF satırının üç hâli de 283 px satır bütçesini bölünmeden geçer."""
    import notifier
    from telegram_measure import genislik
    butce = notifier._kart_esik_px()
    for metin in ("· 4 saatlik de aynı yönde", "· 4 saatlik: yön uyumu yok",
                  "· 4 saatlik onayı yok", "· günlük: yön uyumu yok"):
        assert genislik(metin) <= butce, (metin, genislik(metin), butce)


def test_deterministik():
    a = dev.devamlilik_puani("Kama", 4, 0.25)
    for _ in range(50):
        assert dev.devamlilik_puani("Kama", 4, 0.25) == a


def test_tablo_dokumanla_uyumlu():
    """Dokümandaki örnek tablo (PUANLAMA_MIMARISI §2.4) ile birebir."""
    beklenen = [
        (("Kama", 4, 0.2), 94),
        (("Kama", 4, 0.7), 92),
        (("Kama", 4, 3.0), 85),
        (("Kama", 2, 0.7), 73),
        (("Kama", 2, 1.5), 71),
        (("Üçgen", 2, 0.7), 43),
        (("Üçgen", 2, 3.0), 37),
    ]
    for (aile, mtf, mesafe), puan in beklenen:
        assert dev.devamlilik_puani(aile, mtf, mesafe) == puan, (aile, mtf, mesafe)


# --- kart entegrasyonu / geri dönüş ---------------------------------------
# NOT: modülleri `reload` etmiyoruz; reload diğer testlerin tuttuğu referansları
# bozup sıra bağımlı hatalar üretiyordu. Bayraklar doğrudan yamalanır.

def _ornek_veri():
    """Gerçekçi alert_data (main.py'nin ürettiği alanlar)."""
    from datetime import datetime
    return {
        "stock_name": "THYAO", "timeframe": "1h", "pattern_name": "Yükselen Kama",
        "state": "KIRILIM_TEYITLI", "break_dir": 1, "critical_price_level": 302.0,
        "candle_close_price": 302.35, "confidence_score": 87.0, "break_strength": 80,
        "mtf_uyum": 4, "bant_mesafe_atr": 0.2, "upper_touches": 4, "lower_touches": 3,
        "timestamp": datetime(2026, 10, 12, 15, 30),
    }


def test_kart_ne_geometri_ne_puan_gosterir(monkeypatch):
    """Kullanıcıya aktarılan yerde ne geometri ne devamlılık satırı var."""
    import notifier
    monkeypatch.setattr(notifier, "DEVLAMLILIK_AKTIF", True)
    metin = notifier.TelegramNotifier().format_message(_ornek_veri())
    assert "Devamlılık" not in metin
    assert "formasyon kalitesi" not in metin
    assert "87/100" not in metin


def test_rollback_bayragi_eski_metni_dondurur(monkeypatch):
    """`DEVLAMLILIK_AKTIF=0` eski kartı birebir geri getirir."""
    import notifier
    monkeypatch.setattr(notifier, "DEVLAMLILIK_AKTIF", False)
    metin = notifier.TelegramNotifier().format_message(_ornek_veri())
    assert "· formasyon kalitesi 87/100" in metin
    assert "Devamlılık" not in metin


def test_klasik_stil_de_puan_basmaz(monkeypatch):
    """Klasik gövde de puan/etiket basmaz; rollback (=0) eski kaliteyi döndürür."""
    import notifier
    monkeypatch.setattr(notifier, "DEVLAMLILIK_AKTIF", True)
    monkeypatch.setattr(notifier, "TELEGRAM_ALERT_STYLE", "klasik")
    metin = notifier.TelegramNotifier().format_message(_ornek_veri())
    assert "Devamlılık" not in metin and "Kalite:" not in metin
    assert "Çok güçlü" not in metin


def test_kapsam_disi_ailede_kart_satiri_yok(monkeypatch):
    """Bayrak/Flama: puan yok, satır yok — uydurma sayı basılmaz."""
    import notifier
    monkeypatch.setattr(notifier, "DEVLAMLILIK_AKTIF", True)
    veri = _ornek_veri()
    veri["pattern_name"] = "Bayrak"
    metin = notifier.TelegramNotifier().format_message(veri)
    assert "Devamlılık" not in metin
