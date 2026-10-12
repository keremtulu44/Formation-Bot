from datetime import datetime
from notifier import TelegramNotifier


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


def test_tamamlandi_retest_var():
    notifier = TelegramNotifier()
    data = _base_data(state='FORMASYON_TAMAMLANDI', break_dir=1, retest_seen=True)
    msg = notifier.format_message(data)
    assert "TAMAMLANDI" in msg
    assert "retest başarılı" in msg.lower()


def test_tamamlandi_retest_yok():
    notifier = TelegramNotifier()
    data = _base_data(state='FORMASYON_TAMAMLANDI', break_dir=-1, retest_seen=False)
    msg = notifier.format_message(data)
    assert "TAMAMLANDI" in msg
    # Retest görülmediyse mesajda bu ifade olmalı
    assert "retest olmadan ilerledi" in msg
    assert "geri dönmedi" in msg


def test_tamamlandi_retest_yok_yukari():
    notifier = TelegramNotifier()
    data = _base_data(state='FORMASYON_TAMAMLANDI', break_dir=1, retest_seen=False)
    msg = notifier.format_message(data)
    assert "retest olmadan ilerledi" in msg
    assert "yukarı kırılım" in msg.lower()


def test_tamamlandi_retest_yok_asagi():
    notifier = TelegramNotifier()
    data = _base_data(state='FORMASYON_TAMAMLANDI', break_dir=-1, retest_seen=False)
    msg = notifier.format_message(data)
    assert "aşağı kırılım" in msg.lower()
    assert "retest olmadan" in msg.lower()


def test_tamamlandi_default_retest_var():
    notifier = TelegramNotifier()
    # retest_seen alanı yoksa varsayılan True gibi davranmalı (eski uyumluluk)
    data = _base_data(state='FORMASYON_TAMAMLANDI', break_dir=1)
    # retest_seen'i sil
    data.pop('retest_seen', None)
    msg = notifier.format_message(data)
    # Varsayılan True ise retest başarılı yazar
    assert "TAMAMLANDI" in msg


def test_kirilim_teyitli_yon():
    notifier = TelegramNotifier()
    data_yukari = _base_data(state='KIRILIM_TEYITLI', break_dir=1)
    msg_yukari = notifier.format_message(data_yukari)
    assert "yukarı kırılım" in msg_yukari.lower()

    data_asagi = _base_data(state='KIRILIM_TEYITLI', break_dir=-1)
    msg_asagi = notifier.format_message(data_asagi)
    assert "aşağı kırılım" in msg_asagi.lower()


def test_sikisma_mesaji():
    notifier = TelegramNotifier()
    data = _base_data(state='SIKISMA_GUCLENIYOR', contraction=0.85)
    msg = notifier.format_message(data)
    assert "sıkışma güçleniyor" in msg.lower()
    assert "THYAO" in msg


def test_retest_basarili_mesaji():
    notifier = TelegramNotifier()
    data = _base_data(state='RETEST_BASARILI', break_dir=1)
    msg = notifier.format_message(data)
    assert "RETEST BAŞARILI" in msg
    assert "retest tuttu" in msg.lower()


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
    assert "deneme" in msg.lower()
    assert "yukarı" in msg.lower() or "aşağı" in msg.lower()


def test_basarısız_kirilim_mesaji():
    notifier = TelegramNotifier()
    data = _base_data(state='BASARISIZ_KIRILIM')
    msg = notifier.format_message(data)
    assert "başarısız" in msg.lower()


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
    assert "yukarı" in ozet and "aşağı" in ozet
    # Zaman dilimi üç bölümde de görünür (tutarlılık)
    assert "ISMEN Alçalan Üçgen 2h" in ozet
    assert "AKSEN Alçalan Kama 1d" in ozet
    # Sıkışanlar: hisse önce, daralma sonra
    assert "ISCTR Alçalan Üçgen 4h · %81 daralma" in ozet


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


def test_mesajlar_telefona_sigar_boyutta():
    for state in _TUM_STATELER:
        for varyant in ({}, {"break_dir": -1}, {"retest_seen": False}, {"contraction": 0.93}):
            msg = _mesaj(state, **varyant)
            assert len(msg) <= 400, f"{state}: {len(msg)} karakter (telefon için fazla uzun)"
            for satir in msg.splitlines():
                # Tek satıra sığmayan satır telefonda sarar; hiçbir satır sarmalanmamalı.
                assert len(satir) <= 70, f"{state}: {len(satir)} karakterlik satır sarar"


def test_mesajlar_ayni_iskeleti_paylasir():
    # Her mesaj: "emoji HISSE tf · desen" başlığı ile başlar (tek bakışta ne olduğu anlaşılır).
    for state in _TUM_STATELER:
        ilk_satir = _mesaj(state).splitlines()[0]
        assert "THYAO" in ilk_satir, state
        assert "saatlik" in ilk_satir, state
        assert "Yükselen Üçgen" in ilk_satir, state


def test_mesajlar_tek_sabit_footer_tasir():
    # Eskiden üç cümleden biri rastgele ekleniyordu; artık tek ve sabit footer var.
    for state in ("KIRILIM_ADAYI", "KIRILIM_TEYITLI", "RETEST_BASARILI", "FORMASYON_TAMAMLANDI"):
        msg = _mesaj(state)
        assert msg.count("Formasyon takibi · yatırım tavsiyesi değildir") == 1, state


def test_ozet_tek_sabit_footer_ve_turkce_tarih():
    n = TelegramNotifier()
    ozet = n.format_daily_summary([
        {"stock_name": "THYAO", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
         "state": "FORMASYON_TAMAMLANDI", "confidence_score": 86, "contraction": 0.7, "break_dir": 1},
    ], {"stocks_scanned": 48, "alerts_sent": 1})
    assert "kanalı takipte kal" not in ozet
    assert "Takipteyim" not in ozet
    assert ozet.rstrip().endswith("Formasyon takibi · yatırım tavsiyesi değildir")
    # Türkçe ay kısaltması: strftime('%b') İngilizce basıyordu.
    assert " BIST Formasyon Özeti · " in ozet


def test_ozet_tum_bolumlerde_kalite_gorunur():
    n = TelegramNotifier()
    aktif = [
        {"stock_name": "THYAO", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
         "state": "FORMASYON_TAMAMLANDI", "confidence_score": 86, "contraction": 0.7, "break_dir": 1},
        {"stock_name": "ISMEN", "timeframe": "2h", "pattern_name": "Alçalan Üçgen",
         "state": "RETEST_BASARILI", "confidence_score": 84, "contraction": 0.7, "break_dir": -1},
        {"stock_name": "ISCTR", "timeframe": "4h", "pattern_name": "Alçalan Üçgen",
         "state": "SIKISMA_GUCLENIYOR", "confidence_score": 88, "contraction": 0.81, "break_dir": 0},
    ]
    ozet = n.format_daily_summary(aktif, {"stocks_scanned": 48, "alerts_sent": 1})
    # Üç bölüm de aynı madde biçimini kullanır: hisse · desen · tf · kalite
    assert "THYAO Yükselen Üçgen 1h · kalite 86" in ozet
    assert "ISMEN Alçalan Üçgen 2h · aşağı yön · kalite 84" in ozet
    assert "ISCTR Alçalan Üçgen 4h · %81 daralma" in ozet
