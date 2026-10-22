# Bildirim ve teslim politikası — 16 Ekim 2026

Kullanıcı onayıyla uygulanan kurallar ve işletim sınırları.

## İstekler ve uygulama
- **TF tekrarı:** Aynı hisse/formasyon türü/yön/olay için farklı TF'lerden ilk paket kazanır. Birleştirme penceresi `MTF_ALERT_MERGE_HOURS=4`; karşı yön, farklı olay aşaması ve aynı TF'deki yeni formasyon ayrı kalır. Susturulan formasyon kimlikleri kaydedilir; pencere bitince tekrar belirmez, hiç duyurulmamış TF'nin geçersizleşmesi de gönderilmez. DM ve public tekilleştirmesi ayrı tutulur.
- **Geçersizleşme:** `INVALIDATION_CONFIRM_BARS=3` ardışık kapanmış mum boyunca tolerans ötesinde içeri dönüş görülmeden başarısızlık oluşmaz. Toparlanma sayacı sıfırlar. Her TF kendi mumlarını sayar; aynı mum tekrar sayılmaz, yeni kırılım/formasyonda sayaç sıfırlanır. Kural yalnız mesajda değil yaşam döngüsünde uygulanır.
- **Metin + görsel:** Canlı alarm hattı artık `notification_delivery.py` içindeki kalıcı FIFO'dan geçer. Tüm görseller hazırlanıp kaydedilmeden metin çıkmaz; metnin hemen ardından kendi albümü gider. Başka hissenin alarmı araya girmez. Başarısız iş kuyrukta kalır; metin teslim edilmişse tekrar gönderilmeden yalnız medya denenir. En az 30 sn hata beklemesi vardır; ana döngü seans dışında da yeniden dener.
- **Kalıcılık:** Atomik yerel JSON, tarihleri koruyan snapshot codec'i ve isteğe bağlı Supabase yedeği eklendi. Hazır PNG'ler teslim kaydında saklanır. Bekleyen teslimler TTL ile silinmez; bitmiş kayıtlar yeni kayıt kabulünde 7 günlük pencereye budanır. Bekleyen/parçalı teslim ve hata bilgisi gönderim sağlığına eklenir. Eski cooldown/kota kuyruğu da artık grafik snapshot'ını kaybetmez.
- **Sunum:** Tekli geçersizleşme görselinin altında yalnız hisse + TF. Normal kartlarda aynı veriler korunur; sade işaretler, gerçek Türkçe ay adı ve uygun ek kullanılır: “16 Ekim'den beri”. Uzun tarih gerektiğinde ayrı satıra geçer.
- **Ek hata:** `DeferredAlertBuffer.snapshot` gölgelenmesi kaldırıldı; hem mevcut kalıcılık çağrısı hem `snapshot(now)` desteklenir. İlgili daha önce atlanan test açıldı.

## Sınırlar / işletim
- Telegram ayrı metin ve albümü atomik göndermez. Kabul edilmiş isteğin cevabı kaybolursa veya kabul ile yerel teslim kaydı arasına çökme girerse, son parçada mükerrerlik tamamen dışlanamaz. Belirsiz albüm hatasında tekli fotoğrafa otomatik geçiş kaldırıldı.
- Render'ın geçici diski redeploy'da silinebilir: redeploy sürekliliği için çalışan Supabase yedeği veya kalıcı `DATA_DIR` gerekir. Uzak yazma hataları loglanır; yerel kayıt korunur.
- Çizilemeyen en eski paket, sıralamayı korumak için sonraki alarmları bekletir; `gonderim_durumu()["teslim_kuyrugu"]` ve loglar izlenmelidir. Bu politika sessiz kayıp yerine görünür beklemeyi seçer.
- TF eşleştirmesi ortak bir piyasa-olayı kimliğine değil yukarıdaki tür/yön/zaman politikasına dayanır; pencere gerekirse ayarlanabilir. Cooldown/kota nedeniyle eski acil kuyruğa alınan olayların mevcut kapanış-özeti politikası korunur.

## Doğrulama
- Yeni testler: hazırlık hatası, restart, kısmi teslim, FIFO, TF tekrarı, ters yön/yeni formasyon, uzak yedekten dönüş, retry beklemesi, gerçek grafik JSON round-trip, alt yazı, tarih ve üç mum doğrulaması.
- Tam paket: `1312 passed, 43 skipped` (`.venv/bin/python -m pytest -q --disable-warnings`).
- `git diff --check` ve değişen Python modüllerinin derleme kontrolü temiz. Telegram'a canlı mesaj atılmadı; deploy yapılmadı.

## Güncel grafik politikası
- Grafiklerde engulf ve internal katmanı yok; dış yapı korunur. Her OB/FVG için sağda fiyat aralığı gösterilir.
- Teslim kuyruğu eski hazır görselleri `chart-trust-focus-v3` politikasıyla yeniden üretir; teslim edilmiş metni tekrar göndermez.

- Güven/odak/ayrıntı sözleşmesi: [docs/tasarim/GRAFIK_GUVEN_ODAK_AYRINTI.md](GRAFIK_GUVEN_ODAK_AYRINTI.md). Normal bildirim metni ve motor kuralları bu sunum değişikliğiyle değişmez.

- Güven/odak/ayrıntı sonrası son tam paket: **1345 passed, 43 skipped** (240,86 sn).
