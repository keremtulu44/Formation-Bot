# Destek–direnç karşılaştırması: doğrulama ve kapsam

## Kapsam ve izlenebilirlik

- 174/174 hissede replay tamamlandı; sembol hatası **0**. Önceki direnç çalışmasının 349 arşiv dosyası ve hesaplama kaynağı hash'leri kontrol edildi. Eski 100 hissenin tamamı 174 hisselik evrendedir; bir alt grubun geçerli hisse sayısı filtreye göre daha az olabilir.
- İki tarafla birlikte 33.893 4s olay (17.731 destek, 16.162 direnç), 35.351 native günlük olay ve dört eski soru tarifine yakın 328.762 checkpoint kaydedildi. Sayılar birbirinden farklı örnekleme birimleridir.
- Normal destek, gerçek OHLC üzerinde native günlük algoritmayla kuruldu. Her günlük gözlemde sabit `100.000−fiyat` koordinatındaki yansıma, bağımsız native tersleme ile seviye, sınır, köken, teyit ve ulaşılabilirlik bakımından kontrol edildi. 4s TEST, BREAK, RETURN ve DEPART seçimleri ayrıca gerçek destek fiyatlarıyla doğrudan yeniden türetildi.
- Önceki direnç koşusunun tüm 16.162 ana 4s ve 17.161 günlük olayının kimliği; 4s durum, yön etiketi ve temel fiyat/sonuç sütunları önceki dosyalarla karşılaştırıldı. Aynı mumdaki ortak destek/direnç olaylarının kalite/sansür durumları aynı olmalıydı.
- AEFES, DOCO ve YYAPI için A01, B04, C02, F01 giriş grupları, mevcut eski `research/stabil_replay.py` ve `stabil_bhv48.py` ile bağımsız yeniden üretildi: kapalı bar ve C02'de seviye/ATR'nin mum başında bilinmesi uygulanınca örneklenen grup kimliklerinde, geçerli 8 bar ilk-vuruş/geri getiride ve geçerli 24 bar yarışında **0 fark**. Bu üç örnek, 174 sembolün tamamındaki tüm olası yolların bağımsız kanıtı değildir. İki tarafta 3'er günlük prefix kesimi de geleceğe dayanmazlık için kontrol edildi.
- 2026 TEST eşlemesinde sonuç bakılmadan seçilen 202 çiftin 178'i iki tarafta da geçerli; hiçbir direnç olayı tekrar kullanılmadı ve her çiftin olayları en az 8 bar ayrı. Özet tekrar hesaplandı; bootstrap hisse kümeli, 2.000 tekrar ve sabit tohumludur.
- Ek yol koşusu 5.998 kırılmanın her birini aldı; 4.686'sında tam/temiz 24 bar vardı. İki taraf ve farklı dallardaki 81 geçerli AEFES/DOCO/YYAPI olayı, yansıtılmış fiyat kullanılmadan gerçek fiyat yönleriyle adım adım bağımsız yeniden hesaplandı; 0 fark. Sayılan 392 aday yataylaşma dalı bütün dönemlerdendir.

Makine-okunur kanıt: [ana doğrulama çıktısı](verification.json), [ek yol doğrulaması](path_verification.json), [ana veri/kod manifesti](manifest.json), [rapor manifesti](analysis_manifest.json), [ek yol manifesti](path_manifest.json). Kullanılan arşiv, yakalama ve kalite ayrıntıları [önceki direnç doğrulamasında](../stabil_direnc_replay_2026_11_06/DOGRULAMA.md) da kayıtlıdır.

## Tekrar çalıştırma

```bash
python -m research.stabil_support_resistance_compare --workers 2
python -m research.stabil_support_resistance_report
python -m research.stabil_support_resistance_verify
python -m research.stabil_support_resistance_paths --workers 2
python -m research.stabil_support_resistance_path_verify
pytest -q test_stabil_support_resistance_compare.py test_stabil_support_resistance_paths.py test_stabil_resistance_replay.py test_stabil_arrow_context_replay.py test_stabil_arrow_quality.py test_stabil_vertical_policy.py
```

Araştırma planı ve ek yol planı önceki sonuçlar görüldükten sonra oluşturulmuştur; kör ön kayıt değildir. Zaman penceresi/kalite dışlamaları, aynı-bar belirsizliği, ortak piyasa günleri, çakışan checkpoint'ler, aday rejimin görsel eşlemesinin doğrulanmamışlığı ve canlı 4s sinyal eşdeğerliğinin yokluğu ana sonuçta belirtilmiştir. Bu çalışma üretim kuralını, alarmı veya Telegram'ı değiştirmez.
