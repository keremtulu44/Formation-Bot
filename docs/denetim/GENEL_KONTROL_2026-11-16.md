# Genel kontrol — depo taraması ve son değişiklik denetimi (2026-11-16)

Durum: **Kayıt** (o günkü ölçüm). Tek commit'lik (`7cac9ce`) ağaç üzerinde
yapıldı; git geçmişi squash olduğu için "son değişiklik" *diff* ile değil,
son commit'in mesajındaki iddialar **kodda tek tek doğrulanarak** denetlendi.

## 1. Yöntem (yeniden üretilebilir)

```bash
bash scripts/install_deploy_dependencies.sh       # canlı pinler
python -m pip install -r requirements-dev.txt     # ruff==0.17.2
ruff check .                                      # statik kapı (CI adımı)
python -m pytest -q                               # 4.271 test
```

Yerel koşu Python 3.11.2 / pandas 2.2.2 / numpy 1.26.4 / matplotlib 3.11.2 /
pytest 9.2.0 ile yapıldı; Render ve CI Python 3.12 kullanır. Bu bir **yerel
doğrulamadır**, canlı Render/Telegram kanıtı değildir.

CI'daki diğer adımlar da yerelde aynı komutlarla koşuldu:

| CI adımı | Sonuç (düzeltmelerden sonra) |
|---|---|
| `ruff check .` | temiz |
| `python -m pytest -q` | **4.271 geçti, 0 başarısız**, 43 atlandı (710 sn) |
| `python test_tarama_zamani.py` | 102/102 geçti |
| `test_triangle` / `test_breakout` / `test_flag` / `test_pennant` | dördü de "TÜM KONTROLLER GEÇTİ" |
| Render duman testi (`BOT_HEALTH_SMOKE_ONLY=1 PORT=10000 python main.py`) | `/health` 200 + `commit: deadbee`; `/health?ka=1` 200; `/test` 404; `/ready` 503; smoke-mode guard logda |

## 2. Özet tablo

| Kontrol | Sonuç (düzeltme öncesi) | Durum |
|---|---|---|
| `ruff check .` (CI "Statik kapı") | **2 hata**: `S110` × `domain_engines/stabil/runtime.py:619`, `grafik/render.py:116` | Düzeltildi |
| `python -m pytest -q` | **4.270 geçti / 1 başarısız** / 43 atlandı (955 sn) | Düzeltildi |
| Başarısız test | `test_stabil_domain_and_integration.py::test_chart_stabil_chip_reclaim_triangle_step_colors_and_clean_footer` | Düzeltildi |
| Son commit iddiası: `h4_state` / `daily_raw_state` taşıma | Kodda mevcut, nedensel (bisect) ve replay tanımıyla aynı | Doğru |
| Son commit iddiası: `cok_guclu` / zayıf istisnası | `grafik/tarama.py` + `grafik/render.py` + testte birebir | Doğru |
| Bağlam zenginleştirme maliyeti | Sembol×TF başına **+2,7 sn** (toplam süreyi ~%90 artırıyordu) | Düzeltildi |
| Yeni denetim belgelerinin `docs/README.md` kaydı | 3 belge (2026-11-15) tabloda yoktu (YAPI.md §7.3 ihlali) | Düzeltildi |
| Sır sızıntısı taraması | Token/anahtar gömülü değil; `.env.example` şablon | Temiz |
| `main.py` giriş noktası, çift modül koruması | Geç bağlama alias'ı ve SIGTERM kaydı yerinde | Sağlam |

## 3. Son değişikliğin (7cac9ce) doğrulanması

Commit "Ok bağlamına ikinci kademe: çok güçlü (çift halka) + zayıf istisnası"
şunları iddia ediyordu; kod karşılıkları arandı:

| İddia | Kod kanıtı | Sonuç |
|---|---|---|
| `StabilBarBehavior`'a `h4_state`/`daily_raw_state` | `domain_engines/stabil/signals.py:180-181` (varsayılan `None` → eski kayıtlarla uyumlu) | ✅ |
| Runtime alanları nedensel doldurur | `domain_engines/stabil/runtime.py:586-620`, kapanmış barın `bar_close_time`'ında `bisect_right`; günlük/H4 zaman damgaları kapanış anıdır (`prepare_causal_ohlcv` → `mum_kapanis_anlari`) | ✅ lookahead yok |
| Hata durumunda kademe nötre düşer | `try/except` + alan `None`; `grafik/tarama.py` `cok_guclu` için `None`'ı "güçlü" sayar, zayıf istisnası yalnız `H4_RECOVERY_FAILED` görülürse uygulanır | ✅ fail-open |
| Çift halka | `grafik/render.py:1313-1323`, dış `s=300` + iç `s=170`, ayrı `gid`'ler ve `baglam_cok_guclu_isaret` sayacı | ✅ |
| Zayıf ok soluklaşır (silinmez) | `grafik/render.py:1332-1336`, zemin renkli `^` örtü, `alpha=0.55` | ✅ |
| Sinyal/alarm/kart değişmedi | Yeni alanlar yalnız `grafik/tarama.py` snapshot'ında okunuyor; `bot/*` bu alanları kullanmıyor | ✅ |

Ek doğrulama (bu kontrol sırasında koşuldu): 6 sembol × 2 TF × tüm barlar
(9.480 bar) için bağlam durumları, çizelgeler **yeniden hesaplanarak** üretilen
referansla karşılaştırıldı → **0 fark**, 9.048 bar dolu (kalan 432 bar warm-up,
`data_ready=False`).

## 4. Bulgular ve yapılan düzeltmeler

### 4.1 CI statik kapısı kırmızıydı (S110 ×2)

`ruff.toml` bilinçli olarak `try/except/pass` sessiz yutmayı (S110) hata sayar;
depo `# noqa: S110 - gerekçe` deseniyle kullanır. İki yerde gerekçe yoktu:

- `domain_engines/stabil/runtime.py:619` — **son commit ile geldi**
  (bağlam zenginleştirmesinin fail-open `except`'i).
- `grafik/render.py:116` — `# noqa: BLE001` yazılmış, `S110` eklenmemiş
  (zone künyesi tahmini).

Düzeltme: iki satıra gerekçeli `S110` noqa'sı eklendi. `ruff check .` → temiz.

### 4.2 Sağ şerit genişliği regresyonu → grafik testi kırmızıydı

`_sag_serit_px_hesapla` (2026-11-15 "dinamik sağ şerit") genişliği
**"36 px + 5,6 px × karakter"** ile tahmin ediyordu; şeridin kendi sığdırma
sınavı ise `_sigar_mi` (`_genislik_16 × metin_carpani`) modelini kullanıyor ve
bütçeyi `şerit - 25 px` alıyor. İki model uyuşmadığı için:

| Etiket | Karakter | Şerit (eski formül) | Bütçe | Ölçülen metin | Sonuç |
|---|---:|---:|---:|---:|---|
| `Destek 282,50` | 13 | 108,8 px | 83,8 px | 95,5 px | **iki satıra sarıyordu** |

Görsel sonucu: "Destek / 282,50" iki satırlık çip; test tarafında
`Sağ eksende Destek <fiyat> çipi görünmeli` iddiası düştü (tek başarısız test).
Düzeltme: genişlik artık **aynı ölçü modeliyle** hesaplanıyor —
`25 px çip payı + en uzun etiketin ölçüsü + 8 px nefes`, 84–195 px (mobil 230)
aralığında. Çip yeniden tek satır; `test_stabil_domain_and_integration.py` ve
grafik suite'i yeşil.

### 4.3 Bağlam zenginleştirmesi çizelgeleri ikinci kez hesaplıyordu (+%90 süre)

`trend_engine.analyze(...)` son anlık görüntüyü almak için günlük ve H4
zaman çizelgelerinin **tamamını** üretip atıyor (`_daily_snapshot`,
`_h4_snapshot` → `build_*_timeline(...)[-1]`). Son commit'in zenginleştirmesi
aynı çizelgeleri sembol×TF başına yeniden üretiyordu:

| Ölçüm (THYAO, arşiv verisi) | Önce | Sonra |
|---|---:|---:|
| `4h` tek koşu | 5.859 ms | 3.134 ms |
| `1d` tek koşu | 5.653 ms | 2.888 ms |

Düzeltme: `StabilTrendEngine` ürettiği çizelgeleri `StabilTrendTimelines`
olarak saklıyor (`analyze` içinde tek üretim, `timelines()` erişimi); runtime
zenginleştirmesi bunları okuyor. Matematik değişmedi — 9.480 bar üzerinde
**0 fark** (§3). Tarama turu bu sembol için ~2,7 sn × (sembol × TF) tasarruf eder.

### 4.4 Belge kaydı eksikti (YAPI.md §7.3)

`docs/denetim/` altındaki üç 2026-11-15 belgesi `docs/README.md` tablosunda
yoktu: `GRAFIK_ADIMLARI_VE_STABIL_OK_REPLAY_2026-11-15.md`,
`BILDIRIM_VE_GRAFIK_INCELEME_2026-11-15.md`,
`OK_BAGLAM_DOGRULAMA_VE_UYGULAMA_2026-11-15.md`. Üçü ve bu belge tabloya
eklendi.

## 5. Açık kalan riskler (bilinçli olarak DEĞİŞTİRİLMEDİ)

1. **`analyze` çizelgenin tamamını üretip yalnız `[-1]`'i kullanıyor**
   (~2,7 sn/sembol×TF). Artık iki kez değil, bir kez; ama tam çizelge
   üretimi kendi başına pahalı. Artımlı motor (`domain_engines/stabil/
   incremental.py`) ve `build_single_pass_history` bunun için var; canlı
   taramayı oraya taşımak ayrı bir iş ve ölçüm gerektirir.
2. **Bağlam kademesi görsel sınıftır, filtre değil.** Bootstrap güven
   aralıklarının alt sınırı sıfıra değiyor (`OK_BAGLAM...` §"Ek katman");
   sinyal/alarm/kart kararlarına bağlanmamalı.
3. **Direnç tarafı kademesiz** — kendi replay'i yok; bu bilinçli sınır.
4. **Canlı doğrulama yok.** Bu rapordaki her sayı yerel arşiv/yerel koşudur;
   Render ayarları, gerçek Telegram teslimi ve sağlayıcı verisi bu checkout'ta
   doğrulanmadı.

## 6. Değişen dosyalar

| Dosya | Değişiklik |
|---|---|
| `domain_engines/stabil/stabil_trend_engine.py` | `StabilTrendTimelines`; `analyze` çizelgeleri bir kez üretip saklar, `timelines()` erişimi; kullanımsız kalan `_daily_snapshot`/`_h4_snapshot` sarmalayıcıları kaldırıldı |
| `domain_engines/stabil/runtime.py` | Zenginleştirme çizelgeleri yeniden kullanır; S110 gerekçesi; indeks sınır kontrolü |
| `domain_engines/stabil/__init__.py` | `StabilTrendTimelines` dışa aktarımı |
| `grafik/render.py` | Sağ şerit genişliği ölçü modeliyle hizalı; S110 gerekçesi |
| `docs/README.md` | 2026-11-15 belgeleri + bu rapor tabloya eklendi |

## 7. Veri çekme hattı: "eksik çekilip geçilme" denetimi (2026-11-16, ikinci tur)

Kullanıcı sorusu: *"veri çekilme sürecinde eksik çekilip geçilme olayı gibi
sorunları tespit edip çözer misin"*. Aşağıdaki altı kusur kodda kanıtlandı,
beşi düzeltildi; biri **bilinçli olarak değiştirilmedi** (mevcut test
sözleşmesi, §7.7).

İnceleme yüzeyi: `data/fetch.py`, `data/seed_cache.py`, `data/backfill.py`,
`bot/scan.py` (fetch penceresi + 1H/1D append), `bot/app.py` (ilk yükleme),
`bot/summary.py` (gece yenilemesi) ve `canli_tarama.py`.

### 7.1 Sessiz satır eleme (sağlayıcı çıkışı)

`_saglayici_ohlcv_temizle` sağlayıcı yanıtından NaN/imkânsız OHLC/hayalet
tatil satırlarını ayıklıyor, **kaç satır attığını kimseye söylemiyordu**. 500
satırlık yanıtın 40'ı elense bile log tek satır "başarılı fetch" gösteriyordu;
kullanıcı eksik seriyi ancak grafikte fark ediyordu.

Düzeltme: fonksiyon `attrs` içinde `ham_satir` / `reddedilen_satir` /
`hayalet_satir` taşıyor; `_fetch_yfinance_adaylari` eleme olduğunda sembol,
sağlayıcı adı, dönem ve "kalan mum" ile **WARNING** yazıyor. Kısmi kabul
davranışı (bozuk satır yüzünden tüm geçmişi reddetmemek) aynen korundu.

### 7.2 Append reddi yutuluyordu (hem 1H hem 1D)

`StockDequeManager.append_dataframe` / `append_gunluk_dataframe` OHLCV
doğrulaması sınırıdır ve **bool** döner. Çağıranlar dönüşü yok sayıyordu:
reddedilen veri deque'e yazılmıyor ama üst katman "tazelendi" logluyor,
taze veri varmış gibi analize devam ediyordu (tam olarak "eksik çekilip
geçilme").

Düzeltilen çağrı yerleri:

| Yer | Önce | Sonra |
|---|---|---|
| `bot/scan.py` 1H turu | dönüş yok sayılıyordu | `False` ise `cache_reddi` sayacı + ERROR; `taze=None` yapılıp "taze veri yok" yoluna düşülür |
| `bot/scan.py` 1D turu | `False` olsa da "günlük veri tazelendi" | `True` ise loglanır; `False` ise ERROR + mevcut günlük cache korunur |
| `bot/app.py` ilk 1H | `False` olsa da "diske kaydedildi" | yalnız başarılı yazımda disk+log; aksi hâlde hata sözlüğüne yazılır, sonraki turda tekrar denenir |
| `bot/app.py` ilk 1D | dönüş yok sayılıyordu | aynı şekilde koşullu log + `cache_reddi` |
| `bot/summary.py` preload | dönüş yok sayılıyordu | reddedilirse WARNING |

### 7.3 Seans içi boşluk hiç onarılmıyordu

`select_yfinance_1h_period` pencereyi yalnız **son barın yaşına** göre seçiyor
(taze ise `5d`, değilse `60d`). Cache'te 3 gün önceki bir seansın içinde delik
varsa son bar taze olduğu için pencere `5d` kalıyor, delik **asla** kapanmıyor;
`bot/scan.py` de delikli seriyle analiz sürüyordu (yalnız `split` analizi
durduruyor).

Düzeltme:
* `data/fetch.py::seans_ici_bosluk_sayisi(cached)` — aynı takvim günü içindeki
  `BAR_BOSLUK_ESIK_SAAT` (1,5 saat) üstü aralıkları sayar; gece/hafta sonu
  aralıklarını saymaz.
* Tarama öncesi pencere seçiminde boşluk varsa **tam pencere (60d)** istenir.
  Sağlayıcıda kalıcı delik olan sembol için her turda 60d indirmemek üzere
  sembol başına `BOSLUK_TAMIR_TEKRAR_DK` (180 dk) soğuma uygulanır
  (`StockDequeManager.bosluk_tamir_uygun_mu` / `bosluk_tamir_kaydet`).
* Ayrıca `sureklilik_sorunlari` içindeki pencere içi (`FULL_1H_FETCH_WINDOW_DAYS`)
  boşluk kayıtları da tamir tetikleyicisidir; 60 günden eski delikler için
  boşuna indirme yapılmaz.

Onarım başarılıysa `sureklilik_sorunlari` temizlenir (mevcut `replace/append`
davranışı); başarısızsa §7.4'teki uyarı görünür.

### 7.4 Delik kapatılamazsa analiz sessizdi

`bot/scan.py` boşluk/şokta analize devam ediyor ve yalnız INFO yazıyordu.
Artık `bosluk` içeren sembol için **WARNING** ("analiz delikli seriyle sürüyor;
sinyal kalitesi etkilenebilir") + kaç boşluk olduğu ve `bosluklu_analiz`
sayacı yazılıyor. Karar değişmedi (fail-open korunuyor), yalnız görünürlük
arttı.

### 7.5 Başarısız 1D denemesi sembolü 6 saat kilitliyordu

`gunluk_fetch_denemesi_kaydet` fetch sonucundan **önce** çağrılıyordu; tek bir
geçici sağlayıcı hatası 6 saatlik cooldown yazıyor, sembol yarım gün günlük
veri olmadan resample ile idare ediyordu.

Düzeltme: `basarili=False` parametresi. Başarılı deneme eskisi gibi 6 saatlik
`_gunluk_fetch_attempts` cooldown'ı yazar; başarısız deneme yalnız bellekte
tutulan kısa soğumaya (`GUNLUK_FETCH_HATA_TEKRAR_DK` = 30 dk) yazılır, kalıcı
cooldown'a **dokunmaz**. Böylece sağlayıcı her turda dövülmez ama sembol de
yarım gün verisiz kalmaz. Çağrı yerleri: `bot/scan.py`, `bot/app.py`,
`canli_tarama.py`.

### 7.6 Bir seansın tamamı eksikse hiç görünmüyordu

`sureklilik_sorunlari_bul` boşluğu yalnız `ts.date() == onceki_gun` iken
arıyordu. Bir günün (veya birkaç günün) tüm barları eksikse iki bar arasındaki
aralık farklı güne düşüyor, ne uyarı ne denetim kaydı üretiliyordu.

Düzeltme: `_aradaki_islem_gunu_sayisi` (BIST takvimi: `islem_gunu_mu`) ile
farklı güne düşen aralıkta **atlanmış işlem günü** varsa `gun_boslugu` kaydı
üretilir. Yalnız seans içi (saatlik) seride çalışır — medyan bar aralığı > 12
saat olan günlük serilerde tatil boşlukları yanlış pozitif üretmesin. Normal
gece/hafta sonu aralıkları sayılmaz. `denetle_mum_butunlugu` artık
`gun_boslugu` kayıtlarını da `bosluklu_1h` olarak raporlar.

### 7.7 Bilinçli olarak DEĞİŞTİRİLMEYEN (test sözleşmesi)

* **Geçici sağlayıcı hatasında yedek seriye geçilmez.** `_fetch_yfinance_adaylari`
  retryable hatada `(None, True, ...)` döner; yedek aday denenmez. Bu,
  `test_grafik_veri_guvenilirligi.py::test_gecici_hatada_yedek_istegi_yok` ile
  açıkça sözleşmeye bağlanmış bir karar (spot ↔ vadeli seriyi ağ hatası
  anında sessizce değiştirmemek). Denendi, test kırmızıya döndü → geri
  alındı. "Eksik kalma" riski yeniden-deneme tarafında çözüldü (§7.5).

### 7.8 Yeni sayaçlar

`bot/statestore.py::daily_stats`: `cache_reddi`, `bosluk_tamir_fetch`,
`bosluklu_analiz`. Şema tanımı güncellendi; `reset_daily` listesi aynı
sözlükten türetildiği için ayrıca değişmedi.

### 7.9 Testler

Yeni dosya `test_veri_eksik_akis.py` (14 test) — **ağa çıkmaz**, gerçek
`StockDequeManager` + sahte fetch kullanır:

| Test | Neyi kilitler |
|---|---|
| `test_seans_ici_bosluk_temiz_seride_yok` / `..._eksik_mumda_sayilir` / `..._gece_ve_hafta_sonunu_saymaz` / `..._bos_ve_kisa_seride_sifir` | boşluk ölçütü |
| `test_bosluk_tamir_sogumasi` | 180 dk soğuma |
| `test_saglayici_temizleme_elenen_satirlari_bildirir` | `attrs` sayaçları |
| `test_cache_boslugu_tam_pencereyle_tamir_ister` | delik → 60d istenir, onarılır, sonra 5d'ye döner |
| `test_kalici_delikte_tamir_sogumaya_girer` | kalıcı delikte tekrar 60d indirilmez |
| `test_bosluklu_analiz_uyari_ve_sayac` | delikli analiz uyarısı + sayaç |
| `test_reddedilen_1h_append_taze_veri_sayilmaz` | reddedilen 1H append cache'e sızmaz, `cache_reddi` artar |
| `test_reddedilen_gunluk_append_tazelendi_logu_yazmaz` | sahte "tazelendi" logu yok |
| `test_eksik_seans_gun_boslugu_olarak_yakalanir` / `test_normal_gece_ve_hafta_sonu_gun_boslugu_uretmez` | `gun_boslugu` tespiti ve yanlış pozitif yokluğu |
| `test_gunluk_fetch_hatasi_alti_saat_kilitlemez` | hata → 30 dk, başarı → 6 saat |

Not (test yüzeyi kusuru, düzeltilmedi): `bot/scan.py` 1D fetch'i
`_pkg.fetch_yfinance_1d` üzerinden değil **kendi bağlı adıyla** çağırıyor;
`main` üzerinden yamalayan testler ağa çıkabilir. Bu turda testler iki yüzeyi
birlikte yamaladı. Ayrıca `scan_all_stocks`'un mevcut entegrasyon testleri
(`test_live_data_flow.py`, `test_bist_calendar_regressions.py` içindeki 13+8
test) hâlâ `skip` ve bir kısmı **artık var olmayan** parametreleri
(`require_current_session`, `_run_domain_engines_for_symbol`,
`_safe_completed_domain_frame`, `fetch_valid`) kullanıyor → tarama hattının
uçtan uca otomatik kapsaması yok. Bu turdaki entegrasyon testleri bu boşluğu
kısmen kapatır (gerçek `scan_all_stocks` + gerçek deque).

### 7.10 Doğrulama (bu tur)

| Kapı | Sonuç |
|---|---|
| `ruff check .` | Temiz (0 hata) |
| `python -m pytest -q` (tam süit) | **4304 geçti / 43 atlandı / 675,8 sn** |
| `test_grafik_veri_guvenilirligi.py` (sözleşme geri alımı sonrası) | 9/9 geçti |
| Hedefli veri hattı paketi (9 dosya) | 99 geçti / 35 atlandı |

(Atlanan 43 test, depoda önceden `skip` işaretli testlerdir; bu turda
eklenmedi.)

## 8. Genel kontrol — ikinci tur (2026-11-16, aynı gün)

Kullanıcı isteği: *"şimdi genel bir kontrol yap"*. Bu bölüm **CI'nın sekiz
kapısının tamamını yerelde yeniden üretir** ve GitHub Actions sonucunu kaydeder.
Önceki bölümler (7) veri hattı denetimiydi; bu bölüm depo geneli kontrol.

### 8.1 Kapı sonuçları

| Kapı (CI adı) | Bu turdaki sonuç |
|---|---|
| GitHub CI (`CI (Render parity)`, run `43894494101`) | **success**, 8 dk 58 sn, **12/12 adım yeşil**, Python **3.12** (repo `.python-version`) |
| `Statik kapı (ruff)` | **Temiz** — yerel (3.11.2) ve CI (3.12) aynı sonuç |
| `Unit testler (pytest)` | **4314 geçti / 43 atlandı / 694 sn**; 4357 toplandı (CI'da aynı adım yeşil) |
| `Kurulum doktoru ve grafik (çevrimdışı)` | **39 tamam / 7 uyarı / 0 hata**; `Kare üretildi: AKBNK 4h` (68 mum, 74,9 KB), `Stabil direnç bu karede çizildi`, `Fotoğraf gönderilmedi` — CI'nın üç `grep` beklentisi de karşılandı |
| `Zamanlama / ölü formasyon regresyonu` (`test_tarama_zamani.py`) | **102/102** |
| `Formasyon regresyon scriptleri` | `test_triangle` / `test_breakout` / `test_flag` / `test_pennant` → **dördü de "TÜM KONTROLLER GEÇTİ"** |
| `Render duman testi (/health)` | `/health` **200** `"status": "ok"`, `/health?ka=1` **200** + `"commit": "deadbee"`, `/ready` **503** (`startup_complete: false`), `/test` **404**, `POST /webhook/deneme` **404** |
| Duman testi koruma kontrolü | Log'da `Health smoke mode: provider and command loops disabled` **var**, `TARAMA BAŞLIYOR / Yahoo pacing / 1H fetch penceresi` izi **yok** |

7 uyarının hepsi ortam kaynaklı (Telegram/Supabase tanımsız, `--skip-network`,
eski `setuptools`); kod kaynaklı hata yok.

### 8.2 Bulgu: günlük sayaç şeması ile sıfırlama birbirinden kaymış

`daily_stats` iki yerde tanımlıdır: şema (`bot/statestore.py`) ve gün değişimi
sıfırlaması (`bot/counters.reset_daily_if_needed`, her anahtarı **tek tek**
sıfırlar). Mekanik tarama (kodda `daily_stats[...]` geçen anahtarlar ↔ şema ↔
sıfırlama listesi) iki yönlü kayma buldu:

| Sınıf | Sayaçlar | Sonuç |
|---|---|---|
| Şemada yok, kodda var | `grafik_kare`, `grafik_hata`, `alerts_makro_kapali` | İlk kullanımda sessizce oluşuyordu (gün başından itibaren tanımsız) |
| Şemada var, gün değişiminde sıfırlanmıyor | `cache_reddi`, `bosluk_tamir_fetch`, `bosluklu_analiz` (**§7'de eklendi**), `alerts_makro_kapali` | Dünün değeri bugünün özetine taşınıyordu |

Düzeltme: üç eksik şema anahtarı eklendi; dört eksik sıfırlama yazıldı. Aynı
sınıfın tekrarını önlemek için **sözleşme testi** eklendi
(`test_gunluk_sayac_semasi.py`, 2 test): (a) kodda artırılan her anahtar şemada
olmalı, (b) gün değişiminde her sayısal sayaç 0'a dönmeli.

### 8.3 Doğrulama: yeni `gun_boslugu` tespiti tatilde yanlış pozitif üretmiyor

§7.6'da eklenen eksik-seans tespiti BIST takvimine dayanır; bayram/hafta sonu
boşluklarının eksik veri sanılmaması kritik. Çalıştırılan senaryolar:

| Senaryo | Sonuç |
|---|---|
| 3 günlük resmî tatil (27-29 Mayıs 2026, Kurban Bayramı) atlanmış | **sorun yok** |
| Normal bir iş günü (Salı) tamamen eksik | `gun_boslugu` — "1 işlem günü hiç çekilmemiş" |
| Seans içi 3 saatlik delik | `bosluk` (mevcut davranış) |
| Temiz seri | sorun yok |
| `denetle_mum_butunlugu` çıktısı | `bosluklu_1h: ['DELIK', 'EKSIKGUN']` — yeni tip denetime girdi |

Bu senaryo kalıcı test olarak eklendi
(`test_resmi_tatil_gunleri_gun_boslugu_uretmez`).

### 8.4 Bilgi — aksiyon alınmayan gözlemler

1. **Ölü/tek-referanslı tanımlar:** 2703 fonksiyon tanımından 35'i depo içinde
   tek geçiyor (çoğu `research/` ve `domain_engines/` yardımcıları; bir kısmı
   `getattr` ile dinamik çağrılıyor olabilir). Bunlardan ikisi dikkat çekici:
   `bist_calendar.is_trading_day` ve `bist_calendar.seconds_until_next_bist_open`
   — `data/replay.islem_gunu_mu` / `time_until_next_open` ile **aynı işi yapan
   ikinci yüzey**; atlanan testlerin gerekçesinde geçen "takvimi tek kaynağa
   indirme" işiyle aynı başlık. Bu turda **dokunulmadı** (kapsam dışı refaktör).
2. **`docs/README.md` küratörlü indeks:** 172 belgeden 86'sı tabloda yok;
   `arastirma/` dışında kalan 30 belgenin 4'ü `denetim/` altında
   (`ALARM_DENETIMI_2026-10-22`, `DEPLOY_STABIL_KONTROLU_2026-11`,
   `GRAFIK_VERI_SUREKLILIGI_2026-11`, `P0_P1_P2_UYGULAMA_PLANI`). YAPI §7.3
   "her yeni belge için bir satır" der; bunlar geçmişten kalmış kayıtlar.
   Kayıt/durum bilgisi bilinmediği için **satır eklenmedi**; karar bekliyor.
   Bu raporun kendisi tabloda kayıtlı (satır güncellendi).
3. **Depo boyutu:** `.git` 132 MB; en büyük izlenen dosyalar
   `docs/arastirma/**/*.csv.gz` (19 MB, 18 MB). Bilinçli arşiv — Git LFS'e
   taşımak ayrı bir karar, dokunulmadı.
4. **Sır taraması:** izlenen dosyalarda gerçek anahtar yok; bulunan eşleşmeler
   test fixture'ları (`123456789:AA…`, `eyJhbGciOi…` sahte JWT). `.env`
   izlenmiyor, `.gitignore` kapsıyor. **Temiz.**
5. **TODO/FIXME:** 2 adet (`patterns/pole.py`, `patterns/pivots.py`), ikisi de
   önceden var olan notlar.
6. **Ortam farkı:** sandbox Python **3.11.2**, repo/CI/Render **3.12**. Bu
   turdaki sayılar 3.11'de alındı; **3.12 kanıtı GitHub Actions'tan** (yeşil).

### 8.5 Değişen dosyalar (bu tur)

| Dosya | Değişiklik |
|---|---|
| `bot/statestore.py` | Eksik şema anahtarları: `grafik_kare`, `grafik_hata`, `alerts_makro_kapali` |
| `bot/counters.py` | Gün değişiminde eksik sıfırlamalar: `cache_reddi`, `bosluk_tamir_fetch`, `bosluklu_analiz`, `alerts_makro_kapali` |
| `test_gunluk_sayac_semasi.py` | **Yeni** — şema↔sıfırlama sözleşmesi (2 test) |
| `test_veri_eksik_akis.py` | +1 test: resmî tatilde `gun_boslugu` yanlış pozitifi yok |
| `docs/README.md` | Bu raporun satırı §8'i kapsayacak şekilde güncellendi |

## 9. `/grafik` her zaman çalışsın: seans-farkında veri tazeliği (2026-11-16)

Kullanıcı isteği: *"veri çekme olayına bakar mısın, öyle bir ayarla ki /grafik
rahatlıkla çalışabilsin herhangi bir zamanda"*.

### 9.1 Kök neden: tazelik "yaş" ile ölçülüyordu, seans takvimi yok sayılıyordu

`bot/commands.py::_grafik_cache_tazelik_durumu` veriyi **son kapanmış mumun
yaşına** göre değerlendiriyordu (seans içi: 1H 120 dk, 2H 240, 4H 360, 1D 1560).
Bu ölçüt takvimi bilmediği için seansın doğal boşluklarını "bayat veri" sanıyor:

| Zaman | Son kapanmış mum | Yaş | Eski kapı |
|---|---|---|---|
| Pazartesi 10:05 | Cuma 18:00 | ~3 845 dk | **bayat** (1H/2H/4H/1D) |
| Pazartesi 12:00 | Cuma 18:00 (cache güncellenmemişse) | ~3 930 dk | **bayat** |
| Herhangi bir gün 12:00 (1G) | önceki seans 18:30 | ~2 700 dk | **bayat** (1D sınırı 1 560 dk) |

Sonuç: seansın ilk saatlerinde (ilk saatlik mum kapanmadan) ve **günlük grafikte
günün günlük mumu kapanana kadar (18:30) bütün gün** doğrulayıcı sağlayıcı
yanıtını reddediyor, `/grafik` "cache eski … veri yok" dönüyordu. Bot yeniden
başladığında (Render uyku/restart) cache dünkü hâliyle kaldığı için aynı duvar
her seferinde oluşuyordu.

### 9.2 Ölçüm (öncesi → sonrası)

Senaryo: cache son işlem gününün 18:00 kapanışıyla bitiyor; `seans_acik` gerçek
takvime göre.

| Zaman | Önce (1h / 2h / 4h / 1d) | Sonra |
|---|---|---|
| Pzt 09:55 (açılış) | bayat / bayat / bayat / bayat | **taze** ×4 |
| Pzt 10:05 | bayat / bayat / bayat / bayat | **taze** ×4 |
| Pzt 10:45 | bayat / bayat / bayat / bayat | bayat / **taze** / **taze** / **taze** |
| Pzt 12:00 | bayat / bayat / bayat / bayat | bayat / bayat / **taze** / **taze** |
| Pzt 17:00 | bayat / bayat / bayat / bayat | bayat / bayat / bayat / **taze** |
| Pzt 18:45 · 23:00 · Cmt · Paz | taze ×4 | taze ×4 (değişmedi) |

10:45'ten sonraki "bayat" sonuçlar **doğrudur**: o senaryoda cache gerçekten
Cuma'da kalmıştır. Normal işleyişte cache her tarama turunda (≈5 dk) yazıldığı
için gecikme ~0 olur:

| Gerçekçi senaryo (cache son kapanmış bara kadar güncel) | 1h | 2h | 4h |
|---|---|---|---|
| Pzt 09:58 (açılış + 8 dk) | taze (0 dk) | taze (0) | taze (0) |
| Pzt 10:40 (ilk saatlik mum kapandı) | taze (0) | taze (0) | taze (0) |
| Pzt 12:40 | taze (60) | taze (−60) | taze (0) |
| Pzt 17:55 | taze (0) | taze (0) | taze (0) |
| Salı 09:55 (yeni seans açılışı) | taze (0) | taze (0) | taze (0) |

### 9.3 Düzeltme

1. **`data/replay.py::beklenen_son_kapanis_ani(tf, now)`** — seans takvimine göre
   "şu an kapanmış olması gereken son mum"u üretir. Takvim kararı mevcut tek
   kaynaklardan gelir: `islem_gunu_mu` (hafta sonu/tatil) + `mum_kapanis_anlari`
   (seans sonu, yarım gün). Kova deseni (`09:30`, `11:30`, …) `resample_ohlcv`'ın
   09:30 çapasından türetilir; elle yazılmaz. Ölçüm: 0,6–3,0 ms/çağrı.
2. **`bot/commands.py::_grafik_cache_tazelik_durumu`** — seans açıkken ölçüt
   `gecikme = beklenen kapanış − son kapanış`. Eşikler aynı (1H 120 dk, 2H 240,
   4H 360, 1D 1560). Seans dışı ölçüt eskisi gibi yaş + 14 gün tavanı (davranış
   değişmedi). Sonuç sözlüğüne `gecikme_dk` ve `beklenen_kapanis` eklendi;
   kullanıcıya giden açıklama "seans takvimine göre N dk geride" diyor.
3. **Yarım gün koruması** — desen üretilirken seans sonundan sonra başlayan kova
   etiketleri atılır. Bu olmadan 2026-10-28 (29 Ekim arifesi, 13:00 kapanış)
   için "beklenen kapanış 18:30" gibi imkânsız bir değer çıkıyordu.
4. **pytz LMT hatası** — `datetime.combine(..., tzinfo=ISTANBUL_TZ)` pytz'de
   LMT (+1:56) kayması üretir; 17:30 etiketi 18:34'e kayıyordu. Yeni kodda ve
   §7.6'da eklenen `_aradaki_islem_gunu_sayisi` içinde `.localize()` kullanıldı.
5. **Sınırlı yeniden deneme** — sağlayıcı geçici hata dönerse (429/timeout/503)
   `/grafik` aynı sembol/pencere ile `_GRAFIK_HATA_DENEME` (2) kez, 2–4 sn
   bekleyerek yeniden dener. Yedek seriye (spot ↔ vadeli) geçiş **yok**; o karar
   `test_gecici_hatada_yedek_istegi_yok` sözleşmesiyle korunuyor.
6. **`docs/tasarim/GRAFIK_TASARIM.md`** — "Seans içi tazelik sınırı" bölümü
   gecikme modeline göre güncellendi (belge koda bağlı: YAPI §7.3/4. madde).

### 9.4 Testler

`test_grafik_her_zaman.py` (10 test, ağa çıkmaz):

| Test | Neyi kilitler |
|---|---|
| `test_seans_ilk_dakikalarinda_veri_bayat_sayilmaz[1h/2h/4h/1d]` | Seans açılışında dünün son mumu taze sayılır; `yas_dk` büyük kalırken `gecikme_dk` ~0 |
| `test_gercekten_geride_kalan_cache_hala_reddedilir` | Negatif kontrol: iki seans eksik cache bayat kalır |
| `test_beklenen_son_kapanis_takvimi_izler` | Cumartesi → Cuma 18:00; 29 Ekim tatili + arife yarım gün → 28 Ekim 13:00 |
| `test_seans_basinda_saglayici_kapaliyken_cache_ten_kare_uretilir` | 10:05'te sağlayıcı kapalı → PNG yine üretilir (`/grafik` uçtan uca) |
| `test_gunluk_grafik_gun_icinde_calisir` | 1G kare gün içinde üretilir |
| `test_gecici_saglayici_hatasi_yeniden_denenir` | 429 → ikinci denemede başarı, 2 çağrı |
| `test_kalici_hatada_yeniden_deneme_sinirlidir` | "delisted" gibi kalıcı hatada tek çağrı |

Mevcut grafik sözleşmeleri korunuyor: `test_grafik_istegi.py`, `test_grafik_veri_guvenilirligi.py`,
`test_grafik_album.py`, `test_grafik_grup.py`, `test_grafik_teslim.py` → **127/127 geçti**.

### 9.5 Açık kalan sınırlar (bilinçli)

1. Sağlayıcı tamamen kapalı **ve** cache hiç yok/14 günden eski → `/grafik` yine
   veri yok der; gösterecek güncel veri yoktur (uydurma kadraj çizilmez).
2. Seans **dışında** ölçüt hâlâ yaştır (14 gün tavanı): gece/hafta sonu
   davranışı değişmedi, regresyon riski alınmadı.
3. Tarama hattı (`_cache_verisi_kullanilabilir`) bu turda **değiştirilmedi**;
   gecikme modeli yalnız `/grafik` tazelik kapısında geçerli.

### 9.6 Doğrulama (bu tur)

| Kapı | Sonuç |
|---|---|
| `ruff check .` | Temiz |
| `python -m pytest -q` (tam süit) | **4338 geçti / 43 atlandı / 520,5 sn** (4381 toplandı) |
| Grafik sözleşme dosyaları (5 dosya) | **127/127 geçti** |
| `test_patch_yuzeyi.py` (yamalanan her hedef gerçek mi) | 1160 parametre geçti — yeni testteki tüm yamalar gerçek yüzeyler |
| `beklenen_son_kapanis_ani` maliyeti | 1H 3,0 ms · 2H 2,1 ms · 4H 1,4 ms · 1D 0,6 ms |
