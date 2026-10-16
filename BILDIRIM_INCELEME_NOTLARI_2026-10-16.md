# Bildirim notları — 16 Ekim 2026

Kullanıcı onayıyla uygulandı:
- Aynı hisse/formasyon/yön/olayın farklı TF kopyalarında ilk paket kazanır; varsayılan eşleştirme penceresi 4 saat. Karşı yön ve yeni olaylar ayrı değerlendirilir.
- Geçersizleşme için her TF'de 3 ardışık kapanmış mum gerekir; toparlanmada sayaç sıfırlanır. Eşik ayarlanabilir.
- Görseller hazır olmadan metin gönderilmez; metin + albüm sıralı teslim edilir. Kalıcı kuyruk, restart sonrası devam ve kısmi teslimin tekrar denenmesi eklendi.
- Tekli geçersizleşme alt yazısı yalnız hisse + TF. Normal kartın verisi korunarak Türkçe ay adı ve sade işaretler kullanıldı.
- Grafik snapshot'ının eski kuyrukta kaybolması ve `DeferredAlertBuffer.snapshot` çakışması düzeltildi.

Ayarlar: `INVALIDATION_CONFIRM_BARS=3`, `MTF_ALERT_MERGE_HOURS=4`.
İşletim sınırları ve ayrıntılar: [Bildirim teslim politikası](docs/BILDIRIM_TESLIM_POLITIKASI.md).
Canlı mesaj/deploy yapılmadı; test sonucu politika dosyasında tutulur.

## Grafik — son durum
- Engulf ve internal grafiklerden tamamen kaldırıldı: internal oklar, HH/HL/LH/LL, iç yapı başlığı ve lejantı yok. Dış yapı, motor hesapları ve bildirim metni korunur.
- Her görünür OB/FVG için sağ etikette alt–üst fiyat aralığı var; yakın fiyat etiketleri birleştirilmez, çok satırlı yerleşimle çakışma önlenir. Kutu içi durum yazısı korunur.
- Eski snapshot ve bekleyen hazır PNG'ler de yeni grafik politikasına geçirilir; gönderilmiş metin tekrarlanmaz.
- Tam regresyon: **1312 geçti, 43 atlandı**. `git diff --check` temiz; deploy yapılmadı.

## Grafik SaaS öncelikleri 1–3

- Güven şeridi: analiz zamanı, yıl/TSİ, kaynak ve mum derinliği, seans bazlı tazelik, motor hazırlığı ve RVOL kaynağı.
- Açık bölge durumları ve dolum adı; kritik olay referansı; varsayılan odak, seçilebilir bağlam ve mobil çıktı.
- Gizlenenler silinmez: JSON/HTML bölge ayrıntısı, uzak dış seviyeler ve dış olay zaman çizelgesi.
- Normal bildirim metni/motorlar korunur. Grafik politikası `chart-trust-focus-v3`; eski hazır PNG yenilenir, gönderilmiş metin tekrarlanmaz.
- Kullanım, sınırlar ve kabul sözleşmesi: `docs/GRAFIK_GUVEN_ODAK_AYRINTI.md`.

### Son doğrulama — öncelikler 1–3

- Tam paket: **1345 passed, 43 skipped**, 240,86 saniye.
- 32 yeni güven/odak/ayrıntı regresyonu ve 1 yeni Telegram seçenek aktarımı testi.
- Beş gerçek önbellek örneği odak/bağlam/mobil ile yeniden üretildi; görseller açılıp incelendi.
- Bu örneklerin veri sonu 25 Eylül 2026; beşinde de kullanılabilir formasyon seçilmedi. Gerçek cihaz/tarayıcı ve canlı alarm senaryosu testi değildir.
