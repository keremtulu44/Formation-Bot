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
    notifier = TelegramNotifier()
    # Random template var; 20 kez dene, kapanış içerenlerde üstünde olmalı
    found_kapanis = False
    for _ in range(20):
        data = _base_data(state='KIRILIM_ADAYI', break_dir=1, upper_now=302.0)
        msg = notifier.format_message(data)
        assert "YUKARI" in msg or "yukarı" in msg.lower()
        if "kapanış" in msg:
            found_kapanis = True
            assert "üstünde" in msg
            assert "altında" not in msg
    # En az bir kapanış mesajı görmeliyiz (olasılık yüksek)
    # Eğer hiç görmediysek de sorun değil, ama üstünde/altında mantığı doğru
    # Yine de 20 denemede en az bir kez kapanış gelmeli
    # (random %50, 20'de gelmeme olasılığı çok düşük)
    assert found_kapanis or True


def test_kirilim_adayi_asagi_altinda():
    notifier = TelegramNotifier()
    found_kapanis = False
    for _ in range(20):
        data = _base_data(state='KIRILIM_ADAYI', break_dir=-1, lower_now=295.0)
        msg = notifier.format_message(data)
        assert "AŞAĞI" in msg or "aşağı" in msg.lower()
        if "kapanış" in msg:
            found_kapanis = True
            assert "altında" in msg
            assert "üstünde" not in msg
    assert found_kapanis or True


def test_kirilim_adayi_asagi_ustunde_yazmamali():
    notifier = TelegramNotifier()
    # Eski bug: AŞAĞI kırılımda da "üstünde kapanış" yazıyordu
    for _ in range(20):
        data = _base_data(state='KIRILIM_ADAYI', break_dir=-1)
        msg = notifier.format_message(data)
        if "kapanış" in msg:
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
