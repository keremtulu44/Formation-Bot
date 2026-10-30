# Replay işleri — turlar ve kabul kapıları

Durum: 2026-10-29, uygulama başladı. Referans taslaklar: `../tasarim/TELEGRAM_DM_REPLAY_EGITIM_MODU.md` ve `CAPRAZ_PIYASA_REPLAY_TASLAGI.md`. Arşiv `backfill_data/`, ayrı makro `capraz_piyasa_data/`; 12/12 makro hash doğrulaması veri kullanılabilirliği/kapanış zamanı doğrulaması değildir; USDTRY 31 OHLC tutarsızlığı işaretli. 75 Markdown envanteri tarandı; görevle ilgili tasarım, grafik, Telegram, araştırma ve veri sözleşmeleri önceliklidir. Önceki ilgisiz kirli dosyalar korunur.

## Tur 0: sınırlar ve plan
- İlgili belgeler ve kod akışı okunur; bu plan ve iki önceki taslak ayrı commit edilir.
- Hiçbir iş Supabase'e yazmaz veya canlı dağıtım yapmaz; Replay araştırması canlı alarmları değiştirmez.

## Tur 1: Telegram DM eğitim uygulaması
- 1h/2h/4h/1d ortak as-of kesitleri, arşivden sembol ve geçerli zaman, 8/10/20 eşit seçim, ±1.5 ATR ve kullanıcıya yalnız DM yanıt.
- Soru ve sonuç albümleri; tarihin ve geleceğin gizlenmesi; yalnız tamamlanmış mumlar; N. mum kapanışı; restart/yeni soru iptali; metin zorunlu.
- Mevcut grafik/komut altyapısını ve çalıştırma maliyetini incele; güvenli as-of gösterilemeyen analizleri açıkça sınırlı olarak raporla. Dağıtılan ortamda arşiv bulunmayabilir: hata açık olmalı.
- Birim, zaman hizası, leakage, Telegram yetki, eşzamanlılık ve regresyon testleri. Tam karşılanamayan kabul kriterleri gizlenmez. İlgili dosyalar bağımsız commit.

## Tur 2: çapraz piyasa rapor hattı
- Günlük seans başında yalnız kapanışı/doğrulanmış erişim zamanı bilinen veri; belirsiz kapanış, OHLC ve bayatlık `bilinmiyor`; asla sahte gram OHLC veya spot/vadeli ikamesi yok.
- Hisse 1/5/10 işlem günü, ATR bazlı yön ve eşik adayları, tekli ve birleşik koşullar; sansür/UNKNOWN ve tüm değerlendirilmiş hücrelerin ayrıntısı, kapsam/sayı/baseline; keşif-doğrulama dönemleri ve seçim yanlılığını açıkla.
- Kaynak eşzamanlılığı doğrulanmazsa güvenli biçimde raporla; testlerde geleceği değiştirmek bağlamı değiştirmez. Offline CLI, örnek koşu, kalite ve kapsam raporu; canlı karta bağlama yok. İlgili dosyalar bağımsız commit.

## Tur 3: kaçırılan hareketler araştırması (uygulama değil)
- Fiyat merkezli yükseliş/düşüş ayrı tanımlarla küçük gerçek arşiv pilotları; örnekleme, örtüşme, geleceğe bakma, veri boşluğu ve baz oran testleri.
- Mevcut Replay/olay kayıtlarının neyi temsil ettiğini doğrula; gerçek alarm ile yeniden üretimi ayır, ölçülemeyen filtre/teslim durumunu `bilinmiyor` tut.
- En az iki hareket veya pencere tanımı ve kontrol grubu/örnek analizi; deneylerin sayıları, tarihleri, evreni, sınırları, maliyet ve tekrar komutları yazılır. Kurgusal sonuç sunulmaz.
- Bulgulara dayalı sistem şeması, metrikler, validasyon, yanlış-alarm/missed-event ayrımı ve gelecekteki uygulama aşamaları bir raporda; deney aracı yalnız araştırma içindir. Bağımsız commit.

## Tur 4: regresyon ve teslim
- İlgili testler, Ruff, `git diff --check`, mümkünse daha geniş regresyon; git status ve commit kapsamı kontrol edilir. Her eksik/hata açıkça bildirilir; kullanıcının veri commit'i korunur.
