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
