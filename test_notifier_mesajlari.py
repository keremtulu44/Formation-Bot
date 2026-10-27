from datetime import datetime

import notifier as notifier_mod
from config import TELEGRAM_ALERT_MAX_KARAKTER, TELEGRAM_SATIR_PX
from notifier import TelegramNotifier
from telegram_measure import genislik

_LIFECYCLE = ("KIRILIM_TEYITLI", "RETEST_BASARILI", "KIRILIM_GECERSIZLESTI")


def _base_data(**override):
    data = {
        'stock_name': 'THYAO',
        'timeframe': '1h',
        'pattern_name': 'Yükselen Üçgen',
        'state': 'KIRILIM_ADAYI',
        'confidence_score': 85,
        'critical_price_level': 300.0,
        'upper_now': 302.0,
        'lower_now': 295.0,
        'contraction': 0.75,
        'timestamp': datetime.now(),
        'break_dir': 1,
        'break_strength': 80,
        'break_price': 302.0,
    }
    data.update(override)
    return data


def test_kirilim_adayi_yukari_ustunde():
    # Rastgele şablon seçimi kaldırıldı: mesaj deterministik, tek seferde doğrulanır.
    notifier = TelegramNotifier()
    msg = notifier.format_message(_base_data(state='KIRILIM_ADAYI', break_dir=1, upper_now=302.0))
    assert "YUKARI" in msg
    assert "üstünde kapanış" in msg
    assert "altında kapanış" not in msg


def test_kirilim_adayi_asagi_altinda():
    notifier = TelegramNotifier()
    msg = notifier.format_message(_base_data(state='KIRILIM_ADAYI', break_dir=-1, lower_now=295.0))
    assert "AŞAĞI" in msg
    assert "altında kapanış" in msg
    assert "üstünde kapanış" not in msg


def test_kirilim_adayi_asagi_ustunde_yazmamali():
    # Eski bug: AŞAĞI kırılımda da "üstünde kapanış" yazıyordu
    notifier = TelegramNotifier()
    msg = notifier.format_message(_base_data(state='KIRILIM_ADAYI', break_dir=-1))
    assert "altında kapanış" in msg
    assert "üstünde kapanış" not in msg


def test_tamamlandi_basarısiz_ve_deneme_mesaji_bastirilir():
    notifier = TelegramNotifier()
    for state in ("FORMASYON_TAMAMLANDI", "BASARISIZ_KIRILIM", "KIRILIM_DENEMESI"):
        assert notifier.format_message(_base_data(state=state)) == ""


def test_kirilim_teyitli_yon():
    # Kart: yön ve olay İLK satırda — Telegram bildirimi yalnız ilk satırı gösterir.
    notifier = TelegramNotifier()
    # GÖRSEL-7: `·` ayırıcısı kalktı — satır = TEK konu (≤2 öğe) kuralı; ilk satır
    # yön + hisse + TF + olay taşır ve öyle kalır.
    msg_yukari = notifier.format_message(_base_data(state='KIRILIM_TEYITLI', break_dir=1))
    assert msg_yukari.splitlines()[0] == "▲ THYAO 1s YUKARI KIRILIM"

    msg_asagi = notifier.format_message(_base_data(state='KIRILIM_TEYITLI', break_dir=-1))
    assert msg_asagi.splitlines()[0] == "▼ THYAO 1s AŞAĞI KIRILIM"


def test_sikisma_mesaji():
    notifier = TelegramNotifier()
    data = _base_data(state='SIKISMA_GUCLENIYOR', contraction=0.85)
    msg = notifier.format_message(data)
    assert "sıkışma güçleniyor" in msg.lower()
    assert "THYAO" in msg


def test_retest_basarili_mesaji():
    notifier = TelegramNotifier()
    msg = notifier.format_message(_base_data(state='RETEST_BASARILI', break_dir=1))
    assert "SEVİYE KORUNDU" in msg
    assert "seviye korundu" not in msg
    # 2026-10-26: kırılan seviye ifadesi netleştirildi (· kırılan seviye / kapanış ayrı satır)
    assert "302,00" in msg and "kırılan" in msg
    assert "teyit düşer: 302,00 altı kapanış" in msg


def test_aday_oluyor_mesaji():
    notifier = TelegramNotifier()
    data = _base_data(state='ADAY_OLUSUYOR', contraction=0.6)
    msg = notifier.format_message(data)
    assert "oluşuyor" in msg.lower() or "bir şeyler" in msg.lower()


def test_formasyon_tanimlandi_mesaji():
    notifier = TelegramNotifier()
    data = _base_data(state='FORMASYON_TANIMLANDI')
    msg = notifier.format_message(data)
    assert "tanımlandı" in msg.lower()


def test_kirilim_hazirligi_mesaji():
    notifier = TelegramNotifier()
    data = _base_data(state='KIRILIM_HAZIRLIGI')
    msg = notifier.format_message(data)
    assert "hazırlığında" in msg.lower()


def test_kirilim_denemesi_yon():
    notifier = TelegramNotifier()
    data = _base_data(state='KIRILIM_DENEMESI', break_dir=1, upper_now=310)
    msg = notifier.format_message(data)
    assert msg == ""


def test_basarısız_kirilim_mesaji():
    notifier = TelegramNotifier()
    data = _base_data(state='BASARISIZ_KIRILIM')
    msg = notifier.format_message(data)
    assert msg == ""


def test_sonraki_teyitli_gecersizlesme_ayri_bildirim_mesaji():
    notifier = TelegramNotifier()
    msg = notifier.format_message(_base_data(
        state="KIRILIM_GECERSIZLESTI",
        break_dir=1,
        break_price=302.0,
        candle_close_price=299.5,
        bar_metni="Mum: 2026-10-12 15:30 kapandı",
        confidence_score=82,
        upper_touches=3,
        lower_touches=2,
    ))
    assert "KIRILIM İPTAL" in msg
    assert "banda döndü" in msg
    # GÖRSEL-7 iş bölümü: geçersizleşme metni YALNIZ formasyon + TF + "ne olursa
    # teyit düşerdi" sınırını söyler. Kapanış/marj/temas/kırılan seviye kârede
    # çizili (ölçüm: bugünkü kart 34 satırdı, %40'ı girintili devam satırı).
    assert "dönüş sınırı 302,00 altı" in msg
    # GÖRSEL-8: `· temas üst/alt` isteğe bağlı ölçü olarak geri geldi (formasyonun
    # kaç kez denendiği); `kırılan` dökümü ve marj hâlâ basılmaz.
    assert "kırılan" not in msg and "kaldı" not in msg
    assert "× geçersiz" not in msg
    assert "başarısız kırılım" not in msg.lower()


def test_formasyon_gecersiz_mesaji():
    notifier = TelegramNotifier()
    data = _base_data(state='FORMASYON_GECERSIZ', invalid_reason="Süre doldu")
    msg = notifier.format_message(data)
    assert "geçersiz" in msg.lower()
    assert "Süre doldu" in msg


def test_engine_snapshot_retest_seen_var():
    from patterns.lifecycle import EngineSnapshot
    snap = EngineSnapshot(state="FORMASYON_TAMAMLANDI", retest_seen=True)
    assert snap.retest_seen is True
    snap2 = EngineSnapshot(state="FORMASYON_TAMAMLANDI", retest_seen=False)
    assert snap2.retest_seen is False


def test_engine_snapshot_default_retest_false():
    from patterns.lifecycle import EngineSnapshot
    snap = EngineSnapshot()
    assert snap.retest_seen is False


def test_main_alert_data_retest_seen_alanı():
    # main.py alert_data'ya retest_seen eklenir - simüle et
    from patterns.lifecycle import EngineSnapshot
    snap = EngineSnapshot(state="FORMASYON_TAMAMLANDI", break_dir=1, retest_seen=False)
    alert_data = {
        'stock_name': 'THYAO',
        'timeframe': '1h',
        'pattern_name': 'Yükselen Üçgen',
        'state': snap.state,
        'break_dir': snap.break_dir,
        'retest_seen': getattr(snap, 'retest_seen', False),
    }
    assert 'retest_seen' in alert_data
    assert alert_data['retest_seen'] is False


def test_lifecycle_retest_tracking():
    from patterns.lifecycle import ArgentEngine
    engine = ArgentEngine()
    assert hasattr(engine, '_retest_seen')
    assert engine._retest_seen is False
    # Yeni pattern başladığında False olmalı
    engine._retest_seen = True
    engine.next_pattern_identity = 0
    # reset should clear
    engine.reset()
    assert engine._retest_seen is False


def test_gun_sonu_ozeti_yon_ve_daralma_okunabilir():
    """Özet satırlarında ham break_dir ("- -1 yön") ve dağını daralma basılmamalı."""
    n = TelegramNotifier()
    aktif = [
        {"stock_name": "ISMEN", "timeframe": "2h", "pattern_name": "Alçalan Üçgen",
         "state": "RETEST_BASARILI", "confidence_score": 84, "contraction": 0.7, "break_dir": -1},
        {"stock_name": "AKSEN", "timeframe": "1d", "pattern_name": "Alçalan Kama",
         "state": "RETEST_BASARILI", "confidence_score": 85, "contraction": 0.7, "break_dir": 1},
        {"stock_name": "ISCTR", "timeframe": "4h", "pattern_name": "Alçalan Üçgen",
         "state": "SIKISMA_GUCLENIYOR", "confidence_score": 88, "contraction": 0.81, "break_dir": 0},
    ]
    ozet = n.format_daily_summary(aktif, {"stocks_scanned": 96, "alerts_sent": 2})
    # Ham yön değeri ve çift tire görünmemeli
    assert "- -1 yön" not in ozet and "- 1 yön" not in ozet
    # Yön liste satırlarında okla veriliyor (↑/↓): "yukarı yön" kelimesi satırı
    # 350 px'a çıkarıp her maddeyi ikiye bölüyordu. Ham değer yine basılmamalı.
    assert "↑" in ozet and "↓" in ozet
    # Zaman dilimi üç bölümde de görünür (tutarlılık) ve desen adı korunur
    assert "↓ ISMEN 2h Alçalan Üçgen" in ozet
    assert "↑ AKSEN 1d Alçalan Kama" in ozet
    # Sıkışanlar: hisse önce, daralma sonra
    # Uzun madde satırı " · " üzerinden ikiye iner (telefonda sarmaması için).
    # Madde tek satıra sığıyor: "↔ ISCTR 4h Alçalan Üçgen q88 · %81" yerine kısa
    # biçim ("ISCTR 4h Alçalan Üçgen q88 %81") — veri aynı, satır ikiye bölünmüyor.
    assert "ISCTR 4h Alçalan Üçgen" in ozet and "%81" in ozet


# --- Mesaj kalitesi: ton, sabit metin, telefon uyumu -------------------------
# Bu bölüm "mesajlar herkese açık kanal diliyle, telefonda okunur yazılsın"
# kararının regresyon testidir. İhlal olursa test kırılır.

_TUM_STATELER = [
    "ADAY_OLUSUYOR", "GEOMETRI_ADAYI", "FORMASYON_TANIMLANDI", "SIKISMA_GUCLENIYOR",
    "KIRILIM_HAZIRLIGI", "KIRILIM_DENEMESI", "KIRILIM_ADAYI", "KIRILIM_TEYITLI",
    "RETEST_BEKLENIYOR", "RETEST_EDILIYOR", "RETEST_BASARILI", "FORMASYON_TAMAMLANDI",
    "BASARISIZ_KIRILIM", "FORMASYON_GECERSIZ",
]

# Kişisel asistan sesi ve tavsiye veren cümleler bilerek metin dışı bırakıldı.
_YASAK_KALIPLAR = (
    "radarımda", "gözüm üstünde", "takipteyim", "Takipteyiz", "haber veririm",
    "acele etme", "görev tamam", "kendi analizini", "izliyorum", "bekliyorum",
    "Şimdilik izle", "takipte kal", "grafiğe bak -", "sadece formasyon yetmez",
)


def _mesaj(state, **override):
    return TelegramNotifier().format_message(_base_data(state=state, **override))


def test_mesajlar_kişisel_asistan_tonu_kullanmaz():
    for state in _TUM_STATELER:
        for varyant in ({}, {"break_dir": -1}, {"retest_seen": False}):
            msg = _mesaj(state, **varyant)
            for kalip in _YASAK_KALIPLAR:
                assert kalip not in msg, f"{state}: yasak kalıp '{kalip}' mesajda geçiyor"


def test_mesajlar_deterministik_ayni_olay_hep_aynı_metin():
    # Rastgele şablon/footer seçimi kaldırıldı: aynı veri -> birebir aynı mesaj.
    for state in _TUM_STATELER:
        birinci = _mesaj(state)
        for _ in range(5):
            assert _mesaj(state) == birinci, f"{state}: metin kararsız üretiliyor"


# Kart biçiminde bağlam bloğunun gerçek boyutu test edilsin diye 25 Eyl akışından
# ölçülmüş bir örnek (3 bölge + 4 TF durum satırı + 3 hacim satırı).
_BAGLAM = {
    "yapi": [
        "◈ 4s yapı: dış ↓geçiş · iç ↓ · PH 437,50 · WL 410,75",
        "   dış · CHoCH ↓ 411,75 · geçerli",
        "   iç · BOS ↓ 429,00 · geçerli",
        "▸ 1s ↓/↑ · PH 437,50",
        "▸ 2s ↓geçiş/↑ · WL 410,75",
        "▸ 1g ↑/↑ · PL 399,25",
    ],
    "ust": [
        "▲ OB 1s ayı · 432,25–435,75",
        "   %0 dolu · +%0,9",
        "▲ FVG 4s ayı · 429,00–433,50",
        "   ilk temas · %22 dolu · +%0,2",
    ],
    "alt": [
        "▼ OB 2s boğa · 423,00–425,50",
        "   %0 dolu · −%0,6",
    ],
    "hacim": [
        "▤ 4s hacim: yargı yok (veri bekleniyor)",
        "▤ 2s katılım düşük · RVOL 0,72× ≈DV",
        "▤ 1s alt bölge emilimi geçersizleşti · RVOL 0,53×",
    ],
}


def _olay_verisi(state, **override):
    data = _base_data(state=state, **override)
    data.setdefault("candle_close_price", 303.25)
    data.setdefault("upper_touches", 2)
    data.setdefault("lower_touches", 2)
    data.setdefault("age_bars", 96)
    data.setdefault("mtf_destek", False)
    data.setdefault("retest_seen", False)
    data.setdefault("contraction", 0.79)
    return data


def test_mesajlar_telefona_sigar_boyutta():
    # Kural yeniden ölçeklendi (kart batch'i): eski "≤400 kr ve satır ≤70 karakter"
    # kuralı domain bağlamını HİÇ ölçmüyor, karakter saydığı için de sarmalayan
    # satırları yakalamıyordu (25 Eyl: 1358-1559 kr, 120 sarmalayan satır).
    # Piksel bütçesi push edilen üç state için zorunludur (ALERT_STATES); diğer
    # state'ler yalnız klasik/digest yollarında kullanılır ve eski karakter
    # kuralıyla izlenir — kart onlara dokunmaz.
    for state in _TUM_STATELER:
        for varyant in ({}, {"break_dir": -1}, {"retest_seen": False}, {"contraction": 0.93}):
            msg = _mesaj(state, **varyant)
            sinir = TELEGRAM_ALERT_MAX_KARAKTER if state in _LIFECYCLE else 400
            assert len(msg) <= sinir, f"{state}: {len(msg)} karakter (telefon için fazla uzun)"
            for satir in msg.splitlines():
                if state in _LIFECYCLE:
                    assert genislik(satir) <= TELEGRAM_SATIR_PX, (
                        f"{state}: {satir!r} satırı {genislik(satir):.0f}px — telefonda sarar")
                else:
                    assert len(satir) <= 70, f"{state}: {len(satir)} karakterlik satır sarar"


def test_kart_baglamla_birlikte_tavanin_altinda_kalir():
    # Domain bağlamı DAHİL: olay başına ≤ 1100 kr, satır ≤ 283 px, sarma yok.
    notifier = TelegramNotifier()
    for state in _LIFECYCLE:
        for varyant in ({}, {"break_dir": -1}):
            msg = notifier.format_message(_olay_verisi(
                state, domain_bolumleri=_BAGLAM,
                domain_karsi=["iç yapı ↓", "hacim teyitsiz"], **varyant))
            assert len(msg) <= TELEGRAM_ALERT_MAX_KARAKTER, (
                f"{state}: kart {len(msg)} kr (tavan {TELEGRAM_ALERT_MAX_KARAKTER})")
            for satir in msg.splitlines():
                assert genislik(satir) <= TELEGRAM_SATIR_PX, f"{state}: {satir!r}"
            # `/tara` satırı karttan ÇIKTI (2026-10-22): komut çalışır ama
            # her alarmın altında tekrar etmez; boşalan yer ölçüm dipnotuna gitti.
            assert "/tara" not in msg, state
            assert state == "KIRILIM_TEYITLI" or "geçmiş davranış" not in msg
            assert msg.count("yatırım tavsiyesi değildir") == 1, state
            assert len(msg.splitlines()) <= 44, f"{state}: {len(msg.splitlines())} satır"


def test_kart_uzun_satiri_boler_bilgi_dusmez():
    # Uzun RVOL cümlesi satır bütçesini aşarsa bölünür; hiçbir sayı kaybolmaz.
    notifier = TelegramNotifier()
    baglam = {"hacim": ["• 2s: katılım düşük · Son mum hacmi / 20 mumluk ortalama: 0,46× (RVOL) "
                        "· göreli işlem değeri 0,46× · hacim çok düşük"]}
    msg = notifier.format_message(_olay_verisi("KIRILIM_TEYITLI", domain_bolumleri=baglam))
    for parca in ("0,46×", "katılım düşük", "hacim çok düşük"):
        assert parca in msg, parca
    for satir in msg.splitlines():
        assert genislik(satir) <= TELEGRAM_SATIR_PX, satir


def test_klasik_stil_eski_biçimi_korur(monkeypatch):
    # Geri dönüş anahtarı: TELEGRAM_ALERT_STYLE=klasik → 25 Eyl biçimi aynen üretilir.
    # 2026-10-25: klasik stilde de ne geometri ne devamlılık puanı yazılır
    # (§11–§12: puan tek bayraktan iyi çıkmadı, etiket de hüküm veriyordu).
    # Eski "Kalite:" metni `DEVLAMLILIK_AKTIF=0` ile birebir geri gelir.
    monkeypatch.setattr(notifier_mod, "TELEGRAM_ALERT_STYLE", "klasik")
    monkeypatch.setattr(notifier_mod, "DEVLAMLILIK_AKTIF", True)
    msg = TelegramNotifier().format_message(_base_data(state='KIRILIM_TEYITLI', break_dir=1))
    assert "KIRILIM TEYİTLİ: yukarı kırılım" in msg
    assert "Devamlılık" not in msg and "Kalite:" not in msg


def test_klasik_stil_rollback_kaliteyi_dondurur(monkeypatch):
    """`DEVLAMLILIK_AKTIF=0` + klasik → eski metin birebir (rollback yolu)."""
    monkeypatch.setattr(notifier_mod, "TELEGRAM_ALERT_STYLE", "klasik")
    monkeypatch.setattr(notifier_mod, "DEVLAMLILIK_AKTIF", False)
    msg = TelegramNotifier().format_message(_base_data(state='KIRILIM_TEYITLI', break_dir=1))
    assert "Kalite: 85/100" in msg
    assert "Devamlılık" not in msg


def test_mesajlar_ayni_iskeleti_paylasir():
    # Kart iskeleti: 1. satır "olay + hisse + TF" (önizlemede okunsun), 2. satır desen.
    # Klasik yol eski sırayı korur (desen 1. satırda).
    for state in _TUM_STATELER:
        msg = _mesaj(state)
        if not msg:  # tekil push politikası dışında kalan lifecycle state'leri
            continue
        ilk_satir = msg.splitlines()[0]
        assert "THYAO" in ilk_satir, state
        assert "1s" in ilk_satir or "1 saat" in ilk_satir or "saatlik" in ilk_satir, state
        assert "Yükselen Üçgen" in msg or "YÜKSELEN ÜÇGEN" in msg, state  # kart deseni olduğu gibi yazar
        if state in _LIFECYCLE:
            assert any(kelime in ilk_satir for kelime in
                       ("KIRILIM", "SEVİYE KORUNDU", "KIRILIM İPTAL")), state


def test_mesajlar_tek_sabit_footer_tasir():
    # Eskiden üç cümleden biri rastgele ekleniyordu; artık tek ve sabit footer var.
    # Kart sürümü: yalnız yasal satır kalır; `/tara` CTA'sı 2026-10-22'de
    # karttan çıkarıldı (komut çalışmaya devam eder, alarmda tekrar etmez).
    for state in _LIFECYCLE:
        msg = _mesaj(state)
        assert msg.count("yatırım tavsiyesi değildir") == 1, state
        assert "/tara" not in msg, state


def test_ozet_tek_sabit_footer_ve_turkce_tarih():
    n = TelegramNotifier()
    ozet = n.format_daily_summary([
        {"stock_name": "THYAO", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
         "state": "KIRILIM_TEYITLI", "confidence_score": 86, "contraction": 0.7, "break_dir": 1},
    ], {"stocks_scanned": 48, "alerts_sent": 1})
    assert "kanalı takipte kal" not in ozet
    assert "Takipteyim" not in ozet
    assert ozet.rstrip().endswith("📌 yatırım tavsiyesi değildir")
    # Türkçe ay kısaltması: strftime('%b') İngilizce basıyordu. Başlık artık iki
    # satır (tek satır 310 px'tı), tarih girintili devam satırında.
    assert "📊 BIST Formasyon Özeti\n   " in ozet
    assert "Eki" in ozet


def test_ozet_tum_bolumlerde_kalite_gorunur():
    n = TelegramNotifier()
    aktif = [
        {"stock_name": "THYAO", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
         "state": "KIRILIM_TEYITLI", "confidence_score": 86, "contraction": 0.7, "break_dir": 1},
        {"stock_name": "ISMEN", "timeframe": "2h", "pattern_name": "Alçalan Üçgen",
         "state": "RETEST_BASARILI", "confidence_score": 84, "contraction": 0.7, "break_dir": -1},
        {"stock_name": "ISCTR", "timeframe": "4h", "pattern_name": "Alçalan Üçgen",
         "state": "SIKISMA_GUCLENIYOR", "confidence_score": 88, "contraction": 0.81, "break_dir": 0},
    ]
    ozet = n.format_daily_summary(aktif, {"stocks_scanned": 48, "alerts_sent": 1})
    # Üç bölüm de aynı madde biçimini kullanır: hisse · desen · tf · kalite
    assert "THYAO 1h Yükselen Üçgen" in ozet and "q86" in ozet
    assert "KIRILIM" in ozet
    assert "↓ ISMEN 2h Alçalan Üçgen" in ozet and "q84" in ozet
    # Uzun madde satırı " · " üzerinden ikiye iner (telefonda sarmaması için).
    # Madde tek satıra sığıyor: "↔ ISCTR 4h Alçalan Üçgen q88 · %81" yerine kısa
    # biçim ("ISCTR 4h Alçalan Üçgen q88 %81") — veri aynı, satır ikiye bölünmüyor.
    assert "ISCTR 4h Alçalan Üçgen" in ozet and "%81" in ozet



def test_dogrulanmis_olay_kimlik_fiyat_kalite_tasir_kare_detayini_tekrarlamaz():
    notifier = TelegramNotifier()
    msg = notifier.format_message(_base_data(
        state="KIRILIM_TEYITLI",
        confidence_score=87,
        break_dir=1,
        break_price=302.0,
        bar_metni="Mum: 2026-10-12 15:30 kapandı",
        candle_close_price=303.25,
        upper_touches=4,
        lower_touches=3,
        domain_context="🏗 Market Structure\n• 1h yapı: dış yükseliş",
    ))
    assert "THYAO" in msg and "1s" in msg and "Yükselen Üçgen" in msg
    assert "▲ THYAO 1s YUKARI KIRILIM" in msg
    # 2026-10-26: kapanış/kırılan artık ayrı satırlarda (tek satır bütçeyi aşıyordu)
    assert "303,25" in msg and "302,00" in msg and "kırılan" in msg
    # 2026-10-25: formasyon kalitesi (geometri) karttan KALKTI — ölçülen sonucu
    # öngörmüyordu. Yerine devamlılık puanı gelir; geometri yalnız eşiği besler.
    assert "formasyon kalitesi" not in msg and "kalite" not in msg
    # 2026-10-25 (§11–§12): kartta ne sayı ne kalite etiketi var. Puan tek
    # bayraktan iyi çıkmadı; "Devamlılık: yüksek" satırı tamamen kalktı.
    assert "Devamlılık" not in msg
    assert "kırılım gücü 80/100" in msg
    assert "Güçlü" not in msg and "Çok güçlü" not in msg
    # Sade dil (2026-10-22): "retest" yerine "geri çekilme" yazılır.
    assert "kırılan seviyeye dönüş yok" in msg  # payload'da retest_seen yok
    # GÖRSEL-8: tema sayısı ve mum damgası metinde VAR (kullanıcı kararı), ama
    # ham domain dökümü ve ham `bar_metni` basılmaz.
    assert "Market Structure" not in msg
    assert "Mum: 2026-10-12 15:30 kapandı" not in msg


def test_gunluk_ozet_terminal_ve_basarisiz_statei_gostermez():
    notifier = TelegramNotifier()
    msg = notifier.format_daily_summary([
        {"stock_name": "THYAO", "timeframe": "1h", "pattern_name": "Üçgen",
         "state": "FORMASYON_TAMAMLANDI", "confidence_score": 90},
        {"stock_name": "GARAN", "timeframe": "2h", "pattern_name": "Kama",
         "state": "BASARISIZ_KIRILIM", "confidence_score": 88},
    ], {"tarama_sayisi": 1, "alerts_sent": 0})
    assert "THYAO" not in msg and "GARAN" not in msg
    assert "TAMAMLANDI" not in msg and "başarısız" not in msg.lower()


def test_ozet_ve_bulten_satirlari_sarmaz():
    """Özet/bülten satırları da kartla aynı satır bütçesine uyar.

    Alarm kartı ≤283 px sözü veriyor; özet ve bülten aynı sohbete düşüyor ve
    oradaki 400-1 160 px'lık satırlar kartın okunurluğunu sıfırlıyordu.
    """
    from telegram_measure import genislik
    n = TelegramNotifier()
    kayit = {"stock_name": "TOASO", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
             "state": "KIRILIM_GECERSIZLESTI", "break_dir": -1, "critical_price_level": 281.88,
             "confidence_score": 88.0, "candle_close_price": 285.50,
             "upper_touches": 2, "lower_touches": 2,
             "bar_metni": "25.09 09:30 → 13:30 kapanış mumu · 4 mum · gövde %78"}
    aktif = [kayit, dict(kayit, stock_name="BIMAS", timeframe="4h", state="KIRILIM_TEYITLI")]
    gun = {"tarama_sayisi": 4, "alerts_sent": 6, "stocks_scanned": 28, "tam_tarama_guncel": True,
           "kirilim_teyitli_olay_sayisi": 3, "retest_basarili_olay_sayisi": 1,
           "kirilim_gecersizlesti_olay_sayisi": 2, "son_tarama_bitis": "2026-09-25T16:38:20+03:00"}
    metinler = [n.format_public_tekil(aktif[0]), n.format_public_tekil(aktif[1]),
                n.format_daily_summary(aktif, gun),
                n.format_public_summary(aktif, gun, izleme=[{"stock": "FROTO", "timeframe": "1h",
                                                              "pattern_name": "Alçalan Kama",
                                                              "quality": 82}], kapanis=True)]
    asan = [satir for metin in metinler for satir in metin.splitlines()
            if genislik(satir) > 283]
    assert not asan, asan[:3]


def test_metin_sigdir_bilgi_dusurmez():
    """Bölme yalnız satır sonu ekler: kelimeler aynen durur (ayraç hariç)."""
    n = TelegramNotifier()
    uzun = {"stock_name": "DOHOL", "timeframe": "2h", "pattern_name": "Alçalan Üçgen",
             "state": "KIRILIM_TEYITLI", "break_dir": 1, "critical_price_level": 21.28,
             "confidence_score": 87.0, "candle_close_price": 21.90,
             "upper_touches": 2, "lower_touches": 2}
    metin = n.format_public_tekil(uzun)
    kelimeler = " ".join(metin.split())
    assert "DOHOL" in kelimeler and "21,28" in kelimeler
    assert "formasyon kalitesi" not in kelimeler
    assert "Devamlılık" not in kelimeler
