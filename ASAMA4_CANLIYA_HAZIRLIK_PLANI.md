# Aşama 4 Çalışma Planı — Veri Güvenliği, Takvim Politikası, Kontrollü Doğrulama

**Süre hedefi:** 55 dk iş + 5 dk tampon = 60 dk. Her fazın çıkışında mini kontrol; başarısızlık halinde gevşetme yok, bulgu olarak raporlama var.

**Kanıt seviyeleri (raporda karıştırmayacağız):** `KOD` kod incelemesi · `TEST` izole test (sahte sağlayıcı, tmp disk, ağ yok) · `STAGING` ayrı ortam (bu görevde yok) · `ÜRETİM` gerçek servis (bu görevde yasak).

## Başlangıç durumu (P0 öncesi kaydedildi)

- Branch: `arena/956879bf-formation-bot`; HEAD: `f97c15c` (değişmeyecek; commit/push yok).
- Çalışma ağacı: 7 modified + 8 untracked (önceki turların rapor/test/kod ekleri) — **tümü korunacak**, hiçbiri silinmeyecek/sıfırlanmayacak.
- Önceki tam suite: 281 passed (116.50s). Bu görev başında yeniden ölçülecek ve ayrı kaydedilecek.
- P0 ön-doğrulama: `bar_kapandi_mi()` repo’da yok — mum-tamlığı sözleşmesi `data.py:908 tamamlanmis_mumlar()`. Notifier anchor’ları: `prepare_formation:1159`, `send:1226`, `acknowledge_delivery:407`, `activate_prepared_fallbacks:410`, `event_delivery_id:424`. Watch buffer TTL sabiti görülmedi (P0’da kesinleştirilecek).

## Zaman kutulu fazlar

### P0 — Başlangıç denetimi (0–6 dk)
- Git snapshot: branch/HEAD/status kaydı; korunacak dosya listesi rapora yazılır.
- `TELEGRAM_PRODUCT_AND_LIVE_READINESS_AUDIT.md` tamamı + format örnekleri dosyası okunur (format ve korunacak alanlar çıkarılır).
- Gerçek çağrı zinciri tek geçişte doğrulanır: fetch (`data.py: fetch_yfinance_1h/1d`) → normalize → `append_dataframe` → `tamamlanmis_mumlar` → `resample_all_timeframes` → lifecycle + domain → `prepare_formation` → `send` → `sent`/`ack`. Çıktı: zincir haritası (dosya:fonksiyon).
- Watch/digest TTL ve cooldown reset akışı kesinleştirilir (`telegram_alert_flow.py`, `notifier.py`).
- **Durdur kriteri:** zincirde bu plandaki varsayımla çelişen yapı çıkarsa plan güncellenir, sessizce devam edilmez.

### P1 — İzolasyon ve baseline (6–12 dk)
- Workspace’in geçici kopyası (`.git`, `.venv`, `bot_data` hariç değil — `bot_data` **salt okunur kopya**, testler tmp dizin kullanır); Telegram/Supabase env unset.
- Baseline: hedef regresyon grubu + tam suite çalıştır; 281 ile karşılaştır, farkları “başlangıç başarısızlığı” olarak ayrı kaydet.

### P2 — OHLCV giriş güvenliği (12–26 dk) *(tek kod değişikliği bölgesi)*
**Tasarım — tek doğrulama sınırı:** `data.py` içinde `ohlcv_frame_gecerli_mi(df)` (+ neden-geçersiz dönen yardımcı). Kapı: `StockDequeManager.append_dataframe()` — geçersiz frame deque’ye **hiç yazılmaz**, sorun `sureklilik_sorunlari` benzeri mekanizmayla raporlanır ve `scan_all_stocks` bunu fetch-başarısız yolu gibi işler. Formation ve domain motorları deque’den beslendiği için ayrı katmanda çoğaltma **yapılmaz**. `load_from_disk`/`hydrate_from_supabase` aynı kapıyı kullanır (bozuk satır atlanır — mevcut Supabase hydrate davranışıyla uyumlu).
**Kural matrisi (görevdeki 20 senaryoya eşlenir):**
- Red: boş frame; eksik sütun; NaN/Inf OHLC; `high<low`; `high < max(open,close)`; `low > min(open,close)`; ≤0 fiyat; negatif hacim; non-numeric.
- Kabul (mevcut sözleşme): **sıfır hacim** (BIST ilk bar sözleşmesi — cache’te 1.083/10.080 doğrulandı); duplicate timestamp (mevcut idempotent birleştirme korunur); sırasız timestamp (mevcut sort korunur); kapanmamış/gelecek mum (`tamamlanmis_mumlar` zaten filtreler — çoğaltılmaz); eski son mum (mevcut stale/veri-yok kuralları — gevşetilmez).
- Değişmez: formasyon matematiği, kalite, bildirim politikası, Telegram formatı.
**Test:** `test_ohlcv_guvenligi.py` — 20 senaryo + “hatalı yeni veri eski cache’i bozmuyor” + “hatalı sembol diğerini durdurmuyor” + kapsam raporu. Gerçek ağ yok.
- **Durdur kriteri:** mevcut bir testin gevşetilmesini gerektirirse önce gerekçe raporlanır.

### P3 — Hafta sonu/tatil matrisi (26–36 dk)
- **Kod değişikliği YOK** (ürün kararı); mevcut davranış kilitleyici/gözlemleyici testler: `test_takvim_politikasi.py`.
- Matris (14 senaryo): normal gün; cumartesi; pazar; resmî tatil; yarım gün; kapalıyken restart; hafta sonu biriken digest; TTL dolan mesaj (TTL yoksa bu bir bulgudur); pazartesi restore; pazartesi bekleyen mesaj; İstanbul gün değişimi; restart sonrası aynı mesajın tekrarı; aynı event’in çok taramada görülmesi; eski verinin güncel olay gibi gönderilme riski.
- Her senaryoda: tarama çalışıyor mu / provider isteği var mı / bekleyen mesaj akıbeti / cooldown-cap / heartbeat / “eski olay güncelmiş gibi” mümkün mü — tablo rapora.
- Bilinen bulgu önceden kayıtlı: ana döngü özetleri (09:55/18:45) ve 18:10/20:00 işleri hafta sonu guard’sız; `data.py:88/116/263` seans guard’lı. README “hafta sonu tarama yapmadan bekler” diyor → özetler bununla çelişiyor (kullanıcı kararı).

### P4 — Bildirim güvenilirliği hata pencereleri (36–43 dk)
- Mevcut `test_telegram_notification_delivery.py` kapsamı sayılır; eksikse eklenir: gönderim öncesi crash; Telegram hata; **kabul sonrası crash**; `sent` yazımı başarısız; restore sonrası aynı event; iki taramanın aynı olayı eşzamanlı üretmesi.
- `prepared`/`sent` zinciri garanti tablosu olarak raporlanır; exactly-once iddiası yok — at-least-once + duplicate penceresi açık yazılır.

### P5 — Canlı doğrulama planı + runbook (43–50 dk)
- `CANLI_DOGRLAMA_PLANI_VE_RUNBOOK.md`: Yahoo / Render / Supabase / Telegram için ayrı önkoşul, adım, başarı ölçütü, STOP kriteri; üretim verisine dokunmadan test yöntemleri; kullanıcı onayı gerektiren adımlar **[ONAY GEREKLİ]** etiketiyle; rollback prosedürü; tekrar mesaj / eski veri / bağlantı kopması playbooks.
- Bu görevde canlı test **çalıştırılmaz**; plan belge olarak teslim edilir.

### P6 — Regresyon ve yan etki kontrolü (50–56 dk)
- Yeni OHLCV + takvim + güvenilirlik testleri → hedef grup → izole kopyada tam suite.
- `git status` başlangıçla karşılaştırılır; `bot_data/` 56 commitli dosya + checksum değişimi kontrolü; test artığı yalnız “bu çalıştırmada üretildiği kanıtlanırsa” silinir; başlangıç dosyalarına dokunulmaz.

### P7 — Teslim raporu (56–60+ dk, tamponlu)
- `TELEGRAM_PRODUCT_AND_LIVE_READINESS_AUDIT.md`’ye **Aşama 4** bölümü (10 başlık: başlangıç, kod akışı, OHLCV, takvim politikası, güvenilirlik, testler, yan etki, canlı plan, kalan riskler, GO/NO-GO gerekçeli).
- Karar otomatik GO olmaz; ÜRETİM doğrulaması yapılmadığı sürece NO-GO/CONDITIONAL ayrımı kanıtla yazılır.

## Kullanıcı kararı bekleyen noktalar (kodlanmayacak, yalnız raporlanacak)
1. Hafta sonu/resmî tatilde scheduled özet + bakım/post-close DM’leri: üretilmesin / mevcut davranış kalsın / sonra karar ver.
2. Watch/digest TTL yoksa: süresi dolan aday düşürülsün mü?
3. A–E format seçimi (bu görevin kapsamı dışı — ayrı tutuluyor).

## Kabul kriterleri → faz eşlemesi
| Kriter | Faz |
|---|---|
| OHLCV sınırı açık + testli | P2 |
| Geçersiz veri motora ulaşmıyor / cache’i bozmuyor | P2 |
| Kısmi kapsam doğru raporlanıyor | P2 (mevcut + yeni test) |
| Hafta sonu/tatil testli veya açık ürün kararı | P3 |
| prepared/sent hata pencereleri testli, exactly-once iddiasız | P4 |
| Format/matematik/politika değişmedi | P2–P4 sınır denetimi + diff gözden geçirme |
| Tam suite + yan etki raporu | P1, P6 |
| Canlı plan ayrı, izole test ayrı | P5 |
| Commit/push/deploy/gerçek Telegram yok | Tüm fazlar |
