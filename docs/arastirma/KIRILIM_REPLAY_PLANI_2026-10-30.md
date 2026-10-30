# Kırılım adayı ve teyit Replay araştırması — uygulama planı

Amaç alarmı erkene taşımak değil; mevcut motorun hesaplarını ve aday→teyit
geçişlerini ölçmek, onaylanmamış ve başarısız adayları da dahil ederek zamanlama
ve veri kalitesi sınırlamalarını ortaya koymaktır. Canlı kod/ayar/alarm,
Telegram, Supabase ve ham veri değiştirilmez. Bir bulgu otomatik kural önerisi
veya Pine/TradingView eşdeğerliğinin kanıtı değildir.

## 1. Evren ve veri kapısı

- Ham arşivde hisse olarak sınıflanan tüm semboller; 1h, seans hizalı 1h'den
  türetilen 2h/4h ve native 1d ayrı. Her kaynak hash'i, kapsamı ve başarısız
  seri kaydedilir. Endeks ve Brent havuzda hisse değildir.
- OHLC doğrulaması ve %30 üstü kapanış sıçraması **kalite bayrağıdır**; şirket
  işlemini tespit etmez. Kusurlu girdi temizlenip yok edilmez: o nokta ve
  sonrasındaki ısınma karantinaya alınır; sağ sansür ve keşif/ileri dönem sınırı
  ayrı sayılır. Eksik seans/tatil/etiket ve türetilen kısmi kovalar bağımsız
  doğrulanmadı; sonuçlar gözlemsel kalır.

## 2. As-of yaşam döngüsü ve hesap denetimi

- Yalnızca artan bar öneklerinde izole `ArgentEngine`, Dengeli profil ve kayıtlı
  mevcut kurallar; aday/deneme geçişleri, yön, kalıp, başlangıç, formasyon yaşı,
  aday mumu ve takip eden teyit kontrollerinin sınır, tolerans, gövde/kapanış/
  delinim/genişleme/hacim bileşenleri, eşik ve gerçek state sonucu kaydedilir.
- Adayların tamamı sayılır; teyit, teyitsiz zaman aşımı, geri dönüş, farklı
  yapıya geçiş, sonu gelmeyen takip ve veri kirlenmesi ayrı sınıflanır. Aynı
  state'in tekrar eden her mumu ayrı yeni aday değildir. UUID rastgeleliği ve
  motorun yeniden taramada kaydırılan pencere davranışı nedeniyle bu bir
  araştırma replay'idir, birebir canlı olay/teslim kanıtı değildir.
- Bağımsız referansla çizgi interpolasyonu, smoothstep ve kırılım puanının beş
  bileşenini ve 0–100 aralığını olay anında karşılaştır. Sınır eşitliği ve
  sıfır hacim/ATR koşulları test edilir. Mantığın iç tutarlılığı, Pine kaynağına
  ve canlı/veri eşdeğerliğine bağımsız doğrulama demek değildir.
- Küçük sabit örneklerde prefix/future-değiştirme ve sıfırdan replay karşılaştır;
  uyuşmazlıkları ölç, tüm geçmişin tam yeniden taramasını yaptığını iddia etme.

## 3. Zamanlama ve sonuçlar

- Her aday için aday son kapanışı ve o anda bilinen ATR ile, önceden sabit
  10 mumda ±2 ATR kapanış eşiğinin yönlü 10. kapanışı ve yol içi kapanışları
  ayrı; yetersiz gelecek ve kötü veri UNKNOWN. İlk 2/10 mumda lehte/aleyhte
  gelişim, aday→teyit kapanış bar farkı ve teyit öncesi hareket raporlanır.
  OHLC içi olay sırası, takip emirleri ve gerçekleşen kâr iddia edilmez.
- Teyit alan / alamayan ve yukarı / aşağı sonuçları ayrı; olaya koşullu
  doğrulama, temel oran, eşleşmeyen kontroller, küçük örneklem ve örtüşen
  aday pencereleri açıklanır. Keşif–ileri dönem için adayın 10 mum sonu ileri
  döneme taşıyorsa purged; tarihe göre hisse/TF bazlı split ve verim yazılır.
  Formasyon kümeleri, piyasa ortaklığı ve birden fazla testin belirsizliği
  düzeltilmediyse güçlü/doğrulanmış sonuç etiketi kullanılmaz.

## 4. Yürütme ve teslim

- Önce THYAO vakası ve sentetik sınırlar dahil testler; ardından 174 hissenin
  tüm mevcut serileri. Hata sayıları gizlenmez; uzun iş yeniden başlatılabilir.
- Tarihli özet, günlük/TF/yön/karar grubu sayıları ve okuyabileceği olay/
  kontrol verileri, veri/parametre/versiyon manifesti; README araştırma
  dizinine bağlanır. Önceden kirli dosyalara dokunulmaz. Son turda hedefli
  test/Ruff/diff ve çıktı kontrolü yapılır.
