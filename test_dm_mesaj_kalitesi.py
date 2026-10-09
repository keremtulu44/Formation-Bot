"""DM mesaj kalitesi regresyon testleri (Aşama: mesaj görüntüleme standartları).

Kapsam: günlük özet yön metni, fiyat gösterim birliği (görüntüleme katmanı),
izleme durumlarının ortak Türkçe sözlüğü, MS bağlamının korunması, fallback
sözleşmesi ve public formatının değişmediğinin kilidi. Hesaplama/veri katmanına
dokunulmaz; yalnızca formatter çıktıları doğrulanır.
"""

import copy
import math

import pytest

import main as main_module
import notifier as notifier_module
from formation_dm_context import display_price
from telegram_alert_flow import STATE_TR as STATE_TR_ORTAK


def _notifier():
    n = notifier_module.TelegramNotifier.__new__(notifier_module.TelegramNotifier)
    n.public_sikisma_min = 0.8
    n.public_states = {"FORMASYON_TAMAMLANDI", "RETEST_BASARILI"}
    return n


def _dm_veri(**override):
    data = {
        "stock_name": "KRDMD", "timeframe": "1h", "pattern_name": "Yükselen Üçgen",
        "state": "KIRILIM_TEYITLI", "confidence_score": 89.036,
        "break_price": 45.59949789047241, "critical_price_level": None,
        "upper_now": 45.59949789047241, "lower_now": 44.10,
        "break_dir": -1, "break_strength": 82, "contraction": 0.56,
        "timestamp": "2026-09-14 10:30", "retest_seen": False,
        "upper_touches": 2, "lower_touches": 2, "age_bars": 83,
        "mtf_destek": True, "lifecycle_event_id": "BREAK_CONFIRMED:2026-09-14T10:30",
        "watch_context": [], "dm_context": {},
    }
    data.update(override)
    return data


# --------------------------------------------------------- A: özet yön metni --
def test_yon_metni_kod_eslemesi():
    """Kodda ölçülmüş iç temsil: 1=yukarı, -1=aşağı (main kritik seviye seçimi +
    format_dm_message 'yukarı/aşağı' kullanımı ile aynı sözleşme)."""
    assert notifier_module.yon_metni(1) == "yukarı"
    assert notifier_module.yon_metni(-1) == "aşağı"
    assert notifier_module.yon_metni(2) == "yukarı"      # pozitif = yukarı sözleşmesi
    assert notifier_module.yon_metni(0) == ""            # tahmin yok
    assert notifier_module.yon_metni(None) == ""
    assert notifier_module.yon_metni("x") == ""
    assert notifier_module.yon_metni(float("nan")) == ""


def test_ozet_retest_yonu_turkce_ve_bilinmeyen_tahminsiz():
    n = _notifier()
    ozet = n.format_daily_summary([
        {"stock_name": "GARAN", "pattern_name": "Alçalan Kama",
         "state": "RETEST_BASARILI", "break_dir": -1},
        {"stock_name": "THYAO", "pattern_name": "Yükselen Üçgen",
         "state": "RETEST_BASARILI", "break_dir": 1},
        {"stock_name": "SISE", "pattern_name": "Simetrik Üçgen",
         "state": "RETEST_BASARILI", "break_dir": 0},
    ])
    satirlar = [l for l in ozet.splitlines() if l.startswith("•")]
    assert "• GARAN Alçalan Kama - aşağı yön" in satirlar
    assert "• THYAO Yükselen Üçgen - yukarı yön" in satirlar
    # Bilinmeyen/eksik yön: yön iddiası üretilmez, satır yine de sembol+formasyonu verir.
    assert "• SISE Simetrik Üçgen" in satirlar
    assert not any("-1 yön" in l or "0 yön" in l or "1 yön" in l for l in satirlar)
    assert not any("-  yön" in l for l in satirlar)


# --------------------------------------------------- B: fiyat görüntüleme ----
def test_dm_seviye_iki_ondalik_kaynak_degismez():
    n = _notifier()
    veri = _dm_veri()
    once = copy.deepcopy(veri)
    msg = n.format_dm_message(veri)
    assert veri == once                                  # ham veri dokunulmaz
    olay = [l for l in msg.splitlines() if "kırılım" in l][0]
    assert "Aşağı kırılım 45.60 teyitli · retest bekleniyor" == olay
    assert "45.59949789047241" not in msg


def test_dm_seviye_break_price_onceligi_ve_fallback():
    n = _notifier()
    msg = n.format_dm_message(_dm_veri(break_price=45.60, critical_price_level=44.10))
    assert "45.60 teyitli" in msg
    msg2 = n.format_dm_message(_dm_veri(break_price=None, critical_price_level=44.105))
    assert "44.11" in msg2 or "44.10" in msg2            # fallback seviye de 2 ondalık
    assert "44.105" not in msg2


def test_dm_seviye_farkli_buyuklukler_esik_yuvarlama():
    n = _notifier()
    for ham, beklenen in ((13.2375, "13.24"), (488.55882352941177, "488.56"),
                          (275.25, "275.25"), (45.995, f"{45.995:.2f}")):
        msg = n.format_dm_message(_dm_veri(break_price=ham))
        assert f"kırılım {beklenen}" in msg, (ham, msg)


def test_dm_gecersiz_seviye_gecerli_gibi_gosterilmez():
    n = _notifier()
    for gecersiz in (None, float("nan"), float("inf"), float("-inf"), "abc"):
        msg = n.format_dm_message(_dm_veri(break_price=gecersiz,
                                           critical_price_level=gecersiz))
        assert "nan" not in msg and "inf" not in msg
        assert "kırılım None" not in msg
    # Görüntüleyici yardımcısı aynı sözleşmeyi tek kaynaktan uygular:
    assert display_price("abc") == ""
    assert display_price(None) == ""
    assert display_price(float("nan")) == ""
    assert display_price(45.59949789047241) == "45.60"


def test_seviye_ve_bolge_sinirlari_ayni_gorunum_standarti():
    n = _notifier()
    veri = _dm_veri(dm_context={
        "structure": "1H BOS ↓",
        "volume": "Normal",
        "nearby_zones": ["↑ 1H OB · 45.68–46.26", "↓ 2H OB · 44.54–45.12"],
    })
    msg = n.format_dm_message(veri)
    seviye = [l for l in msg.splitlines() if "kırılım" in l][0]
    assert "45.60" in seviye                              # seviye 2 ondalık
    assert "↑ 1H OB · 45.68–46.26" in msg                 # bölge sınırları da 2 ondalık
    assert "45.59949789047241" not in msg
    # Standart tek kaynaktan: display_price bölge gösterimiyle aynı biçim.
    assert display_price(45.68) == "45.68" and display_price(46.26) == "46.26"


# ------------------------------------- C: izleme durumları ortak sözlük ------
def test_izleme_durumu_turkce_ve_digest_ile_ayni():
    n = _notifier()
    aday = {"stock": "GARAN", "timeframe": "4h", "pattern_name": "Alçalan Kama",
            "state": "SIKISMA_GUCLENIYOR", "quality": 83.2}
    msg = n.format_dm_message(_dm_veri(
        state="KIRILIM_ADAYI",
        watch_context=[aday],
    ))
    assert "• GARAN 4H Alçalan Kama: Sıkışma güçleniyor · kalite 83" in msg
    assert "SIKISMA GUCLENIYOR" not in msg
    digest = main_module._format_deferred_alert_summary([dict(aday, contraction=0.7)])
    assert "Sıkışma güçleniyor" in digest                 # aynı terminoloji


def test_izleme_bilinmeyen_durum_uydurulmaz():
    n = _notifier()
    msg = n.format_dm_message(_dm_veri(
        state="KIRILIM_ADAYI",
        watch_context=[{"stock": "SISE", "timeframe": "1h", "pattern_name": "Kama",
                        "state": "BILINMEYEN_DURUM", "quality": 80.0}],
    ))
    assert "BILINMEYEN_DURUM" in msg                      # ham kod korunur, uydurulmaz


def test_state_tr_tek_kaynak():
    """main ve notifier aynı sözlük nesnesini kullanır (bağımsız kopya yok)."""
    import telegram_alert_flow
    assert main_module.STATE_TR is telegram_alert_flow.STATE_TR
    assert notifier_module.STATE_TR is telegram_alert_flow.STATE_TR
    assert STATE_TR_ORTAK["SIKISMA_GUCLENIYOR"] == "Sıkışma güçleniyor"


# --------------------------------------- D: MS bağlamının korunması ----------
def test_ms_karsi_yonlu_olaylar_bilgi_kaybı_olmadan_gosterilir():
    """Farklı TF'lerde zıt yönlü BOS/CHoCH teknik olarak mümkündür; formatter
    yön oklarını kırılım yönüne zorlamaz ve bağlamı silmez (karar: veri doğru,
    her etiket kendi TF önekiyle ayrıştırılabilir)."""
    n = _notifier()
    msg = n.format_dm_message(_dm_veri(dm_context={
        "structure": "1H BOS ↑ · 2H — · 4H CHoCH ↓ · 1D CHoCH ↓",
        "volume": "Normal",
    }))
    yapilar = [l for l in msg.splitlines() if l.startswith("Yapı:")]
    assert yapilar == ["Yapı: 1H BOS ↑ · 2H — · 4H CHoCH ↓ · 1D CHoCH ↓"]


def test_baglam_olan_alanlar_satir_olur_olmayan_uydurulmaz():
    n = _notifier()
    tam = n.format_dm_message(_dm_veri(dm_context={
        "structure": "1H BOS ↑", "volume": "Yükselen",
        "nearby_zones": ["↑ 1H OB · 45.68–46.26"],
    }))
    for satir in ("Yapı: 1H BOS ↑", "Hacim: Yükselen", "Yakın bölgeler",
                  "↑ 1H OB · 45.68–46.26"):
        assert satir in tam
    yalniz = n.format_dm_message(_dm_veri(dm_context={"volume": "Yükselen"}))
    assert "Hacim: Yükselen" in yalniz
    assert "Yapı:" not in yalniz and "Yakın bölgeler" not in yalniz


# --------------------------------- Fallback ve public sözleşmeleri ------------
def test_fallback_mesaji_baglamsiz_uretilir_format_korunur():
    """Kurtarma yolu (prepared fallback) dm_context={} ile üretilir: bağlam
    satırları yoktur ama temel alanlar (başlık/durum/sayılar/olay) aynen durur."""
    n = _notifier()
    msg = n.format_dm_message(_dm_veri())
    satirlar = msg.splitlines()
    assert satirlar[0] == "KRDMD · 1H Yükselen Üçgen"
    assert satirlar[1] == "KIRILIM TEYİTLİ"
    assert satirlar[2] == "Kalite 89 · Daralma %56 · 4 temas · 83 bar"
    assert "Aşağı kırılım 45.60 teyitli · retest bekleniyor" in msg
    assert "Yapı:" not in msg and "Hacim:" not in msg and "Yakın bölgeler" not in msg


def test_public_formati_dm_baglamindan_etkilenmez():
    """Public renderer dm_context'i hiç kullanmaz; izleme satırları dahil mevcut
    public davranışı bu görevle bilinçli olarak değiştirilmedi."""
    n = _notifier()
    veri = _dm_veri(state="KIRILIM_TEYITLI", dm_context={
        "structure": "1H BOS ↑", "volume": "Yükselen",
        "nearby_zones": ["↑ 1H OB · 45.68–46.26"],
    }, watch_context=[{"stock": "GARAN", "timeframe": "4h",
                       "pattern_name": "Alçalan Kama",
                       "state": "SIKISMA_GUCLENIYOR", "quality": 83.2}])
    public = n.format_message(veri)
    assert "Yapı:" not in public and "Yakın bölgeler" not in public
    assert "aşağı kırılım" in public                     # mevcut public anlatımı (yön)
    assert "45.60" in public                             # public seviye gösterimi zaten 2 ondalık
    assert "sikisma gucleniyor" in public                # public izleme satırı: mevcut ASCII davranışı bilinçli korunur (kapsam dışı)


def test_dm_ana_alanlar_kaybolmaz_ham_fiyat_ornek():
    """Onaylı örnek: KRDMD 1h teyit (gerçek cache değerleri) — önemli alanlar."""
    n = _notifier()
    msg = n.format_dm_message(_dm_veri(dm_context={"volume": "Normal"}))
    satirlar = msg.splitlines()
    assert satirlar[0] == "KRDMD · 1H Yükselen Üçgen"
    assert satirlar[1] == "KIRILIM TEYİTLİ"
    assert satirlar[2] == "Kalite 89 · Daralma %56 · 4 temas · 83 bar"
    assert "Aşağı kırılım 45.60 teyitli · retest bekleniyor" in satirlar
    assert "Seviye direnç olabilir" in satirlar
    assert "MTF: 4H destekliyor" in satirlar
    assert "Hacim: Normal" in satirlar
