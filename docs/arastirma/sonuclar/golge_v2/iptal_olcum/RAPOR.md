# D7 işlem-içi iptal ölçümü

## Kapsam ve yöntem

Mevcut `mod0_baz.csv.gz` dosyasındaki 4s/günlük A_ARTI, sansürsüz 648 işlemin tamamı, aynı giriş, aynı stop ve **2,0 ATR hedef** ile tekrar oynatıldı. Bazın işlem başına getirisi önceki rapora en fazla 0,000068 R farkla uydu. Girişler aynı, barlar arşivden domain adaptörüyle yeniden kuruldu; tüm serilerde domain hatası sıfır. Mevcut senaryodaki ilk üç bar tez iptali korunur (bu örneklemde tetiklenmedi). İşlem maliyeti toplam %0,30, giriş ve çıkışta 15 baz puan. R, işlem başındaki stop mesafesi cinsinden getiridir.

* **Duvar:** önceki kapanışta bilinen, yüksekliği en az 0,5 ATR karşı OB/FVG bandına iki ardışık barda temas ve her iki kapanışta aşılamama; ikinci kapanışta çıkış. İki bar aynı bandı izlemelidir; ilk temasta terminal olan bandın ikinci teması takip edilir. Bu tanım replay bulgularından türetilmiş deneysel bir hipotezdir; replay bu kesin kuralı veya eşiği doğrulamamıştır.
* **Baskı:** hacim kullanılabilir iki ardışık barda yönün tersine 0,13 üzeri `pressure_5`; ikinci kapanışta çıkış. Eksik/kullanılamayan veri sayacı sıfırlar. Eşik deneysel olup kaynak VP eşiğinden alınmıştır.
* **Birleşik:** ikisi birlikte, aynı barda duvar öncelikli.
* Stop/hedef kontrolleri kapanış iptalinden öncedir; aynı mumda stop ve hedef görülürse stop önce sayılır. Kapanış sinyali aynı kapanış fiyatıyla uygulanır: gerçek emir gecikmesi/kayması eklenmediği için iyimserdir. İşlem dışı sermaye tahsisi, short erişimi, portföy getirisi ve faiz farkı burada yeniden simüle edilmedi.

## Mevcut 10 bar ufku — 648 eşleşmiş işlem

| Varyant | Net ortalama R | Toplam R | Net kazanç oranı | İptal sayısı | Bazda kârlı / zararlı iptaller |
|---|---:|---:|---:|---:|---:|
| Baz | +0,1234 | +79,97 | %50,9 | — | — |
| Duvar | +0,1133 | +73,41 | %50,2 | 122 | 76 / 46 |
| Ters baskı | +0,1126 | +72,96 | %49,7 | 58 | 22 / 36 |
| Birleşik | +0,1016 | +65,84 | %49,4 | 159 | 91 / 68 |

Bazda kârlı/zararlı sütunu, iptal edilen aynı işlemin **baz strateji sonucudur**, iptal anındaki kâr/zarar değil. Duvar kolunda hedefe ulaşan işlem 269'dan 224'e, birleşikte 218'e düştü. Duvar değişimi keşifte +0,0066 R, doğrulamada −0,0413 R; baskı keşifte −0,0161 R, doğrulamada −0,0009 R. Bunlar dönemsel betimlemelerdir, bağımsız yeni test değildir.

Farkların hisse-bloklu bootstrap (3.000 çekiliş, seed 42; %95 yüzdelik aralıkları): duvar −0,0101 R [−0,0445; +0,0242], baskı −0,0108 R [−0,0269; +0,0038], birleşik −0,0218 R [−0,0583; +0,0147]. Sembolle gruplayan bu aralıklar ortak tarih/piyasa şoklarını bütünüyle kontrol etmez; kesin bir üstünlük veya zararlılık kanıtı değildir.

## Zaman ufku düzeltmesi — ortak 645 işlem

D7'nin mevcut ufku **zaten 10 bar**; önceki yanıtta `net15_20_r` içindeki 20 yanlışlıkla 20 bar diye okunmuştu. 20, 2,0 ATR hedefi ifade eder. Aynı 645 işlemde (20 barı eksiksiz gözlenemeyen 3 işlem iki koldan da çıkarıldı), baz 10 bar **+0,1187 R**, baz 20 bar **+0,1076 R**; fark +0,0112 R. Bu, mevcut örneklemde 10 barın daha yüksek ortalaması demektir; “risksiz” olduğu veya başka dönemde üstün olacağı anlamına gelmez.

## Sonuç ve sınırlar

Bu tanımlarla duvar ve baskı iptali tek başına da birlikte de gözlenen net beklentiyi artırmadı; birleşim en düşük sonuç. Canlı sisteme uygulama önerilmez. Bir kuralın ölçülmüş sonuçları, bütün duvar/baskı tanımlarının veya bütün işlem-içi izlemenin işe yaramadığını kanıtlamaz. Özellikle replay tabloları farklı örneklem ve hedefler üzerindedir; bu eşikler ve iki bar şartı orada doğrulanmış çıkış kuralları değildir. Önceki “sorun kesin olarak işlem-içi kontrol eksikliği” ve “replay ters MS'yi/trailing'i reddetti” ifadeleri fazla kesindi: bunlar neden-sonuç kanıtı değildir; trailing için yalnız test edilen varyantlar başarısız oldu.

Tekrar: `python -m research.golge_v2_iptal_olcum --workers 2`. Olay bazlı sonuçlar `olaylar.csv.gz`, özetler `ozet.json`.
