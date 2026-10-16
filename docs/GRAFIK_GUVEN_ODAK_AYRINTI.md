# Grafik: güven, odak/bağlam, açıklanabilirlik

16 Ekim 2026 — Kullanıcının onayladığı ilk üç öncelik. Grafik politikası: `chart-trust-focus-v3`.

## Kısa gereksinimler ve kapsam

1. **Güven:** bölge yaşam döngüsü açık; son mum tarihi yıl/TSİ içerir; analiz anındaki tazelik ve motor bazlı hazırlık görünür; RVOL kaynağı ve yüzdelerin anlamı açıklanır.
2. **Okunabilirlik:** varsayılan odak yakın, tamamlanmamış bölgeleri gösterir; bağlam görünümü geçmiş/uzak bölgelere erişim sağlar; tam fiyat aralıkları korunur; yinelenen kutu içi metinler kaldırılır; mobil çıktı ayrı geometri kullanır.
3. **Açıklanabilirlik:** gizlenen bölgeler, uzak dış yapı seviyeleri ve dış olay geçmişi JSON/HTML ayrıntısında korunur. Neden gösterildi/gizlendi açıklanır.

Motor hesapları, normal bildirim metni, formasyon/teyit/retest/geçersizleşme kuralları değiştirilmez. Internal ve engulf hiçbir görsel/ayrıntı katmanına eklenmez. Kalibre edilmemiş olasılık/tek birleşik skor üretilmez. Bu çalışma kullanıcı hesabı, ödeme, çok kiracılı API veya canlı SaaS dağıtımı değildir.

## 1. Güven sözleşmesi

- `anlik_goruntu()` güven bilgisini aynı analiz anında dondurur. Yeniden çizim motor çalıştırmaz ve eski veriyi güncelmiş gibi yeniden zamanlamaz.
- Görsel başlığı **son mum etiketi** der. Günlükte yalnız tarih/yıl/TSİ vardır; resample `00:00` etiketi borsa kapanışı gibi yazılmaz. Diğer TF'lerde saat mum etiketidir, gerçek kapanış saati iddiası değildir.
- Güven şeridi analiz zamanı, kaynak türü, motor girdisi mum sayısı, motor bazlı hazırlık ve RVOL kaynağını taşır. Bu şerit uzun teknik lejanttan bağımsızdır; `GRAFIK_LEJANT_KARE=0` ile kapanmaz.
- `CURRENT`: mevcut XIST takvimi, serinin gözlenen etiket hizası ve mevcut `data.mum_kapanis_ani` sözleşmesine göre son beklenen kapanmış mum analiz anında mevcut. Beş dakikalık veri geliş toleransı vardır.
- `STALE`: beklenen kapanmış mum gerisinde. Hafta sonu/kapalı seansta salt duvar saati yaşıyla gecikme ilan edilmez.
- `HISTORICAL`: açıkça tarihsel/offline inceleme. Güncel veri iddiası yoktur.
- `FUTURE`: son mum zamanı analiz anından ileride.
- `UNKNOWN`: takvim/zaman/etiket hizası eksik veya doğrulanamıyor. Bilinmeyen durum yeşil başarı sayılmaz.
- Veri sağlayıcısına bağımsız doğrulama yapılmaz. “Bellek/önbellek” bir yükleme yoludur; sağlayıcı adı/lisansı kanıtı değildir. Kaynak verilmemişse açıkça belirtilir. Çekim zamanı yoksa icat edilmez.
- Eski snapshot'ta kaydedilmemiş güven/olay bilgisi bilinmiyor kalır; motorları tekrar çalıştırarak doldurulmaz.

Motor hazırlığı `hazır / geçmiş yetersiz veya hazır değil / bu TF desteklenmiyor / bu akışta kapalı / hata / bilinmiyor` olarak ayrılır. Hazır olmak sinyal bulunduğu veya finansal başarı garantisi olduğu anlamına gelmez. Hacim motoru hazır değilken yerel RVOL varsa kaynak ayrıca yazılır; motorun geçmiş eşiği düşürülmez.

Bölge etiketleri yerel durum adını taşır: aktif, aday, tepki kaydı, tam doldu, geçersiz vb. `REACTION`, `FULL_FILL`, `INVALID` birbirine eşitlenmez. OB yüzdesi açıkça `dolum %N`; formasyon puanı `kalite N/100` olarak yazılır. Başarı olasılığı iddiası yoktur. Kritik seviye son seçilen dış BOS/CHoCH referansıdır, otomatik stop/hedef değildir.

## 2. Görünüm sözleşmesi

- **Odak (varsayılan):** geçmiş/terminal bölgeler ana grafikte yoktur. Bölge sınırına uzaklığı varsayılan en fazla 3 ATR olanlar mevcut TF başına üst/alt kotaları içinde seçilir. Bu bir görünüm eşiğidir, doğrulanmış işlem kuralı değildir. `GRAFIK_ODAK_MESAFE_ATR` ile ayarlanabilir. ATR yoksa görünür mum fiyat aralığıyla kesişim kullanılır; ATR uydurulmaz.
- **Bağlam:** geçmiş ve uzak bölgeler mevcut çizim kotaları içinde çizilebilir; yerel durumları açık etiketlenir. Kotanın dışında kalanlar da ayrıntıda korunur. Bağlam “tüm kayıtları aynı anda üst üste çiz” anlamına gelmez.
- Fiyat bölgenin içindeyse **sınır uzaklığı 0**. Merkez uzaklığı ayrı alandır. Motorların kendi ölçümleri yeniden yazılmaz; mevcut merkez uzaklığı alanları korunur.
- İki veya daha çok slot bulunan tarafta, uygun aktif FVG için görünürlük payı korunur.
- Odakta uzak PH/PL/WH/WL ana fiyat eksenini zorunlu genişletmez; ayrıntıda tam fiyatı/rolü korunur. Kadraj öncesi olay yazıları sol kenara yığılmaz; zaman çizelgesinde kalır.
- Çizilen her OB/FVG için sağda alt–üst aralık ayrı ve eksiksiz kalır. Büyük fiyatlarda satıra bölünür; bölgeler tek bir uydurma aralıkta birleştirilmez. Kutu içi aynı kimliği tekrar yazma kaldırılmıştır.
- **Mobil:** 780×1100, en az ×1,35 yazı, daha geniş sağ cetvel ve sol eksen payı. Masaüstü modu varsayılan 1080×810'dur. Gerçek cihaz kabulü ayrıca yapılmalıdır; bu profil bütün olası yoğunluklar için garanti değildir.
- `sade` hâlâ mum/formasyon/kritik/son fiyat modudur; gizlenen bölge sayısı ve ayrıntı durumu doğru güncellenir.

## 3. Ayrıntı sözleşmesi

`meta['ayrinti']` JSON uyumlu sunum modelidir:

- Bölgeler: tam aralık, oluşum yönü, yerel/Türkçe durum, kaynak zamanı/indeksi, aktif/tamamlanmış kaynak türü, OB dolum yüzdesi, fiyatın konumu, sınır ve merkez ATR uzaklığı, görünürlük nedeni.
- Dış yapı seviyeleri: PH/PL/WH/WL, rol, tam fiyat, kaynak zamanı ve odakta görünürlüğü.
- Dış olaylar: zaman, yaş, olay tipi, yön, referans fiyat; teyit/geçerlilik/güncellik ayrı alanlar. Olay geçmişi yeni alarm değildir.
- Güven ve sözlük: aynı dondurulmuş analiz anı; ok/yüzde/RVOL/kritik açıklamaları.

`--ayrinti` ile internet istemeyen tek dosyalık HTML üretilir. Odak/bağlam/mobil PNG'leri **aynı snapshot'tan**, tekrar motor çalıştırmadan eklenir. Bölge araması ve geçmiş filtresi vardır. Veriler HTML-escape edilir; ham hata/sağlayıcı dosya yolları arayüze taşınmaz. Alternatif çizimlerin geçici dosyaları temizlenir. HTML hatası ana PNG'yi silmez; CLI açıkça başarısız dışa aktarım bildirir.

## Kullanım

Telegram (yalnız grafik komutu; normal bildirim metni aynı):

```text
/grafik AKBNK 2s odak
/grafik GARAN 4s baglam
/grafik THYAO 1g odak mobil
```

CLI (mevcut yerel veri, canlı fetch yok):

```sh
.venv/bin/python grafik_uret.py --hisse GARAN --tf 4h --zone --formasyon-tara \
  --gorunum odak --cikti /tmp/garan.png --ayrinti /tmp/garan.html
```

Tarihsel önbellek örneği:

```sh
.venv/bin/python grafik_uret.py --hisse THYAO --tf 1d --zone \
  --veri-dizin bot_data --tarihsel --mobil \
  --cikti /tmp/thyao.png --ayrinti /tmp/thyao.html
```

Ortam seçenekleri: `GRAFIK_GORUNUM=odak|baglam`, `GRAFIK_ODAK_MESAFE_ATR=3.0`, `GRAFIK_MOBIL=0|1`. Açık CLI/çağrı tercihi ortam değerini ezer. Telegram'a ayrıntı dosyası otomatik gönderilmez; HTML dışa aktarımı CLI/Python yüzeyindedir.

## Teslim ve doğrulama

Kuyruk eski hazırlanmış PNG'yi yeni politika ile yeniden üretir; `text_sent` korunur. Yeni politika sadece sunumu değiştirir; daha önce teslim edilmiş metin yeniden gönderilmez. Kalıcı disk/uzak yedek ve Telegram'ın yanıt kaybından doğan belirsizlikler önceki sözleşmedeki gibidir.

Regresyonlar: hafta sonu/seans başı/yarım gün/tatil, takvim bilinmiyor, kaynak ve günlük tarih, motor bazlı hazırlık, durum etiketleri, sınır/merkez uzaklığı, odak/bağlam kayıpsızlığı, gizlenen dış seviyeler, eski internal/engulf snapshot, mobil kapsam sızıntısı, HTML escaping, aynı snapshot'tan dışa aktarım, komut aktarımı ve eski PNG yenileme.

Üretim kodu canlıya dağıtılmadı. Canlı fiyat/Telegram gönderimi yapılmadı. Gerçek cihaz/üretim yük testi ve beş önbellek örneğinde bulunmayan gerçek formasyon-alarm senaryoları ayrıca doğrulanmalıdır.

### Son doğrulama — öncelikler 1–3

- Tam paket: **1345 passed, 43 skipped**, 240,86 saniye.
- 32 yeni güven/odak/ayrıntı regresyonu ve 1 yeni Telegram seçenek aktarımı testi.
- Beş gerçek önbellek örneği odak/bağlam/mobil ile yeniden üretildi; görseller açılıp incelendi.
- Bu örneklerin veri sonu 25 Eylül 2026; beşinde de kullanılabilir formasyon seçilmedi. Gerçek cihaz/tarayıcı ve canlı alarm senaryosu testi değildir.
