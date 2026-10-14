"""telegram_measure birim testleri.

Bu modül kart biçimleyicisinin tek ölçütünü taşıyor: "satır telefonda sarar mı".
Ölçer yanlışsa tüm boyut garantileri (≤SATIR_BUTCE px, sıfır sarma) yanlış olur,
o yüzden biçimden bağımsız olarak tek başına test ediliyor.
"""
from telegram_measure import (SATIR_BUTCE, bol, genislik, metni_sigdir,
                              satirlar_asiyor_mu, sigar_mi)


def test_bos_metin_sifir_genislik():
    assert genislik("") == 0.0
    assert genislik("a") > 0


def test_genislik_uzun_metinle_artar():
    kisa = genislik("▪ kapanış 302,00")
    uzun = genislik("▪ kapanış 302,00 · %1,3 aştı · retest bekleniyor")
    assert uzun > kisa


def test_ayni_karakter_sayisi_farkli_genislik():
    # Genişlik karakter sayısıyla orantılı değil; ölçerin PIL tabanlı olması
    # bu yüzden zorunlu ("ı" ile "m" aynı değil).
    assert genislik("ıııı") != genislik("mmmm")


def test_bol_butce_ustune_cikmaz():
    metin = ("▪ 4s: yukarı katılım teyitli · RVOL 1,70× · göreli işlem değeri 1,70× "
             "· hacim yüksek · işlem değeri yüksek · ↑ yönde katılım desteği var")
    satirlar = bol(metin, 180)
    assert len(satirlar) > 1
    assert all(genislik(s) <= 180 for s in satirlar)


def test_bol_ibareleri_bolerken_ayraci_kaybetmez():
    """Bölünen satırda bilgi birebir korunur; ayraç devam satırının başında kalır."""
    metin = "bir · iki · üç · dört · beş"
    satirlar = bol(metin, 60, ayraclar=(" · ",))
    assert len(satirlar) > 1
    birlesik = " ".join(s.strip() for s in satirlar)
    assert birlesik.replace(" ", "").replace("·", "") == metin.replace(" ", "").replace("·", "")
    # Ayraç yutulursa "iki üç" gibi çarpışan kelimeler çıkar; devam satırı
    # ayraçla başlar ki okur iki bilginin ayrı olduğunu anlasın.
    assert any(s.lstrip().startswith("·") for s in satirlar[1:])


def test_metni_sigdir_butceyi_asmaz_bilgi_dusurmez():
    """Güvenlik ağı: hangi builder'dan gelirse gelsin satırlar bütçeye uyar."""
    metin = ("📡 Gün içi izleme adayları\n"
             "   12/21 gösteriliyor · en yüksek puanlılar\n"
             "• ISCTR 1h Alçalan Üçgen q89 · Sıkışma güçleniyor · daralma %72 · 312.50\n"
             "📈 Gün: 9 tarama · 48 hisse × 4 zaman dilimi · 28 bildirim\n"
             "⚡ Kırılım: 3 · yukarı 1 · aşağı 2")
    sigar = metni_sigdir(metin, guvenlik=1.0)
    assert not satirlar_asiyor_mu(sigar)
    # kelime torbası aynı kalmalı (bilgi kaybı yok)
    assert sorted(sigar.replace("\n", " ").split()) == sorted(metin.split())


def test_bol_parcalanamayan_tokeni_kesmez_bilgi_kaybetmez():
    # Tek kelime bütçeden uzunsa satır taştan zorlanmaz: bilgi kaybı yerine
    # tek uzun satır tercih edilir (denetleyici uyarı loglar).
    metin = "A" * 400
    satirlar = bol(metin, 100)
    assert "".join(satirlar).replace(" ", "") == metin


def test_bol_girintiyi_sonraki_satira_tasir():
    satirlar = bol("x " * 200, 100, girinti="   ")
    assert any(s.startswith("   ") for s in satirlar[1:])


def test_sigar_mi_gercek_kart_satirlari_ile():
    butce = SATIR_BUTCE
    # Kısa footer satırı sığar; 25 Eyl biçiminin uzun satırı sığmaz.
    assert sigar_mi("› /tara THYAO", butce) is True
    assert sigar_mi("m" * 400, butce) is False        # sığmaz
    eski = ("🏗 PİYASA YAPISI · TOASO 1h — 15m: dış yükseliş · iç yükseliş — "
            "BOS ↑ 289,50 TL (dış · teyitli · güncel)")
    assert sigar_mi(eski, butce) is False             # 25 Eyl biçimi sarmalanıyordu


def test_satirlar_asiyor_mu_sarayan_satirlari_listeler():
    uzun = "▪ " + "kelime " * 60
    asanlar = satirlar_asiyor_mu(f"kısa satır\n{uzun}\nbir diğer kısa")
    assert asanlar == [uzun]
    assert satirlar_asiyor_mu("kısa satır\nbir diğer kısa") == []
    # Boş satırlar sayılmaz (mesaj içindeki ayraç satırları).
    assert satirlar_asiyor_mu("\n\n") == []


def test_olcer_hatali_girdide_patlamaz():
    # Bağlam verisi eksik/bozuk olabilir; ölçerin None/boş girdide istisna
    # fırlatması tüm alarm yolunu kırardı (main'de try/except var ama burada
    # ölçerin kendisi güvenli olmalı).
    assert SATIR_BUTCE > 0
    assert genislik(None) == 0.0
    assert bol(None) == []
    assert sigar_mi("", 100) is True
