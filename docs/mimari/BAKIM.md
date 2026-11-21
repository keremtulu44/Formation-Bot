# Mimari haritayla değişiklik yapmak

← [Mimari merkeze dön](README.md) · Durum: Yürürlükte · 20 Kasım 2026

## 1. Değişikliği doğru katmanda başlat

| Yapılacak iş | İzlenecek yol | İlk kontrol |
|---|---|---|
| Bir domain olayını yeni kart gerekçesi yapmak | [`runner.py`](../../domain_engines/runner.py) sonucunda alan var mı? → [`evaluate_domain_alarm_candidates`](../../bot/domain_alarm_service.py#L458) bunu okuyor mu? → Formasyon ya da Stabil yolu aynı olayı zaten taşıyor mu? | [`test_domain_alarm_service.py`](../../test_domain_alarm_service.py): koşul var/yok, eski bar, eksik domain ve karşı örnek. |
| Sadece kartın ifadesini düzeltmek | Önce kart türünü belirle. Birleşik kart: `format_domain_alarm_card`; Stabil 4s: `format_stabil_reclaim_alert_card`; ana formasyonun domain bağlamı: `notification_context.py`. | Aday seçimini ve tetik zamanını değiştirmeden metin ve satır tavanını kontrol et: [`test_kart_metin.py`](../../test_kart_metin.py), ilgili kanal testi. |
| Stabil ve formasyon aynı taramayı farklı yorumluyor | [Tarama önbelleği](../../bot/scan.py#L530) → zaman diliminin kapanışı → [Stabil adayı](../../bot/stabil_service.py#L240). Aynı hisse, TF ve **aynı kapanış** üzerinden karşılaştır. | [`test_stabil_scan_context_order.py`](../../test_stabil_scan_context_order.py). Replay’de desteklenen ama canlıda kapalı olan periyodu ayrıca belirt. |
| Tekrar veya kayıp bildirim incelemek | Aday kimliği → kanalın tekrar anahtarı → `dispatch` → DM/public kuyruk kabulü → hedefe gönderim → varsa görsel. | [`test_notification_delivery.py`](../../test_notification_delivery.py) ile ana yolu, [`test_delivery_security_regressions.py`](../../test_delivery_security_regressions.py) ve kanal testleriyle ilgili teslim davranışını kontrol et. Gerçek gönderim iddiası için ayrıca zaman/hedef eşleşen teslim kaydı gerekir. |
| Replay fikrini değerlendirmek | Önce [araştırma kaydını](../arastirma/README.md), sonra [canlı domain tablosunu](README.md#hangi-domain-kullanıcıya-nasıl-yansıyor) oku. | Aynı zaman dilimi, kapanış ve olay tanımını doğrulamadan araştırma eşiğini canlı ayara taşıma. |

**Örnek — “OB kartı niye tekrar çıktı?”** Dosya gezgininde `bot/domain_alarm_service.py` ile başla. `_bolge_sebepleri` yeni bir temas mı arıyor, yoksa fiyatın bant içinde olmasını mı? Ardından `dispatch_domain_alarm_candidates` içindeki anahtarı **aynı barın yeniden taranması** ve **sonraki barın da bantta kalması** için ayrı kontrol et. En son DM/public teslim satırlarına bak. Aynı gerekçeyi iki mumda bulmak, aynı Telegram mesajının iki kez teslim edildiğini göstermez.

## 2. Harita hangi değişiklikte nasıl yenilenir?

| Ne değişti? | Güncellenecek kayıt | Doğrulama |
|---|---|---|
| Python dosyası, import hedefi veya importun satırı | [Dosya gezgini](DOSYA_HARITASI.html) | Aşağıdaki üretim ve yazmasız kontrol komutları. |
| Motor çıktısı, aday kapısı veya teslim rotası | [Ana haritanın](README.md) katman tablosu, domain satırı ve gerekirse akış şeması | Okun yönünü hem çağıran hem tüketen kodda doğrula; ilgili testi seç. Kaynak linki fonksiyonun bulunduğu yeri göstermeli. |
| Dört kaynak modülde fonksiyon bağlantıları | [GitNexus çağrı kesiti](ALARM_CAGRILARI.csv) | Kaynak ağacını yeniden indeksle; [ana haritada kayıtlı sürüm, kapsam ve Cypher sorgusuyla](README.md#nasıl-üretildi-sınırı-ne) dört sütunu aynı sırada dışa aktar. Yenilenmediyse eski tarihli kayıt olarak bırak. |
| Yeni belge veya giriş yolu | [Belge dizini](../README.md) ve [mimari merkez](README.md) | Durum ve inceleme tarihi ekle. İkinci bir ana harita kopyalama; merkezden bağlantı ver. |

Repo kökünde, harici paket kurmadan:

```bash
python scripts/dosya_haritasi.py          # HTML'yi çalışma ağacından yeniden üretir
python scripts/dosya_haritasi.py --check  # yazmaz; eksik/eski HTML'de sıfırdan farklı kod döner
```

`--check` yalnız import gezgininin üreticiyle aynı olduğunu doğrular; GitNexus CSV’sini, açıklama metnini veya üretimde teslimatı doğrulamaz. GitNexus isteğe bağlıdır; geçici indeks/veritabanını depoya eklemeyin. Kaynak kod değişmiyorsa bir doküman düzeltmesi için yeni indeks gerekmez.

## 3. Değişiklik kaydında bulunması gerekenler

- **Kapsam:** Hangi domain, TF ve kart yolu değişiyor? Diğer yollar aynı mı kalıyor?
- **Sözleşme:** Üreten dosya/fonksiyon → tüketen dosya/fonksiyon → değişen koşul veya alan nedir?
- **Kanıt:** Statik import, kaynakta izlenmiş çağrı, test/replay veya gerçek teslim kaydı mı? Birini diğerinin yerine yazma.
- **Kapanış:** İlgili harita satırı ve test güncellendi mi? Doğrulanmayan kısmı açık bırak. Bir değişiklik yalnız araştırma veya belge ise bunu ayrıca belirt.
