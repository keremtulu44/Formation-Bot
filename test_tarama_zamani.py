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
import sys
from datetime import datetime, time as dt_time

import pandas as pd

from config import (BIST_OPEN, BIST_CLOSE, CANDLE_CLOSE_MINUTE, SCAN_DELAY_AFTER_CLOSE_MIN,
                    STALE_BAR_UYARI_DK, TARAMA_PENCERE_SONU, TERMINAL_TAZE_BAR)
import data as data_mod
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


def t(yil, ay, gun, saat, dakika=0):
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
    kontrol("18:20'de son mum henüz 16:30 (17:30'u henüz analiz etmiyoruz)",
            data_mod.tamamlanmis_mumlar(df, "1h", now=t(2026, 9, 25, 18, 20)).index[-1].strftime("%H:%M") == "16:30")
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
print("=" * 60)
if kalan:
    print(f"SONUÇ: {gecen} geçti, {len(kalan)} KALDI:")
    for k in kalan:
        print(f"   - {k}")
    sys.exit(1)
print(f"SONUÇ: TÜM KONTROLLER GEÇTİ ({gecen}/{gecen})")
