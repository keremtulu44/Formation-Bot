# Bildirim / "uyuyor sanma" / grafik incelemesi — 2026-11-15

## Bulunan ve düzeltilen sorunlar

### 1. (Ana neden) Heartbeat yalnız taramada yazılıyordu → canlı bot "uyuyor" sanılıyordu
`write_heartbeat` yalnız tarama içi/sonunda, hata ve kapanışta çağrılıyordu.
Seans dışı bekleme, uzun uyku ve boş döngülerde `heartbeat.json` saatlerce
güncellenmiyordu. Sonuç: `/health` `heartbeat_stale`, `deploy_check.py` ve
açılışta hesaplanan `/render` boşluğu, uyanık süreci bayat/uyumuş gösterdi.
**Düzeltme:** ana döngünün her turunda kısılmış (varsayılan 60 sn) periyodik
heartbeat (`bot/app.py`). Artık boşluk gerçekten süreç kesintisini ölçer.

### 2. (Ana neden) Teslim kuyruğunda zehirli satır bütün bildirimleri kilitleyebiliyordu
`notification_delivery.DeliveryOutbox.flush` FIFO'dur (metin+albüm sırası
korunur — bilinçli tasarım). Ancak üç kalıcı durum sonsuz kilit üretiyordu:
- `can_send` "tekrar" (bugün zaten bildirildi) derse satır hiç kapanmadan
  başta bekliyordu. **Düzeltme:** tekrar satırı `suppressed` olarak kapatılır,
  arkadakiler gider; `submit` bunu teslim saymaz.
- Kare snapshot'ı kalıcı bozuksa (örn. kare verisi yok) `prepare` her seferinde
  patlıyor, metin hiç gitmiyordu. **Düzeltme:** 3 başarısız hazırlık sonrası
  kart **karesiz** gönderilir (`grafik_atlandi`, log'lu).
- `_gonder_metin` False dönerse `retry_at` basılmadan `break` ediliyordu:
  döngü her turda anında yeniden deniyor + kuyruğu kilitliyordu.
  **Düzeltme:** ortak hata yolu 30 sn backoff basar.

### 3. Bildirim sağlığı dışarıdan görünmüyordu
`/health` artık `bildirim: {enabled, teslim_kuyrugu{pending,last_error,
attempts,...}, acil_kuyruk, son_basarili_gonderim, son_gonderme_hatasi}`
döndürür; `deploy_check.py` bekleyen kuyrukta uyarı verir. `/render` artık
açılıştaki tahmini boşluğun yanına **şu anki** heartbeat yaşını da yazar;
geçmişte uyumuş olmak "hâlâ uyuyor" diye okunmaz.

## Grafikler hakkında genel öneriler (öncelik sırasıyla)

Örnek kareler incelendi: `docs/gorseller/AKBNK_ODAK_MOBIL.png`,
`ornek_gorseller/AKSA_Simetrik_Ucgen.png`.

1. **Sağ panel alan israfı:** Mobil karede genişliğin ~%25'i sağ şerit;
   etiket yokken tamamen boş. Etiket sayısına göre şerit genişliği dinamik
   olmalı (0 etiket → şerit yok), boşalan alan mumlara verilmeli.
2. **Hacim görünmüyor:** RVOL rozetleri var ama hacim paneli yok; kullanıcı
   "hacim artışı" iddiasını grafikte doğrulayamıyor. Alt %15'e soluk hacim
   çubukları + RVOL>eşik mumlarında renklendirme eklenmeli.
3. **Alt bilgi çok yoğun:** 5 satırlık footer telefonda okunmuyor ve asıl
   mesajı (yön/state/son mum) gölgeliyor. Footer 2 satıra inmeli; ayrıntı
   `/grafik ... detay` moduna taşınmalı, karede yalnız "veri tazeliği +
   analiz zamanı" kalmalı.
4. **Etiket çakışması:** Fiyat etiketi (70,95), kritik seviye ve OB kutusu
   sağda üst üste biniyor. Çakışan etiketler fiyat sırasına göre otomatik
   kaydırılmalı (leader-line ile), son fiyat her zaman en üstte/ayrı renkte.
5. **Zaman ekseni:** "07 Eyl9 Eyl11 Eyl" gibi birleşik etiketler okunmuyor.
   TF'ye göre uyarlanmalı: 1s/2s'de saat, 4s/1g'de gün; en fazla 5-6 etiket.
6. **Renk erişilebilirliği:** Yeşil/kırmızı mum + turuncu/teal çizgiler
   renk körlüğünde ayrışmıyor. Yön yalnız renkle değil işaretle de kodlanmalı
   (zaten ▲/▼ var; çizgi stilleri de farklı olmalı: BOS kesikli, CHoCH noktalı).
7. **Formasyon vurgusu:** Üçgen çizgileri tüm kareyi kaplıyor ama kırılım
   mumu/bölgesi vurgulanmıyor. Kırılım mumuna dikey soluk bant + kırılım
   seviyesinde kalınlaşma, "sonraki soru" olan hedef/stop mesafesini
   sağ boşlukta R katı olarak gösterme eklenebilir.
8. **Boş/veri-yok durumu:** "son mum bilinmiyor · 0 mum" gibi belirsiz
   footer yerine karenin köşesinde belirgin "VERİ EKSİK" rozeti olmalı;
   kullanıcı eksik verili kareyi gerçek analiz sanmamalı.
9. **Tutarlılık:** Aynı sembolde 1s/2s/4s/1g kareleri arasında renk/etiket
   dili aynı kalmalı; TF değişince yalnız kadraj değişmeli (küçük çoklu
   önizleme / karşılaştırma modu için de temel bu).
10. **Performans:** 4 karelik albümlerde her kare tam footer/lejant taşıyor;
    albümde ilk kare tam, diğerleri sade olursa Telegram'da hem boyut hem
    okunabilirlik kazanılır.

## Notlar
- Stabil direnç testlerindeki başarısızlıklar bu makinede pinli olmayan
  ortamda (pandas 3.x; repo pandas 2.2.2 pinler) yeniden üretildi; CI pinli
  ortamı kullanır. Kod değişikliği yapılmadı, izlenmeli.
- Render Free gerçekten 15 dk inaktivitede uyur; keep-alive GitHub cron'u
  garanti vermez. Kesin çözüm ücretli plan veya harici uptime pingidir;
  kod tarafı artık uykuyu yanlış teşhis etmeyecektir.
