# Son 10 seans: bildirim ister miydim?

Önce [kör PDF](KOR_INCELEME.pdf); tercihler kilitlenmeden `OYDAN_SONRA.csv` açılmaz. Her grafikte son tamamlanan mum dahil 40 mum ve o mumlara ait hacim var. İleri fiyat, algoritmanın seçimi ve sonucu yok. Bu inceleme bir başarı oranı üretmek için değil, hangi kartın insan açısından faydalı olduğunu tarif etmek için.

Bu checkout’ta üretim `notification_delivery.json` dosyası veya aynı dönemi kapsayan Telegram mesaj dışa aktarımı bulunmadı. Gerçek gönderim, mükerrerlik, teslim gecikmesi ve bütün botun sessiz kaldığı iddiası doğrulanamaz. Sonraki eşleme için ilgili kanalın eksiksiz dönem dökümü (zaman, sembol, TF, kart türü; kimlikler gerekmez), varsa mum kapanış zamanı ve saat dilimi gerekir. Tekil ekran görüntüleri bir teslimatı gösterebilir, sessizliği kanıtlamaz.

Örneklem: önceki karar tablosundaki 24 hisse × 1s/4s/günlük; hepsinde veri bulunan son 10 tam arşiv seansı (5–18 Kasım 2026). 3.120 karar kapanışı, bunların 64’ünde yönlü formasyon teyidi. Her gün bir teyit ve aynı zaman/periyotta başka hissede bir teyitsiz kapanış seçildi. Öncelik aynı mum rengi ve aynı fiyat yapısı, sonra aynı renk; kalan eşitlik sabit hash ile çözülür. Periyot tercihi sırayla 1s/4s/günlük; uygun aday yoksa diğerlerine izin verilir. Gelecek sonuçları örnek veya sıralama seçmek için kullanılmaz. Grafikte formasyon çizgileri yok: ilk turda yalnız o anki fiyat/hacim hareketini puanlıyoruz. On dengeli çift doğal kart sıklığı değildir.

Oy sonrası: kullanıcı “açardım” dediyse replay teyidiyle aynı yön ve zamanda mı? “Açmazdım” dediği bir teyit neden gereksiz? Açmak istediği ama bu kanalın teyit vermediği örnek başka kanaldan zaten gelmiş mi? Yönsüz izlemeyi zorla doğru/yanlış yön etiketleme. Kalan 12 bar tam değilse teknik sonuç `eksik`, başarısızlık değil. Ancak aynı sorun farklı seanslarda tekrarlanır ve gerçek teslimlerle doğrulanırsa bir değişiklik öner. Tekrar eden sorun yoksa eşiklerle oynama.

Üretim: `python -m research.on_seans_kor` (PDF için ReportLab, DejaVu Sans gerekir).
