# Genel kontrol ve Stabil güçlü yukarı mum oku düzeltmesi

**Tarih:** 2026-11-03  
**Dal:** `arena/022e2bca-formation-bot`  
**Kapsam:** `Projeyi incele, sorunları tespit et ve düzelt` + `Stabil grafikte yukarı yön güçlü mumlarda oklar çıkmıyor` + `genel kontrol` + `API eklenirse neler yapılabileceği` değerlendirmesi.

> **Ekler değiştirilmedi.** `docs/arastirma/`, `docs/gorseller/stabil/`, `ornek_gorseller/`, `backfill_data/`, `bot_data/`, `capraz_piyasa_data/`, `state/` ve mevcut JSON/CSV/PNG sonuç dosyalarının hiçbiri düzenlenmedi. Yalnızca kaynak/test dosyaları ve `docs/tasarim/` altında iki yeni değerlendirme notu eklendi.

---

## 1. Kullanıcı bildirimi ve çalışma yorumu

Kullanıcı: yatay destekte ve replay sonuçlarında okların çıktığını, desteğin güzel göründüğünü; ancak **yukarı yön güçlü mumlarda** okların çıkmadığını belirtti. Bu, mevcut destek çizgisini/stepline'ı yeniden tasarlamak olarak değil, **geri alım dışında kalan güçlü boğa mumlarının ayrı bir işaretle görünmesi** olarak ele alındı.

Korunan davranışlar:

- Basamaklı `Destek` çizgisi, renk rolleri, sağ `Destek <fiyat>` çipi.
- Mevcut dolu yeşil `▲` güçlü geri alım işareti.
- `/stabil` kart metni, 4S geri alım alarmı ve native `05_stabil.txt` pivot/destek matematiği.
- Replay ile normal grafik görünümünün birebir eşleşmesi.

---

## 2. Ana sorunun kök nedeni

| Katman | Eski durum | Sonuç |
|---|---|---|
| `domain_engines/stabil/signals.py` | Yalnızca `close_reclaim` / `intrabar_sweep_reclaim` sınıflandırması vardı; `/stabil` içindeki `guclu_cikis` ayrı bir özetti ve `reclaim_kind=None` taşıyordu. | Güçlü boğa mumu grafik katmanına hiç ulaşmıyordu. |
| `grafik/tarama.py::_stabil_verisi` | Yalnızca `reclaim_barlar` üretiyordu. | Güçlü yukarı mum için işaret listesi yoktu. |
| `grafik/render.py::_stabil_ciz` | Tek `marker="^"` / `gid="grafik-stabil-reclaim"` çiziyordu. | Yatay destek/geri alım dışında ok üretilemiyordu. |
| `grafik_uret.py` | Normal `/grafik` canlı `StockDequeManager`, replay arşiv `frames` kullanıyordu. | Aynı sembol/TF/kesim için Stabil bağlamı farklılaşabiliyordu. |

Ek olarak iki hizlama/kesim hatası bulundu:

1. `prepare_causal_ohlcv` içinde `dropna` sonrası `is_closed` / `is_complete` maskeleri `closed_mask[:len(out)]` ile **pozisyonel** uygulanıyordu; NaN satır atlandığında maskeler kayıyordu.
2. Domain projeksiyonu grafik çerçevesinden kısa olduğunda `projeksiyon[sol:sag]` / son `N` dilimleme, okları yanlış barlara taşıyabiliyor veya tamamen düşürebiliyordu.

---

## 3. Yapılan düzeltmeler

### 3.1 Güçlü yukarı momentum ayrı bir olay olarak eklendi

`domain_engines/stabil/signals.py`:

- `STABIL_GUCLU_YUKARI_MOMENTUM_TURLERI = {"long_base_breakout", "upward_rebase_momentum"}`.
- `StabilBarBehavior.momentum_kind` alanı eklendi; varsayılan `None` olduğu için eski kayıtlar/sentetik kartlar bozulmadı.
- Sınıflandırma **geri alımdan bağımsız**: `reclaim_kind is None`, zayıf geri alım yok, pozitif `pct_vs`, gövde ≥ `0.35 ATR`, kapanış pozisyonu ≥ `0.65`, temas < 3, hacim ≥ `1.10×` veya gövde ≥ `0.50 ATR`, `ACTIVE` destek ve 3 bar cooldown.
- `long_base_breakout`: ≥ 20 bar değişmeyen yatay zemin + `0.15–1.80 ATR` uzaklık.
- `upward_rebase_momentum`: `STEPPING_UP` / `REBASED_HIGHER` + `0.10–1.60 ATR` uzaklık. **Destek yukarı basamak yaptığı barda `fixed_support=False` olsa da ok kaybolmuyor.**
- Eşikler `/stabil` komutundaki replay-grounded "güçlü çıkış" kuralıyla aynı; 7 sembolde yapılan sıkı/gevşek karşılaştırmada gevşek filtreler 14–80 aday ürettiği için sıkı ATR sınırları korundu.

### 3.2 Grafikte iki ayrı `▲`

`grafik/core.py`, `grafik/render.py`:

- Dolu yeşil `▲` = güçlü geri alım (`grafik-stabil-reclaim`) **korundu**.
- İçi boş `▲` = güçlü yukarı momentum (`grafik-stabil-momentum`, `momentum_isaret` meta alanı).
- Varsayılan palet `#f2c94c` altın, renk-körü palet `#4da3ff` mavi; **renk + içi boş şekil** çift ayrım taşıyor.
- Aynı bar hem geri alım hem momentum olamaz; momentum listesi reclaim indekslerini dışlar.
- `▲` koordinatları tek `_ok_koordinatlari` yardımcısında toplandı; kadraj dışına taşma/çizgi altına yerleşim korundu.

### 3.3 Zaman ve nedensellik hizalaması

`grafik/tarama.py`:

- `anlik_goruntu` artık görünür `zamanlar[sol:sag]` dizisini `_stabil_verisi`'ne veriyor.
- `mum_kapanis_anlari(..., tf)` ile İstanbul kapanış zamanları üretiliyor; her görünür mum, projeksiyonda `bar_close_time <= close_time` olan **en geç** kayda eşleşiyor.
- Davranışlar `bar_index` üzerinden bağlanıyor; kesim sonrası görünür mumlar için destek `None` bırakılıyor, uydurulmuyor.
- Zaman damgası yoksa/okunamazsa eski indeks tabanlı `_stabil_klasik_dilim` geri uyumlu yol olarak kalıyor.
- `momentum_barlar` ayrı alan olarak snapshot'a ve render meta'sına taşınıyor.

`domain_engines/stabil/runtime.py`:

- `prepare_causal_ohlcv` ham satır sırasını `_source_row` ile taşıyor; `is_closed` / `is_complete` maskeleri artık orijinal satırlara indeksleniyor; yardımcı kolon çıktıdan siliniyor.

### 3.4 Normal / replay Stabil bağlamı tek kaynağa bağlandı

`grafik_uret.py`, `research/replay_egitim.py`, `test_replay_rendering.py`:

- Yeni `stabil_baglami_arsivden(frames, cutoff)`: `1d`/`4h` arşiv çerçevelerini UTC kapanış zamanına göre nedensel keser; canlı state'e yazmaz.
- `kare_uret(..., stabil_frames=None)` **opsiyonel** parametresi eklendi. Varsayılan canlı `/grafik` yolu değişmedi; yalnızca arşiv/replay ile birebir karşılaştırma gerektiğinde aynı kesim kullanılıyor.
- `research/replay_egitim._soru_goruntusu` elle yaptığı `searchsorted` dilimlemeyi bu ortak yardımcıya devretti.
- `test_replay_rendering.py` artık `stabil` alanını da normal/replay eşitliğine dahil ediyor; **yeni assertion kaldırılmadı**, altyapı eşitlendi.
- Replay içindeki Stabil istisnası hâlâ eğitim karesini düşürmüyor, ancak artık `exc_info=True` ile traceback loglanıyor; sessiz yutma gözlemlenebilir hale geldi.

### 3.5 Regresyon testleri

Yeni `test_stabil_momentum_arrow.py` 6 test:

1. Uzun yatay zeminden kopuşta `long_base_breakout` ve geri alım olmaması.
2. Destek yukarı basamak yaparken `upward_rebase_momentum` okunun kaybolmaması.
3. Gelecek mum eklenince geçmiş sınıflandırmanın değişmemesi.
4. `grafik-stabil-momentum` koleksiyonu ve `momentum_isaret` meta alanı.
5. Kısa domain projeksiyonunun kapanış zamanıyla hizalanması + kesim sonrası `None`.
6. NaN satırdan sonra `is_closed` / `is_complete` maskelerinin kaymaması.

---

## 4. Genel kontrol bulguları

### 4.1 Kod, test ve dağıtım doğrulaması

| Kontrol | Sonuç |
|---|---|
| `ruff check .` | ✅ All checks passed |
| `pytest -q` tam suite | ✅ **3299 passed, 43 skipped** — log iyileştirmesinden sonra ikinci tam koşu da aynı sonuçla geçti |
| `pytest -q test_replay_rendering.py test_stabil_momentum_arrow.py` | ✅ **23 passed** |
| Bağımsız scriptler (`pytest.ini` tarafından bilinçle hariç tutulan 5 dosya) | ✅ `test_tarama_zamani.py` 102/102; `test_triangle.py`, `test_breakout.py`, `test_flag.py`, `test_pennant.py` geçti |
| `deploy_check.py --skip-network` | ✅ **28 OK · 6 uyarı · 0 hata** |
| `compileall` | ✅ Sözdizimi/import derlemesi temiz |
| `git diff --check` | ✅ Boşluk/whitespace hatası yok |

`deploy_check` uyarıları kod hatası değil; bu çalıştırmada sırlar bilinçli boş bırakıldı ve ağ kontrolleri atlandı:

1. `TELEGRAM_BOT_TOKEN` yok.
2. `TELEGRAM_CHAT_ID` yok.
3. Telegram kapalı olacak.
4. Supabase kapalı olacak.
5. Yeni durum Supabase'e yedeklenmeyecek.
6. `--skip-network` verildi.

### 4.2 HTTP / API yüzeyi taraması

- `health_server.py`: `GET /health` (liveness, her zaman 200; `?strict=1` bayat heartbeat'te 503), `GET /ready` (yalnız başlangıç/kapanış durumu), `GET /test` (`TELEGRAM_TEST_KEY` olmadan 404), `POST /webhook` (`X-Telegram-Bot-Api-Secret-Token`), eski `/webhook/<secret>` yolu, IP başına 60/dk limit ve 1.000.000 byte gövde sınırı.
- `notifier/api.py`: adına rağmen **HTTP API değil**; 2845 satırlık `TelegramNotifier` sınıfı. Bu turda incelendi.
- `telegram_commands.py`, `bot/commands.py`, `bot/stabil_service.py`: Telegram komut katmanı; HTTP sözleşmesi yok.
- `supabase_store.py`: opsiyonel ve büyük ölçüde salt-okunur uzak state; yeni state yazımı garanti edilmiyor.
- `requirements.txt`: FastAPI/Flask yok; mevcut HTTP katmanı standart `http.server`.

**Sonuç:** Bugün dışarıya açılmış bir analiz API'si yok. API önerisi mevcut bir yüzeyin genişletilmesi değil, yeni bir katman olarak değerlendirilmelidir. Ayrıntılı ürün/use-case teklifi: `docs/tasarim/API_SENARYOLARI_VE_URUN_FIKIRLERI_2026-11-03.md`.

### 4.3 Bilinçli olarak değiştirilmeyen, takip gerektiren noktalar

Bunlar ana görsel hatanın kapsamı dışında kaldı; var olan davranışı bozmamak için bu turda dokunulmadı:

- **Render disk / state kalıcılığı:** `DATA_DIR` Render'da geçici `/tmp` olabilir; Supabase salt-okunur ise restart'ta önbellek/karne/bildirim durumu kaybolabilir. API veya çoklu örnek öncesi kalıcı depolama + tek yazan örnek kilidi gerekir.
- **`/health` semantiği:** 200 yanıtı veri tazeliğini, Telegram teslimini veya domain motorlarının sağlığını kanıtlamaz. Ayrı `data_freshness` / `last_scan` / `domain_errors` alanları önerilir.
- **Çift örnek riski:** Aynı token/Supabase ile iki bot örneği çift bildirim ve state yarışı üretebilir.
- **Makro sembol kapanış zamanı:** Sertifikalı kapanış olmadan Stabil/API sonucu `DATA_ERROR` / `UNAVAILABLE` dönmeli; BIST takvimi varsayılmamalı.
- **Replay yorumu:** `docs/arastirma/` sonuçları betimsel araştırmadır; canlı getiri veya yatırım tavsiyesi değildir. `research/replay_egitim.py` istisnayı artık traceback ile logluyor, fakat yine de kareyi düşürmüyor.
- **Python sürümü:** Yerel doğrulama Python 3.11.2 ile yapıldı; CI/Render `.python-version` 3.12. CI aynı testleri 3.12 üzerinde koşuyor.
- **`pytest.ini`:** 7 `test_*.py` dosyası modül-seviyesi `sys.exit` içerdiği için pytest toplamasından hariç; CI bunları ayrı script olarak çalıştırıyor. Bu turda ayrıca çalıştırıldı.
- **`TELEGRAM_GRAFIK` varsayılanı `yok`:** Alarm grafiği varsayılan kapalı; deploy/config meselesidir, kod hatası değildir.

---

## 5. Değiştirilen / eklenen dosyalar

**Kaynak:**

- `domain_engines/stabil/signals.py`, `domain_engines/stabil/__init__.py`, `domain_engines/stabil/runtime.py`
- `grafik/tarama.py`, `grafik/render.py`, `grafik/core.py`
- `grafik_uret.py`, `research/replay_egitim.py`

**Test:**

- `test_stabil_momentum_arrow.py` (yeni, 6 test)
- `test_replay_rendering.py` (`stabil` parity + `stabil_frames`)

**Yeni değerlendirme notları:**

- `docs/tasarim/GENEL_KONTROL_VE_STABIL_OK_DUZELTMESI_2026-11-03.md` (bu dosya)
- `docs/tasarim/API_SENARYOLARI_VE_URUN_FIKIRLERI_2026-11-03.md`

**Değiştirilmeyen ekler:** araştırma sonuçları, örnek görseller, `backfill_data/`, `bot_data/`, `capraz_piyasa_data/`, `state/`, mevcut JSON/CSV/PNG dosyaları.

---

## 6. Sonuç

Ana görsel sorun düzeltildi: yatay destek/geri alım dışındaki **güçlü yukarı mumlar** artık ayrı, içi boş `▲` ile işaretleniyor; destek yukarı basamak yaptığında da kaybolmuyor. Mevcut dolu yeşil geri alım oku, stepline, `Destek` çipi, kart metni, 4S alarmı ve native Stabil matematiği korundu. Normal/replay görünüm eşitliği `stabil` alanı da dahil olmak üzere test edildi. Genel kod/test/deploy kontrolü temiz; kalan uyarılar yapılandırma ve ürünleşme kararlarına ait, bu turda bilinçli olarak kapsam dışında bırakıldı.

API tarafında **gerçek bir endpoint eklenmedi**; kullanıcı isteği doğrultusunda salt-okunur API, webhook/olay akışı, replay eğitim servisi, dashboard, araştırma/backtest ve B2B sinyal feed'i use-case'leri ayrı notta değerlendirildi.
