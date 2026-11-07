# Stabil desteğinin karşıtı direnç olur mu? — tarihsel replay

**Kısa cevap:** Destek hesabının matematiksel karşıtı olan teyitli tepe çizgisi
oluşturulup test edildi; aşağıdaki sayılar direnç etrafındaki **gözlenen davranışı**
gösterir. Tek başına çizginin düşüşe neden olduğunu, işlem avantajı veya canlı
alarm başarısı sağladığını kanıtlamaz. 20 aday ve referansın tamamı
[plana](PLAN.md) göre aynı arşivde çalıştırıldı; en iyi sonuca bakıp yeni canlı
kural seçilmedi. İlk tam koşu denetiminde gap ile temas ayrımı ve şüpheli gün
sansürü düzeltildi, ardından tüm arşiv yeniden çalıştırıldı.

## En önemli sonuçlar — 2026, testten sonraki 8 adet 4s bar

- **Birebir terslenmiş çizgi:** 1409 TEST olayının 1241'i geçerli (161 hisse); olay kapanışından sonraki ±1 ATR yarışında **aşağı önce %42.1**, **yukarı önce %51.6**, aynı-bar belirsiz %3.1, hiçbiri %3.2. Medyan son kapanış **+0.05 4s ATR**; 8 barda medyan aşağı/yukarı uç hareket 1.22/1.53 ATR. Bunlar işlem getirisi değil.
- Bu geçerli TEST'lerin 324'i yalnız yaklaşma bandına girdi; 28 tanesinde gap sonrası mumun tamamı çizgi üzerinde kaldı. **Tepe seviyesi mumun yüksek–düşük aralığında olan 889 olayın 500'i (%56.2) aynı mumda çizgide/altında kapandı**. Mum içi önce-sonra bilinmiyor.
- **Basit 20 günlük tepe referansı:** 2015 geçerli TEST'te aşağı/yukarı önce %41.1/%52.4. Olay kümesi ve seviye mesafesi farklı olduğu için bu ham tablo doğrudan üstünlük veya nedensel etki göstermez.
- **Eşleştirilmiş yakın sahte çizgiler:** SHIFT_UP eşleşmesinde fark -3.1 puan (n=129; hisse-kümeli %95 -16.2…+10.0); SHIFT_DOWN eşleşmesinde fark +10.3 puan (n=194; hisse-kümeli %95 +0.0…+19.3). Bu aralıklar ortak piyasa günlerini, kalıntı kovaiçi farkları, çoklu hipotezleri ve önceden incelenmiş arşivi düzeltmez.
- **Dönem karşılaştırması:** 2025 kesitindeki 1093 geçerli TEST'te aşağı/yukarı önce %42.4/%50.9; bu da bağımsız yeni veri değil.
- **Ufuk duyarlılığı:** 4 bar: n=1257, −1 önce %36.5, +1 önce %46.1; 8 bar: n=1241, −1 önce %42.1, +1 önce %51.6; 16 bar: n=1207, −1 önce %43.9, +1 önce %52.9. Geçerli n ve dört sonuç sınıfı [toplu tabloda](toplu_bulgular.md).
- **Native günlük gerçek TESTED olayı:** 1140 geçerli olayda sonraki 8 **günlük** barda aşağı/yukarı önce %45.7/%50.5. Bu grup 4s yaklaşma bandından ayrı tanımlanır.

## Kullanıcının fiyat/çizgi yolu ve native karşılık

[Kullanıcı davranış dosyası](../STABIL_DAVRANIS_MODELI.md) eski özgün belge
bulunamadığı için konuşmadan yeniden kaydedilmiştir. Onun `uzaklaşma → çizgi
takibi → yataylaşma → test/kırılma → dönüş` sırası, ters yönde TEST, üstte
kapanış, retest ve aşağı dönüş olarak ölçüldü. Görsel “dikey/yatay” ile bu
kodun rejim etiketleri henüz birebir eşlenmedi; tablolar **proxy**, onaylı görsel
tanım değil. Native teyide keyfî 2/3/5 mum bekleme eklenmedi.

Tersleme değiştirilmemiş native günlük destek çekirdeğine `O'=-O, H'=-L,
L'=-H, C'=-C` girdisi verip sonucu tekrar tersleyerek yapılır: son teyitli günlük
tepe, iki tepe + iki dip yapısı ve `tavan=tepe+0,35 × köken günlük ATR`.
Ayrıca günlük native TESTED/HELD/BREACHED/tavan kırımı/geri dönüş olayları
ters anlamla ve **günlük** ufukla hesaplanmıştır. 4s TEST tanımı ve diğer 19
aday araştırma ölçümüdür; canlı 4s ok/alarm kurallarının birebir ters çevrilip
uygulandığı iddia edilmez.

**Kırılma ve dönüş:** 1340 geçerli yukarı kapanış
kırılmasının 781 tanesinde (%58.3) sonraki 8 barda
çizgiye/altına kapanış görüldü. İlk retestlerin gap/açılış ile temiz üstten
temas ayrımı ve önceden bilinen taşma derinliği grupları
[toplu tablodadır](toplu_bulgular.md). Fiyatın çizgiye göre taraf değiştirmesi
fiyatın hareketinden, çizginin güncellenmesinden veya ikisinden kaynaklanabilir;
bu katkılar da ayrı sayıldı. İlk gözlenen çizginin eski temas sayısı ve kırılma
süresi bilinmiyorsa UNKNOWN bırakıldı. 1,5 ATR uzaklaşma sonrası eski çizgiye
fiyat dönüşü / çizginin fiyatı takip yarışı da ölçüldü; kısa ufukta 4 günlük
pivot teyidinin doğal gecikmesi özellikle dikkate alınmalı.

## Veri, sansür ve dürüst sınırlar

- 174/174 uygun hisse; hata **0**. 86771 kapalı native günlük, 186625 kapalı 4s bar; 4s kapsamı 2025-05-07 13:30:00+03:00 → 2026-10-19 13:30:00+03:00 (İstanbul).
- İndirme anında henüz kapanmamış 174 günlük ve 174 adet 4s bar çıkarıldı. 2249 eksik saatlik bileşenli 4s kova, günlük oturumlarla karşılaştırmada 1523 beklenen ama görünmeyen 4s kova; 13 hissede 15 şüpheli günlük bar (> %30 sıçrama dahil) saptandı. Şüpheli günlük bar sonrasındaki tüm ufuklar da ATR/pivot geçmişi korunamadığı için ihtiyatla dışlandı. Geçersiz geçmiş/gelecek ve tamamlanmamış ufuk dışlandı; ana 8-bar durumları: VALID: 1241, BAD_HISTORY_OR_MISSING: 75, BAD_DAILY_SOURCE_HISTORY: 60, BAD_FUTURE_OR_MISSING: 32, RIGHT_CENSORED: 1. Bu durum önceliklerinden bağımsız olarak sağdan sansürlü olay: 1.
- Daily seviye, 4s mumun yalnız kapanışında değil **başında** biliniyorsa o mumun OHLC testi yapılır. Pivot kökeni teyit zamanı değildir. Veri eksikliği, ücretsiz arşiv fiyat düzeltmeleri, aynı anda çift eşik, kısa seans-sonu hacmi ve gün/hisse korelasyonu sonuçları etkiler. 4s ATR'nin Wilder yumuşatmasında 20 bar öncesindeki bir şokun etkisi tamamen sıfırlanmaz. Günlük ve saatlik kaynakta birlikte eksik bir seans ve bütün kurumsal işlemler bağımsız doğrulanmış değildir.
- `PRE_2026` ve `Y2026` takvim karşılaştırmasıdır; arşiv daha önce araştırıldığından gerçek bağımsız/kör örnek değildir. Çok sayıda varyant karşılaştırıldı; yüksek yüzdeli adayı seçip doğrulanmış ilan etmeyin. İleri tarihte, aynı tanımlarla, görsel etiket ve gerçek işlem maliyetiyle yeni test gerekir.

## Dosyalar ve yeniden üretim

[Ön kayıt ve 20 adayın tanımı](PLAN.md) · [Tüm paydalı tablolar](toplu_bulgular.md) · [somut grafik örnekleri](ornekler.md) · [doğrulama](DOGRULAMA.md) · [makine özeti](summary.json) · [4s olaylar](events_4h.csv.gz) · [native günlük olaylar](native_daily_events.csv.gz) · [eşleştirilmiş kontroller](matched_controls.csv.gz) · [veri/kod hash ve kalite manifesti](manifest.json).

```bash
python -m research.stabil_resistance_replay --workers 4
python -m research.stabil_resistance_report
python -m research.stabil_resistance_examples
python -m research.stabil_resistance_verify
pytest -q test_stabil_resistance_replay.py
```

Çalışma yalnız yerel arşiv ve araştırma dosyalarını kullanır; canlı bot, Telegram,
üretim filtresi ve grafik kodu değiştirilmemiştir.
