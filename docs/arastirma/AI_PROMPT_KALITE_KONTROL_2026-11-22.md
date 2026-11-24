# AI prompt derleyicisi — veri koruma ve doğruluk kontrolü

## Amaç ve sınır

Öncelik, yapay bir karakter hedefi uğruna yorum açısından önemli bilgiyi
kaybetmemek. Araç bağımsız ve yereldir; gerçek alarm, AI model yanıtı, API
veya Telegram entegrasyonu üretmez. Test kesiti `2026-09-25 18:30` İstanbul
saatidir. Sonuçlar 2026-11-22 tarihinde kontrol edilmiştir; güncel piyasa
verisi veya bu anda gerçekten verilmiş alarm olarak sunulamaz.

## Önceki sürüme göre önemli düzeltmeler

1. Derleyici, grafiğin zaten seçip gösterdiği OB/FVG bölgelerini ayrıca üç
   bölgeyle kesmiyor. Grafik viewport'unun uzaklık, geçmiş ve kota filtreleri
   sürüyor: bu hâlâ tüm motor kayıtlarının listesi değildir.
2. FVG yaşam döngüsünde `CANDIDATE`, aktif bölge olarak sayılmaz; tanınmayan
   durum ve eksik döküm bilinmiyor olarak kalır. Adayın replay ile
   eşleşmemesi sıfır temas değildir. Epizot hesaplama hatası da sıfır olmaz.
3. Fiyat gösteriminde tek tip iki ondalık kaldırıldı: kaynak float32 ise ona
   geri dönüştürülebilen en kısa sayı; diğerlerinde 12 anlamlı basamak
   kullanılır. Türetilmiş metrikler yaklaşık gösterilir. Araştırma yükseklik
   kovası **yuvarlanmamış** doğum yüksekliği / doğum ATR ile hesaplanır.
   Metin gösterimi yine bir yuvarlamadır; paket ham sayıları korur.
4. FVG istatistiğinin birimi günlük **temas epizodu**, ölçümü epizottan
   sonraki en fazla 12 günlük mum olarak düzeltildi. Ölçüm bölgenin beklenen
   yönündeki kenardan, temas sonu ATR'siyledir; payda tüm epizotlardır ve
   eksik gelecek pencere de bulunabilir. Doğumdaki ATR yalnız yükseklik
   grubunu belirler. Bu sayılar işlem başarısı veya 4s olasılığı değildir.
5. Klasik formasyon eğilimi, mevcut kırılım yönü ve aşamasıyla karıştırılmadan
   ayrıca gösterilir. MS olaylarının seçimi, gelen listenin sırasına bağlı
   kalmadan zaman sırasına göre yapılır.
6. Stabil için günlük destek kimliği ve araştırmanın günlük temas sırasını
   temel alan bir özet eklendi: yalnız kesitte bilinen günlük gözlemler,
   0,35 günlük ATR ayrılma, son iki temas gününün kapanışı. İlk destek
   kimliğinde geçmiş ve gerçek sıra bilinmez. Kimliğin kaybolup geri dönmesi
   veya gerekli ATR eksikliği de kesin sıra çıkarılmamasını gerektirir. Destek
   ilk kez o günün kapanışında öğrenildiyse aynı günün OHLC örtüşmesi önceden
   bilinen desteğin testi sayılamaz. Bu **4s temas sayısı veya sonuç replay'i
   değildir**; ileri getiri/tepki hesabı yapılmaz.
7. `strict` kipte tarih güvenliği olmayan araştırma sayıları yine atlanır;
   ancak her domainin zamandan bağımsız temel yorumlama ilkesi korunur.
   `retrospective` örnekler, kesitten sonra oluşan veya tarihi belirsiz
   araştırmaları açıkça etiketler.
8. Seans içi süreklilik kontrolünün bütün eksik seansları doğrulamadığı,
   tek bağımsız günlük kayıtla saatlikten türetmeye geçilirse bunun kaynağı
   açıkça belirtilir.

## Uygulanan kontroller

- Yerel cache: **28 sembol, 112 TF**, 241 gösterilen bölge; derleyicinin ek
  kotası nedeniyle dışarıda kalan grafik bölgesi 0, seçili replay eşleşmesi
  241/241. 93 TF'de günlük Stabil destek kimliği vardı; 19 TF'de yoktu.
  1s FVG 28, 2s FVG 28 örnekte çalıştırılmadı; bunlar yok sayılmadı.
- Günlük arşiv: aynı 28 sembolde **13.020 günlük kesit**; sırası bilinen
  **11.543** kesit mevcut araştırma referansıyla birebir karşılaştırıldı,
  **507 temas günü** bu bilinen kesitlere dahildi. Sayısal uyuşmazlık yok.
  Pencere başı veya ATR belirsiz olanların kesin sayısı karşılaştırılmadı;
  bu kontrol araştırmanın ileri getiri hesaplarını veya 4s temaslarını
  doğruladığı anlamına gelmez.
- 28 prompt, retrospective kipinde 9.761–12.132 karakter; daha önceki üç
  örneğin v3→v5 boyutları: BIMAS 9.277→10.997, ALARK 9.898→11.539,
  PETKM 8.502→10.228. Büyüme, anlam/sınırlama ve kapsamı korumanın bilinçli
  sonucudur. 2–6 bin karakter tercihi **henüz karşılanmıyor**.
- Birim/entegrasyon testleri: 168 başarılı, 1 atlandı. Sentetik durumlar
  FVG adayı, bilinmeyen/hatalı replay, küçük fiyat, ATR eşik sınırları,
  kapanmamış mum, geleceğe sızıntı, sırasız olay, Stabil kimlik değişimi,
  eksik ATR ve arada kaybolan destek gibi riskleri de kapsar.

Tekrarlanabilir komutlar (`backfill_data/` günlük arşivi gerekli):

```bash
python scripts/diagnostics/ai_prompt_audit.py --as-of 2026-09-25T18:30:00+03:00
python scripts/diagnostics/ai_prompt_stabil_parity.py --as-of 2026-09-25T18:30:00+03:00
python -m pytest -q test_ai_prompt_builder.py test_alarm_context_packet.py test_directional_zone_replay.py test_domain_engines.py test_domain_incremental_parity.py test_stabil_support_resistance_compare.py
```

## Açık kalanlar

- Grafik viewport'u zaten bazı uzak/terminal bölgeleri elemiş olabilir.
- OHLC örtüşmesi, otomatik alıcı/satıcı niyeti veya dönüş teyidi değildir.
  OB/FVG replay geçmişi yalnız pencere ve kullanılabilirlik sonrasıdır;
  eşleşmeyen kayıt veya önceki geçmiş sıfır sayılmaz.
- Günlük veri saatlikten türediğinde pencere kısa ve ilk kova eksik olabilir;
  süreklilik kontrolü bütün eksik seansları güvenceye almaz.
- Stabil 4s seviyesinde özel dinamik temas replay'i ve model yanıtının gerçek
  içerik/hız testi yapılmamıştır. Üç yerel örnekte ana TF için gözlenen günlük
  Stabil temas günü bulunmadı; gerçek temaslı günlük arşiv ve sentetik senaryolar
  ayrı test edildi.
- Yayın/veri bitiş tarihleri eksik araştırmalar `strict` kipte nicel olarak
  eklenmez; bu durum her alarmda bütün bulguların otomatik verilmesi
  beklentisinden ayrı bir tarih güvenliği kısıtıdır.
