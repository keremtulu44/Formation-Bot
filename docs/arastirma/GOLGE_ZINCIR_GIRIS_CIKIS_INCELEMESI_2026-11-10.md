# Gölge Zincir — Giriş/Çıkış İncelemesi (704 seri, 2.771 plan)

**Tarih:** 2026-11-10 · **Veri:** tam koşu defteri + `research/golge_inceleme.py`
**Çıktı:** `docs/arastirma/sonuclar/golge_zincir/inceleme_ozet.json`
**Bağlantı:** [Ana rapor (Faz 0–5)](GOLGE_ZINCIR_REPLAY_2026-11-09.md)

> Amaç: al/sat nerede verildi — giriş dibe erken mi geç mi, çıkış tepede mi
> ortada mı, nerede kaybedildi, **hangi kapı izni kapattı**. Close tabanlı,
> ATR normalize; zamanlama penceresi ±10 bar; yarış H=10 (koşucuyla aynı).

---

## 1. Girişte nerede yakalandı? (n = 2.765 sonuçlu plan)

Giriş kvadrantı = (önceki10 bardaki dipten kaçış) × (girişten sonraki10 bardaki düşüş).

| Giriş yeri | n | % | hedef | zaman | stop | **stop oranı** |
|---|---:|---:|---:|---:|---:|---:|
| **İyi zamanlama** (dibe yakın, hemen döndü) |1.384|%50,1|663|643|78|**%5,6**|
| **Erken girdi, düştü** (dibe doğru geriledi, ≥1 ATR) |843|%30,5|56|90|697|**%82,7**|
| **Geç girdi, dibi kaçırdı** (dip olmuş, yukarıdan aldı) |338|%12,2|144|176|18|%5,3|
| **Yüksekten girdi, düştü** (kovalayıp düştü, her ikisi ≥1 ATR) |200|%7,2|9|33|158|**%79,0**|

**Ana bulgu:** **951 stopun 855'i (%90) "erken girdi" ve "yüksekten girdi"
kesiminden geliyor.** İyi zamanlama + geç girişte toplam 1.722 işlemde yalnız
96 stop (%5,6) var. Yani sistem ne rastgele ne de geç giriyor — **sorun
dibe erken girmek / düşüş bıçağına girmek**: tetik (bant ∩ tepki onayı) geliyor
ama fiyat henüz dönmemiş. Metrikler: girişten önceki dipten kaçış ort
**0,56 ATR** (p90 1,49); girişten sonraki10 barda düşüş ort **1,08 ATR**
(medyan 0,61, p90 2,75) — bu, MAE p50 −0,54 ile tutarlı.

Erken giriş kesiminin %82'sinin stop yemesi, **stop'un değil giriş yerinin**
sorunlu olduğunu kanıtlıyor (bkz. §3).

## 2. Satış nerede verildi? (çıkış kalitesi)

| Çıkış yeri (işlem+sonrası bandın %'si) | n | % | dağılım |
|---|---:|---:|---|
| **Tepede sattı** (≥%80) |510|%18,5|hedef341 · zaman146 · stop23|
| **Ortada sattı** |1.731|%62,6|zaman622 · stop594 · hedef515|
| **Dibe sattı** (≤%20) |524|%19,0|**stop334** · zaman174 · hedef16|

- **Hedef çıkışları (n=872) erken:** satıştan sonraki10 barda fiyat **medyan
  1,05 ATR (ort 1,63) daha koşmuş** — toplam **1.419,9 ATR masada bırakıldı.**
  Sebep yapısal: hedef = *en yakın* karşıt yapı (kural gereği muhafazakâr;
  hedef mesafesi medyanı 1,76 ATR).
- **Geri verilen** (tepeden çıkışa kadar, hedef+zaman, n=1.814): medyan **0,0**
  — çıkışlar büyük ölçüde tepesiz/yanında; p90 1,26 ATR.
- **Zaman çıkışları (n=942):** hedefe kalan **medyan 2,24 ATR** (ortalama 11,9 —
  uç değerler şişiriyor: 113 planda hedef >10 ATR, maks **610 ATR** →
  karşıt yapı listesi bazı serilerde çok uzak; §5 patoloji).

## 3. Stoplar doğru muydu? — %93 evet

| Stop sonrası (10 bar) | n | % |
|---|---:|---:|
| **Doğrulandı** — fiyat stopun altına devam etti |884|**%93**|
| **Toparlandı** — geri geldi (potansiyel çırpınma) |67|%7|

Toparlananların ort koşusu 1,24 ATR (medyan 0,82). **Stop mekaniği sağlıklı;
kayıp nedeni kötü giriş yeri** (§1) — "erken gir, stopa düş, doğru dur" döngüsü.

## 4. Hangi kapı izni kapattı? (geometri geçerli ama plan açılmayan 6.932 tetik)

| Kapı (TYR gerekçesi / kural) | n | % | Karşıt-olgu beklenti* |
|---|---:|---:|---:|
| **BEKLE · olgunluk yok (desteğe mesafe > 1 ATR)** |**4.899**|**%70,7**|+0,2989 ATR|
| 20-bar boşluk (üst üste tetik) |914|%13,2|+0,2370|
| BEKLE · taze karşıt MS uyarısı sürüyor |868|%12,5|+0,2705|
| RET · G1 kapandı (tez öldü) |207|%3,0|+0,3296|
| BEKLE · G1 kapısı kapalı (motor susar) |37|%0,5|+0,1632|
| RET · planda ters yapı geldi |4|%0,1|+0,3810|

\* Her tetik **bağımsız** aynı yarışla koşuldu (örtüşmezlik yok — kaba üstel;
kabul edilen planların bekleneni +0,3091'dir).

**Yorum:**
1. **İzin vermeyen birincil kapı: "olgunluk" (desteğe ≤1 ATR olgunluk) —
   engellemenin %71'i.** Ve bu engellenen kitle, karşıt-olguda **kabul
   edilenlerle aynı kalitede** (+0,30 ≈ +0,31). Kapı işlem *kötülüğünü*
   elemiyor; **izin vermiyor / geciktiriyor** — "daha güçlü işlemler açılmış
   ama şu sebepten beklemiş" hipotezini destekleyen bulgu bu.
2. Taze karşıt MS (868) ve RET-G1 (207) de benzer/iyi kalitede karşıt-olgu
   gösteriyor — ancak bunlar *bilinçli risk kapıları* (tez iptali); K2'nin
   "hüküm katmanı ek değer katmıyor" sonucuyla aynı resmin parçası.
3. Bu sonuçlar **kabul edilen planlarla aynı filtrelerden geçmedi** (örtüşmezlik
   yok); kesin hüküm kapıdadır: **K2 = −0,67 < +5 → GEÇMEDİ.**

**Geometri kapıları (281.341 band∩onay tetikte kart üretilemedi):**

| Red nedeni | n | % |
|---|---:|---:|
| Hedef adayı yok veya R < 1,2 (yakın karşıt yapı) |135.866|%48,3|
| Stop çok uzak (> 2,5 ATR) |82.076|%29,2|
| Stop çok yakın (< 0,5 ATR) |63.083|%22,4|
| Destek veya bant yok (G1/G5 yapısal) |316|%0,1|

Geçerli geometri: 9.700 / 291.041 tetik = **%3,3** — asıl eleme burada:
**yakın karşıt yapı yokluğu (hedef/R) ve stop bandı.**

## 5. Patolojiler ve küçük bulgular

- **Uzak hedefler:** 113 plan >10 ATR hedef (maks 610 ATR) — MS karşıt yapı
  listesi seyrek/uzak; zaman çıkışlarında hedefe kalır ortalamasını şişiriyor.
  Aday düzeltme: hedef üst sınırı (ör. ≤ 6 ATR) — **yeni belgeyle**.
- **Hüküm gücü zayıf:** girişteki `lehte` 4 → hedef %31,3; lehte 5 → %34,0 —
  K2 ile tutarlı, TYR sayacı ayırıcı değil.
- **RET · G1 kapandı** karşıt-olgusu +0,33 (n=207): destek kırıldıktan sonraki
 10 barda fiyat toparlanıyor olabilir (bull-trap riski de var — kaba ölçüm).

## 6. Genel sonuç (tek paragraf)

Sistem **yarı yarıya doğru yerden** giriyor (iyi zamanlama %50 → stop %5,6);
**kaybın %90'ını erken/yüksek giriş üretiyor** (dibe erken girmek, düşüş
bıçağına girmek); **stoplar doğru** (%93 doğrulandı) — yani arıza giriş
zamanlamasında, durdurucuda değil; **hedefler yapısal olarak erken** (medyan
1 ATR daha koşu, 1.420 ATR bırakıldı); **izin kapılarının %71'ini "desteğe
uzak" olgunluk kuralı kapıyor ve bu engellenen kitle aynı kalitede** — kapılar
seçici değil, geciktirici. Özet: **"daha güçlü işlemler açıldı ama olgunluk
kapısı bekletti; açılanlarda erken giriş kaybı yarattı; durdurucular doğru
çalıştı."** Sıradaki iş (Faz 6 adayı): giriş onayını *dibe yerleşmek* ölçütüne
bağlamak (erken-girdi kvadrantını küçültmek) ve olgunluk kapısını K2 ile
birlikte yeniden değerlendirmek — hepsi **yeni önceden-kayıtlı eşiklerle**.

## 7. Erken ve yüksekten girişlerin profili (tam veri +30 sembol doğrulama)

**"Erken girdi, düştü" (n=843) ile "iyi zamanlama" (n=1.384) giriş ÖNCESİ
neredeyse aynı:** ikisi de kırmızı giriş barında (erken %76 / iyi %77),
zirveden ≥1 ATR uzakta (erken %94 / iyi %95; ort. −2,8 ATR), giriş öncesi3
bar momentumu benzer (erken −0,62 / iyi −0,65 ATR), desteye mesafe benzer
(erken p50 1,51 / iyi 1,76 ATR). **Yani "erken" ayrı bir tür değil — aynı
kurulum ama tepki onayı düşüş bitmeden geldi:** ilk sıçrama dönüş sanıldı,
dip biraz daha derine girdi (sonrası düşüş p50 0,61 → p90 2,75 ATR) ve %83'ü
stop yedi. **Ortak eksik: dip teyidi yok (dönüşün teyitlenmemesi).**

**"Yüksekten girdi, düştü" (n=200) net ayrışıyor — kovalama profili:**
- giriş öncesi3 barın **%52'si yükselişte** (mom3 p50 +0,09 ATR; iyi/erken'de
  −0,65) — güç kovalanarak giriliyor;
- giriş **20-bar zirvesine yakın** (yalnız %61'i zirveden ≥1 ATR uzak; iyi/erken
  %94-95; ort. −1,48 ATR);
- giriş **bandın tepesinin üstünde** (band_pos p50 **1,63**; iyi 1,13, erken 1,25);
- desteye mesafe zaten kapanmış (**p50 0,78 ATR**; %34'ü ≤0,5) — tepki
  gerçekleşmiş, sekme kovalanıyor;
- giriş barı yeşil payı %47 (iyi'de %23), stop daha geniş (p50 1,14 vs 0,90).
**Kapıyı açan:** olgunluk (desteğe yakınlık) + tepki onayı — ama giriş,
olgunluğun gerçekleştiği hareketin **sonunda** yapılıyor; geri çekilince %79 stop.

**"Geç girdi" (n=338) zararsız** (stop %5,3) — dibi kaçırmak kaybettirmiyor.

Profil kesiti: tam veri CSV+frame (kvadrant × momentum/zirve/bar rengi) +
30 sembol alt koşusu (mesafe/bant/gerekçe;527 plan, kvadrant payları tam
koşuyla aynı: %50/%32/%8/%10).

## 8. Tekrar

```bash
python3 research/golge_inceleme.py   # ~10 sn → inceleme_ozet.json
```
Sınırlamalar: tetik öncesi kapılar (bant/onay yoksa tetik yazılmaz) defterde
yok; karşıt-olguları bağımsız (örtüşmesiz) — kaba.
