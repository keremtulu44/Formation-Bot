# Fiyat koşulundan bağımsız sabit çizgi yolu — 50 hisse

Bu keşifsel ek test, aynı tam/temiz 24 × 4s kırılma epizotlarında önce çizginin ters yönde taşındığı olaylarla sınırlıdır. Çizgi aday yatay sınıfına veya fiyatın günlük taraftaki konumuna göre seçilmez. Güvenli taraf destekte çizgiye eşit/üstü, dirençte çizgiye eşit/altıdır. İhlal kesin olarak destekte alt, dirençte üst kapanıştır.

| Dönem / taraf | İlk taşınmada fiyat | n | Hisse | Fiyat karşı tarafa önce | Çizgi kimliği değişimi önce | Aynı-bar | Hiçbiri | Kalan bar yok |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| PRE_2026 / Direnç | İhlal | 4 | 4 | 0 (%0.0) | 0 (%0.0) | 0 (%0.0) | 3 (%75.0) | 1 (%25.0) |
| PRE_2026 / Direnç | Güvenli | 50 | 31 | 11 (%22.0) | 2 (%4.0) | 0 (%0.0) | 34 (%68.0) | 3 (%6.0) |
| PRE_2026 / Destek | İhlal | 2 | 2 | 1 (%50.0) | 1 (%50.0) | 0 (%0.0) | 0 (%0.0) | 0 (%0.0) |
| PRE_2026 / Destek | Güvenli | 26 | 20 | 6 (%23.1) | 0 (%0.0) | 0 (%0.0) | 18 (%69.2) | 2 (%7.7) |
| Y2026 / Direnç | İhlal | 6 | 6 | 6 (%100.0) | 0 (%0.0) | 0 (%0.0) | 0 (%0.0) | 0 (%0.0) |
| Y2026 / Direnç | Güvenli | 46 | 32 | 11 (%23.9) | 3 (%6.5) | 0 (%0.0) | 24 (%52.2) | 8 (%17.4) |
| Y2026 / Destek | İhlal | 6 | 6 | 5 (%83.3) | 0 (%0.0) | 0 (%0.0) | 1 (%16.7) | 0 (%0.0) |
| Y2026 / Destek | Güvenli | 65 | 35 | 16 (%24.6) | 3 (%4.6) | 0 (%0.0) | 40 (%61.5) | 6 (%9.2) |

2026'da yeni direncin ilk taşınmasında fiyat üstünde olan 6 olayın 6 tanesinde fiyat çizgiye eşit/alt kapandı; çizgi kimliği değişmeden kesin alt kapanış 5 tanesinde görüldü. İlk eşit/alt kapanış sonrası 4 olayda fiyat kalan pencerede önce tekrar üstte kapandı. Bu küçük sayı bir başarı oranı değildir.

Bu bir native çizgi **kimliğinin sabit kalması** ölçümüdür; sabit stepline segmenti kullanıcı tarifindeki görsel yatay rejimle aynı ilan edilmez. Fiyatın ilk taşınma anındaki konumu farklı yolları ayırır. Kalan pencere olay başına farklı uzunluktadır; 0 bar kalanlar ayrı. İlk aşağı/yukarı dönüş, kalıcı tutunma demek değildir.

İlk güvenli kapanış eşitlik de olabilir; kesin alt/üst kapanış ve ihlal tarafından fiyat önce güvenli tarafa geçen alt dalın sonraki sonuçları [makine özetinde](fixed_line_summary.json), tüm olaylar [CSV'dedir](fixed_line_paths.csv.gz). Seçim, [ek planda](EK_YOL_PLANI.md) açıklandığı gibi önceki sonuçlar görüldükten sonra yapılmış keşifsel analizdir.
