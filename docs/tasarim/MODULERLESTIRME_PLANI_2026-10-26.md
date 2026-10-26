# Modülerleştirme planı — mega dosyaların bölünmesi (2026-10-26)

**Durum:** Yürürlükte (plan — uygulama bir sonraki turda, fazlar hâlinde) ·
**Kapsam:** `main.py` (5.097), `grafik.py` (5.044), `notifier.py` (3.938),
`data.py` (1.949) · **Girdi:** [denetim/KOD_DENETIMI_2026-10-26.md](../denetim/KOD_DENETIMI_2026-10-26.md) §4.5

Amaç dosya küçültmek **değil**, bakımı ölçülebilir birimlere bölmektir.
Kural: **refactoring = davranış aynı**. Her faz, tam test suite'i yeşilken
biter; davranış değişikliği isteyen iş bu planın dışındadır.

---

## 1. Değişmez sözleşmeler (taşınmazlar)

| Sözleşme | Neden | Sonuç |
|---|---|---|
| `python main.py` giriş | `render.yaml`, `ci.yml` (duman testi), `bist-bot.service`, README | Kök `main.py` kalır; ince başlatıcı olur |
| Testlerin monkeypatch yüzeyi | 579 `monkeypatch.setattr` çağrısının **298'i `main`'e** dokunuyor | §3 kuralı: çağrı yeri namespace'i + geç bağlama |
| `import main`'in testlerdeki adları | `main_mod._live_state`, `main_module.datetime`, `M._notifier_ref` … | Her fazda import satırları bilinçli güncellenir (§4) |
| `notifier`'ın dış API'si | `main`/`notifier`/testler `TelegramNotifier`, `devamlilik_puani` kullanır | `__init__` yeniden dışa aktarır |
| `grafik`'in dış API'si | `grafik_uret.py`, testler `ciz`, `kare_listesi`, `kareyi_yaz` çağırır | Aynı — paket facade'ı korur |
| `data`'nın dış API'si | `StockDequeManager`, `resample_ohlcv`, `tamamlanmis_mumlar`… | Aynı |
| AST koruma testleri | `test_tanimsiz_ad_korumasi.py` (F821 + kullan-önce-ata) | Bölme sonrası da koşulmalı — taşıma hatalarını yakalar |

## 2. Bilinçli olarak bu tur DIŞINDA kalanlar

`patterns/`, `state/`, `domain_engines/`, `analytics/`, `research/`,
`reporting/`, `transport/` paketleri ve tek amaçlı kök modüller
(`canli_tarama.py`, `health_server.py`, `deploy_check.py`, `telegram_*.py`,
`notification_*.py`, `live_state.py`, `karne.py`, `devamlilik.py`,
`zone_scoring.py`, `grafik_uret.py`, …) zaten makul birimler.
Büyüyenler için ileride: `deploy_check.py` (1.030 satır) ve
`notification_context.py` (1.278) aynı yöntemle bölünebilir.

## 3. Taşıma tekniği — geç bağlama kuralı (planın kalbi)

Testlerin çoğu, **çağıran modülün namespace'indeki** adları yamalar:

```python
monkeypatch.setattr(main_module, "write_heartbeat", sahte)   # main_loop bunu çağırmalı
monkeypatch.setattr(main_module, "datetime", sahte_tarih)    # fonksiyon datetime'ı kendi
                                                             # global'inden okumalı
```

Python'da fonksiyon içindeki `ad(...)` çağrısı **çağrı anında** o modülün
global namespace'inden okunur (geç bağlama). Dolayısıyla:

> **Bir `ad`'i `X.py`'den `Y.py`'ye taşımak, `X.py`'de `from Y import ad`
> satırı bırakmakla yetinir; `X.py` içindeki çağrılar ve testlerin
> `X_mod.ad` yamaları AYNEN çalışır.** Yalnız `X_mod`'u artık `Y`'den değil,
> `X`'ten import eden testlerde import hedefi güncellenir — ya da test,
> yamayı `Y_mod` üzerinden yapar (o zaman çağıran `X` DEĞİL, `Y` okumalıdır).

İki katı kural:

1. **Global durum (DATA_DIR, daily_stats, _live_state…) okunduğu modülde
   kalır ya da okuyanla birlikte taşınır.** `conftest.py`'nin
   `raising=False` yamaları hedef kaybolursa SESSİZCE işe yaramaz olur
   (testler gerçek dizine yazar) — bu yüzden §4'ün ilk işi
   `test_patch_yuzeyi.py` korumasıdır.
2. **`from X import *` YASAK.** Paket `__init__`'leri açık `__all__` listesiyle
   yalnız API'yı yeniden aktarır; mutable state proxy'lenmez.

## 4. Faz 0.5 — ilk iş: patch yüzeyi koruması (`test_patch_yuzeyi.py`)

Bölmeden ÖNCE yazılacak. Envanter komutu (kayıt yeniden üretilebilir):

```bash
python - <<'EOF'
import re, glob
for f in glob.glob('test_*.py') + ['conftest.py']:
    for m in re.finditer(r'monkeypatch\.setattr\(\s*([A-Za-z_][\w.]*)\s*,\s*["\'](\w+)["\']', open(f).read()):
        print(f"{m.group(1)}.{m.group(2)}  <- {f}")
EOF
```

Bu çıktı dondurulur: her `(modül, öznitelik)` çifti için
`hasattr(modül, öznitelik)` doğrulanır. Bir isim taşındığında test
**kırmızıya döner**; sessiz yanlış-patch riski kapanır. Her fazda tablo
güncellenir (taşınan hedefler yeni yerini alır).

Bugünkü envantetten seçmeler (213 farklı hedefin en yoğunları):

| Hedef | Adet | Sahibi bugün | Not |
|---|---|---|---|
| `main._live_state` | 48 | main | canlı durum — `bot.statestore` |
| `main.fetch_1h_stocks_paced` / `reset_daily_if_needed` / `write_heartbeat` / `create_yahoo_pacer` / `son_tarama_kaydet`… | ~40 | main | `main_loop`'un **çağrıları**; §3 gereği `bot.app` namespace'inde kalmalı ya da hedef oraya güncellenmeli |
| `main.ACTIVE_STOCKS` / `daily_stats` / `datetime` / `tarama_penceresi_acik_mi`… | ~60 | main | config okumaları + taklit saat |
| `main._supabase_store_ref` / `_deque_manager_ref` / `_notifier_ref` / `_telegram_*_ref` | ~35 | main | süreç ref'leri → `bot.statestore` |
| `grafik.kareyi_yaz` | 8 | grafik | → `grafik.frame` (çağıran orada) |
| `K.DATA_DIR` (karne) | 14 | karne | dokunulmaz |
| `config.DATA_DIR` | ~20 | config | dokunulmaz |
| `notifier.DEVLAMLILIK_AKTIF` | 4 | notifier | format koduyla birlikte taşınır |
| `tt.*` (telegram hata enjeksiyonu) | ~15 | telegram_* | dokunulmaz |

## 5. Hedef dosya yapısı

```
main.py                      # İNCE başlatıcı (~40 satır): setup_logging + bot.app.main()
                             # + __main__/health-smoke guard. Giriş sözleşmesi AYNI.

bot/                         # main.py'den
├── __init__.py              # yalnız açıklama + __all__ (state proxy'lenmez)
├── app.py                   # main(), main_loop(639), signal_handler, morning_preload,
│                            #   _bekle_veya_tarama, kapanış yolu
├── scan.py                  # scan_all_stocks(875) + tarama olay defteri:
│                            #   _note_* (3), _record_daily_lifecycle_events,
│                            #   _classified_lifecycle_events, _alert_break_level,
│                            #   _closed_formation_event_confirmed, _karne_* (7),
│                            #   _domain_results_for_notification, _completed_domain_frames,
│                            #   _endekse_gore_guc, _goreli_guc_satiri, _ms_hata_* (2),
│                            #   fetch_1h_stocks_paced, create_yahoo_pacer,
│                            #   _cache_verisi_kullanilabilir
├── lifecycle_events.py      # _invalidation_* (2), _capture_digest_lifecycle_baseline,
│                            #   _event_bar_number, _event_field, _event_local_time
├── counters.py              # reset_daily_if_needed, _gunluk_sayac_* (3), _ozet_isaret_* (2),
│                            #   _gun_sayacini_gonderimle_hizala, _successful_full_scan_today,
│                            #   _is_full_universe_scan, _istek_tam_evrende_tamamlandi
├── heartbeat.py             # write_heartbeat(100), _heartbeat_* (3), _saglik_ozeti,
│                            #   _tarama_saglik_kontrolu, son_tarama_kaydet/yukle
├── statestore.py            # süreç ref'leri: _live_state, _supabase_store_ref,
│                            #   _notifier_ref, _deque_manager_ref, _karne_defteri,
│                            #   _deferred_alert_buffer, _daily_lifecycle_event_keys,
│                            #   _telegram_update_processor_ref, _telegram_listener_ref,
│                            #   _shutdown_requested + digest_tamponu_* (2), _acil_kuyruk_* (2)
├── security.py              # _alarm_izni_var, _tekil_ornek_kontrolu, _analiz_hatasi_kaydi,
│                            #   _bos_analiz_mesaji, _evren_olcek_uyarisi,
│                            #   _formation_history_baslangic_kontrolu, _public_turu_kapat
├── commands/
│   ├── __init__.py          # _telegram_komut_katmanini_kur + yönlendirme tablosu
│   ├── durum.py             # _komut_durum(177), _komut_durumu, _panel_raporu
│   ├── formasyon.py         # _komut_formasyonlar(72), _komut_kirilim, _komut_retest,
│   │                        #   _komut_sikisanlar, _komut_tamamlanan, _komut_canli
│   ├── grafik_cmd.py        # _komut_grafik(81), _grafik_isi_yurut(128), _grafik_isi_calistir,
│   │                        #   _grafik_ozet_metni, _grafikleri_tur_sonunda, _kare_altyazisi,
│   │                        #   _calistir_istek_taramasi, _manuel_tarama_* (2)
│   ├── ozet.py              # _komut_ozet(60), _komut_karne, _komut_backtest, _komut_olcum,
│   │                        #   _komut_oneri_cevabi, _komut_evet/hayir, _komut_yardim,
│   │                        #   _onceki_sonuc_uyarisi, _sonuc_yok_mesaji
│   └── webhook.py           # _telegram_webhook_* (7), _render_test_sender
└── summary.py               # evening_maintenance(46), _daily_summary_payload,
                             #   _build_active_formations_for_summary, _kacirilan_digest_ozeti,
                             #   _format_post_close_diff_report, _gece_denetimi, _gece_onerisi_gonder,
                             #   _gece_raporu_yaz, _ileri_test_gece/kaydet, _haftalik_karne_* (2),
                             #   _parse_summary_hours + _parse_deferred_alert_digest_time +
                             #   _parse_post_close_analysis_time, _effective_summary_hours,
                             #   _ozet_slot_gonderilmeli, _kismi_kapsam_notu, _komut_ozet yard.

grafik/                      # grafik.py'den
├── __init__.py              # Dış API: ciz, anlik_goruntu, kare_listesi, kareyi_yaz,
│                            #   kare_yolu, bayat_kareleri_supur, grafik_aktif_mi,
│                            #   grafik_kare_adedi, kare_mum_tavani, sag_bosluk_mum,
│                            #   girdi_ozeti, alarm_turu_bul, formasyon_durum_etiketi
├── env_style.py             # _ModKapsami, _PaletSarmalayici, _SabitlerSarmalayici,
│                            #   _ortam_bayrak/_ortam_sayi, _pyplot_getir, _font_emoji_var,
│                            #   _metin_px, _olcu_px/_olcu_figir, _rozet_px, _butce_px
├── frame.py                 # _kare_ciz(367), _kare_ciz_modlu, _cerceve_ayristir, _kadrajla,
│                            #   _mum_cakisma_say, _mum_kutulari_px, _mumlar_ciz, _meta_kur,
│                            #   _atom_yaz, _kare_olcu, kareyi_yaz (çağrı yeri)
├── zones.py                 # _zone_havuzu(188), _zone_ciz(193), _zone_* (12), _ob_mitigated,
│                            #   _bolge, _kutu_yazisi_koy, _kutu_yazisi_sigar
├── events.py                # _olay_verisi(137), _olay_ciz(162), _olay_yazi_koy(97),
│                            #   _olay_meta, _isaret_listesi, _grafik_dis_yapi, _grafik_yapi_metni
├── layers.py                # _formasyon_ciz, _formasyon_araligi, _formasyon_serileri,
│                            #   _formasyon_kopyala, _direk_ciz, _alarm_ciz, _alarm_kopyala,
│                            #   _projeksiyon_ciz, _gecersiz_katmani, _guven_ciz/_guven_satirlari
├── layout.py                # _sag_ciz(204), _sag_ele/_sag_panel/_sag_sirali_yerlesim,
│                            #   _lejant, _lejant_satirlar, _tik_etiketleri, _alt_yerlesim,
│                            #   _gorunur_parcalar
├── series_badges.py         # _rvol_rozetleri(215), _rozet_ciz, _serit_ciz, _serit_verisi,
│                            #   _serit_meta, _rvol_katı, _swing_ofseti
└── text.py                  # _metinler(152), _metin_ciz, _tarih/_tarih_metni, _ikon,
                             #   _ad/_alan/_alan_var/_kirp/_tam/_yon/_gercek, _yapı_satırı,
                             #   _durum_adi, _zaman_bul, _kayit_listesi, _sonuc_sec,
                             #   _wilder_atr, _grafik_yapi_metni yardımcıları

notifier/                    # notifier.py'den
├── __init__.py              # TelegramNotifier + DİŞ API (devamlilik_puani, quality_*,
│                            #   token_bicimi_uygun_mu, telegram_hata_ipucu) yeniden aktarır
├── api.py                   # TelegramNotifier sınıfı (2.604) — bu fazda BÜTÜN taşınır;
│                            #   iç ayrıştırma (send/queue/gates) opsiyonel son faz
├── format_kart.py           # _format_lifecycle_alert_kart_sade(279), _kart(162),
│                            #   _klasik(84), _format_lifecycle_alert(6), _kart_* (11),
│                            #   _quality_grade, quality_comment/emoji, devamlilik_puani,
│                            #   DEVLAMLILIK_AKTIF okuyanlar
├── format_summary.py        # _summary_lifecycle_counts, _summary_last_full_scan,
│                            #   _public_izleme_adaylari, _evren_ozeti, _summary_int
└── util.py                  # _format_price(_tl), _kirp, _satir, _sayı, _tr_tarih, _istanbul,
                             #   _yon_kisa/_yon_metni, _yuzde, _dm_*, _muhur_ttl_saat,
                             #   _kuyruk_verisi, _px_butce, _env_temizle, _grafik_basligi,
                             #   _grafik_dipnotu, _grafik_salteri_acik

data/                        # data.py'den (EN SON, opsiyonel — şimdilik tek dosya da olabilir)
├── __init__.py              # StockDequeManager + DATA_DIR/SEED_DATA_DIR burada kalır
├── session.py               # is_bist_open, islem_gunu_mu, tarama_penceresi_acik_mi,
│                            #   tarama_animi_mi, mum_kapanis_ani/anlari, bar_kapandi_mi,
│                            #   time_until_*, son_kapanan_mum_ani, seans_* (3), bist_tatil_adi,
│                            #   yarim_gun_kapanisi, sonraki_islem_gunu, veri_yok_modu_acik_mi
├── fetch.py                 # fetch_yfinance_1h/1d, select_yfinance_1h_period,
│                            #   yfinance_error_is_retryable, mock_fetch_60d_1h,
│                            #   saglayici_adaylari, fetch_last_bar
├── quality.py               # ohlcv_girdi_sorunlari, sureklilik_sorunlari_bul,
│                            #   _ohlcv_kayit_sorunlari
└── resample.py              # resample_ohlcv, resample_all_timeframes, _resample_sabit_capali,
                             #   _istanbul_dizin, _gun_kapanis_damgalari, tamamlanmis_mumlar,
                             #   _bist_seans_serisi
```

**Bağımlılık yönü (döngü yasak):**

```
main.py → bot.app
bot.*   → notifier.* · grafik.* · data.* · patterns.* · state.* · config
notifier.* → (yalnız notifier içi + config; grafik'e lazy/çevresel bağı korunur:
              grafik.py `_tarih_tr`'i notifier'dan lazy alır — taşınırken
              notifier.util'den okunacak şekilde düzeltilir)
grafik.* → data.* · config · patterns (indicators)
data.*   → config · (yfinance/pandas)
```

Ortak süreç durumu yalnız `bot.statestore`'da; `bot/*` birbirini oradan okur.

## 6. Faz sırası (her faz tek PR/commit, tam suite yeşil)

| Faz | İçerik | Dokunan testler (envanterden) | Risk |
|---|---|---|---|
| **0.5** | `test_patch_yuzeyi.py` + envanter dondurma | — (yeni) | yok |
| **1** | `notifier/` (önce saf fonksiyonlar → sınıf BÜTÜN) | `test_devamlilik` (DEVLAMLILIK_AKTIF), `test_kart_metin`, `test_notifier_*`, `test_telegram_*` (format çağrıları) | düşük |
| **2** | `grafik/`: env_style+text → series_badges → zones → events → layers → layout → frame (sıra önemli: yapraklar önce) | `test_grafik_*` (~15 dosya), `test_chart_experience` (`grafik.kareyi_yaz`) | orta |
| **3** | `bot/statestore`, `bot/counters`, `bot/heartbeat` | `test_gorunurluk_ve_digest`, `test_kaynak_ve_guvenlik`, `test_gonderim_sagligi`, `test_restart_surekliligi`, `test_son_tarama_kaliciligi` | orta |
| **4** | `bot/commands/*` | `test_telegram_commands`, `test_telegram_webhook`, `test_telegram_alert_flow`, `test_gece_denetimi` | orta |
| **5** | `bot/scan` + `lifecycle_events` + `security` (ejderha: `scan_all_stocks` 875) | `test_live_data_flow`, `test_mum_kapanis_penceresi`, `test_domain_*`, `test_karne`, `test_takvim_politikasi` | **yüksek** |
| **6** | `bot/app` (`main_loop` 639) + `main.py` incelmesi + `bot/summary` | `test_bist_calendar_regressions` (60 yama), `test_health_server`, `test_deploy_check`, `test_gece_*` | **yüksek** |
| **7** (ops.) | `TelegramNotifier` iç ayrıştırma: `api.send` / `api.queue` / `api.gates` | `test_notification_delivery`, `test_public_grup` | çok yüksek — yalnız gerekirse |
| **8** (ops.) | `data/` | `test_ohlcv_guvenligi`, `test_yahoo_backfill`, `test_live_data_flow` | orta |

Her fazın iç adımları (sistematik):

1. Hedef modül(ler)i oluştur; fonksiyonları **değiştirmeden** taşı.
2. Eski modülde `from bot.x import ad` ile yeniden bağla (§3).
3. `grep -rn "monkeypatch.setattr(.*\b<ad>\b" test_*.py conftest.py` →
   hedefi çağıran modüle göre güncelle; `test_patch_yuzeyi.py` tablosunu tazele.
4. `ruff check .` → temiz.
5. `pytest -q` **tamamı** → yeşil (43 skip kabul; yeni fail YOK).
6. `test_tarama_zamani.py` + 4 bağımsız script → yeşil.
7. Satır bütçesi raporu: hiçbir modül > ~1.200 satır; hedef ~800.

## 7. Riskler

| Risk | Önlem |
|---|---|
| `raising=False` yamalar hedefi kaybedince sessizce işe yaramaz | Faz 0.5 koruması; ayrıca faz sonlarında `grep "raising=False"` ile kalanlar tek tek doğrulanır |
| Döngüsel import (`bot.scan` ↔ `bot.app`) | Ortak durum `bot.statestore`'da; `bot/*` birbirini yalnız ihtiyaça göre import eder, `__init__` ağırlık yapmaz |
| `scan_all_stocks`'un `continue`/`global` kırılganlığı | Taşıma ÖNCESİ davranışı sabitleyen test zaten var (kullan-önce-ata AST + `test_dm_gecersizlesme_kapisi_publici_durdurmaz` yapısal sözleşme) — taşımada yeniden koş |
| İnsan gözünden kaçan davranış kayması | Fazlar küçük; `git diff` yalnız taşıma + import satırı içermeli (yorum/değişiklik sızarsa review) |
| CI mavi, lokal kırmızı (ya da tersi) | Aynı kapılar: ruff.toml + pytest + 4 script; `.python-version` 3.12 |

## 8. Bitiş kriterleri

- `main.py` ≤ 60 satır (başlatıcı); `python main.py`, CI duman testi, systemd aynı.
- Kök mega dosya kalmamış: `grafik.py`, `notifier.py`, `data.py` paket.
- `test_patch_yuzeyi.py` güncel envanterle yeşil; 579 yama geçerli.
- Tam suite + ruff + bağımsız scriptler yeşil; davranış farkı SIFIR
  (yalnız yapı).
- README `Hızlı başlangıç` komutları değişmez; docs/YAPI.md'ye yeni paket
  satırları eklenir.
