"""
FAZ 1 zamanlama + ölü-formasyon regresyon testleri.

Neden bu test? 6 Eylül 2026 ölçümlerinde bulunan iki sistematik hata
botu sessizce körleştiriyordu:
  1) yfinance'in .IS 1H mumları :30'da kapanır (etiket = mum BAşı, son mum 17:30
     etiketli ve 18:30'da kapanır) ama bot "saat başı + 5 dk" (=:05) tetikleniyordu
     -> her tarama veriyi 35 DAKİKA geç gösteriyordu ve günün son mumu hiç
     analiz edilmiyordu (pencere 18:10'da kapanıyordu).
  2) Terminal (ölü) formasyonlar "canlı" gibi raporlanıyordu -> günler önce
     tamamlanmış/başarısız formasyonlar için her taramada "🏁 TAMAMLANDI" mesajı.

Çalıştırma:  python3 test_tarama_zamani.py
"""

import inspect
import os
import sys
import tempfile
from datetime import datetime, time as dt_time

import pandas as pd

from config import (BIST_OPEN, BIST_CLOSE, CANDLE_CLOSE_MINUTE, SCAN_DELAY_AFTER_CLOSE_MIN,
                    STALE_BAR_UYARI_DK, TARAMA_PENCERE_SONU, TERMINAL_TAZE_BAR)
import data as data_mod
import main as main_mod
from data import (son_kapanan_mum_ani, tarama_animi_mi, tarama_penceresi_acik_mi,
                  time_until_next_candle_close)
from patterns import ArgentEngine
from patterns.constants import (ST_BREAK_FAILED, ST_BREAK_TIMEOUT, ST_COMPLETED, ST_INVALID,
                                 f_is_dead_state)

IST = data_mod.ISTANBUL_TZ
gecen, kalan = 0, []


def kontrol(ad, kosul, detay=""):
    global gecen
    if kosul:
        gecen += 1
        print(f"  [OK]   {ad}" + (f"  ({detay})" if detay else ""))
    else:
        kalan.append(ad)
        print(f"  [FAIL] {ad}" + (f"  ({detay})" if detay else ""))


def t(yil, ay, gun, saat=0, dakika=0):
    """Istanbul saat diliminde sabit bir an."""
    return IST.localize(datetime(yil, ay, gun, saat, dakika))


print("=== 1. MUM KAPANIŞ / TARAMA ANI ZAMANLAMASI ===")
print(f"    config: mum :{CANDLE_CLOSE_MINUTE:02d} kapanır, "
      f"+{SCAN_DELAY_AFTER_CLOSE_MIN} dk -> tarama :{CANDLE_CLOSE_MINUTE + SCAN_DELAY_AFTER_CLOSE_MIN:02d}")
kontrol("mum kapanışı :30 (ölçüm: barlar bitişik, close[i]==open[i+1])",
        CANDLE_CLOSE_MINUTE == 30)
kontrol("tarama anı mum kapanışı + 5 dk = :35",
        CANDLE_CLOSE_MINUTE + SCAN_DELAY_AFTER_CLOSE_MIN == 35)

# son kapanan mum
kontrol("09:50 -> bugün henüz mum kapanmadı",
        son_kapanan_mum_ani(t(2026, 9, 25, 9, 50)) is None)
kontrol("10:29 -> henüz kapanmadı",
        son_kapanan_mum_ani(t(2026, 9, 25, 10, 29)) is None)
kontrol("10:35 -> ilk mum 10:30'da kapandı",
        son_kapanan_mum_ani(t(2026, 9, 25, 10, 35)) == t(2026, 9, 25, 10, 30))
kontrol("12:35 -> 12:30'da kapandı (11:30 etiketli mum)",
        son_kapanan_mum_ani(t(2026, 9, 25, 12, 35)) == t(2026, 9, 25, 12, 30))
kontrol("18:35 -> GÜNÜN SON MUMU 18:30'da kapandı",
        son_kapanan_mum_ani(t(2026, 9, 25, 18, 35)) == t(2026, 9, 25, 18, 30),
        "17:30 etiketli mum analiz edilebilir olmalı")

# tarama anı mı?
for saat, dk, beklenen in [
    (9, 50, False), (10, 29, False), (10, 30, False), (10, 34, False),
    (10, 35, True), (11, 35, True), (12, 35, True), (17, 35, True), (18, 35, True),
    (12, 30, False), (18, 30, False),
]:
    kontrol(f"{saat:02d}:{dk:02d} tarama anı mı -> {beklenen}",
            tarama_animi_mi(t(2026, 9, 25, saat, dk)) == beklenen)

# aynı kapanış iki kez taranmasın
kontrol("aynı mum 2. kez taranmaz",
        not tarama_animi_mi(t(2026, 9, 25, 12, 36), t(2026, 9, 25, 12, 30)))
kontrol("yeni mum kapanınca tekrar taranır",
        tarama_animi_mi(t(2026, 9, 25, 13, 35), t(2026, 9, 25, 12, 30)))
kontrol("hafta sonu tarama yok",
        not tarama_animi_mi(t(2026, 9, 26, 12, 35)))

# tarama penceresi
kontrol("pencere 09:50'de açık", tarama_penceresi_acik_mi(t(2026, 9, 25, 9, 50)))
kontrol("pencere 18:40'ta (son tarama + pay) açık", tarama_penceresi_acik_mi(t(2026, 9, 25, 18, 40)))
kontrol("pencere 18:45'te kapalı", not tarama_penceresi_acik_mi(t(2026, 9, 25, 18, 45)))
kontrol("pencere hafta sonu kapalı", not tarama_penceresi_acik_mi(t(2026, 9, 26, 12, 0)))
kontrol("BIST_OPEN hâlâ seans başlangıcı", BIST_OPEN == dt_time(9, 50))
kontrol("TARAMA_PENCERE_SONU 18:30 kapanışını KAPLAR (>18:30)",
        TARAMA_PENCERE_SONU > dt_time(18, 30))
kontrol("eski 18:10 kapanış sınırı kaldırıldı", BIST_CLOSE != TARAMA_PENCERE_SONU)

# gecikme: tarama anındaki en yeni TAMAMLANMIŞ mum 5 dk önce kapanmış olmalı
bekle = time_until_next_candle_close(t(2026, 9, 25, 12, 35))
kontrol("12:35'te bir sonraki tarama 13:35", abs(bekle - 3600) < 1, f"{bekle/60:.0f} dk")

print()
print("=== 2. TAMAMLANMIŞ MUM FİLTRESİ GÜNÜN SON MUMUNU GÖRÜYOR ===")
mgr = data_mod.StockDequeManager()
df = mgr.to_dataframe("THYAO")
if df is not None:
    son_tarama = t(2026, 9, 25, 18, 35)
    t_df = data_mod.tamamlanmis_mumlar(df, "1h", now=son_tarama)
    kontrol("18:35 taramasında son mum = 17:30 (günün son mumu)",
            t_df is not None and t_df.index[-1].strftime("%H:%M") == "17:30",
            t_df.index[-1].strftime("%H:%M") if t_df is not None else "yok")
    kontrol("17:59'da son mum 16:30 (17:30'lu mum henüz kapanmadı)",
            data_mod.tamamlanmis_mumlar(df, "1h", now=t(2026, 9, 25, 17, 59)).index[-1].strftime("%H:%M") == "16:30")
    kontrol("18:00'de son mum 17:30 (1H mum 1 saat sonra kapanır)",
            data_mod.tamamlanmis_mumlar(df, "1h", now=t(2026, 9, 25, 18, 0)).index[-1].strftime("%H:%M") == "17:30")
else:
    print("  [SKIP] THYAO cache yok")

print()
print("=== 3. ÖLÜ (TERMINAL) FORMASYON ALERT ÜRETMİYOR ===")
kontrol("f_is_dead_state: COMPLETED/BREAK_FAILED/INVALID/BREAK_TIMEOUT ölü",
        all(f_is_dead_state(s) for s in (ST_COMPLETED, ST_BREAK_FAILED, ST_INVALID, ST_BREAK_TIMEOUT)))
kontrol("f_is_dead_state: canlı state'ler (SIKISMA/OLGUNLASIYOR) canlı",
        not f_is_dead_state("SIKISMA_GUCLENIYOR") and not f_is_dead_state("OLGUNLASIYOR"))
kontrol("TERMINAL_TAZE_BAR makul (1-10 bar)", 1 <= TERMINAL_TAZE_BAR <= 10)
kontrol("STALE_BAR_UYARI_DK makul (30-360 dk)", 30 <= STALE_BAR_UYARI_DK <= 360)

# --- 3a. Mekanizmanın birebir testi (sentetik piyasaya bağımlı değil) ---
# Amaç: terminal geçiş "tazeyse" (son TERMINAL_TAZE_BAR bar) raporlanır,
# eskidiğinde canlı formasyon None olur.
from patterns.constants import ST_RETEST_OK

import contextlib  # noqa: E402
import io as _io   # noqa: E402

# test_triangle modül düzeyinde kendi testlerini çalıştırır -> çıktısını yut
with contextlib.redirect_stdout(_io.StringIO()):
    from test_triangle import create_perfect_symmetrical_triangle  # noqa: E402
    d = create_perfect_symmetrical_triangle(140)
eng = ArgentEngine(profile="Dengeli")
eng.process(d)
if eng.active is None or not eng.active.valid:
    # formasyon kurulup bitmiş olabilir: canlı olduğu son anı bul
    for i in range(len(d) - 1, 100, -1):
        s2 = eng.process(d.iloc[:i])
        if s2.active is not None:
            break
kontrol("sentetik veride canlı formasyon bulundu", eng.active is not None and eng.active.valid)

# terminal geçiş 10 bar önce olmuş -> ÖLÜ, raporlanmamalı
eng.pattern_state = ST_COMPLETED
eng.pattern_state_bar = eng.bar_index - 10
snap_olu = eng._snapshot(ST_RETEST_OK, [], d)
kontrol("terminal + eski geçiş -> canlı formasyon None", snap_olu.active is None, snap_olu.log)
kontrol("log ölü formasyonu açıkça yazar", "Ölü formasyon" in snap_olu.log, snap_olu.log)

# terminal geçiş 1 bar önce olmuş -> TAZE, bir kez raporlanır (az önce tamamlandı)
eng.pattern_state_bar = eng.bar_index - 1
snap_taze = eng._snapshot(ST_RETEST_OK, [], d)
kontrol("terminal + TAZE geçiş (1 bar) -> hâlâ raporlanır", snap_taze.active is not None)

# terminal geçiş tam sınırda (TERMINAL_TAZE_BAR bar) -> raporlanır
eng.pattern_state_bar = eng.bar_index - TERMINAL_TAZE_BAR
snap_sinir = eng._snapshot(ST_RETEST_OK, [], d)
kontrol(f"terminal + {TERMINAL_TAZE_BAR} bar önce -> hâlâ raporlanır", snap_sinir.active is not None)

# sınırın 1 fazlası -> raporlanmaz
eng.pattern_state_bar = eng.bar_index - TERMINAL_TAZE_BAR - 1
snap_asim = eng._snapshot(ST_RETEST_OK, [], d)
kontrol(f"terminal + {TERMINAL_TAZE_BAR + 1} bar önce -> raporlanmaz", snap_asim.active is None)

# canlı state (SIKISMA) hiç filtrelenmez
eng.pattern_state = "SIKISMA_GUCLENIYOR"
eng.pattern_state_bar = eng.bar_index - 500
snap_canli = eng._snapshot(ST_RETEST_OK, [], d)
kontrol("canlı state 500 bar sonra da raporlanır", snap_canli.active is not None)

# --- 3b. Gerçek BIST verisi invaryantı ---
# Kural: state ölü VE geçiş eskiyse snapshot.active None olmalı.
# (Eski davranışta günler önce biten 44 formasyon "canlı" görünüyordu.)
try:
    from data import resample_all_timeframes, tamamlanmis_mumlar as tmm
    from patterns import PatternLifecycleManager

    lc = PatternLifecycleManager(profile="Dengeli")
    olu_filtrelenen = taze_terminal = toplam_olu = 0
    for stock in ("THYAO", "ISCTR", "KRDMD", "PETKM", "HALKB", "GARAN"):
        df = mgr.to_dataframe(stock)
        if df is None or len(df) < 50:
            continue
        for tf_name, d_tf in resample_all_timeframes(df).items():
            d_tf = tmm(d_tf, tf_name, now=t(2026, 9, 25, 12, 35))
            if d_tf is None or len(d_tf) < 30:
                continue
            snap = lc.scan(stock + "_" + tf_name, d_tf, tam_yeniden=True)
            if not f_is_dead_state(snap.state):
                continue
            toplam_olu += 1
            yas = lc.get_engine(stock + "_" + tf_name).bar_index - \
                lc.get_engine(stock + "_" + tf_name).pattern_state_bar
            if yas > TERMINAL_TAZE_BAR:
                olu_filtrelenen += 1
                if snap.active is not None:
                    kalan.append(f"{stock} {tf_name} ölü formasyon canlı gösterildi ({snap.state})")
            else:
                taze_terminal += 1
    kontrol("gerçek veride ölü formasyonlar filtrelendi (en az 1)",
            olu_filtrelenen >= 1, f"{olu_filtrelenen}/{toplam_olu} ölü, {taze_terminal} taze")
    kontrol("filtrelenenlerin hiçbiri canlı gösterilmiyor",
            not [k for k in kalan if "canlı gösterildi" in k])
except Exception as e:
    kalan.append(f"gerçek veri invaryantı çalıştırılamadı: {e}")
    print(f"  [FAIL] gerçek veri hatası: {e}")

print()
print("=== 4. fetch_yfinance_1h auto_adjust=False ===")
src = inspect.getsource(data_mod.fetch_yfinance_1h)
kontrol("history() çağrısı auto_adjust=False içeriyor", "auto_adjust=False" in src)

print()
print("=== 5. FAZ 2: 1D GECİKME DÜZELTMESİ ===")
from data import resample_all_timeframes, tamamlanmis_mumlar as tmm
kontrol("1D mumu seans kapanışında (18:30) tamamlanır",
        tmm(resample_all_timeframes(df)['1d'], '1d', now=t(2026, 9, 25, 18, 29)).index[-1].strftime('%d') == '24',
        "18:29'da hâlâ 24 Eylül")
kontrol("18:35'te günün 1D mumu analiz edilir (24 saatlik körlük bitti)",
        tmm(resample_all_timeframes(df)['1d'], '1d', now=t(2026, 9, 25, 18, 35)).index[-1].strftime('%d') == '25',
        "25 Eylül mumu görülüyor")
# P0 DÜZELTMESİ (2 Eki 2026): 2h/4h kovaları artık seans sonunda (18:00) kesilir.
# Eski hata: kova "+2sa/+4sa" ile 19:30/21:30'a kadar yarım sayılıyordu ->
# 18:35 taramasında 2h son kova 15:30, 4h son kova 13:30'da kalıyor, günün
# kapanış saati (17:30–18:00) hiç analiz edilmiyordu.
for tf_name, beklenen in [('1h', '17:30'), ('2h', '17:30'), ('4h', '17:30')]:
    d_ = tmm(resample_all_timeframes(df)[tf_name], tf_name, now=t(2026, 9, 25, 18, 35))
    kontrol(f"{tf_name} günün son kapanan kovası (seans sonu kesmesi)",
            d_.index[-1].strftime('%H:%M') == beklenen, beklenen)
# Kısmi (devam eden) bar kapısı: :05 taraması 12:30 barını kapanmış SAYMAZ.
kontrol("13:05'te 12:30 barı henüz kapanmadı (kısmi bar sızmaz)",
        tmm(df, '1h', now=t(2026, 9, 25, 13, 5)).index[-1].strftime('%H:%M') == '11:30',
        "son kapanan 11:30")

print()
print("=== 6. FAZ 2: BIST TATİL TAKVİMİ / YARIM GÜN ===")
from config import BIST_TATILLER, BIST_YARIM_GUNLER
from data import bist_tatil_adi, seans_kapanis_saati, veri_yok_modu_acik_mi
kontrol("29 Ekim 2026 tatil (Cumhuriyet Bayramı)", bist_tatil_adi(t(2026, 10, 29)) == "Cumhuriyet Bayramı")
kontrol("1 Ocak 2026 tatil (Yılbaşı)", bist_tatil_adi(t(2026, 1, 1)) == "Yılbaşı")
kontrol("27 Mayıs 2026 tatil (Kurban Bayramı)", bist_tatil_adi(t(2026, 5, 27)) is not None)
kontrol("25 Eylül 2026 tatil DEĞİL", bist_tatil_adi(t(2026, 9, 25)) is None)
kontrol("tatil günü tarama penceresi kapalı", not data_mod.tarama_penceresi_acik_mi(t(2026, 10, 29, 12, 35)))
kontrol("tatil günü tarama anı da kapalı", not data_mod.tarama_animi_mi(t(2026, 10, 29, 12, 35)))
kontrol("normal gün penceresi açık", data_mod.tarama_penceresi_acik_mi(t(2026, 9, 25, 12, 35)))

# P0 DÜZELTMESİ: yarım günde günlük mum 18:30 yerine SEANS KAPANIŞINDA (13:00)
# tamamlanır. Eski davranışta o gün günlük formasyon/kırılım hiç bildirilmiyordu.
kontrol("yarım günde günlük mum 13:00'te tamamlanır (eski hata: 18:30)",
        data_mod.mum_kapanis_ani(t(2026, 3, 19), '1d').strftime('%H:%M') == '13:00')
kontrol("19 Mart 2026 yarım gün (kapanış 13:00)",
        seans_kapanis_saati(t(2026, 3, 19)) == dt_time(13, 0))
kontrol("yarım günde son mum 12:30 etiketli, kapanış 13:00",
        data_mod.son_kapanan_mum_ani(t(2026, 3, 19, 13, 5)).strftime('%H:%M') == '13:00')
kontrol("yarım gün 12:35'te son kapanan 12:30 (11:30 etiketli mum)",
        data_mod.son_kapanan_mum_ani(t(2026, 3, 19, 12, 35)).strftime('%H:%M') == '12:30')
kontrol("yarım gün 13:05'te tarama anı", data_mod.tarama_animi_mi(t(2026, 3, 19, 13, 5)))
kontrol("yarım gün 13:04'te henüz tarama yok", not data_mod.tarama_animi_mi(t(2026, 3, 19, 13, 4)))
kontrol("yarım gün 14:00'te pencere kapalı", not data_mod.tarama_penceresi_acik_mi(t(2026, 3, 19, 14, 0)))

kontrol("veri yok modu: eski veri + seans içi -> True",
        veri_yok_modu_acik_mi(t(2026, 9, 25, 12, 35), 26 * 60))
kontrol("veri yok modu: taze veri -> False", not veri_yok_modu_acik_mi(t(2026, 9, 25, 12, 35), 5))
kontrol("veri yok modu: tatil günü -> False (tatil zaten elci)",
        not veri_yok_modu_acik_mi(t(2026, 10, 29, 12, 35), 26 * 60))
kontrol("veri yok modu: pencere dışı -> False",
        not veri_yok_modu_acik_mi(t(2026, 9, 25, 20, 0), 26 * 60))

print()
print("=== 7. FAZ 2: SPLIT / VERİ SÜREKLİLİĞİ ===")
import copy
from data import sureklilik_sorunlari_bul, yuvarlak_orana_yakin_mi
temiz_mumlar = list(mgr.get_deque('THYAO'))
kontrol("temiz gerçek veride sorun yok", len(sureklilik_sorunlari_bul(temiz_mumlar)) == 0)

mumlar = copy.deepcopy(temiz_mumlar)
for c in mumlar[-5:]:
    for k in ('open', 'high', 'low', 'close'):
        c[k] = c[k] / 2
s_ = sureklilik_sorunlari_bul(mumlar)
kontrol("2:1 split yakalandı", any(x['tip'] == 'split' and x.get('oran') == 2.0 for x in s_))

mumlar = copy.deepcopy(temiz_mumlar)
for c in mumlar[-5:]:
    for k in ('open', 'high', 'low', 'close'):
        c[k] = c[k] / 3
s_ = sureklilik_sorunlari_bul(mumlar)
kontrol("3:1 split yakalandı", any(x['tip'] == 'split' and x.get('oran') == 3.0 for x in s_))

mumlar = copy.deepcopy(temiz_mumlar)
c_ = mumlar[len(mumlar) // 2]
for k in ('open', 'high', 'low', 'close'):
    c_[k] = c_[k] * 1.15
s_ = sureklilik_sorunlari_bul(mumlar)
kontrol("%15 haber şoku split DEĞİL olarak sınıflanır",
        any(x['tip'] == 'sok' for x in s_) and not any(x['tip'] == 'split' for x in s_))

mumlar = copy.deepcopy(temiz_mumlar)
son_gun = mumlar[-1]['timestamp'].date()
idx_ = [i for i, c in enumerate(mumlar) if c['timestamp'].date() == son_gun]
del mumlar[idx_[len(idx_) // 2]]
s_ = sureklilik_sorunlari_bul(mumlar)
kontrol("seans içi eksik mum 'bosluk' olarak sınıflanır",
        any(x['tip'] == 'bosluk' for x in s_))
kontrol("yuvarlak oran yardımcısı doğru (3:1 -> %66.67 düşüş)",
        yuvarlak_orana_yakin_mi(50.0) == 2.0 and yuvarlak_orana_yakin_mi(66.67) == 3.0
        and yuvarlak_orana_yakin_mi(15.0) is None and yuvarlak_orana_yakin_mi(80.0) == 5.0)

print()
print("=== 8. FAZ 2: TELEGRAM GLOBAL KAPANI ===")
from config import TELEGRAM_MAX_MESAJ_SAAT, TELEGRAM_MAX_MESAJ_GUN
from notifier import TelegramNotifier, KRITIK_STATELER
kontrol("limitler makul", 5 <= TELEGRAM_MAX_MESAJ_SAAT <= 100 and 50 <= TELEGRAM_MAX_MESAJ_GUN <= 1000)
kontrol("kritik state'ler tanımlı", 'KIRILIM_ADAYI' in KRITIK_STATELER
        and 'FORMASYON_TAMAMLANDI' in KRITIK_STATELER)

_nt_data = tempfile.mkdtemp(prefix='bot_kap_')
os.environ['DATA_DIR'] = _nt_data          # C4: repo dışı veri dizini
import config as config_mod
config_mod.DATA_DIR = _nt_data             # notifier/cooldown bu klasörü kullanır
import notifier as _notifier_mod
_notifier_mod.DATA_DIR = _nt_data          # C4: DATA_DIR modülde import anında bağlanıyor
nt_test = TelegramNotifier()
for _f in (os.path.join(_nt_data, 'telegram_kap.json'),):
    if os.path.exists(_f):
        os.remove(_f)
nt_test = TelegramNotifier()


def _mesaj(state, hisse):
    return {'stock_name': hisse, 'timeframe': '1h', 'pattern_name': 'Yükselen Üçgen',
            'state': state, 'confidence_score': 85, 'critical_price_level': 10.0,
            'upper_now': 10.0, 'lower_now': 9.0, 'contraction': 0.8,
            'timestamp': datetime.now(data_mod.ISTANBUL_TZ)}


gonderilen = sum(1 for i in range(TELEGRAM_MAX_MESAJ_SAAT + 10)
                 if nt_test.send(_mesaj('SIKISMA_GUCLENIYOR', f'IZ{i}')))
kontrol(f"izleme state'leri saatlik kapta kesilir ({TELEGRAM_MAX_MESAJ_SAAT})",
        gonderilen == TELEGRAM_MAX_MESAJ_SAAT, f"{gonderilen} gönderildi")

gonderilen2 = sum(1 for i in range(5)
                  if nt_test.send(_mesaj('KIRILIM_ADAYI', f'KR{i}')))
kontrol("kritik state'ler saatlik kaptan etkilenmez", gonderilen2 == 5, f"{gonderilen2} gönderildi")

nt_test._gunluk_sayac = TELEGRAM_MAX_MESAJ_GUN
kontrol("günlük kap aşıldığında kritik state bile gitmez",
        not nt_test.send(_mesaj('KIRILIM_ADAYI', 'SON')))
kontrol("kap durumu raporlanıyor",
        nt_test.kap_durumu()['gunluk_limit'] == TELEGRAM_MAX_MESAJ_GUN)
if os.path.exists('bot_data/telegram_kap.json'):
    os.remove('bot_data/telegram_kap.json')

print()
print("=== 9. FAZ 2: 1D DERİN VERİ (ayrı deque) ===")
from data import StockDequeManager
mgr_t = StockDequeManager(data_dir='/tmp/test_gunluk_dir')
kontrol("günlük deque boş -> eksik sayılır", mgr_t.gunluk_veri_eksik_mi('TEST'))
kontrol("günlük DataFrame boş", mgr_t.to_gunluk_dataframe('TEST') is None)
sentetik = pd.DataFrame(
    {'open': [10 + i * 0.1 for i in range(50)], 'high': [10.2 + i * 0.1 for i in range(50)],
     'low': [9.8 + i * 0.1 for i in range(50)], 'close': [10 + i * 0.1 for i in range(50)],
     'volume': [1000] * 50},
    index=pd.date_range('2026-08-01', periods=50, freq='B', tz=IST))
mgr_t.append_gunluk_dataframe('TEST', sentetik)
kontrol("günlük veri eklendi", len(mgr_t.to_gunluk_dataframe('TEST')) == 50)
kontrol("bugüne ait veri -> eksik değil",
        not mgr_t.gunluk_veri_eksik_mi('TEST', t(2026, 9, 25, 18, 35)))
mgr_t.save_gunluk_to_disk('TEST')
mgr_t2 = StockDequeManager(data_dir='/tmp/test_gunluk_dir')
kontrol("günlük veri diskten yüklenir", len(mgr_t2.to_gunluk_dataframe('TEST')) == 50)
kontrol("günlük deque ayrı dosyada", os.path.exists('/tmp/test_gunluk_dir/TEST_gunluk.json'))
import shutil
shutil.rmtree('/tmp/test_gunluk_dir', ignore_errors=True)

print()
print("=== 10. FAZ 2: TARAMA SÜRESİ ÖLÇÜMÜ ===")
kontrol("daily_stats tarama süresi alanı içeriyor", 'son_tarama_suresi_dk' in main_mod.daily_stats)
kontrol("heartbeat tarama süresi alanı içeriyor",
        'son_tarama_suresi_dk' in open('main.py', encoding='utf-8').read().split('payload = {')[1])
kontrol("telegram_kap heartbeat alanı içeriyor", 'telegram_kap' in open('main.py', encoding='utf-8').read())
kontrol("veri_sorunlari heartbeat alanı içeriyor", 'veri_sorunlari' in open('main.py', encoding='utf-8').read())


print()
print("=== 11. N+1: TATİL / YARIM GÜN UYKU DÖNGÜSÜ ===")
# Kök neden: is_bist_open tatili bilmiyordu -> kapalı dalda time_until_next_open 0
# dönüyordu -> ana döngü 0 sn uykuyla boş dönüyordu (ölçüm: ~21.500 log satırı/sn).
_acik_29 = t(2026, 10, 29, 12, 0)
_hedef_30 = t(2026, 10, 30, 9, 50)
kontrol("tatil günü bekleme > 0 (0 sn uyku fırtınası yok)",
        data_mod.time_until_next_open(_acik_29) > 0,
        f"{data_mod.time_until_next_open(_acik_29)/3600:.1f} sa")
kontrol("29 Eki tatil -> sonraki açılış 30 Eki 09:50",
        abs(data_mod.time_until_next_open(_acik_29)
            - (_hedef_30 - _acik_29).total_seconds()) < 1)
kontrol("29 Ekim (tatil) is_bist_open False (tatil artık takvimden biliniyor)",
        not data_mod.is_bist_open(_acik_29))
kontrol("30 Ekim 09:00 (tatil ertesi, seans öncesi) -> bugün 09:50",
        abs(data_mod.time_until_next_open(t(2026, 10, 30, 9, 0))
            - (t(2026, 10, 30, 9, 50) - t(2026, 10, 30, 9, 0)).total_seconds()) < 1)
# 28 Eki yarım gün (kapanış 13:00), 29 Eki tatil -> ikisi de atlanır.
kontrol("yarım gün 13:30 (arefe, seans kapandı) -> 30 Eki 09:50",
        abs(data_mod.time_until_next_open(t(2026, 10, 28, 13, 30))
            - (t(2026, 10, 30, 9, 50) - t(2026, 10, 28, 13, 30)).total_seconds()) < 1)
kontrol("cuma 20:00 -> pazartesi 09:50 (hafta sonu atlanır)",
        abs(data_mod.time_until_next_open(t(2026, 10, 2, 20, 0))
            - (t(2026, 10, 5, 9, 50) - t(2026, 10, 2, 20, 0)).total_seconds()) < 1)
kontrol("cumartesi 12:00 -> pazartesi 09:50",
        abs(data_mod.time_until_next_open(t(2026, 10, 3, 12, 0))
            - (t(2026, 10, 5, 9, 50) - t(2026, 10, 3, 12, 0)).total_seconds()) < 1)
kontrol("seans içinde (12:35) bekleme 0", data_mod.time_until_next_open(t(2026, 9, 30, 12, 35)) == 0)
# Sözleşme: pencere kapalıysa bekleme HER ZAMAN > 0.
_ornekler = [t(2026, 9, 30, 8, 0), t(2026, 9, 30, 20, 0), t(2026, 10, 29, 10, 0),
             t(2026, 10, 28, 13, 30), t(2026, 10, 3, 12, 0), t(2026, 9, 30, 12, 35),
             t(2026, 10, 30, 9, 50)]
kontrol("pencere kapalı <=> bekleme > 0 (tüm örnekler)",
        all((data_mod.tarama_penceresi_acik_mi(an)) == (data_mod.time_until_next_open(an) == 0)
            for an in _ornekler))
_main_kaynak = open('main.py', encoding='utf-8').read()
kontrol("ana döngüde taban uyku var (0 sn uyku imkânsız)", "sleep_time = max(sleep_time, 60.0)" in _main_kaynak)


print()
print("=" * 60)
if kalan:
    print(f"SONUÇ: {gecen} geçti, {len(kalan)} KALDI:")
    for k in kalan:
        print(f"   - {k}")
    sys.exit(1)
print(f"SONUÇ: TÜM KONTROLLER GEÇTİ ({gecen}/{gecen})")
