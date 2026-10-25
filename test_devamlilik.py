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
    assert en_iyi == 95
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
        assert dev.kart_satiri(ad, 4, 0.1) == ""
        assert dev.bant(None) == ""
        assert dev.gerekce(ad, 4, 0.1) == []


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


def test_kart_satiri_bicimi():
    satir = dev.kart_satiri("Kama", 2, 0.7)
    assert satir.startswith("Devamlılık: ")
    assert satir.endswith("/100")
    assert satir.count("·") == 1
    # kart sınırı: tek satır, kısa
    assert len(satir) <= 32
    assert "\n" not in satir


def test_gerekce_en_fazla_uc_parca():
    for mtf in (0, 4):
        for mesafe in (0.1, 1.5, 3.0):
            g = dev.gerekce("Kama", mtf, mesafe)
            assert 1 <= len(g) <= 3, (mtf, mesafe, g)


def test_gerekce_yalniz_gercek_nedenler():
    """Trend uyumlu ancak MTF 4'te; 'yakın' ancak 0,3 ATR altında yazılır."""
    assert "trend uyumlu" in dev.gerekce("Kama", 4, 1.5)
    assert "trend uyumlu" not in dev.gerekce("Üçgen", 4, 1.5)   # üçgende etki yok
    assert "giriş seviyeye yakın" in dev.gerekce("Kama", 0, 0.2)
    assert "giriş seviyeye yakın" not in dev.gerekce("Kama", 0, 0.31)
    assert "giriş seviyeden uzak" in dev.gerekce("Kama", 0, 2.1)


def test_deterministik():
    a = dev.devamlilik_puani("Kama", 4, 0.25)
    for _ in range(50):
        assert dev.devamlilik_puani("Kama", 4, 0.25) == a


def test_tablo_dokumanla_uyumlu():
    """Dokümandaki örnek tablo (PUANLAMA_MIMARISI §2.4) ile birebir."""
    beklenen = [
        (("Kama", 4, 0.2), 95),
        (("Kama", 4, 0.7), 93),
        (("Kama", 4, 3.0), 83),
        (("Kama", 2, 0.7), 75),
        (("Kama", 2, 1.5), 71),
        (("Üçgen", 2, 0.7), 45),
        (("Üçgen", 2, 3.0), 34),
    ]
    for (aile, mtf, mesafe), puan in beklenen:
        assert dev.devamlilik_puani(aile, mtf, mesafe) == puan, (aile, mtf, mesafe)
